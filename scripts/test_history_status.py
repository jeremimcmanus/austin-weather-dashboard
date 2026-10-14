import importlib.util
import json
import pathlib
import sqlite3
import tempfile
import unittest
from history_status import history_status
from collect import collect
from production import write_status
class HistoryTests(unittest.TestCase):
    def test_empty_storage_never_claims_running_collector(self):
        with tempfile.TemporaryDirectory() as directory:
            status=history_status(directory)
            self.assertIsNone(status['collector'])
            self.assertEqual(status['snapshots'],0)
    def test_persisted_history_and_deduplicated_observations(self):
        def fake(url):
            if '/points/' in url:return {'properties':{'forecastHourly':'https://api.weather.gov/hourly'}}
            if '/observations/' in url:return {'properties':{'timestamp':'2026-10-14T15:00:00Z','temperature':{'value':30}}}
            return {}
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)
            collect(str(path/'snapshots.sqlite'),fake)
            collect(str(path/'snapshots.sqlite'),fake)
            write_status(path/'collector-status.json',{'state':'healthy','lastSuccessAt':'2026-10-14T15:01:00Z'})
            status=history_status(directory)
            self.assertEqual(status['runs'],2)
            self.assertEqual(status['collector']['state'],'healthy')
            self.assertEqual(status['observationHistory'],[{'observedAt':'2026-10-14T15:00:00Z','receivedAt':status['observationHistory'][0]['receivedAt'],'temperatureF':86.0}])
            self.assertGreater(status['bytes'],0)
    def test_broken_status_is_visible_without_hiding_database(self):
        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory,'collector-status.json').write_text('invalid')
            self.assertEqual(history_status(directory)['collector']['state'],'unreadable')
if __name__=='__main__':unittest.main()
