"""Prepare static assets without network access; refreshes are a separate command."""
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
snapshot = json.loads(Path(os.environ.get('STOCKMONITOR_SNAPSHOT', root / 'data/snapshot.json')).read_text())
assert snapshot['companies'], 'Run python3 scripts/update_data.py first'
(root / 'assets/dashboard.json').write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')))
