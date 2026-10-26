import copy
import datetime as dt
import json
import pathlib
import sqlite3
import unittest
from research import forecast_peak, probability, bounds, matches, issue_forecasts, evaluate_holdout, train_parameters, official_days
from trading_validation import policy
from test_trading_validation import market,series
ROOT=pathlib.Path(__file__).resolve().parent.parent
SPEC=json.loads((ROOT/'evidence/research-spec.json').read_text())
NOW=dt.datetime(2026,10,26,20,tzinfo=dt.timezone.utc)
def forecast(day):
 from zoneinfo import ZoneInfo
 zone=ZoneInfo('America/Chicago');start=dt.datetime.combine(day,dt.time(),zone).astimezone(dt.timezone.utc);end=dt.datetime.combine(day+dt.timedelta(days=1),dt.time(),zone).astimezone(dt.timezone.utc)
 return {'properties':{'updateTime':NOW.isoformat(),'periods':[{'startTime':(start+dt.timedelta(hours=i)).isoformat(),'endTime':(start+dt.timedelta(hours=i+1)).isoformat(),'temperature':84,'temperatureUnit':'F'} for i in range(int((end-start).total_seconds()/3600))]}}
def markets():
 result=[]
 for kind,low,high,name in [('less',None,80,'T80'),('between',80,81,'B80.5'),('between',82,83,'B82.5'),('between',84,85,'B84.5'),('between',86,87,'B86.5'),('greater',87,None,'T87')]:
  m=market();m.update(ticker='KXHIGHAUS-26OCT27-'+name,strike_type=kind,floor_strike=low,cap_strike=high);result.append(m)
 return result
def database():
 db=sqlite3.connect(':memory:');db.execute('CREATE TABLE snapshots(id INTEGER PRIMARY KEY,run_at TEXT,received_at TEXT,source TEXT,url TEXT,payload TEXT,error TEXT)')
 for source,payload in [('kalshi.markets',{'markets':markets()}),('nws.hourly',forecast(dt.date(2026,10,27))),('kalshi.series',{'series':series()})]:db.execute('INSERT INTO snapshots(run_at,received_at,source,payload) VALUES(?,?,?,?)',(NOW.isoformat(),NOW.isoformat(),source,json.dumps(payload)))
 db.commit();return db
