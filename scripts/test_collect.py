import importlib.util
import json
import pathlib
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import subprocess
spec = importlib.util.spec_from_file_location('collect', pathlib.Path(__file__).with_name('collect.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
class CollectorTests(unittest.TestCase):
    def test_fetch_records_safe_http_diagnostics(self):
        with patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],22,stdout='503',stderr='untrusted upstream details')):
            with self.assertRaises(module.SourceFetchError) as caught:module.fetch('https://api.weather.gov/example')
            self.assertEqual(caught.exception.safe_code,'curl=22;http=503')
            self.assertNotIn('untrusted',str(caught.exception))

    def test_fetch_parses_only_final_output_file(self):
        def fake(args, **kwargs):
            pathlib.Path(args[args.index('--output')+1]).write_text('{"ok": true}')
            return subprocess.CompletedProcess(args,0,stdout='200',stderr='')
        with patch.object(module.subprocess,'run',side_effect=fake):
            self.assertEqual(module.fetch('https://api.weather.gov/example'),{'ok':True})

    def test_snapshots_append_and_capture_orderbooks(self):
        def fake(url):
            if '/points/' in url:
                return {'properties': {'forecastHourly': 'https://api.weather.gov/hourly'}}
            if '/markets?' in url:
                return {'markets': [{'ticker': 'KXHIGHAUS-26JUL15-B97'}]}
            return {'source': url}
        with tempfile.TemporaryDirectory() as directory:
            path = str(pathlib.Path(directory)/'snapshots.sqlite')
            self.assertEqual(module.collect(path, fake), [])
            self.assertEqual(module.collect(path, fake), [])
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0], 28)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM snapshots WHERE source='kalshi.orderbook'").fetchone()[0], 2)
    def test_partial_failures_are_recorded(self):
        def fail(url):
            raise RuntimeError('offline')
        with tempfile.TemporaryDirectory() as directory:
            path = str(pathlib.Path(directory)/'snapshots.sqlite')
            self.assertTrue(module.collect(path, fail))
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM snapshots WHERE payload IS NOT NULL').fetchone()[0], 0)
                self.assertTrue(db.execute('SELECT error FROM snapshots').fetchall())
if __name__ == '__main__':
    unittest.main()
