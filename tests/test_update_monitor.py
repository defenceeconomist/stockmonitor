"""Verify update failures preserve the last successful monitor."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_monitor as monitor


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'data').mkdir()
        self.saved = self.root / 'data/snapshot.json'
        self.saved.write_text(json.dumps({'generated_at': '2026-11-20', 'companies': [
            {'market': {'status': 'ok'}}], 'warnings': ['Example warning']}))
        (self.root / '_site').mkdir()
        (self.root / '_site/index.html').write_text('previous site')
        self.patch = patch.object(monitor, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def report(self):
        return json.loads((self.root / 'data/update-report.json').read_text())

    @patch.object(monitor.shutil, 'which', return_value='/tool')
    def test_failed_checks_preserve_snapshot_and_site(self, _):
        original = self.saved.read_bytes()
        with patch.object(monitor, 'run', side_effect=subprocess.CalledProcessError(1, 'tests')):
            with self.assertRaises(subprocess.CalledProcessError):
                monitor.update(cached=True)
        self.assertEqual(self.saved.read_bytes(), original)
        self.assertEqual((self.root / '_site/index.html').read_text(), 'previous site')
        self.assertEqual(self.report()['status'], 'failed')
        self.assertFalse((self.root / '.update-lock').exists())

    @patch.object(monitor.shutil, 'which', return_value='/tool')
    def test_success_promotes_rendered_site_and_records_warnings(self, _):
        commands = []

        def fake_run(command, env):
            commands.append(command)
            self.assertTrue(Path(env['STOCKMONITOR_SNAPSHOT']).is_file())
            if command[0] == 'quarto':
                site = Path(command[-1])
                (site / 'assets').mkdir(parents=True)
                (site / 'index.html').write_text('new site')
                (site / 'assets/dashboard.json').write_bytes(self.saved.read_bytes())

        with patch.object(monitor, 'run', side_effect=fake_run):
            monitor.update(cached=True)
        self.assertEqual(len(commands), 3)
        self.assertEqual((self.root / '_site/index.html').read_text(), 'new site')
        self.assertEqual(self.report()['status'], 'success')
        self.assertEqual(self.report()['warnings'], ['Example warning'])

    def test_promotion_failure_restores_previous_outputs(self):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            staging = Path(directory)
            site = staging / 'site'
            site.mkdir()
            (site / 'index.html').write_text('new site')
            original = self.saved.read_bytes()
            with self.assertRaises(FileNotFoundError):
                monitor.promote(staging / 'missing-candidate', site, staging)
            self.assertEqual(self.saved.read_bytes(), original)
            self.assertEqual((self.root / '_site/index.html').read_text(), 'previous site')

    def test_existing_lock_is_respected(self):
        lock = self.root / '.update-lock'
        lock.mkdir()
        with self.assertRaisesRegex(RuntimeError, 'Another update'):
            monitor.update(cached=True)
        self.assertTrue(lock.is_dir())


if __name__ == '__main__':
    unittest.main()
