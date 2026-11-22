import importlib.util
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
spec = importlib.util.spec_from_file_location('pipeline', Path(__file__).resolve().parents[1] / 'scripts/update_data.py')
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class PipelineTests(unittest.TestCase):
    def test_official_source_strict_threshold(self):
        companies, notes = pipeline.parse_table((pipeline.ROOT/'data/source/mod-tic-2025.ods').read_bytes())
        self.assertEqual(len(companies), 78)
        self.assertEqual(companies[0]['name'], 'BAE Systems PLC')
        self.assertEqual(companies[0]['spend_m'], 6741)
        self.assertTrue(all(c['spend_m'] > 50 for c in companies))
        self.assertNotIn('Warwick & Esplen Ltd', [c['name'] for c in companies])
        self.assertEqual(len(notes), 7)

    def test_news_sessions_with_timezone_after_close_and_weekend(self):
        market = {'timezone':'America/New_York', 'normal_close':'16:00', 'bars':[
            {'date':'2026-11-19','adjusted':100},
            {'date':'2026-11-20','adjusted':105},
            {'date':'2026-11-23','adjusted':102.9}]}
        stories = [{'published':d} for d in [
            '2026-11-20T20:59:00+00:00',  # Before New York close.
            '2026-11-20T21:01:00+00:00',  # After close.
            '2026-11-21T12:00:00+00:00',  # Saturday.
            '2026-11-24T12:00:00+00:00']]
        result = pipeline.map_news(stories, market)
        self.assertEqual([n['session'] for n in result], ['2026-11-20','2026-11-23','2026-11-23',None])
        self.assertEqual([n['move_pct'] for n in result], [5,-2,-2,None])

    def test_first_observed_session_has_no_prior_move(self):
        result = pipeline.map_news([{'published':'2026-11-20T10:00:00+00:00'}], {
            'timezone':'Europe/London','normal_close':'16:30','bars':[{'date':'2026-11-20','adjusted':100}]})
        self.assertIsNone(result[0]['move_pct'])

    def test_snapshot_integrity(self):
        import json, csv
        snapshot = json.loads((pipeline.ROOT/'data/snapshot.json').read_text())
        with (pipeline.ROOT/'data/listings.csv').open() as handle:
            mappings = list(csv.DictReader(handle))
        self.assertEqual(len(mappings), len({c['ticker'] for c in mappings}))
        self.assertEqual(len(mappings), 50)
        for company in snapshot['companies']:
            bars = company['market']['bars']
            self.assertEqual([b['date'] for b in bars], sorted({b['date'] for b in bars}))
            for news in company['news']:
                self.assertTrue(news['url'].startswith('https://'))
                self.assertTrue(news['session'] is None or news['session'] in {b['date'] for b in bars})


if __name__ == '__main__':
    unittest.main()
