"""Fetch auditable MOD, Yahoo daily bars, and headline metadata. Never fabricate data."""
import argparse
import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from io import BytesIO
import json
from pathlib import Path
import time
from urllib.parse import quote
import xml.etree.ElementTree as ET
import zipfile
from zoneinfo import ZoneInfo
import requests
from weekly_summary import add_weekly_summaries

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = 'https://assets.publishing.service.gov.uk/media/69aff1f1d620c14fa183ef3e/Data_tables_relating_to_MOD_trade__industry_and_contracts_2025.ods'
PUBLICATION_URL = 'https://www.gov.uk/government/statistics/mod-trade-industry-and-contracts-2025'
NS = {'t': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0'}
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; MODSupplierMonitor/1.0)'}


def get(url):
    for attempt in range(3):
        try:
            response = requests.get(url, headers=HEADERS, timeout=35)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def parse_table(blob):
    root = ET.fromstring(zipfile.ZipFile(BytesIO(blob)).read('content.xml'))
    result, notes = [], []
    for table in root.findall('.//t:table', NS):
        name = table.get('{'+NS['t']+'}name')
        if name not in ('Table_4a', 'Symbols_and_Notes'):
            continue
        for row in table.findall('t:table-row', NS):
            cells = [' '.join(c.itertext()).strip() for c in row if c.tag.endswith('table-cell')]
            if name == 'Symbols_and_Notes':
                if len(cells) > 1 and cells[0] in ('note 4', 'note 11', 'note 12', 'note 16', 'note 20', 'note 21', 'note 22'):
                    notes.append({'id': cells[0], 'text': cells[1]})
                continue
            if len(cells) < 5:
                continue
            try:
                spend = float(cells[1].replace(',', ''))
            except ValueError:
                continue
            # Strictly greater than £50m, using published rounded values.
            if spend > 50:
                result.append({'name': cells[0], 'spend_m': spend,
                               'competitive_pct': float(cells[2]),
                               'noncompetitive_pct': float(cells[3]),
                               'other_pct': float(cells[4])})
    if len(result) < 50 or not notes:
        raise ValueError('Unexpected Table 4a layout; review the source before publishing.')
    return result, notes


def fetch_market(ticker):
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker)}?range=5y&interval=1d'
    chart = get(url).json()['chart']
    if chart.get('error') or not chart.get('result'):
        raise ValueError(str(chart.get('error')))
    result = chart['result'][0]
    meta = result['meta']
    if meta.get('instrumentType') != 'EQUITY' or meta.get('symbol', '').upper() != ticker.upper():
        raise ValueError('Unexpected instrument identity')
    tz = ZoneInfo(meta['exchangeTimezoneName'])
    regular = meta.get('currentTradingPeriod', {}).get('regular', {})
    close_hour = datetime.fromtimestamp(regular.get('end', 0), tz).strftime('%H:%M')
    closes = result['indicators']['quote'][0]['close']
    adjusted = result['indicators'].get('adjclose', [{}])[0].get('adjclose', [])
    if len(adjusted) != len(closes):
        raise ValueError('Adjusted close series unavailable')
    today = datetime.now(tz).date()
    bars = []
    for ts, close, adj in zip(result.get('timestamp', []), closes, adjusted):
        day = datetime.fromtimestamp(ts, tz).date()
        # Only completed sessions: ignore an intraday partial bar.
        if day == today and datetime.now(tz).strftime('%H:%M') < close_hour:
            continue
        if close is not None and adj is not None and close > 0 and adj > 0:
            bars.append({'date': day.isoformat(), 'close': round(close, 6), 'adjusted': round(adj, 6)})
    if len(bars) < 2:
        raise ValueError('Insufficient completed sessions')
    return {'provider_name': meta.get('longName', meta.get('shortName', ticker)),
            'currency': meta['currency'], 'exchange': meta.get('fullExchangeName', meta.get('exchangeName')),
            'timezone': meta['exchangeTimezoneName'], 'normal_close': close_hour,
            'fetched_at': datetime.now(timezone.utc).isoformat(), 'bars': bars, 'status': 'ok'}


def fetch_news(company, week_end=None):
    window = 'when:90d'
    if week_end:
        end = datetime.fromisoformat(week_end).date()
        window = f'after:{end-timedelta(days=8)} before:{end+timedelta(days=1)}'
    query = quote(f'"{company}" (shares OR stock OR earnings OR contract) {window}')
    url = f'https://news.google.com/rss/search?q={query}&hl=en-GB&gl=GB&ceid=GB:en'
    root = ET.fromstring(get(url).content)
    stories, seen = [], set()
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    for item in root.findall('./channel/item'):
        title, link = item.findtext('title', ''), item.findtext('link', '')
        if not title or not link.startswith('https://') or title in seen:
            continue
        try:
            published = parsedate_to_datetime(item.findtext('pubDate', '')).astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
        if published < cutoff or published > datetime.now(timezone.utc) + timedelta(hours=1):
            continue
        seen.add(title)
        source = item.find('source')
        stories.append({'title': title, 'url': link, 'published': published.isoformat(),
                        'source': source.text if source is not None else 'Google News'})
    return sorted(stories, key=lambda n: n['published'], reverse=True)[:30]


