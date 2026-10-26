"""Archive official documents with TLS verification and source receipts; acquisition is not review."""
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import tempfile
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = {
 'terms': 'https://assets.kalshi.com/contract_terms/GLOBALTEMPERATURE.pdf',
 'fees': 'https://kalshi.com/docs/kalshi-fee-schedule.pdf',
 'settlement': 'https://weather.com/kalshi',
 'station': 'https://weather.com/kalshi/api/climate/primary?date=2026-10-25',
 'feeRounding': 'https://docs.kalshi.com/getting_started/fee_rounding.md',
 'fixedPoint': 'https://docs.kalshi.com/getting_started/fixed_point_migration.md'
}

def acquire(folder):
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for name, url in SOURCES.items():
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary)/'body'
            result = subprocess.run(['curl','--silent','--show-error','--location','--proto','=https','--proto-redir','=https','--max-time','25','--max-filesize','10000000','--output',str(output),'--write-out','%{http_code}\n%{url_effective}',url],capture_output=True,text=True)
            status, _, effective = result.stdout.partition('\n')
            record = {'url':url,'retrievedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'httpStatus':status,'curlExit':result.returncode,'reviewed':False}
            permitted = urlparse(effective).hostname in {'kalshi.com','www.kalshi.com','assets.kalshi.com','weather.com','www.weather.com','docs.kalshi.com'}
            body = output.read_bytes() if output.exists() else b''
            pdf = name in ('terms','fees')
            station_ok=True
            if name=='station':
                try:station_ok=any(item.get('station',{}).get('icao')=='KAUS' and item.get('station',{}).get('cliId')=='AUS' for item in json.loads(body).get('results',[]))
                except (ValueError,AttributeError):station_ok=False
            if not result.returncode and status == '200' and permitted and body and station_ok and (not pdf or body.startswith(b'%PDF')):
                filename=name+('.pdf' if pdf else '.json' if name=='station' else '.md' if name in ('feeRounding','fixedPoint') else '.html')
                (folder/filename).write_bytes(body)
                record.update(file=filename,sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),status='acquired_not_reviewed')
            else:
                record['status']='unavailable_or_invalid'
            receipts[name]=record
    (folder/'receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
    return receipts

if __name__=='__main__':
    print(json.dumps(acquire(ROOT/'evidence'/'official'),indent=2))
