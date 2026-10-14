// User-supplied decision evidence, plus separately retrieved exchange-reported finalized outcomes.
export const calibrationSummary={
 window:['2026-08-09','2026-10-07'],pairedDays:34,sourceDays:{'The Weather Company':29,NWS:5},trainingDays:20,holdoutDays:9,
 reportedLogLoss:[0.258,0.099],reportedBrier:[0.0178,0.0033],
 target:'Settlement-source calibration; not demonstrated contract win-probability calibration',independentlyVerified:false
};
export const retrospectiveCases=[
 {id:'austin-2026-10-08',label:'Austin · Oct 8 · 92–93°F',family:'KXHIGHAUS',ticker:"KXHIGHAUS-26OCT08-B92.5",reportedSettlement:{"status":"finalized","result":"yes","closeTime":"2026-10-09T06:00:00Z","sourceUrl":"https://api.elections.kalshi.com/trade-api/v2/markets?event_ticker=KXHIGHAUS-26OCT08&limit=100","rulesPrimary":"If the maximum temperature recorded at Austin (CLIAUS) for Oct 8, 2026, is between 92-93\u00b0 fahrenheit according to The Weather Company, then the market resolves to Yes.","floorStrike":92,"capStrike":93,"proposedSidePayoutCents":0},side:'NO',quantity:null,budgetUSD:null,probabilityRange:[.55,.70],priceRangeCents:null,
 forecast:{rangeF:[90,90],issuedAt:'2026-10-08T06:54:00-05:00',station:'KAUS',source:'NWS'},decisionAt:null,book:null,fees:null,
 status:'NOT SUBSTANTIATED',headline:'A modest forecast error reaches the alleged losing band; an observation cannot establish the settled maximum.',
 notes:['A ±2°F sensitivity around 90°F spans 88–92°F and touches the reported 92–93°F band. Exact strike inclusivity and rounding remain unknown. This stress is not a probability distribution.',
 'The later 91.4°F observation is neither an official daily maximum nor proof it was available at the original decision. Do not use it as hindsight evidence.',
 'Approximately 66% YES does not establish a 34¢ executable NO ask. That complement requires a contemporaneous executable YES bid, with sufficient size.',
 'The 55–70% NO range is explicitly uncalibrated. Source-mapping statistics do not validate this trade probability.']},
 {id:'austin-2026-10-07',label:'Austin · Oct 7 · 91–92°F',family:'KXHIGHAUS',ticker:"KXHIGHAUS-26OCT07-B91.5",reportedSettlement:{"status":"finalized","result":"yes","closeTime":"2026-10-08T06:00:00Z","sourceUrl":"https://api.elections.kalshi.com/trade-api/v2/markets?event_ticker=KXHIGHAUS-26OCT07&limit=100","rulesPrimary":"If the maximum temperature recorded at Austin (CLIAUS) for Oct 7, 2026, is between 91-92\u00b0 fahrenheit according to The Weather Company, then the market resolves to Yes.","floorStrike":91,"capStrike":92,"proposedSidePayoutCents":0},side:'NO',quantity:null,budgetUSD:[150,175],probabilityRange:[.65,.75],priceRangeCents:[34,40],
 forecast:{rangeF:[87,88],issuedAt:null,referencedAt:'2026-10-07T12:53:00-05:00',station:'KAUS',source:'NWS'},decisionAt:null,book:null,fees:null,
 status:'NOT SUBSTANTIATED',headline:'The attractive apparent discount rests on an unvalidated probability and an indicative price, not reconstructable execution.',
 notes:['A ±2°F sensitivity around the reported 87–88°F forecast spans 85–90°F, below the alleged 91–92°F band. That supports the direction only under this chosen bound; larger errors, reporting differences, and remaining daytime warming are unresolved.',
 'The 12:53 p.m. reference and 87°F observation do not authenticate the forecast issue time or model timestamp. An instantaneous observation does not cap the eventual daily maximum.',
 'Conditional arithmetic only: 65–75% minus an indicative 34–40¢ entry gives 25–41¢ gross expected value per contract. The probability, fill, fees, and timing have not been verified, so this is not an established edge.',
 '$150–$175 is a proposed allocation, not a quantity. No contract count or executable fill is inferred from that budget. A losing position can lose the entire spend.']},
 {id:'los-angeles-2026-10-07',label:'Los Angeles · Oct 7 · 91°F+',family:null,ticker:null,side:'YES',quantity:null,budgetUSD:null,probabilityRange:[.60,.65],priceRangeCents:null,
 forecast:null,decisionAt:null,book:null,fees:null,status:'NOT SUBSTANTIATED',headline:'Settlement location, threshold, and source are unresolved; neither pricing nor model evidence can be reconstructed.',
 notes:['A city forecast cannot be silently mapped to an airport, downtown station, or other settlement location.',
 'No exact ticker, executable ask, depth, forecast archive, or independently calibrated probability is available. No net edge can be calculated.']},
 {id:'miami-2026-10-07',label:'Miami · Oct 7 · measurable rain',family:null,ticker:null,side:'YES',quantity:null,budgetUSD:null,probabilityRange:[.88,.92],priceRangeCents:null,
 forecast:null,decisionAt:null,book:null,fees:null,status:'WITHDRAWN',headline:'Withdrawn for settlement interpretation risk; high claimed rain probability cannot repair an undefined event.',
 notes:['Verify the exact gauge/station, accumulation period, measurable threshold, treatment of trace rainfall, and revision policy. Rain somewhere in Miami is not necessarily the contract event.',
 'The 88–92% estimate is unverified. No pricing, executable depth, or timestamped probability supports a review. Keep this candidate withdrawn.']}
];
export function auditCalibration(summary){
 const objections=[];
 const accounted=summary.trainingDays+summary.holdoutDays;
 if(accounted!==summary.pairedDays)objections.push(`${summary.pairedDays-accounted} of ${summary.pairedDays} paired days are not explained by the reported training/holdout split. Reconcile exclusions and target definitions.`);
 if(Object.keys(summary.sourceDays).length>1)objections.push('Mixed settlement sources require per-source labels and a documented historical rule-change timeline; do not treat them as interchangeable outcomes.');
 objections.push('Nine holdout days cannot establish stable station/season/threshold calibration or trading profitability. Inspect individual predictions, base rates, leakage, tuning, and uncertainty.');
 objections.push('Reported score improvements have not been reproduced from raw rows. Identify the scored target and baseline before relating them to a trade win probability.');
 return objections;
}
export function auditCase(record){
 const blockers=[];
 if(!record.ticker)blockers.push('Exact contract ticker, strike inclusivity, expiration, and historical rules are missing.');
 else blockers.push('Exchange-reported identity and final rules are recovered, but the decision-time rule version and underlying settlement publication are not independently authenticated.');
 if(!Number.isInteger(record.quantity)||record.quantity<=0)blockers.push('Contract quantity is unspecified; a dollar budget is not a quantity.');
 if(!record.decisionAt)blockers.push('Decision/quote capture time is unknown, so decision-time forecast freshness cannot be reconstructed.');
 if(!record.book)blockers.push('No archived executable order book supports a quantity-weighted fill or efficient-market price comparison.');
 if(record.fees===null)blockers.push('Applicable transaction fees, rounding, slippage, and worst-case fill are unverified.');
 blockers.push('No independently validated event probability or conservative probability bound is available. A ±2°F forecast perturbation does not supply one.');
 return {id:record.id,status:record.status,blockers,notes:record.notes,reportedSettlement:record.reportedSettlement||null,netEdge:null,eligibleForBuy:false};
}
