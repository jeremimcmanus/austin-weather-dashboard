import datetime as dt
import gzip
import json
import pathlib
import sqlite3
import tempfile
import unittest
from backup import backup, restore, digest
from monitor import issues

class BackupTests(unittest.TestCase):
    def make_database(self, directory):
        path=pathlib.Path(directory)/'snapshots.sqlite'
        with sqlite3.connect(path) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE snapshots (received_at TEXT, payload TEXT)')
            db.executemany('INSERT INTO snapshots VALUES (?,?)',[('2026-10-22T00:00:00Z','first'),('2026-10-26T00:00:00Z','last')])
        return path
    def test_backup_restores_all_rows_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            self.make_database(directory)
            meta=backup(directory)
            self.assertTrue(meta['restoreVerified']);self.assertEqual(meta['snapshots'],2)
            archive=pathlib.Path(directory)/'backups'/meta['file']
            self.assertEqual(digest(archive),meta['sha256'])
            target=pathlib.Path(directory)/'isolated.sqlite'
            self.assertEqual(restore(archive,target)['snapshots'],2)
            with sqlite3.connect(target) as db:self.assertEqual(db.execute('SELECT payload FROM snapshots ORDER BY received_at').fetchall(),[('first',),('last',)])
            with self.assertRaises(ValueError):restore(archive,target)
            self.assertEqual(backup(directory)['file'],meta['file'])
    def test_online_backup_includes_committed_wal_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path=self.make_database(directory)
            db=sqlite3.connect(path)
            try:
                db.execute('PRAGMA wal_autocheckpoint=0')
                db.execute("INSERT INTO snapshots VALUES ('2026-10-27T00:00:00Z','wal-row')")
                db.commit()
                self.assertTrue(pathlib.Path(str(path)+'-wal').exists())
                meta=backup(directory)
                self.assertEqual(meta['snapshots'],3)
            finally:db.close()

    def test_corrupt_backup_is_not_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            bad=pathlib.Path(directory)/'bad.gz'
            with gzip.open(bad,'wb') as f:f.write(b'not a sqlite database')
            target=pathlib.Path(directory)/'target.sqlite'
            with self.assertRaises(sqlite3.DatabaseError):restore(bad,target)
            self.assertFalse(target.exists())
    def test_missing_source_does_not_fabricate_backup(self):
        with tempfile.TemporaryDirectory() as directory:self.assertIsNone(backup(directory))
    def test_alerts_detect_stale_missing_backup_and_disk_pressure(self):
        now=dt.datetime(2026,10,26,tzinfo=dt.timezone.utc)
        healthy={'collector':{'state':'healthy','lastSuccessAt':now.isoformat()},'diskFreeBytes':200*1024*1024,'backup':{'restoreVerified':True,'createdAt':now.isoformat()}}
        self.assertEqual(issues(healthy,now),[])
        broken={'collector':{'state':'error','lastSuccessAt':'2026-10-20T00:00:00Z'},'diskFreeBytes':1}
        self.assertEqual(len(issues(broken,now)),4)
if __name__=='__main__':unittest.main()
