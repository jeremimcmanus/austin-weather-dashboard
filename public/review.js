import {estimateFill} from './math.js';
export function asksForSide(book,side){
 if(!['YES','NO'].includes(side))throw Error('Choose YES or NO');
 const fp=book?.orderbook_fp;
 const key=side==='YES'?'no':'yes';
 const raw=fp?.[key+'_dollars']??book?.orderbook?.[key];
 if(!Array.isArray(raw))return [];
 return raw.map(([p,q])=>({price:Math.round((100-(fp?Number(p)*100:Number(p)))*10000)/10000,size:Number(q)})).filter(x=>Number.isFinite(x.price)&&x.price>=0&&x.price<=100&&Number.isFinite(x.size)&&x.size>0).sort((a,b)=>a.price-b.price);
}
export function reviewTrade(input){
 const {book,side,quantity,probability,probabilityHaircut,totalFeeCents,slippageCents,modelAt,forecastAt,bookAt,now=Date.now(),settlementVerified=false,calibrationVerified=false,feeScheduleVerified=false,isDemo=false,marketOpen=false}=input;
 const reasons=[];
 const fail=(code,message)=>reasons.push({code,message});
 if(isDemo)fail('demo','Illustrative data cannot substantiate a trade.');
 if(!marketOpen)fail('market','Market is not confirmed open and before its close time.');
 if(!settlementVerified)fail('settlement','Settlement source, station, date, threshold/rounding, reporting window, and revision rules are not independently verified. NWS cannot substitute for the declared Weather Company source.');
 if(!feeScheduleVerified)fail('fee_verification','The entered fee has not been checked against the applicable current fee schedule, order type, rounding, and quantity.');
 if(!calibrationVerified)fail('calibration','No verified out-of-sample calibration for this station, lead time, season, and contract threshold. Treat model confidence as unproven.');
 const age=(stamp,limit,code,label)=>{const t=Date.parse(stamp);const minutes=(now-t)/60000;if(!Number.isFinite(minutes)||minutes<0||minutes>limit)fail(code,`${label} missing, future-dated, or older than the review limit (${limit} minutes).`);return Number.isFinite(minutes)?minutes:null;};
 const ages={book:age(bookAt,1,'book_age','Order-book receipt'),forecast:age(forecastAt,120,'forecast_age','Weather forecast issue'),model:age(modelAt,120,'model_age','Model issue')};
 if(Number.isFinite(Date.parse(modelAt))&&Number.isFinite(Date.parse(forecastAt))&&Date.parse(modelAt)<Date.parse(forecastAt))fail('model_update','Model predates the displayed forecast; it may not incorporate the latest weather evidence.');
 if(!Number.isFinite(probability)||probability<0||probability>1)fail('probability','A model probability for the selected side between 0 and 100% is required.');
 if(!Number.isFinite(probabilityHaircut)||probabilityHaircut<0||probabilityHaircut>1)fail('haircut','An explicit probability haircut between 0 and 100 percentage points is required.');
 if(!Number.isFinite(totalFeeCents)||totalFeeCents<0)fail('fees','Verified total transaction fees are missing; zero must be explicitly justified, not assumed.');
 if(!Number.isFinite(slippageCents)||slippageCents<0)fail('slippage','A nonnegative extra execution-cost buffer per contract is required.');
 let fill=null;const asks=asksForSide(book,side);
 try{fill=estimateFill(asks,quantity);if(fill.remaining>0)fail('depth',`Visible depth cannot fill ${quantity} contracts: short ${fill.remaining}. No complete trade cost is established.`);}catch{fail('quantity','Quantity must be a whole number between 1 and 100,000.');}
 let metrics=null;
 if(fill&&fill.remaining===0&&[probability,probabilityHaircut,totalFeeCents,slippageCents].every(Number.isFinite)&&probability>=0&&probability<=1&&probabilityHaircut>=0&&probabilityHaircut<=1&&totalFeeCents>=0&&slippageCents>=0){
 const averageCost=fill.cost/quantity+totalFeeCents/quantity;
 const stressedCost=averageCost+slippageCents;
 const conservativeProbability=Math.max(0,probability-probabilityHaircut);
 // Midpoint is a counter-hypothesis only, never a calibrated probability or fill price.
 const opposingAsks=asksForSide(book,side==='YES'?'NO':'YES');
 const bestBid=opposingAsks.length?100-opposingAsks[0].price:null;
 const midpoint=bestBid===null||bestBid>asks[0].price?null:(bestBid+asks[0].price)/200;
 const baseEdge=probability*100-averageCost;
 const stressEdge=conservativeProbability*100-stressedCost;
 const efficientEdge=midpoint===null?null:Math.min(conservativeProbability,midpoint)*100-stressedCost;
 metrics={averageCost,stressedCost,conservativeProbability,baseEdge,stressEdge,efficientEdge,marketMidpoint:midpoint,breakEven:stressedCost/100,worstCaseLoss:Math.max(0,quantity*stressedCost/100)};
 if(baseEdge<=0)fail('base_edge','Even the supplied model probability does not cover the depth-weighted entry cost and fees.');
 if(stressEdge<=0)fail('stress_edge','The estimated edge disappears under the probability haircut and execution buffer.');
 if(midpoint===null)fail('market_prior','A coherent two-sided market is missing; the efficient-market counter-hypothesis cannot be evaluated.');
 else if(efficientEdge<=0)fail('efficient_market','The edge fails if the market midpoint is closer to the truth than the model. This is a competing hypothesis, not proof that the midpoint is correct.');
 }
 return {status:reasons.length?'NOT SUBSTANTIATED':'SURVIVES CONFIGURED CHECKS — NOT A TRADE RECOMMENDATION',reasons,metrics,ages,limits:'Age limits (book 1 minute; forecast/model 120 minutes) and stress inputs are review policy, not empirically validated guarantees. Receipt time does not prove exchange quote freshness. Hold-to-settlement costs exclude any early exit fees.'};
}
