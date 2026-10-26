"""Immutable prospective forecasts, frozen experiments, and event-clustered holdout evaluation.
The initial Gaussian prior is an engineering baseline, not an empirically calibrated model.
"""
import argparse
import datetime as dt
import json
import math
import pathlib
import random
import re
import sqlite3
from zoneinfo import ZoneInfo
from collect import fetch
from trading_validation import canonical_hash, rule_hash, audit_contract, audit_fees, quote, stamp, policy, ROOT, UTC


def event_day(ticker):
    match=re.fullmatch(r'KXHIGHAUS-(\d{2})([A-Z]{3})(\d{2})',ticker or '')
    if not match:return None
    months=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
    try:return dt.date(2000+int(match[1]),months.index(match[2])+1,int(match[3]))
    except ValueError:return None


def definition_hash(market):
    return canonical_hash({k:market.get(k) for k in ('ticker','event_ticker','strike_type','floor_strike','cap_strike','rules_primary','rules_secondary')})


def bounds(market):
    kind=market.get('strike_type')
    if kind=='between':return float(market['floor_strike']),float(market['cap_strike'])
    if kind=='greater':return float(market['floor_strike']),math.inf
    if kind=='less':return -math.inf,float(market['cap_strike'])
    raise ValueError('Unsupported or custom temperature strike')


def matches(value,lower,upper):
    return (value>lower if upper==math.inf else value>=lower) and (value<upper if lower==-math.inf else value<=upper)


def probability(center,sigma,lower,upper,quantum=1):
    # A PMF on the SOURCE'S reported values. Never round a settlement value.
    if not math.isfinite(center) or not math.isfinite(sigma) or sigma<=0 or lower>upper or quantum<=0:raise ValueError('Invalid distribution')
    first=math.floor((center-12*sigma)/quantum);last=math.ceil((center+12*sigma)/quantum)
    if last-first>100000:raise ValueError('Unsupported distribution resolution or dispersion')
    total=inside=0.0
    for index in range(first,last+1):
        value=round(index*quantum,6);weight=math.exp(-.5*((value-center)/sigma)**2)
        total+=weight
        if matches(value,lower,upper):inside+=weight
    return max(0,min(1,inside/total))


def forecast_probabilities(peak,parameters,market,spec):
    lower,upper=bounds(market);center=peak+parameters['biasF'];sigma=parameters['sigmaF']
    base=probability(center,sigma,lower,upper,spec['sourceValueQuantumF'])
    stresses=[probability(center+delta,sigma*scale,lower,upper,quantum) for delta in spec['temperatureStressF'] for scale in spec['sigmaMultipliers'] for quantum in spec['sourceQuantumStressF']]
    return base,max(0,min(stresses)-spec['calibrationMarginProbability']),min(1,max(stresses)+spec['calibrationMarginProbability'])


def forecast_peak(payload,day,spec):
    zone=ZoneInfo(spec['assumedTimezone'])
    start=dt.datetime.combine(day,dt.time(),zone).astimezone(UTC)
    end=dt.datetime.combine(day+dt.timedelta(days=1),dt.time(),zone).astimezone(UTC)
    properties=payload['properties'];issued=properties.get('updateTime') or properties.get('updated') or properties.get('generatedAt')
    issued=stamp(issued)
    coverage={}
    for period in properties.get('periods',[]):
        a,b=stamp(period['startTime']),stamp(period['endTime'])
        if start<=a<end and b-a==dt.timedelta(hours=1):
            value=period.get('temperature');unit=period.get('temperatureUnit')
            if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or unit not in ('F','C'):continue
            fahrenheit=value if unit=='F' else value*9/5+32
            if -150<=fahrenheit<=200:coverage[a]=fahrenheit
    required=[start+dt.timedelta(hours=i) for i in range(int((end-start).total_seconds()/3600))]
    if not required or any(hour not in coverage for hour in required):raise ValueError('Forecast does not cover the complete assumed event window')
    return max(coverage[hour] for hour in required),issued,start,end


