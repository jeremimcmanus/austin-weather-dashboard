import {test} from 'node:test';
import assert from 'node:assert/strict';
import {yesAsks,estimateFill} from '../public/math.js';
test('fixed point NO bids become ascending YES asks with fractional sizes',()=>{
 const asks=yesAsks({orderbook_fp:{no_dollars:[['0.90','2.50'],['0.95','3.00']]}});
 assert.deepEqual(asks,[{price:5,size:3},{price:10,size:2.5}]);
 assert.deepEqual(estimateFill(asks,5),{remaining:0,cost:35});
 assert.deepEqual(estimateFill(asks,6),{remaining:.5,cost:40});
});
test('legacy book and empty liquidity remain distinct from a free fill',()=>{
 assert.deepEqual(yesAsks({orderbook:{no:[[75,4]]}}),[{price:25,size:4}]);
 assert.deepEqual(estimateFill([],10),{remaining:10,cost:0});
 assert.throws(()=>estimateFill([],0),/Invalid/);
});
