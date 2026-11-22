"""Deterministic, cited weekly briefings. Headline evidence never proves causation."""
from datetime import date, datetime, time, timedelta
import re
from zoneinfo import ZoneInfo

THEMES = [
    ('earnings and outlook', r'earnings|results|profit|revenue|guidance|cash.flow|outlook|backlog'),
    ('contracts and orders', r'contract|order\b|orders\b|award|deal\b'),
    ('corporate changes', r'acquisit|merger|takeover|buyout|spin.off|sale\b|disposal|offer update'),
    ('costs and restructuring', r'job cuts|layoff|restructur|workforce reduction|cut.{0,20}jobs|cost.saving'),
    ('analyst assessments', r'analyst|broker|rating|price target|target price|upgrade|downgrade|reiterat'),
    ('capital returns', r'dividend|buyback|treasury shares|share repurchase|share count'),
    ('operational or regulatory developments', r'meltdown|router|disruption|outage|probe|investigat|ground stop|shutdown|regulat|production|delay|cost overrun'),
]
NOISE = re.compile(r'RTX\s*(?:[3456]0[0-9]{2}|\d{4})|GeForce|graphics card|quote.*history|interactive stock chart|recent insider transactions|holding\(s\) in company|director/pdmr|stock forecasts|stock.*fair value|fairly priced|undervalued|valuation|stock.*to own|company diary|market.*forecast to|over (?:one |the |a |last |past |\d+[- ]?)?(?:month|quarter|year)|stock price, news|stock major holders|stock forecast.*predictions|stock analysis$|latest stock news|stock price forecast|what.{0,15}invested|shares.*acquired by|stock sold by|shares.*purchased by|form 8\.3|price to earnings forward', re.I)
# Only directional moves with an explicit connecting phrase are called reported catalysts.
CAUSAL = re.compile(r'\b(?:shares?|stock)\b.{0,45}\b(?:rise|rises|rose|jump|jumps|climb|climbs|gain|gains|surge|surges|fall|falls|fell|slide|slides|slip|slips|drop|drops|down|up)\b.{0,20}\b(?:after|on|as|because|amid|following)\b', re.I)
REPUTABLE = re.compile(r'reuters|bloomberg|wall street journal|\bwsj\b|financial times|barron|marketwatch|bbc|investing.com|sharecast|morningstar|cnbc|yahoo finance|associated press', re.I)
WEAK = re.compile(r'ad-hoc-news|kalkine|traders union|tokenpost|journalarta', re.I)


def headline(story):
    title = story['title']
    suffix = ' - ' + story.get('source', '')
    return title[:-len(suffix)] if title.endswith(suffix) else title


def mentions_company(story, company):
    name = company.get('news_name') or company['name']
    words = re.findall(r'[\w]+', name.lower())
    stop = {'the','group','holdings','holding','international','company','corporation','corp','inc','plc','ltd','se','ag','ab','spa','defence','hellas'}
    words = [word for word in words if word not in stop]
    text = re.sub(r'[^\w]+', ' ', headline(story).lower())
    return bool(words) and all(re.search(r'\b'+re.escape(word)+r'\b', text[:150]) for word in words)


def classify(story):
    title = headline(story)
    return [name for name, pattern in THEMES if re.search(pattern, title, re.I)]


def is_reported_catalyst(story, company):
    title = headline(story)
    if re.search(r'\b(?:could|should|would|will)\b|\?', title, re.I):
        return False
    if re.search(r'key drivers unveiled|what.{0,15}driving|why.{0,25}stock|\bon (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Mon|Tue|Wed|Thu|Fri|Sat|Sun|\d)', title, re.I):
        return False
    match = CAUSAL.search(title)
    if match and not re.search(r'profit|earnings|revenue|backlog', match.group().split('rise')[0], re.I):
        # “down by 3% on Nov 18” reports a date, not a reason.
        if not re.search(r'\b(?:on|as) (?:Nov|Mon|Tue|Wed|Thu|Fri|Sat|Sun|\d)', title, re.I):
            return True
    brand = re.escape(company.get('news_name', company['name']).split()[0])
    return bool(re.search(r'^'+brand+r' (?:shares? |stock )?(?:falls?|rises?|jumps?|slides?|slips?).{0,35}\b(?:after|as|amid|following)\b', title, re.I))


