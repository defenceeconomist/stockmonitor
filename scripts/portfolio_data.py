"""Download dated benchmark proxies and GBP-per-unit FX for the supplier basket."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path

BENCHMARKS = {
    'global': {'ticker': 'VWRP.L', 'label': 'Global equities', 'index': 'FTSE All-World',
               'fund': 'Vanguard FTSE All-World UCITS ETF (Acc)',
               'source_url': 'https://www.vanguard.co.uk/professional/product/etf/equity/9679/ftse-all-world-ucits-etf-accumulating-Vanguard'},
    'uk': {'ticker': 'FTAL.L', 'label': 'UK equities', 'index': 'FTSE All-Share',
           'fund': 'State Street SPDR FTSE UK All Share UCITS ETF (Acc)',
           'source_url': 'https://www.ssga.com/uk/en_gb/institutional/etfs/state-street-spdr-ftse-uk-all-share-ucits-etf-acc-spyf-gy'},
}


def refresh(snapshot, previous, fetch_series):
    """Retain failed series explicitly as stale; never invent a rate or omit a currency."""
    top = sorted(snapshot['companies'], key=lambda c: (-c['spend_m'], c['name']))[:50]
    currencies = sorted({c['market'].get('currency') for c in top if c.get('ticker')
                         and c['market'].get('currency') not in (None, 'GBP', 'GBp')})
    old = previous.get('portfolio_market', {})
    result = {'fetched_at': datetime.now(timezone.utc).isoformat(), 'benchmarks': {}, 'fx': {}, 'warnings': []}
    jobs = [('benchmarks', key, info['ticker'], 'ETF') for key, info in BENCHMARKS.items()]
    jobs += [('fx', currency, currency + 'GBP=X', 'CURRENCY') for currency in currencies]

    def download(job):
        group, key, ticker, instrument = job
        try:
            series = fetch_series(ticker, instrument)
            expected_currency = {'GBP', 'GBp'} if instrument == 'ETF' else {'GBP'}
            if series.get('currency') not in expected_currency:
                raise ValueError(f'Expected a GBP-denominated {instrument} series')
        except Exception as exc:
            series = dict(old.get(group, {}).get(key, {}).get('market', {'bars': []}))
            series['status'] = 'stale' if series.get('bars') else 'unavailable'
            return group, key, ticker, series, f'{ticker}: {str(exc)[:180]}'
        return group, key, ticker, series, None

    with ThreadPoolExecutor(max_workers=4) as pool:
        for group, key, ticker, series, warning in pool.map(download, jobs):
            metadata = BENCHMARKS[key] if group == 'benchmarks' else {
                'ticker': ticker, 'label': f'GBP per {key}', 'direction': 'GBP per unit of foreign currency'}
            result[group][key] = dict(metadata, market=series)
            if warning:
                result['warnings'].append(warning)
    snapshot['portfolio_market'] = result
    return snapshot


def main():
    from update_data import ROOT, fetch_market
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/snapshot.json')
    args = parser.parse_args()
    saved = json.loads((ROOT / 'data/snapshot.json').read_text())
    result = refresh(saved, saved, fetch_market)
    # Supplier/news evidence is unchanged, so its snapshot timestamp stays intact.
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
    temporary.replace(args.output)
    print('Portfolio market data saved:', len(result['portfolio_market']['benchmarks']), 'benchmarks,',
          len(result['portfolio_market']['fx']), 'FX series; warnings:', result['portfolio_market']['warnings'])


if __name__ == '__main__':
    main()
