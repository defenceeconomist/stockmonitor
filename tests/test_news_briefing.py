"""Editorial integrity: exact coverage, current dates and traceable citations."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from news_briefing import prepare, validate


class NewsBriefingTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {'generated_at': '2026-11-23T12:00:00+00:00', 'companies': [
            {'name': f'Example {i} PLC', 'ticker': None, 'spend_m': i, 'news': []}
            for i in range(78)]}
        self.story = {'title': 'Example 77 wins radar contract - Reuters', 'source': 'Reuters',
                      'published': '2026-11-22T12:00:00+00:00', 'url': 'https://example.org/news'}
        self.snapshot['companies'][-1]['news'] = [self.story]
        evidence = prepare(self.snapshot)
        self.briefing = {'author': 'Codex', 'generated_at': datetime.now(timezone.utc).isoformat(),
                         'source_generated_at': self.snapshot['generated_at'],
                         'window_start': evidence['window_start'], 'overview': 'The week in news.',
                         'companies': [{'name': c['name'], 'status': 'no_news', 'summary': 'No qualifying news.', 'sources': []}
                                       for c in evidence['companies']]}
        self.briefing['companies'][0].update(status='covered', summary='A radar contract was reported.', sources=[self.story])

    def test_top_fifty_include_unquoted_and_exact_spending_boundary(self):
        evidence = prepare(self.snapshot)
        self.assertEqual(len(evidence['companies']), 50)
        self.assertEqual(evidence['companies'][0]['spend_m'], 77)
        self.assertEqual(evidence['companies'][-1]['spend_m'], 28)
        self.assertEqual(evidence['companies'][0]['stories'], [self.story])
        self.assertIs(validate(self.briefing, self.snapshot), self.briefing)

    def test_old_future_noisy_and_unrelated_headlines_are_excluded(self):
        c = self.snapshot['companies'][-1]
        for overrides in ({'published': '2026-11-15T12:00:00+00:00'},
                          {'published': '2026-11-24T12:00:00+00:00'},
                          {'title': 'Other firm wins radar contract'},
                          {'source': 'ad-hoc-news.de'},
                          {'title': 'Example 77 stock price, news and history'}):
            c['news'] = [self.story | overrides]
            self.assertEqual(prepare(self.snapshot)['companies'][0]['stories'], [])

    def test_stale_or_wrong_window_briefings_fail(self):
        for field in ('source_generated_at', 'window_start'):
            b = deepcopy(self.briefing)
            b[field] = '2026-11-01T12:00:00+00:00'
            with self.assertRaises(ValueError):
                validate(b, self.snapshot)

    def test_missing_duplicate_and_foreign_suppliers_fail(self):
        for entries in (self.briefing['companies'][:-1],
                        self.briefing['companies'][:-1] + [self.briefing['companies'][0]],
                        self.briefing['companies'][:-1] + [{'name': 'Outside PLC'}]):
            with self.assertRaises(ValueError):
                validate(self.briefing | {'companies': entries}, self.snapshot)

    def test_invented_or_changed_citations_fail(self):
        for overrides in ({'url': 'https://example.org/invented'}, {'title': 'Different title'},
                          {'published': '2026-11-21T12:00:00+00:00'}):
            b = deepcopy(self.briefing)
            b['companies'][0]['sources'][0].update(overrides)
            with self.assertRaises(ValueError):
                validate(b, self.snapshot)

    def test_covered_summary_requires_citation(self):
        self.briefing['companies'][0]['sources'] = []
        with self.assertRaises(ValueError):
            validate(self.briefing, self.snapshot)


if __name__ == '__main__':
    unittest.main()
