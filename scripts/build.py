"""Prepare static assets without network access; refreshes are a separate command."""
import json
import os
from news_briefing import validate
from pathlib import Path

root = Path(__file__).resolve().parents[1]
snapshot = json.loads(Path(os.environ.get('STOCKMONITOR_SNAPSHOT', root / 'data/snapshot.json')).read_text())
assert snapshot['companies'], 'Run python3 scripts/update_data.py first'
(root / 'assets/dashboard.json').write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')))

briefing_path = root / 'data/news-briefing.json'
briefing = None
if briefing_path.exists():
    saved = json.loads(briefing_path.read_text())
    # Never label prose from an earlier snapshot as the latest briefing.
    if saved.get('source_generated_at') == snapshot['generated_at']:
        briefing = validate(saved, snapshot)
(root / 'assets/news-briefing.json').write_text(json.dumps(briefing, ensure_ascii=False, separators=(',', ':')))
