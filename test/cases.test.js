import {test} from 'node:test';
import assert from 'node:assert/strict';
import {retrospectiveCases,calibrationSummary,auditCase,auditCalibration} from '../public/cases.js';
for(const record of retrospectiveCases)test(record.id+' remains ineligible without invented execution or probability evidence',()=>{
 const result=auditCase(record);
 assert.equal(result.eligibleForBuy,false);assert.equal(result.netEdge,null);
 if(record.family==='KXHIGHAUS')assert.ok(record.ticker.startsWith('KXHIGHAUS-26OCT'));else assert.equal(record.ticker,null);assert.equal(record.quantity,null);
 assert.ok(result.blockers.some(x=>x.includes('archived executable order book')));
 assert.ok(result.blockers.some(x=>x.includes('freshness')));
});
test('Oct 7 allocation stays a budget, and reference time does not become forecast issue time',()=>{
 const record=retrospectiveCases.find(x=>x.id==='austin-2026-10-07');
 assert.deepEqual(record.budgetUSD,[150,175]);assert.equal(record.quantity,null);
 assert.equal(record.forecast.issuedAt,null);assert.equal(record.decisionAt,null);
});
test('Oct 8 probability remains an uncalibrated range, never a synthetic point probability',()=>{
 const record=retrospectiveCases.find(x=>x.id==='austin-2026-10-08');
 assert.deepEqual(record.probabilityRange,[.55,.70]);assert.equal(record.priceRangeCents,null);
 assert.equal(record.probability,undefined);assert.equal(auditCase(record).netEdge,null);
});
test('unaccounted calibration days and mixed labels remain explicit',()=>{
 const objections=auditCalibration(calibrationSummary);
 assert.ok(objections.some(x=>x.startsWith('5 of 34')));
 assert.ok(objections.some(x=>x.includes('Mixed settlement sources')));
 assert.equal(calibrationSummary.independentlyVerified,false);
});
test('withdrawn Miami case is never promoted by a high claimed probability',()=>{
 const record=retrospectiveCases.find(x=>x.id==='miami-2026-10-07');
 assert.equal(auditCase(record).status,'WITHDRAWN');assert.equal(auditCase(record).eligibleForBuy,false);
});

test('retrieved Austin YES settlements make both proposed NO payouts zero without fabricating P&L',()=>{
 for(const record of retrospectiveCases.filter(x=>x.family==='KXHIGHAUS')){
  assert.equal(record.reportedSettlement.status,'finalized');assert.equal(record.reportedSettlement.result,'yes');
  assert.equal(record.reportedSettlement.proposedSidePayoutCents,0);assert.equal(auditCase(record).netEdge,null);
  assert.ok(record.reportedSettlement.rulesPrimary.includes('The Weather Company'));
 }
});
