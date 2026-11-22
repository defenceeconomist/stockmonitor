from copy import deepcopy
from datetime import datetime
from pathlib import Path
import json
import os
import sys
import unittest
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from weekly_summary import summarize_company, add_weekly_summaries, is_reported_catalyst


def story(title, published='2026-11-18T12:00:00+00:00', session='2026-11-18'):
    return {'title':title,'source':'Reuters','url':'https://example.org/report',
            'published':published,'session':session,'move_pct':-2}


def company():
    return {'name':'Example PLC','news_name':'Example','ticker':'EX.L',
            'market':{'status':'ok','timezone':'Europe/London','normal_close':'16:30','bars':[
                {'date':'2026-11-13','adjusted':100},
                {'date':'2026-11-16','adjusted':110},
                {'date':'2026-11-18','adjusted':105},
                {'date':'2026-11-20','adjusted':95}]},
            'weekly_news_status':'ok','weekly_news':[]}


class WeeklyTests(unittest.TestCase):
    def test_week_return_and_largest_move(self):
        result = summarize_company(company(),'2026-11-20')
        self.assertEqual(result['change_pct'],-5)
        self.assertEqual(result['largest_session'],{'date':'2026-11-16','change_pct':10})
        self.assertEqual(result['status'],'insufficient')

    def test_reported_catalyst_requires_price_subject(self):
        c=company()
        c['weekly_news']=[story('Example shares fall after profit warning')]
        result=summarize_company(c,'2026-11-20')
        self.assertEqual(result['status'],'reported')
        self.assertIn('profit warning',result['text'])
        self.assertFalse(is_reported_catalyst(story('Example H1 profit rises on contract wins'),c))
        self.assertFalse(is_reported_catalyst(story('Example stock moved down by 3% on Nov 18: Key Drivers Unveiled'),c))
        self.assertFalse(is_reported_catalyst(story('Will Example shares rise on new orders?'),c))

    def test_cutoff_and_future_news_cannot_explain_week(self):
        c=company()
        c['weekly_news']=[
            story('Example contract awarded','2026-11-13T17:00:00+00:00','2026-11-16'),
            story('Example contract awarded before window','2026-11-13T16:00:00+00:00','2026-11-13'),
            story('Example shares fall after profit warning','2026-11-20T16:31:00+00:00','2026-11-23'),
            story('Example shares rise after earnings beat','2026-11-21T12:00:00+00:00',None)]
        result=summarize_company(c,'2026-11-20')
        self.assertEqual(len(result['sources']),1)
        self.assertEqual(result['status'],'context')
        self.assertEqual(result['sources'][0]['session'],'2026-11-16')

    def test_no_quote_and_old_week_not_recycled(self):
        c=company();c['ticker']=None
        self.assertEqual(summarize_company(c,'2026-11-20')['status'],'unquoted')
        c=company();c['weekly_news']=[story('Example shares fall after earnings miss','2026-11-06T12:00:00+00:00','2026-11-06')]
        self.assertEqual(summarize_company(c,'2026-11-20')['status'],'insufficient')

    def test_noise_unrelated_and_reindexed_history_excluded(self):
        c=company();c['weekly_news']=[story('Other shares fall after earnings miss'),
            story('Example Stock Price, News, Quote & History'),
            story('Example recounts contract work (11/16/2005)')]
        self.assertEqual(summarize_company(c,'2026-11-20')['sources'],[])

    def test_every_company_has_only_in_week_evidence(self):
        root=Path(__file__).resolve().parents[1]
        data=add_weekly_summaries(json.loads(Path(os.environ.get('STOCKMONITOR_SNAPSHOT', root/'data/snapshot.json')).read_text()))
        self.assertEqual(len(data['companies']),78)
        for c in data['companies']:
            w=c['weekly_summary'];self.assertEqual(w['week_end'],data['weekly_period']['end'])
            for source in w['sources']:
                self.assertTrue(w['price_start']<source['session']<=w['price_end'])
                tz=ZoneInfo(c['market']['timezone'])
                end=datetime.fromisoformat(w['price_end']+'T'+c['market']['normal_close']).replace(tzinfo=tz)
                self.assertLessEqual(datetime.fromisoformat(source['published']),end)


if __name__=='__main__':unittest.main()