def map_news(stories, market):
    """Map after-hours/weekend headlines to the next observable daily session."""
    bars = market.get('bars', [])
    tz = ZoneInfo(market.get('timezone', 'UTC'))
    close = market.get('normal_close', '23:59')
    for story in stories:
        local = datetime.fromisoformat(story['published']).astimezone(tz)
        day = local.date()
        if local.strftime('%H:%M') >= close:
            day += timedelta(days=1)
        index = next((i for i, b in enumerate(bars) if b['date'] >= day.isoformat()), None)
        story['session'] = bars[index]['date'] if index is not None else None
        story['move_pct'] = round((bars[index]['adjusted'] / bars[index-1]['adjusted'] - 1) * 100, 3) if index is not None and index > 0 else None
    return stories


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh-source', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/snapshot.json',
                        help='Write a candidate snapshot here instead of replacing the saved snapshot')
    args = parser.parse_args()
    source = ROOT / 'data/source/mod-tic-2025.ods'
    if args.refresh_source or not source.exists():
        source.write_bytes(get(SOURCE_URL).content)
    companies, notes = parse_table(source.read_bytes())
    with (ROOT / 'data/listings.csv').open() as handle:
        listings = {r['organisation']: r for r in csv.DictReader(handle)}
    if set(listings) - {c['name'] for c in companies}:
        raise ValueError('Listing mapping contains unknown Table 4a companies')
    path = args.output
    saved = ROOT / 'data/snapshot.json'
    previous = json.loads(saved.read_text()) if saved.exists() else {}
    old = {c['name']: c for c in previous.get('companies', [])}
    errors = []

    def enrich(c):
        listing = listings.get(c['name'])
        c['ticker'] = listing['ticker'] if listing else None
        c['news_name'] = listing['news_name'] if listing else c['name']
        if not listing:
            c['market'] = {'status': 'unmapped', 'bars': []}
            c['news'] = []
            return c
        try:
            c['market'] = fetch_market(c['ticker'])
        except Exception as exc:
            c['market'] = dict(old.get(c['name'], {}).get('market', {'bars': []}))
            c['market']['status'] = 'stale' if c['market'].get('bars') else 'unavailable'
            errors.append(f"{c['ticker']} prices: {str(exc)[:180]}")
        try:
            c['news'] = map_news(fetch_news(listing['news_name']), c['market'])
            c['news_status'] = 'ok'
            c['news_fetched_at'] = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            c['news'] = map_news(old.get(c['name'], {}).get('news', []), c['market'])
            c['news_status'] = 'stale' if c['news'] else 'unavailable'
            c['news_fetched_at'] = old.get(c['name'], {}).get('news_fetched_at')
            errors.append(f"{c['ticker']} news: {str(exc)[:180]}")
        print(f"{c['ticker']}: {len(c['market']['bars'])} sessions, {len(c['news'])} headlines", flush=True)
        return c

    with ThreadPoolExecutor(max_workers=4) as pool:
        enriched = list(pool.map(enrich, companies))
    week_end = max(c['market']['bars'][-1]['date'] for c in enriched if c['market']['bars'])

    def weekly_news(c):
        if not c['ticker']:
            return c
        try:
            c['weekly_news'] = map_news(fetch_news(c['news_name'], week_end), c['market'])
            c['weekly_news_status'] = 'ok'
        except Exception as exc:
            # In-week items from the general feed are an explicit fallback, not stale last-week prose.
            c['weekly_news'] = c.get('news', [])
            c['weekly_news_status'] = 'fallback'
            errors.append(f"{c['ticker']} weekly news: {str(exc)[:180]}")
        return c

    with ThreadPoolExecutor(max_workers=4) as pool:
        enriched = list(pool.map(weekly_news, enriched))
    available = sum(bool(c['market'].get('bars')) for c in enriched)
    fresh = sum(c['market'].get('status') == 'ok' for c in enriched)
    if fresh < len(listings) * .8:
        raise RuntimeError(f'Only {fresh}/{len(listings)} series refreshed; retaining previous snapshot.')
    payload = {'generated_at': datetime.now(timezone.utc).isoformat(),
               'source_url': SOURCE_URL, 'publication_url': PUBLICATION_URL,
               'spending_period': '2024/25', 'source_revision': '12 March 2026',
               'threshold_m': 50, 'companies': enriched, 'notes': notes, 'warnings': errors}
    add_weekly_summaries(payload)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
    temporary.replace(path)
    for error in errors:
        print(f'WARNING: {error}')
    print(f'Saved {len(companies)} companies; {available}/{len(listings)} price series.')


if __name__ == '__main__':
    main()
