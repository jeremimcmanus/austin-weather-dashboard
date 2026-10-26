"""Fail-closed rule/fee audits and Decimal-based quantity-specific research quotes."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import re
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = Decimal
UTC = dt.timezone.utc

def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def rule_hash(market):
    return canonical_hash({key:market.get(key) for key in ('ticker','event_ticker','strike_type','floor_strike','cap_strike','rules_primary','rules_secondary','early_close_condition','close_time','expiration_time')})

def stamp(value):
    result=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone required')
    return result

def active_period(start,end,now):
    try:return stamp(start)<=now<stamp(end)
    except (ValueError,TypeError,AttributeError):return False

def policy():
    return json.loads((ROOT/'evidence'/'trading-policy.json').read_text())

def document_verified(name, config, root=ROOT):
    try:
        expected=config['documents'][name]
        receipts=json.loads((root/'evidence'/'official'/'receipts.json').read_text())
        receipt=receipts[name]
        filename=name+('.json' if name=='station' else '.md' if name in ('feeRounding','fixedPoint') else '.pdf')
        content=(root/'evidence'/'official'/filename).read_bytes()
        return bool(expected['sha256'] and receipt['url']==expected['url'] and receipt['httpStatus']=='200' and receipt['status']=='acquired_not_reviewed' and receipt['file']==filename and hashlib.sha256(content).hexdigest()==expected['sha256']==receipt['sha256'] and (bool(content.strip()) if name in ('feeRounding','fixedPoint') else content.startswith(b'%PDF') if name!='station' else any(item.get('station',{}).get('icao')=='KAUS' and item.get('station',{}).get('cliId')=='AUS' for item in json.loads(content).get('results',[]))))
    except (KeyError,ValueError,OSError,TypeError):return False

def template_matches(market,reviewed):
    template=reviewed.get('ruleTemplate') or {}
    if template.get('version')!='austin_full_precision_v1':return False
    event=market.get('event_ticker') or ''
    parsed=re.fullmatch(r'KXHIGHAUS-(\d{2})([A-Z]{3})(\d{2})',event)
    months=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
    try:
        day=dt.date(2000+int(parsed[1]),months.index(parsed[2])+1,int(parsed[3]))
        numeric=lambda value:format(D(str(value)).normalize(),'f')
        kind=market['strike_type']
        if kind=='between':comparison='between '+numeric(market['floor_strike'])+'-'+numeric(market['cap_strike'])+'°'
        elif kind=='greater':comparison='greater than '+numeric(market['floor_strike'])+'°'
        elif kind=='less':comparison='less than '+numeric(market['cap_strike'])+'°'
        else:return False
        date=f'{months[day.month-1].title()} {day.day}, {day.year}'
        full_date=['January','February','March','April','May','June','July','August','September','October','November','December'][day.month-1]+' '+str(day.day)+', '+str(day.year)
        early=' '.join((market.get('early_close_condition') or '').split()).replace(full_date,'<DATE>')
        expected=f'If the maximum temperature recorded at Austin (CLIAUS) for {date}, is {comparison} fahrenheit according to The Weather Company, then the market resolves to Yes.'
        return bool(hashlib.sha256(early.encode()).hexdigest()==template.get('earlyCloseSha256') and market['rules_primary']==expected and hashlib.sha256((market.get('rules_secondary') or '').encode()).hexdigest()==template.get('secondarySha256') and market['ticker'].startswith(event+'-') and D(str(market.get('notional_value_dollars')))==1)
    except (TypeError,ValueError,KeyError,ArithmeticError):return False


def audit_contract(market,series,config=None,now=None,root=ROOT):
    config=config or policy();now=now or dt.datetime.now(UTC)
    rules=(market.get('rules_primary') or '')+'\n'+(market.get('rules_secondary') or '')
    identifier=re.search(r'\((CLI[A-Z]+)\)',rules)
    reviewed=config['settlement'];fingerprint=rule_hash(market)
    terms_ok=document_verified('terms',config,root)
    sources=series.get('settlement_sources') or []
    source_ok=bool(sources and sources[0].get('name')==reviewed['source'] and reviewed['source'] in rules)
    fields={name:{'verified':bool(terms_ok and document_verified(reviewed.get(name,{}).get('document','terms'),config,root) and reviewed.get(name,{}).get('value') and reviewed.get(name,{}).get('quote')),'value':reviewed.get(name,{}).get('value')} for name in ('stationMapping','measurementWindow','rounding','revisions')}
    dated=active_period(reviewed.get('reviewedAt'),reviewed.get('validUntil'),now)
    bound=reviewed.get('contractRuleHashes',{}).get(market.get('ticker'))==fingerprint or template_matches(market,reviewed)
    verified=bool(terms_ok and source_ok and dated and bound and all(f['verified'] for f in fields.values()))
    return {'ticker':market.get('ticker'),'verified':verified,'ruleHash':fingerprint,'officialTermsAcquired':terms_ok,'reviewInDate':dated,'exactRuleVersionApproved':bound,'checks':fields,
      'exchangeDeclared':{'source':series.get('settlement_sources',[]),'stationCode':identifier.group(1) if identifier else None,'forecastStation':'KAUS','closeTime':market.get('close_time'),'expirationTime':market.get('expiration_time'),'earlyCloseCondition':market.get('early_close_condition'),'rulesPrimary':market.get('rules_primary'),'rulesSecondary':market.get('rules_secondary')},
      'caution':'Exchange-declared values do not prove station equivalence, the measurement window, rounding, or source finality. Trading close is not the weather reporting window.'}

def fee_context_verified(series,context,event_ticker,now):
    if not context or context.get('eventTicker')!=event_ticker:return False
    try:
        if not 0<=(now-stamp(context['receivedAt'])).total_seconds()<=60:return False
        parent=context['seriesChanges']['series_fee_change_arr'];events=context['eventChanges']['event_fee_changes']
        if not isinstance(parent,list) or not isinstance(events,list) or context['eventChanges'].get('cursor'):return False
        if any(row['series_ticker']!=series['ticker'] for row in parent):return False
        if any(row['event_ticker']!=event_ticker or row['series_ticker']!=series['ticker'] for row in events):return False
        for row in parent+events:
            if now<stamp(row['scheduled_ts'])<=now+dt.timedelta(seconds=60):return False
        active_parent=sorted((r for r in parent if stamp(r['scheduled_ts'])<=now),key=lambda r:stamp(r['scheduled_ts']))
        if active_parent and (active_parent[-1]['fee_type']!=series['fee_type'] or D(str(active_parent[-1]['fee_multiplier']))!=D(str(series['fee_multiplier']))):return False
        active=sorted((r for r in events if stamp(r['scheduled_ts'])<=now),key=lambda r:stamp(r['scheduled_ts']))
        if active:
            last=active[-1]
            if last.get('fee_type_override') not in (None,series['fee_type']):return False
            if last.get('fee_multiplier_override') is not None and D(str(last['fee_multiplier_override']))!=D(str(series['fee_multiplier'])):return False
        return True
    except (KeyError,ValueError,TypeError,AttributeError,ArithmeticError):return False


def audit_fees(series,config=None,now=None,root=ROOT,fee_context=None,event_ticker=None):
    config=config or policy();now=now or dt.datetime.now(UTC);fees=config['fees']
    rate=False
    try:
        coefficient=D(str(fees['takerCoefficient']));multiplier=D(str(fees['multiplier']))
        rate=bool(document_verified('fees',config,root) and active_period(fees['effectiveFrom'],fees['effectiveUntil'],now) and fees.get('reviewedAt') and stamp(fees['reviewedAt'])<=now and fees.get('quote') and fees['series']==series['ticker'] and fees['feeType']==series['fee_type']=='quadratic' and multiplier==D(str(series['fee_multiplier'])) and coefficient.is_finite() and 0<=coefficient<=1 and multiplier.is_finite() and multiplier>0)
    except (KeyError,ValueError,TypeError,AttributeError,ArithmeticError):pass
    context_ok=fee_context_verified(series,fee_context,event_ticker,now)
    mechanics=bool(document_verified('feeRounding',config,root) and document_verified('fixedPoint',config,root) and fees.get('rounding')=='documented_per_fill_accumulator' and fees.get('minimumFillQuantity')=='0.01' and fees.get('tradeFeePrecisionDollars')=='0.000001')
    account=fees.get('accountType');account_ok=account=='direct'
    # Broker/FCM users need their additional brokerage charges verified separately.
    verified=rate and context_ok and mechanics and account_ok
    return {'verified':bool(verified),'baseRateVerified':rate,'rateVerified':rate and context_ok,'eventFeeContextVerified':context_ok,'roundingMechanicsVerified':mechanics,'accountType':account,'accountScope':fees.get('accountScope'),'roundingStatus':fees.get('rounding'),'takerCoefficient':fees.get('takerCoefficient') if rate else None,'exchangeFeeType':series.get('fee_type'),'exchangeMultiplier':series.get('fee_multiplier'),'policy':fees if verified else None,'reason':None if verified else 'Current series/event overrides, account category, and any brokerage charges must be verified. The fee result is a conservative bound, not a realized fill receipt.'}


def asks(book,side):
    if side not in ('YES','NO'):raise ValueError('Side must be YES or NO')
    fp=book.get('orderbook_fp');key='no' if side=='YES' else 'yes'
    raw=fp.get(key+'_dollars') if fp is not None else (book.get('orderbook') or {}).get(key)
    if raw is None:return []
    levels={}
    for price,size in raw:
        p=D(str(price)) if fp is not None else D(str(price))/100
        q=D(str(size))
        if not p.is_finite() or not q.is_finite() or not 0<=p<=1 or q<=0 or q*100!=(q*100).to_integral_value() or p*10000!=(p*10000).to_integral_value():raise ValueError('Malformed order book')
        cost=1-p;levels[cost]=levels.get(cost,D(0))+q
    return sorted(levels.items())

def on_grid(price,ranges):
    try:
        return any(D(str(band['step']))>0 and D(str(band['start']))<=price<=D(str(band['end'])) and (price-D(str(band['start'])))%D(str(band['step']))==0 for band in ranges)
    except (KeyError,ValueError,TypeError,ArithmeticError):return False


def fill(book,side,quantity):
    if not isinstance(quantity,int) or isinstance(quantity,bool) or not 1<=quantity<=100000:raise ValueError('Quantity must be an integer from 1 to 100000')
    levels=asks(book,side);opposite=asks(book,'NO' if side=='YES' else 'YES')
    if levels and opposite and levels[0][0]+opposite[0][0]<1:raise ValueError('Crossed book; refuse executable-price estimate')
    remaining=D(quantity);fills=[]
    for price,size in levels:
        take=min(size,remaining)
        if take:fills.append((price,take));remaining-=take
        if not remaining:break
    return fills,remaining

def simulate_fee_components(fills,account_type):
    # Only an explicit fill sequence has an exact accumulator result. Books are aggregated.
    precision=D('0.0001') if account_type=='direct' else D('0.01')
    accumulator=D(0);result=[]
    for revenue,model_fee in fills:
        revenue=D(str(revenue));model_fee=D(str(model_fee))
        if not revenue.is_finite() or not model_fee.is_finite() or model_fee<0:raise ValueError('Invalid fee simulation input')
        trade=(model_fee/D('0.000001')).to_integral_value(rounding=ROUND_CEILING)*D('0.000001')
        aligned=((revenue-trade)/precision).to_integral_value(rounding=ROUND_FLOOR)*precision
        rounding=revenue-trade-aligned;accumulator+=rounding
        rebate=min((accumulator/precision).to_integral_value(rounding=ROUND_FLOOR)*precision,((trade+rounding)/precision).to_integral_value(rounding=ROUND_FLOOR)*precision)
        accumulator-=rebate
        result.append({'trade':trade,'rounding':rounding,'rebate':rebate,'net':trade+rounding-rebate,'accumulator':accumulator})
    return result


def fee_cents(fills,fees):
    dollars=sum((q*p*(1-p) for p,q in fills),D(0))*D(str(fees['takerCoefficient']))*D(str(fees['multiplier']))
    if fees.get('rounding')=='documented_per_fill_accumulator':
        precision=D('0.0001') if fees.get('accountType')=='direct' else D('0.01')
        max_fills=sum((q for _,q in fills),D(0))/D('0.01')
        dollars+=max_fills*(precision+D('0.000001'))
        return (dollars*100).quantize(D('0.0001'),rounding=ROUND_CEILING)
    return (dollars*100).to_integral_value(rounding=ROUND_CEILING)

def quote(market,series,book,side,quantity,prediction=None,config=None,now=None,book_at=None,root=ROOT,fee_context=None,current_forecast_issued_at=None,forecast_received_at=None):
    config=config or policy();now=now or dt.datetime.now(UTC)
    audit=audit_contract(market,series,config,now,root);fees=audit_fees(series,config,now,root,fee_context,market.get('event_ticker'))
    blockers=[]
    if market.get('notional_value_dollars') is None or D(str(market['notional_value_dollars']))!=1:blockers.append('UNSUPPORTED_OR_UNKNOWN_PAYOUT')
    if not audit['verified']:blockers.append('SETTLEMENT_UNVERIFIED')
    if not fees['verified']:blockers.append('FEES_UNVERIFIED')
    if market.get('status') not in ('active','open') or not active_period(market.get('open_time'),market.get('close_time'),now):blockers.append('MARKET_NOT_OPEN')
    try:
        if not 0<=(now-stamp(book_at)).total_seconds()<=config['risk']['maxBookAgeSeconds']:blockers.append('BOOK_STALE')
    except (ValueError,TypeError,AttributeError):blockers.append('BOOK_TIMESTAMP_MISSING')
    fills,remaining=fill(book,side,quantity)
    if not market.get('price_ranges'):blockers.append('PRICE_GRID_UNVERIFIED')
    elif any(not on_grid(p,market['price_ranges']) for p,_ in fills):raise ValueError('Off-grid executable price')
    result={'ticker':market['ticker'],'side':side,'quantity':quantity,'bookReceivedAt':book_at,'fillGuaranteed':False,'unfilledQuantity':str(remaining),'fills':[{'priceDollars':str(p),'quantity':str(q)} for p,q in fills], 'entryCostCents':None,'feeCents':None,'feeIsConservativeUpperBound':True,'realizedFeeCents':None,'stressedCostCents':None,'conservativeEdgeCents':None,'status':'BLOCKED','contractAudit':audit,'feeAudit':fees,'blockers':blockers,'automaticTrading':False,'limits':'Visible depth is a snapshot, not a fill guarantee. Fee bounds cover documented taker rounding and maximum fill fragmentation; realized fees may be lower. Unknown event overrides and brokerage charges block approval. Extra execution cost excludes later liquidation. Scenario bounds are not calibrated confidence intervals.'}
    if remaining:result['blockers'].append('INSUFFICIENT_VISIBLE_DEPTH');return result
    entry=sum((p*q*100 for p,q in fills),D(0));result['entryCostCents']=str(entry)
    result['averageEntryCents']=str(entry/quantity);result['worstVisibleFillCents']=str(fills[-1][0]*100)
    if fees['baseRateVerified'] and fees['roundingMechanicsVerified']:
        raw=sum((q*p*(1-p) for p,q in fills),D(0))*D(str(config['fees']['takerCoefficient']))*D(str(config['fees']['multiplier']))*100
        direct={**config['fees'],'accountType':'direct'};nondirect={**config['fees'],'accountType':'non_direct'}
        result['feeScenariosCents']={'directUpperBound':str(fee_cents(fills,direct)),'nonDirectExchangeUpperBound':str(fee_cents(fills,nondirect)),'unroundedFormula':str(raw),'centPerOrder':str(raw.to_integral_value(rounding=ROUND_CEILING)),'centicentTotalCost':str(((entry+raw)*100).to_integral_value(rounding=ROUND_CEILING)/100-entry),'qualifier':'Bounds ignore all rebates and allow up to 100 minimum-size fills per contract. Broker charges are excluded. Book levels cannot identify the actual fill sequence.'}
    if fees['verified']:
        charge=fee_cents(fills,fees['policy']);result['feeCents']=str(charge)
        result['stressedCostCents']=str(entry+charge+D(str(config['risk']['extraExecutionCents']))*quantity)
    if not prediction or not prediction.get('calibrationVerified'):
        blockers.append('NO_VALIDATED_PROBABILITY')
    if prediction:
        try:
            latest=stamp(current_forecast_issued_at);received=stamp(forecast_received_at);used=stamp(prediction['forecastIssuedAt'])
            if not 0<=(now-latest).total_seconds()<=7200 or not 0<=(now-received).total_seconds()<=60:blockers.append('WEATHER_SOURCE_STALE')
            if latest>used:blockers.append('NEWER_FORECAST_AVAILABLE')
            if latest<used:blockers.append('WEATHER_SOURCE_TIMESTAMP_REGRESSED')
        except (KeyError,ValueError,TypeError,AttributeError):blockers.append('CURRENT_FORECAST_FRESHNESS_UNVERIFIED')
        result['researchPrediction']=prediction
        if prediction.get('ticker')!=market['ticker']:blockers.append('PREDICTION_CONTRACT_MISMATCH')
        if prediction.get('ruleHash')!=audit['ruleHash']:blockers.append('RULES_CHANGED_SINCE_PREDICTION')
        try:
            if not 0<=(now-stamp(prediction['issuedAt'])).total_seconds()<=7200:blockers.append('MODEL_STALE')
        except (KeyError,ValueError,TypeError,AttributeError):blockers.append('MODEL_TIMESTAMP_MISSING')
        lower=prediction.get('lowerYes') if side=='YES' else (1-prediction['upperYes'] if prediction.get('upperYes') is not None else None)
        if lower is not None and math.isfinite(lower) and 0<=lower<=1 and result['stressedCostCents'] is not None:
            edge=D(str(lower))*100-D(result['stressedCostCents'])/quantity
            result['conservativeEdgeCents']=str(edge)
            if edge<=D(str(config['risk']['minimumEdgeCents'])):blockers.append('NO_CONSERVATIVE_NET_EDGE')
        else:blockers.append('CONSERVATIVE_PROBABILITY_OR_COST_MISSING')
    if not blockers:result['status']='ELIGIBLE_FOR_REVIEW_NOT_AN_ORDER'
    result['limits']='Visible depth is a snapshot, not a fill guarantee. Fee bounds cover documented taker rounding and maximum fill fragmentation; realized fees may be lower. Unknown event overrides and brokerage charges block approval. Extra execution cost excludes later liquidation. Scenario bounds are not calibrated confidence intervals.'
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input-json',required=True);args=parser.parse_args()
    request=json.loads(args.input_json)
    from research import status
    research=status(os.environ.get('DATA_DIR',str(ROOT/'data')))
    prediction=next((p for p in research['predictions'] if p['ticker']==request['market']['ticker']),None)
    if prediction:
        report=next((r for r in research['reports'] if r['experimentId']==prediction['experimentId']),{})
        prediction['calibrationVerified']=bool(prediction['calibrationVerified'] and report.get('calibrationVerified') and dt.datetime.now(UTC)<stamp(report['validationExpiresAt']))
    request['prediction']=prediction
    print(json.dumps(quote(**request),allow_nan=False))
