import copy
import datetime as dt
import json
import pathlib
import unittest
from decimal import Decimal
from trading_validation import audit_contract,audit_fees,policy,quote,fill,fee_cents,template_matches,simulate_fee_components
ROOT=pathlib.Path(__file__).resolve().parent.parent
NOW=dt.datetime(2026,10,26,22,tzinfo=dt.timezone.utc)

def market():
 return {'ticker':'KXHIGHAUS-26OCT27-B80.5','event_ticker':'KXHIGHAUS-26OCT27','strike_type':'between','floor_strike':80,'cap_strike':81,'notional_value_dollars':'1.0000','price_ranges':[{'start':'0','end':'1','step':'0.01'}],'status':'active','open_time':'2026-10-26T00:00:00Z','close_time':'2026-10-28T06:00:00Z','rules_primary':'If the maximum temperature recorded at Austin (CLIAUS) for Oct 27, 2026, is between 80-81° fahrenheit according to The Weather Company, then the market resolves to Yes.','rules_secondary':'test revisions','early_close_condition':'test'}
def series():return {'ticker':'KXHIGHAUS','fee_type':'quadratic','fee_multiplier':1,'settlement_sources':[{'name':'The Weather Company','url':'https://weather.com/kalshi'}]}
BOOK={'orderbook_fp':{'no_dollars':[['0.60','2.50'],['0.50','20.00']],'yes_dollars':[['0.35','20.00']]}}
class TradingTests(unittest.TestCase):
 def test_unknown_window_and_fee_rounding_block_despite_official_rate(self):
  c=policy();m=market();audit=audit_contract(m,series(),c,NOW)
  self.assertFalse(audit['verified']);self.assertFalse(audit['checks']['measurementWindow']['verified'])
  self.assertTrue(audit['checks']['stationMapping']['verified']);self.assertTrue(audit['checks']['rounding']['verified'])
  c['fees']['accountType']=None;fees=audit_fees(series(),c,NOW,fee_context={'eventTicker':market()['event_ticker'],'receivedAt':NOW.isoformat(),'seriesChanges':{'series_fee_change_arr':[]},'eventChanges':{'event_fee_changes':[],'cursor':''}},event_ticker=market()['event_ticker']);self.assertTrue(fees['rateVerified']);self.assertTrue(fees['roundingMechanicsVerified']);self.assertFalse(fees['verified'])
 def test_rule_template_detects_wrong_date_station_operator_and_source(self):
  c=copy.deepcopy(policy());m=market();import hashlib
  c['settlement']['ruleTemplate']['secondarySha256']=hashlib.sha256(m['rules_secondary'].encode()).hexdigest()
  c['settlement']['ruleTemplate']['earlyCloseSha256']=hashlib.sha256(m['early_close_condition'].encode()).hexdigest()
  self.assertTrue(template_matches(m,c['settlement']))
  for old,new in [('Oct 27','Oct 28'),('CLIAUS','CLIATT'),('between','greater than'),('The Weather Company','Other source')]:
   changed={**m,'rules_primary':m['rules_primary'].replace(old,new)};self.assertFalse(template_matches(changed,c['settlement']))
 def test_fill_walks_fractional_depth_and_preserves_no_complement(self):
  levels,left=fill(BOOK,'YES',5);self.assertEqual(left,0);self.assertEqual(sum(p*q for p,q in levels),Decimal('2.2500'))
  levels,left=fill(BOOK,'NO',5);self.assertEqual(levels,[(Decimal('.65'),Decimal(5))])
  _,left=fill(BOOK,'YES',30);self.assertEqual(left,Decimal('7.50'))
 def test_malformed_or_crossed_books_cannot_produce_prices(self):
  with self.assertRaises(ValueError):fill({'orderbook_fp':{'no_dollars':[['NaN','2']]}},'YES',1)
  with self.assertRaises(ValueError):fill({'orderbook_fp':{'no_dollars':[['.7','2']],'yes_dollars':[['.7','2']]}},'YES',1)
  with self.assertRaises(ValueError):fill(BOOK,'YES',True)
 def test_exact_decimal_fee_matches_published_cent_table_scenario(self):
  fees={'takerCoefficient':'0.07','multiplier':1}
  self.assertEqual(fee_cents([(Decimal('.5'),Decimal(100))],fees),175)
  self.assertEqual(fee_cents([(Decimal('.5'),Decimal(1))],fees),2)
 def test_quote_does_not_treat_fee_scenarios_or_manual_probability_as_verified(self):
  result=quote(market(),series(),BOOK,'YES',5,{'ticker':market()['ticker'],'calibrationVerified':False,'lowerYes':.9,'upperYes':.95,'issuedAt':NOW.isoformat()},now=NOW,book_at=NOW.isoformat())
  self.assertEqual(result['status'],'BLOCKED');self.assertIsNone(result['feeCents']);self.assertIn('feeScenariosCents',result)
  self.assertIn('FEES_UNVERIFIED',result['blockers']);self.assertIn('SETTLEMENT_UNVERIFIED',result['blockers']);self.assertIn('NO_VALIDATED_PROBABILITY',result['blockers'])
 def test_documented_rounding_example_and_capped_accumulator(self):
  example=simulate_fee_components([('-.055000','.00363825')],'non_direct')[0]
  self.assertEqual(example['trade'],Decimal('.003639'));self.assertEqual(example['rounding'],Decimal('.001361'));self.assertEqual(example['net'],Decimal('.005'))
  sequence=simulate_fee_components([('-.006','0'),('-.006','0'),('-.006','.01')],'non_direct')
  self.assertEqual(sequence[-1]['rebate'],Decimal('.01'));self.assertEqual(sequence[-1]['accumulator'],Decimal('.002'))
 def test_conservative_bound_covers_fragmented_direct_fills(self):
  fees={'takerCoefficient':'0.07','multiplier':1,'rounding':'documented_per_fill_accumulator','accountType':'direct'}
  exact=simulate_fee_components([('-.0001','.00000693')]*100,'direct')
  upper=fee_cents([(Decimal('.01'),Decimal(1))],fees)
  self.assertGreaterEqual(upper,sum((r['net'] for r in exact),Decimal(0))*100)
 def test_event_override_and_imminent_changes_invalidate_fee_applicability(self):
  c=policy();context={'eventTicker':market()['event_ticker'],'receivedAt':NOW.isoformat(),'seriesChanges':{'series_fee_change_arr':[]},'eventChanges':{'event_fee_changes':[{'series_ticker':'KXHIGHAUS','event_ticker':market()['event_ticker'],'scheduled_ts':(NOW-dt.timedelta(hours=1)).isoformat(),'fee_type_override':'flat','fee_multiplier_override':1}],'cursor':''}}
  result=audit_fees(series(),c,NOW,fee_context=context,event_ticker=market()['event_ticker']);self.assertFalse(result['rateVerified'])
 def test_newer_forecast_blocks_an_older_model_even_within_two_hours(self):
  prediction={'ticker':market()['ticker'],'calibrationVerified':False,'lowerYes':.9,'upperYes':.95,'issuedAt':NOW.isoformat(),'forecastIssuedAt':(NOW-dt.timedelta(hours=1)).isoformat()}
  result=quote(market(),series(),BOOK,'YES',5,prediction,now=NOW,book_at=NOW.isoformat(),current_forecast_issued_at=NOW.isoformat(),forecast_received_at=NOW.isoformat())
  self.assertIn('NEWER_FORECAST_AVAILABLE',result['blockers'])
 def test_off_grid_quotes_cannot_be_called_executable(self):
  book={'orderbook_fp':{'no_dollars':[['.6001','10']],'yes_dollars':[['.35','10']]}}
  with self.assertRaises(ValueError):quote(market(),series(),book,'YES',1,now=NOW,book_at=NOW.isoformat())

 def test_insufficient_depth_never_returns_complete_entry_cost(self):
  result=quote(market(),series(),BOOK,'YES',100,now=NOW,book_at=NOW.isoformat())
  self.assertIsNone(result['entryCostCents']);self.assertIn('INSUFFICIENT_VISIBLE_DEPTH',result['blockers'])
if __name__=='__main__':unittest.main()
