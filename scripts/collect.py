"""Append immutable public-source snapshots to SQLite. Python standard library + curl."""
import argparse
import datetime as dt
import json
import pathlib
import re
import sqlite3
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

class SourceFetchError(Exception):
    def __init__(self, curl_code, http_status):
        self.safe_code = f'curl={curl_code};http={http_status}'
        super().__init__(self.safe_code)

def fetch(url):
    # A file lets curl truncate failed bodies before a retry; stdout holds only status.
    with tempfile.TemporaryDirectory() as directory:
        output = pathlib.Path(directory)/'response.json'
        result = subprocess.run(['curl', '--fail-with-body', '--silent', '--show-error', '--max-time', '25', '--retry', '2', '--retry-max-time', '30', '--retry-delay', '1', '--write-out', '%{http_code}', '--output', str(output), '--max-filesize', '5000000', '-H', 'User-Agent: AustinWeatherDashboard/1.0', url], capture_output=True, text=True)
        status = result.stdout.strip()
        if result.returncode:
            raise SourceFetchError(result.returncode, status if status.isdigit() else 'unknown')
        return json.loads(output.read_text())

def collect(path, get=fetch):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")
    db.execute('CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, run_at TEXT NOT NULL, received_at TEXT NOT NULL, source TEXT NOT NULL, url TEXT NOT NULL, payload TEXT, error TEXT)')
    run = dt.datetime.now(dt.timezone.utc).isoformat()
    failures = []
    def capture(source, url):
        data = None
        error = None
        try:
            data = get(url)
        except Exception as exc:
            # Store only safe numeric diagnostics; never proxy details or raw response text.
            error = type(exc).__name__+(':'+exc.safe_code if isinstance(exc, SourceFetchError) else '')
            failures.append(source)
        db.execute('INSERT INTO snapshots(run_at,received_at,source,url,payload,error) VALUES(?,?,?,?,?,?)', (run, dt.datetime.now(dt.timezone.utc).isoformat(), source, url, json.dumps(data) if data is not None else None, error))
        db.commit()
        return data
    try:
        point = capture('nws.point', 'https://api.weather.gov/points/30.1831,-97.6799')
        hourly = (point or {}).get('properties', {}).get('forecastHourly', '')
        if hourly.startswith('https://api.weather.gov/'):
            capture('nws.hourly', hourly)
        capture('nws.observation', 'https://api.weather.gov/stations/KAUS/observations/latest')
        # Official climate reports are retained as evidence; parsing and contract verification remain a manual gate.
        reports = capture('nws.cli.index', 'https://api.weather.gov/products/types/CLI/locations/AUS')
        for report in (reports or {}).get('@graph', [])[:2]:
            identifier = report.get('id', '')
            if re.fullmatch(r'[a-fA-F0-9-]+', identifier):
                capture('nws.cli.report', 'https://api.weather.gov/products/' + identifier)
        capture('kalshi.series', 'https://api.elections.kalshi.com/trade-api/v2/series/KXHIGHAUS')
        cursor = ''
        for page in range(10):
            from urllib.parse import quote
            url = 'https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHAUS&status=open&limit=100' + ('&cursor='+quote(cursor, safe='') if cursor else '')
            response = capture('kalshi.markets', url)
            for market in (response or {}).get('markets', []):
                ticker = market.get('ticker', '')
                if re.fullmatch(r'KXHIGHAUS-[A-Za-z0-9.-]+', ticker):
                    capture('kalshi.orderbook', 'https://api.elections.kalshi.com/trade-api/v2/markets/' + ticker + '/orderbook?depth=100')
            cursor = (response or {}).get('cursor')
            if not cursor:
                break
        else:
            failures.append('kalshi.pagination_limit')
        # Revisit recently closed events to archive exchange results and later revisions.
        today = dt.datetime.now(ZoneInfo('America/Chicago')).date()
        for offset in range(1, 8):
            day = today-dt.timedelta(days=offset)
            months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
            event = f'KXHIGHAUS-{day.year % 100:02d}{months[day.month-1]}{day.day:02d}'
            capture('kalshi.recent_event', 'https://api.elections.kalshi.com/trade-api/v2/markets?event_ticker='+event+'&limit=100')
    finally:
        db.close()
    return failures

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='data/snapshots.sqlite')
    args = parser.parse_args()
    errors = collect(args.db)
    print(json.dumps({'database': args.db, 'failed_sources': errors}))
    sys.exit(1 if errors else 0)