def summarize_company(company, week_end):
    end = date.fromisoformat(week_end)
    start = end - timedelta(days=7)
    output = {'week_start': start.isoformat(), 'week_end': week_end,
              'basis': 'Automated summary of headline evidence; article bodies are not analysed.',
              'sources': [], 'change_pct': None}
    bars = company['market'].get('bars', [])
    if not company.get('ticker'):
        return output | {'status': 'unquoted', 'label': 'No direct public quote',
                         'text': 'No direct public stock listing is mapped for this holding company, so a weekly share-price movement cannot be calculated or explained.'}
    baseline = next((b for b in reversed(bars) if b['date'] <= start.isoformat()), None)
    last = next((b for b in reversed(bars) if b['date'] <= week_end), None)
    if not baseline or not last or last['date'] <= start.isoformat():
        return output | {'status': 'unavailable', 'label': 'Insufficient price data',
                         'text': 'There are not enough completed sessions to calculate a share-price change for the latest week.'}
    output['price_start'] = baseline['date']
    output['price_end'] = last['date']
    change = (last['adjusted'] / baseline['adjusted'] - 1) * 100
    output['change_pct'] = round(change, 3)
    action = 'rose' if change > 0 else 'fell' if change < 0 else 'were unchanged'
    opening = f'Shares {action}' + (f' {abs(change):.2f}%' if change else '') + ' over the latest week.'
    tz = ZoneInfo(company['market']['timezone'])
    close = time.fromisoformat(company['market']['normal_close'])
    begin = datetime.combine(date.fromisoformat(baseline['date']), close, tz)
    finish = datetime.combine(date.fromisoformat(last['date']), close, tz)
    # The weekly feed is separate from the capped 90-day list so it cannot be crowded out.
    candidates, seen = [], []
    for story in company.get('weekly_news', company.get('news', [])):
        published = datetime.fromisoformat(story['published'])
        if not begin < published <= finish or not story.get('session') or not baseline['date'] < story['session'] <= last['date']:
            continue
        if NOISE.search(headline(story)) or '?' in headline(story) or not mentions_company(story, company):
            continue
        # Re-indexed historical articles must not explain this week's movements.
        years = re.findall(r'(?<![\d$£€])\b(?:19|20)\d{2}\b', headline(story))
        if any(int(year) < end.year-1 for year in years):
            continue
        if not classify(story) and not is_reported_catalyst(story, company):
            continue
        candidates.append(story)
    def score(story):
        return (10 if is_reported_catalyst(story, company) else 0) + (8 if REPUTABLE.search(story.get('source','')) else 0) + (len(classify(story))*2) - (10 if WEAK.search(story.get('source','')) else 0)
    candidates.sort(key=score, reverse=True)
    sources = []
    for story in candidates:
        tokens = set(re.findall(r'[a-z0-9]+', headline(story).lower()))
        if any(len(tokens & earlier)/max(1,len(tokens | earlier)) > .5 for earlier in seen):
            continue
        seen.append(tokens)
        sources.append(story)
        if len(sources) == 3:
            break
    output['sources'] = [dict(s, headline=headline(s), themes=classify(s)) for s in sources]
    themes = list(dict.fromkeys(t for story in sources for t in classify(story)))[:3]
    if not sources or not themes:
        output.update(status='insufficient', label='No clear explanation found',
                      text=opening + ' The available in-week headlines do not establish a company-specific explanation. Broader market or sector effects have not been measured.')
    else:
        reported = next((s for s in sources if is_reported_catalyst(s, company) and not WEAK.search(s.get('source',''))), None)
        if reported:
            output.update(status='reported', label='Reported catalyst',
                          text=opening + f' {reported["source"]} reported: “{headline(reported)}” [1]. Coverage also highlighted ' + ', '.join(themes) + '. This is a reported catalyst for a move during the week, not proof of what drove the whole weekly return.')
            # Put the causally worded report first, as promised in the text.
            output['sources'].sort(key=lambda s: s['url'] != reported['url'])
        else:
            output.update(status='context', label='News context; cause unconfirmed',
                          text=opening + ' In-week coverage concerned ' + ', '.join(themes) + '. Notable reports: ' + '; '.join(f'“{headline(story)}” [{i+1}]' for i, story in enumerate(sources[:2])) + '. These are possible influences; the headlines do not establish the cause of the weekly move.')
    # Add observed largest-session move without attributing it to the headlines.
    period = [b for b in bars if baseline['date'] <= b['date'] <= last['date']]
    if len(period) > 1:
        moves = [(b['date'], (b['adjusted']/a['adjusted']-1)*100) for a,b in zip(period, period[1:])]
        day, move = max(moves, key=lambda x: abs(x[1]))
        output['largest_session'] = {'date': day, 'change_pct': round(move,3)}
    if company['market'].get('status') != 'ok' or last['date'] < (end-timedelta(days=4)).isoformat():
        output['text'] += ' Price coverage is stale or incomplete; treat this briefing cautiously.'
    if company.get('weekly_news_status',company.get('news_status')) != 'ok':
        output['text'] += ' The weekly news refresh failed; coverage may be incomplete.'
    return output


def add_weekly_summaries(snapshot):
    dates = [b['date'] for c in snapshot['companies'] for b in c['market'].get('bars', [])[-1:]]
    if not dates:
        raise ValueError('No quote sessions available for the weekly briefing')
    end = max(dates)
    snapshot['weekly_period'] = {'start': (date.fromisoformat(end)-timedelta(days=7)).isoformat(), 'end': end}
    for company in snapshot['companies']:
        company['weekly_summary'] = summarize_company(company, end)
    return snapshot