class ResearchTests(unittest.TestCase):
 def test_target_day_coverage_handles_dst_23_and_25_hours(self):
  for day,n in [(dt.date(2026,3,8),23),(dt.date(2026,11,1),25),(dt.date(2026,10,27),24)]:
   data=forecast(day);self.assertEqual(len(data['properties']['periods']),n);self.assertEqual(forecast_peak(data,day,SPEC)[0],84)
   data['properties']['periods'].pop()
   with self.assertRaises(ValueError):forecast_peak(data,day,SPEC)
 def test_reported_values_are_not_rounded_and_strict_boundaries_are_preserved(self):
  self.assertFalse(matches(81.1,80,81));self.assertFalse(matches(87,87,float('inf')));self.assertTrue(matches(87.01,87,float('inf')))
  total=sum(probability(84,4,*bounds(m)) for m in markets());self.assertAlmostEqual(total,1)
 def test_probabilities_are_immutable_prospective_and_not_calibrated(self):
  db=database();params={'biasF':0,'sigmaF':4,'trainingDays':0}
  result=issue_forecasts(db,SPEC,params,NOW,policy());self.assertEqual(result['issued'],6)
  original=db.execute('SELECT payload FROM probability_forecasts ORDER BY ticker').fetchall()
  again=issue_forecasts(db,SPEC,params,NOW+dt.timedelta(minutes=15),policy());self.assertEqual(again['issued'],0)
  self.assertEqual(db.execute('SELECT payload FROM probability_forecasts ORDER BY ticker').fetchall(),original)
  for (text,) in original:
   p=json.loads(text);self.assertFalse(p['calibrationVerified']);self.assertEqual(p['issuedAt'],NOW.isoformat());self.assertLessEqual(p['lowerYes'],p['probabilityYes']);self.assertGreaterEqual(p['upperYes'],p['probabilityYes'])
  report=evaluate_holdout(db,result['experimentId'],NOW);self.assertEqual(report['status'],'HOLDOUT_LOCKED');self.assertIsNone(report['scores'])
 def test_complete_holdout_cannot_pass_without_training_and_execution_evidence(self):
  from research import definition_hash,forecast_probabilities
  from trading_validation import canonical_hash
  db=database();spec=copy.deepcopy(SPEC);spec['bootstrapReplicates']=20
  result=issue_forecasts(db,spec,{'biasF':0,'sigmaF':4,'trainingDays':0},NOW,policy())
  experiment=result['experimentId'];db.execute('DELETE FROM probability_forecasts')
  for index in range(30):
   day=dt.date(2026,10,27)+dt.timedelta(days=index);text=day.isoformat();issued=dt.datetime.combine(day-dt.timedelta(days=1),dt.time(20),dt.timezone.utc);received=dt.datetime.combine(day+dt.timedelta(days=1),dt.time(12),dt.timezone.utc)
   weather=forecast(day);weather['properties']['updateTime']=(issued-dt.timedelta(minutes=30)).isoformat()
   db.execute("INSERT INTO snapshots(source,received_at,payload) VALUES('nws.hourly',?,?)",((issued-dt.timedelta(minutes=1)).isoformat(),json.dumps(weather)));forecast_id=db.execute('SELECT last_insert_rowid()').fetchone()[0]
   from research import forecast_peak
   peak,source_issued,start,finish=forecast_peak(weather,day,spec)
   ms=markets()
   for m in ms:
    m['ticker']=m['ticker'].replace('26OCT27',day.strftime('%y%b%d').upper());m['event_ticker']=m['ticker'].rsplit('-',1)[0]
    lo,hi=bounds(m);y=int(matches(84,lo,hi));m.update(status='finalized',result='yes' if y else 'no',settlement_value_dollars=str(y))
    base,low_p,high_p=forecast_probabilities(peak,{'biasF':0,'sigmaF':4},m,spec)
    record={'ticker':m['ticker'],'issuedAt':issued.isoformat(),'forecastSnapshotId':forecast_id,'forecastSnapshotHash':canonical_hash(weather),'forecastReceivedAt':(issued-dt.timedelta(minutes=1)).isoformat(),'forecastIssuedAt':source_issued.isoformat(),'forecastPeakF':peak,'assumedWindowStart':start.isoformat(),'eventTickers':sorted(x['ticker'].replace('26OCT27',day.strftime('%y%b%d').upper()) for x in markets()),'probabilityYes':base,'lowerYes':low_p,'upperYes':high_p,'contractVerifiedAtIssue':False,'definitionHash':definition_hash(m),'assumedWindowEnd':finish.isoformat()}
    db.execute('INSERT INTO probability_forecasts VALUES(?,?,?,?,?,?)',(m['ticker'],experiment,m['ticker'],text,issued.isoformat(),json.dumps(record)))
   for source,payload in [('kalshi.recent_event',{'markets':ms}),('twc.daily',{'date':text,'results':[{'station':{'icao':'KAUS','cliId':'AUS'},'data':{'reportDate':text,'maxTemp':84,'isOfficial':True},'status':'official'}]})]:
    db.execute('INSERT INTO snapshots(source,received_at,payload) VALUES(?,?,?)',(source,received.isoformat(),json.dumps(payload)))
  db.commit();report=evaluate_holdout(db,experiment,dt.datetime(2026,11,30,tzinfo=dt.timezone.utc))
  self.assertEqual(report['completeEventDays'],30);self.assertGreater(report['scores']['modelBrier'],0)
  self.assertFalse(report['calibrationVerified']);self.assertEqual(report['status'],'VALIDATION_FAILED')
  self.assertIsNone(report['scores']['meanStressedPaperProfitCents'])
  self.assertTrue(any('fitted' in message for message in report['blockers']))

 def test_stale_data_cannot_create_predictions(self):
  db=database();result=issue_forecasts(db,SPEC,{'biasF':0,'sigmaF':4},NOW+dt.timedelta(hours=3),policy());self.assertEqual(result['issued'],0)
  report=evaluate_holdout(db,result['experimentId'],NOW+dt.timedelta(hours=3));self.assertIsNone(report['firstTargetDay']);self.assertEqual(report['status'],'WAITING_FIRST_ELIGIBLE_EVENT')
 def test_nonbinary_fallback_and_withdrawn_final_outcomes_are_not_gold_labels(self):
  from research import outcomes
  db=database();m=market();m.update(status='finalized',result='yes',settlement_value_dollars='0.45')
  def save():db.execute("INSERT INTO snapshots(source,received_at,payload) VALUES('kalshi.recent_event',?,?)",(NOW.isoformat(),json.dumps({'markets':[m]})));db.commit()
  save();self.assertNotIn(m['ticker'],outcomes(db))
  m['settlement_value_dollars']='1.0000';save();self.assertNotIn(m['ticker'],outcomes(db))
  m['ticker']='KXHIGHAUS-26OCT27-B82.5';save();self.assertIn(m['ticker'],outcomes(db))
  m['status']='closed';save();self.assertNotIn(m['ticker'],outcomes(db))

 def test_no_training_on_unverified_labels_or_fewer_than_policy_days(self):
  with self.assertRaises(ValueError):train_parameters([],NOW)
  row={'day':'2026-10-24','predictionAt':'2026-10-23T00:00:00Z','settledAt':'2026-10-25T00:00:00Z','sourceReceivedAt':'2026-10-25T00:00:00Z','peakF':80,'actualMaxF':82,'lowerF':82,'upperF':83,'verified':False}
  with self.assertRaises(ValueError):train_parameters([row],NOW,1)
  row['verified']=True;result=train_parameters([row],NOW,1);self.assertEqual(result['biasF'],2);self.assertEqual(result['sigmaF'],1)
  row['sourceReceivedAt']='2026-10-27T00:00:00Z'
  with self.assertRaises(ValueError):train_parameters([row],NOW,1)
 def test_preliminary_wrong_station_and_revised_values_are_not_silently_final(self):
  db=database();data={'date':'2026-10-25','results':[{'station':{'icao':'KAUS','cliId':'AUS'},'data':{'reportDate':'2026-10-25','maxTemp':82,'isOfficial':False},'status':'preliminary'}]}
  def save():db.execute("INSERT INTO snapshots(source,received_at,payload) VALUES('twc.daily',?,?)",(NOW.isoformat(),json.dumps(data)));db.commit()
  save();self.assertFalse(official_days(db))
  data['results'][0]['data']['isOfficial']=True;data['results'][0]['status']='official';save();self.assertEqual(official_days(db)['2026-10-25']['seen'],{82})
  data['results'][0]['data']['maxTemp']=83;data['results'][0]['status']='revised';save();self.assertEqual(official_days(db)['2026-10-25']['seen'],{82,83})
  data['results'][0]['status']='preliminary';data['results'][0]['data']['isOfficial']=False;save();self.assertNotIn('2026-10-25',official_days(db))
if __name__=='__main__':unittest.main()
