"""Refresh, check and render a candidate before replacing the local monitor."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(command, env):
    print('+ ' + ' '.join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=ROOT, env=env, check=True)


def promote(candidate, site, staging):
    """Roll back both outputs if either replacement fails."""
    snapshot = ROOT / 'data/snapshot.json'
    target = ROOT / '_site'
    backup = staging / 'previous-snapshot.json'
    old_site = staging / 'previous-site'
    had_snapshot, had_site = snapshot.exists(), target.exists()
    if had_snapshot:
        shutil.copy2(snapshot, backup)
    if had_site:
        target.rename(old_site)
    try:
        site.rename(target)
        candidate.replace(snapshot)
    except BaseException:
        if target.exists():
            shutil.rmtree(target)
        if had_site:
            old_site.rename(target)
        if had_snapshot:
            backup.replace(snapshot)
        raise


def update(cached=False, refresh_source=False):
    lock = ROOT / '.update-lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise RuntimeError('Another update holds .update-lock. If it was interrupted, remove the lock after checking no update is running.')
    report = {'started_at': datetime.now(timezone.utc).isoformat(),
              'mode': 'cached' if cached else 'refresh', 'status': 'failed',
              'step': 'check required tools'}
    try:
        for executable in ('node', 'quarto'):
            if not shutil.which(executable):
                raise RuntimeError(f'{executable} is required; see README.md for setup.')
        with tempfile.TemporaryDirectory(prefix='.update-', dir=ROOT) as directory:
            staging = Path(directory)
            candidate = staging / 'snapshot.json'
            site = staging / 'site'
            env = dict(os.environ, STOCKMONITOR_SNAPSHOT=str(candidate))
            if cached:
                report['step'] = 'load saved snapshot'
                shutil.copy2(ROOT / 'data/snapshot.json', candidate)
            else:
                report['step'] = 'refresh prices and news'
                command = [sys.executable, ROOT / 'scripts/update_data.py', '--output', candidate]
                if refresh_source:
                    command.append('--refresh-source')
                run(command, env)
            report['step'] = 'check data and calculations'
            run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], env)
            run(['node', 'tests/test_windows.cjs'], env)
            report['step'] = 'render website'
            run(['quarto', 'render', '--output-dir', site], env)
            if not (site / 'index.html').is_file() or not (site / 'assets/dashboard.json').is_file():
                raise RuntimeError('Rendered site is missing index.html or dashboard data')
            payload = json.loads(candidate.read_text())
            if json.loads((site / 'assets/dashboard.json').read_text()) != payload:
                raise RuntimeError('Rendered dashboard does not match the candidate snapshot')
            report.update(generated_at=payload['generated_at'],
                          companies=len(payload['companies']),
                          fresh_prices=sum(c['market']['status'] == 'ok' for c in payload['companies']),
                          warnings=payload.get('warnings', []))
            report['step'] = 'save verified outputs'
            promote(candidate, site, staging)
            report.update(status='success', step='complete')
    except BaseException as exc:
        report['error'] = str(exc)
        raise
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        try:
            (ROOT / 'data/update-report.json').write_text(json.dumps(report, indent=2) + '\n')
        finally:
            lock.rmdir()
    print('Update complete. Website: _site/index.html; report: data/update-report.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--cached', action='store_true', help='Check and build saved data without downloading')
    mode.add_argument('--refresh-source', action='store_true', help='Also re-download the pinned MOD source')
    args = parser.parse_args()
    update(cached=args.cached, refresh_source=args.refresh_source)


if __name__ == '__main__':
    main()
