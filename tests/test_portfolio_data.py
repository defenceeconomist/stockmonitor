"""Benchmark identity, FX direction and failed-download preservation."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from portfolio_data import refresh
from update_data import fetch_market


def series(currency='GBP'):
    return {'status': 'ok', 'currency': currency, 'bars': [
        {'date': '2026-11-19', 'adjusted': 1, 'close': 1},
        {'date': '2026-11-20', 'adjusted': 1.1, 'close': 1.1}], 'fetched_at': '2026-11-20T22:00:00+00:00'}


class PortfolioDataTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {'companies': [
            {'name': 'Euro PLC', 'ticker': 'EU', 'spend_m': 100, 'market': {'currency': 'EUR'}},
            {'name': 'UK PLC', 'ticker': 'UK', 'spend_m': 100, 'market': {'currency': 'GBp'}},
            {'name': 'Private Ltd', 'ticker': None, 'spend_m': 100, 'market': {}}]}

    def test_downloads_two_accumulating_proxies_and_only_required_fx(self):
        fetch = Mock(side_effect=lambda ticker, instrument: series())
        result = refresh(self.snapshot, {}, fetch)['portfolio_market']
        self.assertEqual(set(result['benchmarks']), {'global', 'uk'})
        self.assertEqual(set(result['fx']), {'EUR'})
        self.assertEqual(result['fx']['EUR']['direction'], 'GBP per unit of foreign currency')
        self.assertEqual(result['warnings'], [])
        self.assertEqual({c.args for c in fetch.call_args_list},
                         {('VWRP.L', 'ETF'), ('FTAL.L', 'ETF'), ('EURGBP=X', 'CURRENCY')})

    def test_failed_fetch_preserves_dated_cache_and_marks_it_stale(self):
        saved = refresh(deepcopy(self.snapshot), {}, lambda *args: series())
        result = refresh(self.snapshot, saved, Mock(side_effect=RuntimeError('rate limited')))['portfolio_market']
        self.assertEqual(len(result['warnings']), 3)
        cached = result['fx']['EUR']['market']
        self.assertEqual(cached['status'], 'stale')
        self.assertEqual(cached['bars'], saved['portfolio_market']['fx']['EUR']['market']['bars'])
        self.assertEqual(cached['fetched_at'], '2026-11-20T22:00:00+00:00')
        self.assertEqual(saved['portfolio_market']['fx']['EUR']['market']['status'], 'ok')

    def test_failure_without_cache_and_wrong_rate_direction_are_unavailable(self):
        for fetch in (Mock(side_effect=RuntimeError('no connection')), lambda *args: series('EUR')):
            result = refresh(deepcopy(self.snapshot), {}, fetch)['portfolio_market']
            self.assertEqual(result['fx']['EUR']['market']['status'], 'unavailable')
            self.assertEqual(result['fx']['EUR']['market']['bars'], [])
            self.assertEqual(len(result['warnings']), 3)

    def response(self, symbol, instrument):
        return {'chart': {'result': [{'meta': {'symbol': symbol, 'currency': 'GBP', 'instrumentType': instrument,
                'exchangeTimezoneName': 'Europe/London'},
                'timestamp': [1795089600, 1795176000],
                'indicators': {'quote': [{'close': [100, 101]}], 'adjclose': [{'adjclose': [100, 101]}]}}]}}

    @patch('update_data.get')
    def test_etf_identity_is_checked_and_currency_alias_is_explicit(self, get):
        get.return_value.json.return_value = self.response('VWRP.L', 'ETF')
        self.assertEqual(fetch_market('VWRP.L', 'ETF')['currency'], 'GBP')
        with self.assertRaisesRegex(ValueError, 'identity'):
            fetch_market('VWRP.L')
        get.return_value.json.return_value = self.response('GBP=X', 'CURRENCY')
        self.assertEqual(fetch_market('USDGBP=X', 'CURRENCY')['status'], 'ok')
        with self.assertRaisesRegex(ValueError, 'identity'):
            fetch_market('EURGBP=X', 'CURRENCY')


if __name__ == '__main__':
    unittest.main()
