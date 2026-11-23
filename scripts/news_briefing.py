"""Prepare headline evidence for Codex and validate its saved editorial briefing."""
import argparse
from datetime import datetime, timedelta
import json
import os
import re
from pathlib import Path
from weekly_summary import NOISE, WEAK, headline, mentions_company

ROOT = Path(__file__).resolve().parents[1]


def top_companies(snapshot):
    return sorted(snapshot['companies'], key=lambda c: (-c['spend_m'], c['name']))[:50]


def prepare(snapshot):
    end = datetime.fromisoformat(snapshot['generated_at'])
    start = end - timedelta(days=7)
    companies = []
    for rank, company in enumerate(top_companies(snapshot), 1):
        stories, seen = [], set()
        for story in sorted(company.get('news', []) + company.get('weekly_news', []), key=lambda n: n['published'], reverse=True):
            title = headline(story)
            if not start <= datetime.fromisoformat(story['published']) <= end:
                continue
            if story['url'] in seen or NOISE.search(title) or WEAK.search(story.get('source', '')) or not mentions_company(story, company):
                continue
            if '?' in title or re.search(r'technical analysis|stock traders daily|simply wall st|seasonal returns|tokenized|dividend analysis', title + ' ' + story.get('source', ''), re.I):
                continue
            seen.add(story['url'])
            stories.append({k: story[k] for k in ('title', 'url', 'source', 'published')})
        companies.append({'rank': rank, 'name': company['name'], 'ticker': company['ticker'],
                          'spend_m': company['spend_m'], 'news_status': company.get('news_status', 'unavailable'),
                          'stories': stories[:8]})
    return {'source_generated_at': snapshot['generated_at'], 'window_start': start.isoformat(),
            'window_end': end.isoformat(), 'basis': 'Headline metadata only; do not imply article bodies were read.',
            'companies': companies}


def validate(briefing, snapshot):
    """A dated, complete top-50 briefing; citations must refer to the saved evidence."""
    if briefing.get('author') != 'Codex':
        raise ValueError('Briefing author must be Codex')
    datetime.fromisoformat(briefing['generated_at'])
    if briefing.get('source_generated_at') != snapshot['generated_at']:
        raise ValueError('Briefing belongs to a different snapshot; regenerate it with Codex')
    evidence = prepare(snapshot)
    if briefing.get('window_start') != evidence['window_start']:
        raise ValueError('Briefing window must match the seven-day evidence window')
    expected = {c['name']: c for c in evidence['companies']}
    entries = briefing.get('companies', [])
    if len(entries) != len(expected) or {c['name'] for c in entries} != set(expected):
        raise ValueError('Briefing must contain each top-50 supplier exactly once')
    for entry in entries:
        if entry.get('status') not in ('covered', 'no_news') or not isinstance(entry.get('summary'), str) or not entry['summary'].strip():
            raise ValueError(f"Invalid summary for {entry['name']}")
        sources = entry.get('sources', [])
        if (entry['status'] == 'covered') != bool(sources):
            raise ValueError('Covered summaries need citations; no-news entries must not have them')
        allowed = {s['url']: s for s in expected[entry['name']]['stories']}
        for source in sources:
            if source.get('url') not in allowed or source != allowed[source['url']]:
                raise ValueError(f"Citation not in the current evidence for {entry['name']}")
    if not isinstance(briefing.get('overview'), str) or not briefing['overview'].strip():
        raise ValueError('Briefing needs an overview')
    return briefing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true', help='Print compact top-50 evidence for Codex to summarise')
    args = parser.parse_args()
    snapshot = json.loads(Path(os.environ.get('STOCKMONITOR_SNAPSHOT', ROOT / 'data/snapshot.json')).read_text())
    if args.prepare:
        print(json.dumps(prepare(snapshot), ensure_ascii=False, indent=2))
    else:
        validate(json.loads((ROOT / 'data/news-briefing.json').read_text()), snapshot)
        print('Codex briefing verified: all top-50 firms and current, linked evidence.')


if __name__ == '__main__':
    main()
