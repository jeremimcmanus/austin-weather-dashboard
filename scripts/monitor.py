"""External collector checks and checksum-verified off-site backup download."""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
from collect import fetch

BASE = 'https://austin-weather-dashboard.onrender.com'

def issues(status, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    found = []
    collector = status.get('collector') or {}
    def age(value):
        try:
            return (now-dt.datetime.fromisoformat(value.replace('Z','+00:00'))).total_seconds()
        except (ValueError, TypeError, AttributeError):
            return float('inf')
    if collector.get('state') not in ('healthy','collecting'):
        found.append('Collector is not healthy or collecting')
    if not 0 <= age(collector.get('lastSuccessAt')) <= 2700:
        found.append('No successful full collection in the last 45 minutes (or timestamp invalid)')
    if status.get('diskFreeBytes', 0) < 100*1024*1024:
        found.append('Less than 100 MB free; expand storage without deleting history')
    backup = status.get('backup') or {}
    if not backup.get('restoreVerified') or not 0 <= age(backup.get('createdAt')) <= 129600:
        found.append('A restore-verified backup from the last 36 hours is missing')
    if collector.get('backupError'):
        found.append('Collector reports backup failure')
    return found

def download(directory, get=fetch):
    folder = pathlib.Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    for attempt in range(2):
        metadata = get(BASE+'/api/history').get('backup') or {}
        if not metadata.get('restoreVerified'):
            raise ValueError('No verified backup exists')
        size = metadata.get('bytes')
        if not isinstance(size,int) or not 0 < size <= 10*1024*1024:
            raise ValueError('Off-site archive exceeds the configured 10 MB limit; review storage budget')
        target = folder/'snapshots.sqlite.gz.partial'
        subprocess.run(['curl','--fail','--silent','--show-error','--max-time','120','--max-filesize',str(10*1024*1024),'--output',str(target),BASE+'/api/backup/latest'],check=True)
        checksum = hashlib.sha256(target.read_bytes()).hexdigest()
        if checksum == metadata.get('sha256') and target.stat().st_size == size:
            target.replace(folder/'snapshots.sqlite.gz')
            (folder/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
            return metadata
        target.unlink(missing_ok=True)
    raise ValueError('Downloaded checksum differs from backup metadata; no archive retained')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-dir')
    args = parser.parse_args()
    status = fetch(BASE+'/api/history')
    problems = issues(status)
    if args.backup_dir:
        metadata = download(args.backup_dir)
        print(json.dumps({'offsiteBackup':metadata}))
        raise SystemExit(0)
    for problem in problems:
        print('::error::'+problem)
    if problems:
        raise SystemExit(1)
    print('Collector and backup checks passed')
