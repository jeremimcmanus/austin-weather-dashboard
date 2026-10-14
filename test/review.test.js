import {test} from 'node:test';
import assert from 'node:assert/strict';
import {asksForSide,reviewTrade} from '../public/review.js';
const now=Date.parse('2026-10-14T20:00:00Z');
const stamp=new Date(now-30000).toISOString();
const book={orderbook_fp:{no_dollars:[['0.60','10'],['0.50','10']],yes_dollars:[['0.35','20']]}};
const valid={book,side:'YES',quantity:15,probability:.70,probabilityHaircut:.10,totalFeeCents:15,slippageCents:2,modelAt:stamp,forecastAt:stamp,bookAt:stamp,now,marketOpen:true,settlementVerified:true,calibrationVerified:true,feeScheduleVerified:true};
const codes=x=>reviewTrade(x).reasons.map(r=>r.code);
test('depth-weighted net cost includes total fees and extra stress cost',()=>{
 const r=reviewTrade(valid);assert.ok(Math.abs(r.metrics.averageCost-(650/15+1))<1e-8);
 assert.ok(Math.abs(r.metrics.stressEdge-(60-(650/15+3)))<1e-8);
 assert.ok(r.metrics.baseEdge>0);assert.ok(r.metrics.efficientEdge<0);
 assert.deepEqual(codes(valid),['efficient_market']);
});
test('NO trades use complementary YES bids',()=>{
 assert.deepEqual(asksForSide(book,'NO'),[{price:65,size:20}]);
 const r=reviewTrade({...valid,side:'NO',quantity:10});assert.equal(r.metrics.averageCost,66.5);
});
test('unknown settlement, calibration, and fee evidence cannot pass',()=>{
 const r=codes({...valid,settlementVerified:false,calibrationVerified:false,feeScheduleVerified:false});
 for(const key of ['settlement','calibration','fee_verification'])assert.ok(r.includes(key));
});
test('missing fees, insufficient liquidity, and missing probabilities suppress edge calculation',()=>{
 const r=reviewTrade({...valid,quantity:21,totalFeeCents:NaN,probability:NaN});
 assert.equal(r.metrics,null);assert.ok(r.reasons.some(r=>r.code==='depth'));assert.ok(r.reasons.some(r=>r.code==='fees'));
});
test('stale and future timestamps block confidence and model cannot predate new evidence',()=>{
 const old=new Date(now-3*3600000).toISOString();
 const r=codes({...valid,modelAt:old,forecastAt:old,bookAt:new Date(now+1000).toISOString()});
 for(const key of ['model_age','forecast_age','book_age'])assert.ok(r.includes(key));
 assert.ok(codes({...valid,modelAt:old}).includes('model_update'));
});
test('fees and stress can reverse an apparent model advantage',()=>{
 const r=reviewTrade({...valid,quantity:10,probability:.43,totalFeeCents:40});
 assert.ok(r.metrics.baseEdge<0);assert.ok(codes({...valid,quantity:10,probability:.43,totalFeeCents:40}).includes('base_edge'));
});
test('demo and closed market are never substantiated',()=>{
 const r=codes({...valid,isDemo:true,marketOpen:false});assert.ok(r.includes('demo'));assert.ok(r.includes('market'));
});
test('missing or crossed complementary book does not invent market prior',()=>{
 const single={orderbook_fp:{no_dollars:[['0.60','10']]}};
 const r=reviewTrade({...valid,book:single,quantity:10});assert.equal(r.metrics.efficientEdge,null);assert.ok(r.reasons.some(r=>r.code==='market_prior'));
});
