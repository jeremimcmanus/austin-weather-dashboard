"""Online SQLite backups with integrity verification, gzip checksum, and isolated restore."""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import pathlib
import shutil
import sqlite3
import tempfile


def digest(path):
    checksum = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def verify(path):
    with sqlite3.connect(pathlib.Path(path).resolve().as_uri()+'?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity verification failed')
        rows, first, last = db.execute('SELECT COUNT(*),MIN(received_at),MAX(received_at) FROM snapshots').fetchone()
        return {'snapshots': rows, 'firstReceivedAt': first, 'lastReceivedAt': last}


def backup(directory, force=False):
    directory = pathlib.Path(directory)
    source = directory/'snapshots.sqlite'
    if not source.exists():
        return None
    folder = directory/'backups'
    folder.mkdir(exist_ok=True)
    manifest_path = folder/'latest.json'
    if manifest_path.exists() and not force:
        manifest = json.loads(manifest_path.read_text())
        age = dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(manifest['createdAt'])
        if age.total_seconds() < 86400 and (folder/manifest['file']).exists():
            return manifest
    # The full temporary database plus compressed output needs headroom.
    wal = pathlib.Path(str(source)+'-wal')
    required = (source.stat().st_size+(wal.stat().st_size if wal.exists() else 0))*2+50*1024*1024
    if shutil.disk_usage(directory).free < required:
        raise OSError('Insufficient space for verified backup; expand disk without deleting history')
    created = dt.datetime.now(dt.timezone.utc)
    name = 'snapshots-'+created.strftime('%Y%m%dT%H%M%S%fZ')+'.sqlite.gz'
    target = folder/name
    temporary_gzip = folder/(name+'.tmp')
    try:
        with tempfile.TemporaryDirectory(dir=folder) as temporary:
            copy = pathlib.Path(temporary)/'copy.sqlite'
            with sqlite3.connect(source.resolve().as_uri()+'?mode=ro', uri=True, timeout=30) as origin, sqlite3.connect(copy) as destination:
                origin.backup(destination, pages=256, sleep=.05)
            summary = verify(copy)
            with open(copy, 'rb') as original, gzip.open(temporary_gzip, 'wb', compresslevel=6) as compressed:
                shutil.copyfileobj(original, compressed, length=1024*1024)
            # Restore the exact compressed artifact before calling it verified.
            restored = pathlib.Path(temporary)/'restored.sqlite'
            with gzip.open(temporary_gzip, 'rb') as compressed, open(restored, 'wb') as stream:
                shutil.copyfileobj(compressed, stream, length=1024*1024)
            if digest(copy) != digest(restored) or verify(restored) != summary:
                raise ValueError('Backup restore verification failed')
        temporary_gzip.replace(target)
        manifest = {'createdAt': created.isoformat(), 'file': name, 'sha256': digest(target), 'bytes': target.stat().st_size, 'restoreVerified': True, **summary}
        temp = folder/'latest.json.tmp'
        temp.write_text(json.dumps(manifest)+'\n')
        temp.replace(manifest_path)
        # Retain three generated backups. Never delete source snapshots or arbitrary files.
        for old in sorted(folder.glob('snapshots-*.sqlite.gz'), reverse=True)[3:]:
            old.unlink()
        return manifest
    finally:
        temporary_gzip.unlink(missing_ok=True)


def restore(archive, destination):
    target = pathlib.Path(destination)
    if target.exists():
        raise ValueError('Restore destination already exists; refusing overwrite')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as directory:
        temp = pathlib.Path(directory)/'restore.sqlite'
        with gzip.open(archive, 'rb') as source, open(temp, 'wb') as stream:
            shutil.copyfileobj(source, stream, length=1024*1024)
        summary = verify(temp)
        # Hard-link creation refuses a concurrently created destination as well.
        os.link(temp, target)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default=os.environ.get('DATA_DIR', 'data'))
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--restore')
    parser.add_argument('--destination')
    args = parser.parse_args()
    if args.restore:
        if not args.destination:
            parser.error('--destination is required with --restore')
        print(json.dumps(restore(args.restore, args.destination)))
    else:
        print(json.dumps(backup(args.data_dir, args.force)))
