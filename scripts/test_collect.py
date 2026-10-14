import importlib.util
import json
import pathlib
import sqlite3
import tempfile
import unittest
spec = importlib.util.spec_from_file_location('collect', pathlib.Path(__file__).with_name('collect.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
class CollectorTests(unittest.TestCase):
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
