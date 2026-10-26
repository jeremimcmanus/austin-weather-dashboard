"""Supervise HTTP and timer-driven collection; persistent DATA_DIR is required in hosting."""
import datetime as dt
import json
import os
import pathlib
import signal
import subprocess
import sys
import threading
import time
from collect import collect
from backup import backup
from research import run as research_run

ROOT = pathlib.Path(__file__).resolve().parent.parent

def write_status(path, state):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state)+'\n')
    temporary.replace(path)

def main():
    directory = pathlib.Path(os.environ.get('DATA_DIR', str(ROOT/'data')))
    directory.mkdir(parents=True, exist_ok=True)
    interval = max(60, int(os.environ.get('COLLECTION_INTERVAL_SECONDS', '900')))
    stop = threading.Event()
    status_path = directory/'collector-status.json'
    state = {'startedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'intervalSeconds': interval, 'lastSuccessAt': None, 'state': 'starting'}
    if status_path.exists():
        try:
            state['lastSuccessAt'] = json.loads(status_path.read_text()).get('lastSuccessAt')
        except (ValueError, OSError):
            pass
    write_status(status_path, state)
    def worker():
        while not stop.is_set():
            began = time.monotonic()
            state.update(state='collecting', lastAttemptAt=dt.datetime.now(dt.timezone.utc).isoformat())
            try:
                write_status(status_path, state)
                # Before collection writes: back up existing history on startup, then daily.
                try:
                    state['backup'] = backup(directory)
                    state.pop('backupError', None)
                except Exception as exc:
                    state['backupError'] = type(exc).__name__
                failures = collect(str(directory/'snapshots.sqlite'))
                if state.get('backup') is None:
                    try:
                        state['backup'] = backup(directory)
                        state.pop('backupError', None)
                    except Exception as exc:
                        state['backupError'] = type(exc).__name__
                try:
                    state['research'] = research_run(directory)
                    state.pop('researchError', None)
                except Exception as exc:
                    state['researchError'] = type(exc).__name__
                ended = dt.datetime.now(dt.timezone.utc).isoformat()
                state.update(state='degraded' if failures else 'healthy', failedSources=failures, lastFinishedAt=ended)
                if not failures:
                    state['lastSuccessAt'] = ended
                state.pop('errorType', None)
            except Exception as exc:
                state.update(state='error', errorType=type(exc).__name__)
            try:
                write_status(status_path, state)
            except OSError:
                print('Collector status write failed', file=sys.stderr, flush=True)
            stop.wait(max(1, interval-(time.monotonic()-began)))
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    server = subprocess.Popen(['node', 'server.js'], cwd=ROOT)
    def shutdown(*_):
        stop.set()
        server.terminate()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        code = server.wait()
    finally:
        stop.set()
        thread.join(timeout=30)
    return code

if __name__ == '__main__':
    sys.exit(main())
