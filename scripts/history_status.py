"""Read-only bounded status for the public dashboard. No credentials or raw environment."""
import datetime as dt
import json
import os
import pathlib
import sqlite3
import shutil

def history_status(directory):
    directory = pathlib.Path(directory)
    status = {'collector': None, 'snapshots': 0, 'errors': 0, 'runs': 0, 'firstReceivedAt': None, 'lastReceivedAt': None, 'observationHistory': []}
    if directory.exists():
        usage = shutil.disk_usage(directory)
        status['diskFreeBytes'] = usage.free
        status['diskTotalBytes'] = usage.total
    path = directory/'collector-status.json'
    if path.exists():
        try:
            status['collector'] = json.loads(path.read_text())
        except (ValueError, OSError):
            status['collector'] = {'state': 'unreadable'}
    manifest = directory/'backups'/'latest.json'
    status['backup'] = None
    if manifest.exists():
        try:
            status['backup'] = json.loads(manifest.read_text())
        except (ValueError, OSError):
            status['backupError'] = 'unreadable'
    path = directory/'snapshots.sqlite'
    if not path.exists():
        return status
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=10) as db:
        count, errors, runs, first, last = db.execute('SELECT COUNT(*), COALESCE(SUM(error IS NOT NULL),0), COUNT(DISTINCT run_at), MIN(received_at), MAX(received_at) FROM snapshots').fetchone()
        status.update(snapshots=count, errors=errors, runs=runs, firstReceivedAt=first, lastReceivedAt=last, bytes=sum(p.stat().st_size for p in (path,pathlib.Path(str(path)+'-wal'),pathlib.Path(str(path)+'-shm')) if p.exists()))
        status['errorSummary'] = [dict(zip(('source','error','count','firstAt','lastAt'), row)) for row in db.execute('SELECT source,error,COUNT(*),MIN(received_at),MAX(received_at) FROM snapshots WHERE error IS NOT NULL GROUP BY source,error ORDER BY COUNT(*) DESC').fetchall()]
        status['recentErrors'] = [dict(zip(('source','error','receivedAt'), row)) for row in db.execute('SELECT source,error,received_at FROM snapshots WHERE error IS NOT NULL ORDER BY id DESC LIMIT 10').fetchall()]
        rows = db.execute("SELECT received_at,payload FROM snapshots WHERE source='nws.observation' AND error IS NULL ORDER BY id DESC LIMIT 72").fetchall()
        seen = set()
        for received, payload in reversed(rows):
            try:
                observation = json.loads(payload)['properties']
                stamp = observation['timestamp']
                c = observation['temperature']['value']
                if stamp not in seen and isinstance(c, (float,int)):
                    status['observationHistory'].append({'observedAt': stamp, 'receivedAt': received, 'temperatureF': round(c*9/5+32,1)})
                    seen.add(stamp)
            except (ValueError, KeyError, TypeError):
                continue
    return status

if __name__ == '__main__':
    print(json.dumps(history_status(os.environ.get('DATA_DIR', str(pathlib.Path(__file__).resolve().parent.parent/'data')))))