def schema(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS research_experiments (id TEXT PRIMARY KEY, frozen_at TEXT NOT NULL, first_target_day TEXT NOT NULL, spec TEXT NOT NULL, parameters TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS probability_forecasts (id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, ticker TEXT NOT NULL, event_day TEXT NOT NULL, issued_at TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(experiment_id,ticker,event_day));
    CREATE TABLE IF NOT EXISTS research_execution (prediction_id TEXT PRIMARY KEY, received_at TEXT NOT NULL, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS validation_reports (experiment_id TEXT PRIMARY KEY, evaluated_at TEXT NOT NULL, payload TEXT NOT NULL);
    ''')
    db.commit()


def partition(markets):
    # Exhaustive under the declared integer SOURCE support assumption only.
    intervals=[bounds(m) for m in markets]
    return bool(intervals and all(sum(matches(value,lo,hi) for lo,hi in intervals)==1 for value in range(-200,201)))


def approved_assumptions(config,spec):
    s=config['settlement']
    return s.get('stationMapping',{}).get('value')=={'forecastStation':spec['forecastStation'],'settlementStation':spec['assumedSettlementStation']} and s.get('measurementWindow',{}).get('value')=={'timezone':spec['assumedTimezone'],'window':spec['assumedWindow']} and s.get('rounding',{}).get('value')==spec['assumedRounding']


def issue_forecasts(db,spec,parameters,now,config,get=None):
    schema(db)
    parameters=dict(parameters)
    settlement=config['settlement'];fees=config['fees']
    semantic_policy={'documents':config['documents'],'settlement':{key:(settlement[key].get('value') if isinstance(settlement.get(key),dict) and 'value' in settlement[key] else settlement.get(key)) for key in ('source','stationMapping','measurementWindow','rounding','revisions','ruleTemplate')},'fees':{key:fees.get(key) for key in ('series','feeType','multiplier','takerCoefficient','rounding','accountType','minimumFillQuantity','tradeFeePrecisionDollars')},'risk':config['risk']}
    frozen_spec={**spec,'minimumEdgeCents':config['risk']['minimumEdgeCents'],'extraExecutionCents':config['risk']['extraExecutionCents'],'maxExecutionQuoteAgeSeconds':config['risk']['maxBookAgeSeconds'],'validationPolicyHash':canonical_hash(semantic_policy),'implementationHash':canonical_hash({'research':(ROOT/'scripts'/'research.py').read_text(),'validation':(ROOT/'scripts'/'trading_validation.py').read_text()})}
    experiment_id=canonical_hash({'spec':frozen_spec,'parameters':parameters})
    zone=ZoneInfo(spec['assumedTimezone']);tomorrow=now.astimezone(zone).date()+dt.timedelta(days=1)
    db.execute('INSERT OR IGNORE INTO research_experiments VALUES(?,?,?,?,?)',(experiment_id,now.isoformat(),'',json.dumps(frozen_spec),json.dumps(parameters)));db.commit()
    experiment=db.execute('SELECT frozen_at,first_target_day FROM research_experiments WHERE id=?',(experiment_id,)).fetchone()
    latest={}
    for source in ('kalshi.markets','nws.hourly','kalshi.series'):
        row=db.execute('SELECT id,received_at,payload FROM snapshots WHERE source=? AND error IS NULL AND received_at<=? ORDER BY id DESC LIMIT 1',(source,now.isoformat())).fetchone()
        if not row:return {'experimentId':experiment_id,'issued':0,'reason':'Missing '+source}
        latest[source]=(row[0],stamp(row[1]),json.loads(row[2]))
    if any((now-row[1]).total_seconds()>7200 for row in latest.values()):return {'experimentId':experiment_id,'issued':0,'reason':'Archived source receipt stale'}
    groups={}
    for m in latest['kalshi.markets'][2].get('markets',[]):
        day=event_day(m.get('event_ticker'))
        if day and day>=tomorrow and (not experiment[1] or day>=dt.date.fromisoformat(experiment[1])) and m.get('status') in ('active','open'):groups.setdefault(day,[]).append(m)
    inserted=[];notes=[]
    for day,markets in sorted(groups.items()):
        if not partition(markets):notes.append(day.isoformat()+': strikes do not form a complete partition under the stated research rounding assumption');continue
        try:peak,issued,start,end=forecast_peak(latest['nws.hourly'][2],day,spec)
        except (ValueError,KeyError,TypeError):notes.append(day.isoformat()+': incomplete forecast or invalid timestamps');continue
        if not issued<=latest['nws.hourly'][1]<=now or not 0<=(now-issued).total_seconds()<=spec['maxForecastAgeMinutes']*60:notes.append(day.isoformat()+': stale or future forecast issue time');continue
        if (start-now).total_seconds()<spec['minimumLeadHours']*3600:continue
        if not experiment[1]:
            db.execute("UPDATE research_experiments SET first_target_day=? WHERE id=? AND first_target_day=''",(day.isoformat(),experiment_id))
            experiment=(experiment[0],day.isoformat())
        series=latest['kalshi.series'][2].get('series',{})
        for market in sorted(markets,key=lambda m:m['ticker']):
            base,scenario_low,scenario_high=forecast_probabilities(peak,parameters,market,spec)
            audit=audit_contract(market,series,config,now)
            evidence_ok=audit['verified'] and approved_assumptions(config,spec)
            previous=db.execute('SELECT payload FROM validation_reports WHERE experiment_id=?',(experiment_id,)).fetchone()
            previous=json.loads(previous[0]) if previous else {}
            previously_validated=bool(previous.get('calibrationVerified') and now<stamp(previous['validationExpiresAt']))
            record={'ticker':market['ticker'],'eventDay':day.isoformat(),'experimentId':experiment_id,'issuedAt':now.isoformat(),'forecastReceivedAt':latest['nws.hourly'][1].isoformat(),'forecastIssuedAt':issued.isoformat(),'forecastSnapshotId':latest['nws.hourly'][0],'forecastSnapshotHash':canonical_hash(latest['nws.hourly'][2]),'marketSnapshotId':latest['kalshi.markets'][0],'eventTickers':sorted(m['ticker'] for m in markets),'ruleHash':rule_hash(market),'definitionHash':definition_hash(market),'assumedWindowStart':start.isoformat(),'assumedWindowEnd':end.isoformat(),'forecastPeakF':peak,'forecastStation':spec['forecastStation'],'settlementStation':spec['assumedSettlementStation'],'probabilityYes':base,'lowerYes':scenario_low,'upperYes':scenario_high,'contractVerifiedAtIssue':evidence_ok,'calibrationVerified':previously_validated,'fittedTrainingDays':parameters.get('trainingDays',0),'status':'VALIDATED_RESEARCH_REQUIRES_REVIEW' if previously_validated else 'UNCALIBRATED_RESEARCH','boundsAre':'scenario envelope, not a confidence interval','assumptions':{'rounding':spec['assumedRounding'],'window':spec['assumedWindow'],'timezone':spec['assumedTimezone'],'sourceQuantumF':spec['sourceValueQuantumF'],'quantumIsAssumption':True}}
            identifier=canonical_hash({'experiment':experiment_id,'ticker':market['ticker'],'day':day.isoformat()})
            changed=db.execute('INSERT OR IGNORE INTO probability_forecasts VALUES(?,?,?,?,?,?)',(identifier,experiment_id,market['ticker'],day.isoformat(),now.isoformat(),json.dumps(record))).rowcount
            if changed:inserted.append((identifier,record,market,series))
    db.commit()
    # Capture quotes only AFTER immutable predictions have been recorded; never backdate fills.
    if get:
        contexts={}
        for identifier,record,market,series in inserted:
            try:
                event=market['event_ticker']
                if event not in contexts:
                    series_changes=get('https://api.elections.kalshi.com/trade-api/v2/series/fee_changes?series_ticker=KXHIGHAUS&show_historical=true')
                    context_at=dt.datetime.now(UTC).isoformat()
                    event_changes=get('https://api.elections.kalshi.com/trade-api/v2/events/fee_changes?event_ticker='+event+'&limit=100')
                    contexts[event]={'eventTicker':event,'receivedAt':context_at,'seriesChanges':series_changes,'eventChanges':event_changes}
                book=get('https://api.elections.kalshi.com/trade-api/v2/markets/'+market['ticker']+'/orderbook?depth=100')
                received=dt.datetime.now(UTC)
                snapshot={'book':book,'market':market,'series':series,'bookReceivedAt':received.isoformat(),'receivedAfterPrediction':received>=stamp(record['issuedAt']),'feeContext':contexts[event],'feeAudit':audit_fees(series,config,received,fee_context=contexts[event],event_ticker=event),'risk':config['risk']}
                if (received-stamp(record['issuedAt'])).total_seconds()>config['risk']['maxBookAgeSeconds']:snapshot['executionError']='Quote arrived more than 60 seconds after prediction'
            except Exception as exc:
                received=dt.datetime.now(UTC);snapshot={'executionError':type(exc).__name__}
            db.execute('INSERT OR IGNORE INTO research_execution VALUES(?,?,?)',(identifier,received.isoformat(),json.dumps(snapshot)));db.commit()
    return {'experimentId':experiment_id,'issued':len(inserted),'notes':notes}


def outcomes(db):
    from decimal import Decimal
    history={};payouts={};latest={}
    for _,received,text in db.execute("SELECT id,received_at,payload FROM snapshots WHERE source='kalshi.recent_event' AND error IS NULL ORDER BY id"):
        for market in json.loads(text).get('markets',[]):
            key=market.get('ticker')
            if not key:continue
            latest[key]=(received,market)
            if market.get('status')=='finalized' and market.get('result') in ('yes','no'):
                history.setdefault(key,set()).add(market['result'])
                try:payouts.setdefault(key,set()).add(str(Decimal(str(market['settlement_value_dollars'])).normalize()))
                except (KeyError,ValueError,ArithmeticError):payouts.setdefault(key,set()).add('unknown')
    values={}
    for key,(received,market) in latest.items():
        if market.get('status')!='finalized' or market.get('result') not in ('yes','no') or len(payouts.get(key,set()))!=1:continue
        try:
            if Decimal(str(market['settlement_value_dollars']))!=int(market['result']=='yes'):continue
        except (KeyError,ValueError,ArithmeticError):continue
        values[key]={'seen':history.get(key,set()),'market':market,'received':received}
    return values


def official_days(db):
    days={};latest={}
    for received,text in db.execute("SELECT received_at,payload FROM snapshots WHERE source='twc.daily' AND error IS NULL ORDER BY id"):
        payload=json.loads(text);day=payload.get('date')
        if not isinstance(day,str):continue
        latest[day]=None
        for item in payload.get('results',[]):
            station=item.get('station') or {};data=item.get('data') or {};value=data.get('maxTemp')
            if station.get('icao')!='KAUS' or station.get('cliId')!='AUS' or not data.get('isOfficial') or item.get('status') not in ('official','revised') or not isinstance(value,(float,int)) or isinstance(value,bool) or not math.isfinite(value) or not -150<=value<=200 or data.get('reportDate')!=day:continue
            entry=days.setdefault(day,{'seen':set()});entry['seen'].add(value)
            entry.update(value=value,received=received,status=item['status']);latest[day]=entry
    return {day:value for day,value in latest.items() if value is not None}


def percentile(values,p):
    ordered=sorted(values);return ordered[min(len(ordered)-1,int((len(ordered)-1)*p))]


def evaluate_holdout(db,experiment_id,now=None):
    now=now or dt.datetime.now(UTC)
    row=db.execute('SELECT frozen_at,first_target_day,spec,parameters FROM research_experiments WHERE id=?',(experiment_id,)).fetchone()
    if not row:raise ValueError('Unknown frozen experiment')
    frozen,first,spec,parameters=row[0],row[1],json.loads(row[2]),json.loads(row[3]);labels=outcomes(db);source_days=official_days(db)
    if not first:return {'experimentId':experiment_id,'frozenAt':frozen,'firstTargetDay':None,'lastTargetDay':None,'trainingDays':parameters.get('trainingDays',0),'requiredTrainingDays':spec['minimumTrainingDays'],'requiredHoldoutDays':spec['holdoutDays'],'completeEventDays':0,'calibrationVerified':False,'status':'WAITING_FIRST_ELIGIBLE_EVENT','scores':None,'blockers':['Frozen model is waiting for its first eligible future event; no holdout dates or scores are invented']}
    end=dt.date.fromisoformat(first)+dt.timedelta(days=spec['holdoutDays'])
    report={'experimentId':experiment_id,'frozenAt':frozen,'firstTargetDay':first,'lastTargetDay':(end-dt.timedelta(days=1)).isoformat(),'trainingDays':parameters.get('trainingDays',0),'requiredTrainingDays':spec['minimumTrainingDays'],'requiredHoldoutDays':spec['holdoutDays'],'completeEventDays':0,'calibrationVerified':False,'status':'HOLDOUT_LOCKED','scores':None,'blockers':[],'outcomeExceptions':[]}
    implementation=canonical_hash({'research':(ROOT/'scripts'/'research.py').read_text(),'validation':(ROOT/'scripts'/'trading_validation.py').read_text()})
    if spec.get('implementationHash')!=implementation:
        report.update(status='SUPERSEDED_IMPLEMENTATION',blockers=['Implementation changed; use a new frozen future experiment'])
        return report
    groups={}
    for identifier,day,text in db.execute('SELECT id,event_day,payload FROM probability_forecasts WHERE experiment_id=? ORDER BY event_day,ticker',(experiment_id,)):
        if first<=day<end.isoformat():groups.setdefault(day,[]).append((identifier,json.loads(text)))
    daily=[];verified=True;execution_ok=True
    for day,records in sorted(groups.items()):
        expected=records[0][1].get('eventTickers') if records else None
        if not expected or sorted(r['ticker'] for _,r in records)!=expected or any(r.get('eventTickers')!=expected for _,r in records):continue
        if len({r.get('forecastSnapshotId') for _,r in records})!=1 or len({r['issuedAt'] for _,r in records})!=1:continue
        try:
            raw=db.execute("SELECT received_at,payload FROM snapshots WHERE id=? AND source='nws.hourly' AND error IS NULL",(records[0][1]['forecastSnapshotId'],)).fetchone()
            if not raw:raise ValueError('Missing raw forecast')
            peak,forecast_issued,start,finish=forecast_peak(json.loads(raw[1]),dt.date.fromisoformat(day),spec)
            for _,r in records:
                issued_at=stamp(r['issuedAt'])
                if not stamp(frozen)<=issued_at<start or not forecast_issued<=stamp(raw[0])<=issued_at or (issued_at-forecast_issued).total_seconds()>spec['maxForecastAgeMinutes']*60:raise ValueError('Look-ahead or stale input')
                if r.get('forecastSnapshotHash')!=canonical_hash(json.loads(raw[1])) or stamp(r['forecastReceivedAt'])!=stamp(raw[0]) or stamp(r['forecastIssuedAt'])!=forecast_issued or stamp(r['assumedWindowStart'])!=start or stamp(r['assumedWindowEnd'])!=finish or r['forecastPeakF']!=peak:raise ValueError('Source provenance mismatch')
                market=labels.get(r['ticker'],{}).get('market')
                if market:
                    expected=forecast_probabilities(peak,parameters,market,spec)
                    if any(not math.isfinite(r[key]) or abs(r[key]-value)>1e-12 for key,value in zip(('probabilityYes','lowerYes','upperYes'),expected)):raise ValueError('Frozen model probability mismatch')
        except (KeyError,TypeError,ValueError):
            report['outcomeExceptions'].append({'day':day,'reason':'Forecast provenance, timing, or frozen-model computation does not verify'});continue
        source=source_days.get(day)
        if not source or len(source['seen'])!=1:
            report['outcomeExceptions'].append({'day':day,'reason':'Official source absent, withdrawn, or revised inconsistently'});continue
        if any(r['ticker'] not in labels for _,r in records):continue
        results=[labels[r['ticker']] for _,r in records]
        if len(records)<2 or sum(x['market']['result']=='yes' for x in results)!=1 or any(len(x['seen'])!=1 for x in results):continue
        if any(stamp(x['received'])<=stamp(r['issuedAt']) or definition_hash(x['market'])!=r['definitionHash'] for (_,r),x in zip(records,results)):continue
        if any(now<stamp(r['assumedWindowEnd']) for _,r in records):continue
        if any(matches(source['value'],*bounds(item['market']))!=(item['market']['result']=='yes') for item in results):continue
        if abs(source['value']/spec['sourceValueQuantumF']-round(source['value']/spec['sourceValueQuantumF']))>1e-8:
            report['outcomeExceptions'].append({'day':day,'reason':'Official precision falls outside the frozen model support; value was not rounded'});continue
        model_losses=[];market_losses=[];calibration=[];candidates=[]
        for (identifier,r),label in zip(records,results):
            y=int(label['market']['result']=='yes');p=r['probabilityYes'];model_losses.append((p-y)**2);calibration.append((p,y))
            verified=verified and r['contractVerifiedAtIssue']
            execution=db.execute('SELECT payload FROM research_execution WHERE prediction_id=?',(identifier,)).fetchone()
            if not execution:execution_ok=False;continue
            execution=json.loads(execution[0])
            if execution.get('executionError') or not execution.get('receivedAfterPrediction'):execution_ok=False;continue
            try:
                from trading_validation import asks, fill, fee_cents, on_grid
                book=execution['book'];yes=asks(book,'YES');no=asks(book,'NO')
                if not yes or not no or yes[0][0]+no[0][0]<1:raise ValueError('Invalid two-sided book')
                mid=(float(yes[0][0])+1-float(no[0][0]))/2;market_losses.append((mid-y)**2)
                if not execution['feeAudit']['verified']:execution_ok=False;continue
                for side in ('YES','NO'):
                    levels,remaining=fill(book,side,1)
                    if remaining:continue
                    if any(not on_grid(price,execution['market'].get('price_ranges',[])) for price,_ in levels):raise ValueError('Off-grid stored quote')
                    from decimal import Decimal
                    cost=float(sum((p*q*100 for p,q in levels),Decimal(0))+fee_cents(levels,execution['feeAudit']['policy']))+spec['extraExecutionCents']
                    lower=r['lowerYes'] if side=='YES' else 1-r['upperYes']
                    edge=lower*100-cost
                    if edge>spec['minimumEdgeCents']:candidates.append((edge,r['ticker'],side,(y if side=='YES' else 1-y)*100-cost))
            except (KeyError,ValueError,TypeError,ArithmeticError):execution_ok=False
        profit=sorted(candidates,key=lambda x:(-x[0],x[1],x[2]))[0][3] if candidates else 0
        daily.append({'day':day,'model':sum(model_losses)/len(model_losses),'market':sum(market_losses)/len(market_losses) if len(market_losses)==len(model_losses) else None,'profit':profit,'calibration':calibration})
    report['completeEventDays']=len(daily)
    if now.date()<end or len(daily)<spec['holdoutDays']:
        if now.date()>=end:report['status']='WAITING_FOR_COMPLETE_VERIFIED_OUTCOMES'
        report['blockers'].append('Untouched prospective window is incomplete; scores remain hidden to discourage retuning')
        return report
    if parameters.get('trainingDays',0)<spec['minimumTrainingDays']:report['blockers'].append('Baseline prior has not been fitted on the required verified training days')
    if not verified:report['blockers'].append('Contract/source assumptions were not verified at prediction time')
    if not execution_ok or any(d['market'] is None for d in daily):report['blockers'].append('Complete timestamped quotes and verified fee schedules are missing; net profitability is not established')
    def gap(days):
        bins={}
        for day in days:
            for p,y in day['calibration']:bins.setdefault(min(9,int(p*10)),[]).append((p,y))
        return max((abs(sum(y-p for p,y in entries)/len(entries)) for entries in bins.values()),default=1)
    rng=random.Random(spec['bootstrapSeed']);improvements=[];profits=[];gaps=[]
    for _ in range(spec['bootstrapReplicates']):
        sample=[rng.choice(daily) for _ in daily]
        if all(d['market'] is not None for d in sample):improvements.append(sum(d['market']-d['model'] for d in sample)/len(sample))
        profits.append(sum(d['profit'] for d in sample)/len(sample));gaps.append(gap(sample))
    score={'modelBrier':sum(d['model'] for d in daily)/len(daily),'marketBrier':sum(d['market'] for d in daily)/len(daily) if all(d['market'] is not None for d in daily) else None,'brierImprovementLower95':percentile(improvements,.025) if improvements else None,'maximumBucketGapUpper95':percentile(gaps,.975),'meanStressedPaperProfitCents':sum(d['profit'] for d in daily)/len(daily) if execution_ok else None,'paperProfitLower95Cents':percentile(profits,.025) if execution_ok else None,'bootstrapUnit':'event day; related contract rows stay together'}
    report['scores']=score
    if score['brierImprovementLower95'] is None or score['brierImprovementLower95']<=0:report['blockers'].append('No out-of-sample improvement over the paired market benchmark at the configured confidence threshold')
    if score['maximumBucketGapUpper95']>spec['maximumCalibrationError']:report['blockers'].append('Probability calibration uncertainty exceeds the configured tolerance')
    if score['paperProfitLower95Cents'] is None or score['paperProfitLower95Cents']<=0:report['blockers'].append('Conservative fee-adjusted paper profitability is not demonstrated')
    report['validationExpiresAt']=dt.datetime.combine(end+dt.timedelta(days=30),dt.time(),UTC).isoformat()
    report.update(status='VALIDATION_FAILED' if report['blockers'] else 'PASSED_CONFIGURED_TESTS_REQUIRES_REVIEW',calibrationVerified=not report['blockers'])
    report['limitations']='Policy sample minima and event-cluster bootstrap are not guarantees of future performance; changed stations, seasons, lead times, sources, and fees need new validation.'
    return report


def train_parameters(rows,cutoff,minimum_days=60):
    if len({r['day'] for r in rows})!=len(rows):raise ValueError('Training unit must be one independent event day')
    if len(rows)<minimum_days:raise ValueError('Insufficient verified training days')
    for r in rows:
        if not r['verified'] or not stamp(r['predictionAt'])<stamp(r['settledAt'])<cutoff:raise ValueError('Unverified label or training look-ahead')
    if any('actualMaxF' not in r or not math.isfinite(r['actualMaxF']) or stamp(r['sourceReceivedAt'])>=cutoff for r in rows):raise ValueError('Verified numeric source values known before freeze are required')
    residuals=[r['actualMaxF']-r['peakF'] for r in rows]
    bias=sum(residuals)/len(residuals)
    sigma=max(1,math.sqrt(sum((x-bias)**2 for x in residuals)/len(residuals)))
    return {'biasF':bias,'sigmaF':sigma,'trainingDays':len(rows),'trainedBefore':cutoff.isoformat(),'method':'Gaussian source-value forecast errors; sigma floor 1F; source values never rounded','trainingHash':canonical_hash([{**r,'lowerF':str(r['lowerF']),'upperF':str(r['upperF'])} for r in rows])}


def run(directory,get=fetch):
    directory=pathlib.Path(directory);path=directory/'snapshots.sqlite'
    if not path.exists():return {'status':'NO_ARCHIVE'}
    spec=json.loads((ROOT/'evidence'/'research-spec.json').read_text());config=policy();now=dt.datetime.now(UTC)
    parameters={'biasF':spec['priorBiasF'],'sigmaF':spec['priorSigmaF'],'trainingDays':0,'method':'unfitted engineering prior'}
    # A separately fitted, reviewed model artifact can seed a new frozen experiment; never mutate an existing experiment.
    artifact=directory/'fitted-model.json'
    if artifact.exists():
        candidate=json.loads(artifact.read_text())
        if candidate.get('trainingDays',0)>=spec['minimumTrainingDays'] and stamp(candidate['trainedBefore'])<now:parameters=candidate
    with sqlite3.connect(path,timeout=30) as db:
        db.execute('PRAGMA journal_mode=WAL');result=issue_forecasts(db,spec,parameters,now,config,get)
        for (identifier,) in db.execute('SELECT id FROM research_experiments').fetchall():
            report=evaluate_holdout(db,identifier,now)
            db.execute('INSERT OR REPLACE INTO validation_reports VALUES(?,?,?)',(identifier,now.isoformat(),json.dumps(report)))
        db.commit()
    return result


def status(directory):
    path=pathlib.Path(directory)/'snapshots.sqlite'
    empty={'status':'NOT_INITIALIZED','calibrationVerified':False,'predictions':[],'reports':[],'automaticTrading':False}
    if not path.exists():return empty
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=15) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='probability_forecasts'").fetchone():return empty
        return {'status':'RESEARCH_ONLY','calibrationVerified':False,'automaticTrading':False,'predictionCount':db.execute('SELECT COUNT(*) FROM probability_forecasts').fetchone()[0],'predictions':[json.loads(row[0]) for row in db.execute('SELECT payload FROM probability_forecasts ORDER BY issued_at DESC,ticker LIMIT 24')],'reports':[json.loads(row[0]) for row in db.execute('SELECT v.payload FROM validation_reports v JOIN research_experiments e ON e.id=v.experiment_id ORDER BY e.frozen_at DESC LIMIT 5')]}


def training_rows(db,cutoff):
    spec=json.loads((ROOT/'evidence'/'research-spec.json').read_text())
    labels=outcomes(db);sources=official_days(db);groups={}
    for day,text in db.execute('SELECT event_day,payload FROM probability_forecasts ORDER BY issued_at,ticker'):
        record=json.loads(text)
        assumptions=record.get('assumptions') or {}
        same_window=assumptions.get('timezone')==spec['assumedTimezone'] and assumptions.get('window')==spec['assumedWindow'] and assumptions.get('rounding')==spec['assumedRounding']
        if same_window and record.get('contractVerifiedAtIssue') and stamp(record['issuedAt'])<cutoff:
            groups.setdefault(day,[]).append(record)
    rows=[]
    for day,records in sorted(groups.items()):
        official=sources.get(day)
        if not official or len(official['seen'])!=1 or stamp(official['received'])>=cutoff:continue
        seen={r['ticker']:r for r in reversed(records)}  # earliest issued version per ticker
        winners=[]
        for ticker,record in seen.items():
            label=labels.get(ticker)
            if label and len(label['seen'])==1 and label['market']['result']=='yes' and stamp(label['received'])<cutoff and definition_hash(label['market'])==record['definitionHash']:
                winners.append((record,label))
        if len(winners)!=1:continue
        record,label=winners[0];low,high=bounds(label['market'])
        if not matches(official['value'],low,high):continue
        rows.append({'day':day,'predictionAt':record['issuedAt'],'settledAt':label['received'],'peakF':record['forecastPeakF'],'actualMaxF':official['value'],'sourceReceivedAt':official['received'],'lowerF':low,'upperF':high,'verified':True})
    return rows


def train(directory):
    directory=pathlib.Path(directory);artifact=directory/'fitted-model.json'
    if artifact.exists():raise ValueError('A frozen fitted model already exists; version and preregister a new experiment before replacing it')
    cutoff=dt.datetime.now(UTC);spec=json.loads((ROOT/'evidence'/'research-spec.json').read_text())
    with sqlite3.connect(directory/'snapshots.sqlite') as db:
        schema(db);rows=training_rows(db,cutoff)
    model=train_parameters(rows,cutoff,spec['minimumTrainingDays'])
    artifact.write_text(json.dumps(model,indent=2)+'\n')
    return model

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('run','status','train'));parser.add_argument('--data-dir',default=str(ROOT/'data'));args=parser.parse_args()
    action={'run':run,'status':status,'train':train}[args.command]
    print(json.dumps(action(args.data_dir),allow_nan=False))
