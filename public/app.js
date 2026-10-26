import {retrospectiveCases,calibrationSummary,auditCase,auditCalibration} from '/cases.js';
import {reviewTrade} from '/review.js';
import {yesAsks,estimateFill} from '/math.js';
const $=s=>document.querySelector(s);
let validationGeneration=0,validationBookAt=null;
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const time=d=>new Date(d).toLocaleString('en-US',{timeZone:'America/Chicago',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
let currentMarkets=[],generation=0,depthGeneration=0,book=null,selectedTicker="",currentWeather=null,bookAt=null,reviewedBookAt=null;
function demo(){const start=new Date('2026-07-15T11:00:00-05:00');return {weather:{fetchedAt:start.toISOString(),forecastUpdated:start.toISOString(),periods:[89,92,94,96,97,98,98,97,95,92,89,87].map((temperature,i)=>({startTime:new Date(+start+i*3600000).toISOString(),temperature,temperatureUnit:'F',shortForecast:'Mostly Sunny'})),observation:{timestamp:start.toISOString(),temperature:{value:31.1}}},markets:{fetchedAt:start.toISOString(),markets:['94° or below','95° to 96°','97° to 98°','99° to 100°','101° or above'].map((title,i)=>({ticker:'DEMO-'+i,event_ticker:'DEMO-JUL15',title,yes_bid_dollars:[.03,.15,.40,.25,.07][i].toFixed(2),yes_ask_dollars:[.06,.19,.46,.30,.11][i].toFixed(2),rules_primary:'ILLUSTRATIVE ONLY. These are invented quotes and simplified contract labels, not actual Kalshi contracts. For live contracts, read all rules on Kalshi before using weather evidence.'}))}};}
function metric(label,value,detail){return `<article class="metric"><div class="label">${escape(label)}</div><div class="value">${escape(value)}</div><div class="detail">${escape(detail)}</div></article>`;}
function renderWeather(w){
 const p=(w?.periods||[]).filter(p=>Number.isFinite(p.temperature)).slice(0,24);
 const c=w?.observation?.temperature?.value;
 const obs=typeof c==='number'?Math.round(c*9/5+32)+'°':'—';
 const high=p.length?Math.max(...p.map(x=>x.temperatureUnit==='C'?x.temperature*9/5+32:x.temperature)):null;
 $('#metrics').innerHTML=metric('Latest observation',obs,w?.observation?.timestamp?`KAUS · ${time(w.observation.timestamp)} CT`:'KAUS · source unavailable')+metric('Next 24h forecast peak',high===null?'—':Math.round(high)+'°','Hourly forecast peak; not daily settlement')+metric('Market coverage',String(currentMarkets.length),'Open contracts returned · select event below')+metric('Forecast issued',w?.forecastUpdated?new Date(w.forecastUpdated).toLocaleTimeString('en-US',{timeZone:'America/Chicago',hour:'numeric',minute:'2-digit'}):'—',w?.forecastUpdated?time(w.forecastUpdated)+' CT':'Waiting for source');
 if(!p.length){$('#forecast').innerHTML='<div class="empty">Weather data unavailable. Refresh live sources or select the illustrative demo.</div>';return;}
 const values=p.map(x=>x.temperatureUnit==='C'?x.temperature*9/5+32:x.temperature),min=Math.floor((Math.min(...values)-3)/5)*5,max=Math.ceil((Math.max(...values)+3)/5)*5;
 const x=i=>45+i*610/Math.max(1,p.length-1),y=v=>200-(v-min)/(max-min)*170;
 const points=values.map((v,i)=>`${x(i)},${y(v)}`).join(' ');
 $('#forecast').innerHTML=`<svg class="chart" viewBox="0 0 680 240" role="img" aria-label="Hourly forecast in Fahrenheit, ranging from ${Math.min(...values)} to ${Math.max(...values)} degrees"><defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#cbdcca" stop-opacity=".8"/><stop offset="1" stop-color="#f9fcf6" stop-opacity=".2"/></linearGradient></defs>${[min,(min+max)/2,max].map(v=>`<line x1="40" x2="660" y1="${y(v)}" y2="${y(v)}" stroke="#e8eee5" stroke-dasharray="3 4"/><text x="4" y="${y(v)+4}">${v}°</text>`).join('')}<polygon points="45,200 ${points} 655,200" fill="url(#fill)"/><polyline points="${points}" fill="none" stroke="#4d7957" stroke-width="3" stroke-linejoin="round"/>${values.map((v,i)=>`<circle cx="${x(i)}" cy="${y(v)}" r="3" fill="#4d7957"><title>${escape(time(p[i].startTime))} CT: ${v}°F</title></circle>`).join('')}${p.map((v,i)=>i%Math.ceil(p.length/5)===0?`<text x="${x(i)}" y="226" text-anchor="middle">${escape(new Date(v.startTime).toLocaleTimeString('en-US',{timeZone:'America/Chicago',hour:'numeric'}))}</text>`:'').join('')}</svg>`;
}
function price(m,side){const dollars=m['yes_'+side+'_dollars'];if(dollars!==undefined&&dollars!==null&&dollars!=='')return Number(dollars)*100;const n=m['yes_'+side];return typeof n==='number'?n:null;}
function renderMarkets(){const ms=currentMarkets.filter(m=>m.event_ticker===$('#event').value);$('#markets').innerHTML=ms.length?ms.map(m=>{const bid=price(m,'bid'),ask=price(m,'ask'),valid=Number.isFinite(bid)&&Number.isFinite(ask)&&bid>=0&&ask<=100&&ask>=bid;return `<tr data-ticker="${escape(m.ticker)}"><td><button class="row-select" data-contract="${escape(m.ticker)}">Inspect</button> ${escape(m.yes_sub_title||m.subtitle||m.title)}<div class="muted">${escape(m.ticker)}</div></td><td class="price">${Number.isFinite(bid)?bid.toFixed(1)+'¢':'—'}</td><td class="price">${Number.isFinite(ask)?ask.toFixed(1)+'¢':'—'}</td><td>${valid?(ask-bid).toFixed(1)+'¢':'—'}</td><td>${valid?'Quote snapshot':'Incomplete or crossed quote'}</td></tr>`;}).join(''):'<tr><td colspan="5">No contracts available for this view.</td></tr>';
 $('#rules').textContent=ms.length?ms.map(m=>`${m.ticker}\n${m.rules_primary||'Primary rules were not provided. Verify full rules on Kalshi.'}${m.rules_secondary?'\n'+m.rules_secondary:''}`).join('\n\n'):'Live market rules will appear here when available.';
 if(ms.length&&!$('#mode').value.includes('demo')){const link=document.createElement('a');link.href='https://kalshi.com/markets/kxhighaus';link.target='_blank';link.rel='noopener noreferrer';link.textContent='Open Kalshi to verify full contract rules and current order books ↗';$('#rules').prepend(link,document.createElement('br'));}}
async function load(){if($('#validation-status'))invalidateValidation();invalidateReview();currentWeather=null;book=null;bookAt=null;++depthGeneration;const id=++generation;$('#refresh').disabled=true;$('#notice').className='notice';$('#notice').textContent='Fetching selected sources…';currentMarkets=[];renderWeather(null);renderMarkets();renderSeries(null,false);let w,m,series,fail=[];const isDemo=$('#mode').value==='demo';
 if(isDemo){const d=demo();w=d.weather;m=d.markets;series=null;}else{const results=await Promise.allSettled(['/api/weather','/api/markets','/api/series'].map(async url=>{const r=await fetch(url,{signal:AbortSignal.timeout(45000)});const d=await r.json();if(!r.ok)throw Error(d.error);return d;}));if(id!==generation)return;results.forEach((r,i)=>r.status==='fulfilled'?(i===0?w=r.value:i===1?m=r.value:series=r.value):fail.push(i===0?'NWS weather':i===1?'Kalshi markets':'Kalshi series metadata'));}
 ++depthGeneration;book=null;selectedTicker='';$('#depth').textContent='No contract selected. Fee schedule and settlement source: not independently verified.';currentMarkets=m?.markets||[];const events=[...new Set(currentMarkets.map(x=>x.event_ticker))].sort();$('#event').innerHTML=events.length?events.map(x=>`<option>${escape(x)}</option>`).join(''):'<option>No events available</option>';
 currentWeather=w;renderWeather(w);renderMarkets();renderSeries(series,isDemo);$('#notice').className='notice'+(fail.length?' error':'');$('#notice').textContent=isDemo?'DEMO MODE · Invented quotes and illustrative weather for July 15, 2026. Nothing on this view is live.':fail.length?`${fail.join(' and ')} unavailable. No demo data has been substituted. Check API access in environment settings, then refresh.`:`Public sources fetched ${time(m?.fetchedAt||w.fetchedAt)} CT. This is a snapshot; refresh for new quotes. Verify source timestamps and full settlement rules.`;$('#refresh').disabled=false;
}
if(new URLSearchParams(location.search).get('mode')==='demo') $('#mode').value='demo';
$('#mode').addEventListener('change',load);$('#refresh').addEventListener('click',load);$('#event').addEventListener('change',renderMarkets);load();

function renderDepth(){
 if(!book)return;
 const asks=yesAsks(book);
 const qty=Number($('#quantity').value),feeText=$('#fee').value,fee=feeText===''?null:Number(feeText);
 if(!Number.isInteger(qty)||qty<1||qty>100000||fee!==null&&(!Number.isFinite(fee)||fee<0)){$('#depth').textContent='Enter a whole quantity from 1 to 100,000 and a nonnegative total fee.';return;}
 const {remaining,cost}=estimateFill(asks,qty);
 const levels=asks.slice(0,8).map(x=>`${x.price.toFixed(2)}¢ × ${x.size} contracts`).join(' · ');
 $('#depth').textContent=`${selectedTicker} · ${$('#mode').value==='demo'?'ILLUSTRATIVE':'Source snapshot'}
YES asks: ${levels||'No visible ask depth'}
`+(remaining>0?`Insufficient visible liquidity: ${qty-remaining} of ${qty} contracts available. No complete fill estimate.`:`Estimated cost for ${qty} YES: $${(cost/100).toFixed(2)} before fees.`+(fee===null?' Enter a verified total fee to estimate full cost.':` With your entered total fee: $${((cost+fee)/100).toFixed(2)}; average ${((cost+fee)/qty).toFixed(2)}¢ per contract.`))+'\nFee amount is user supplied; no fee schedule or settlement verification is implied. Snapshot prices are not a fill guarantee.';
}
async function inspect(ticker){if(selectedTicker!==ticker){$('#review-probability').value='';$('#review-model-at').value='';}invalidateReview();bookAt=null;const request=++depthGeneration;selectedTicker=ticker;book=null;$('#fee').value='';$('#depth').textContent='Loading order book…';if($('#mode').value==='demo'){const ask=price(currentMarkets.find(m=>m.ticker===ticker),'ask');book={orderbook:{no:[[100-ask,8],[98-ask,22],[95-ask,40]]}};bookAt=new Date().toISOString();renderDepth();return;}try{const r=await fetch('/api/orderbook/'+encodeURIComponent(ticker),{signal:AbortSignal.timeout(30000)});if(!r.ok)throw Error();const data=await r.json();if(request!==depthGeneration)return;book=data;bookAt=data.fetchedAt;renderDepth();}catch{if(request===depthGeneration)$('#depth').textContent='Order book unavailable. No liquidity or execution estimate can be verified.';}}
$('#markets').addEventListener('click',e=>{const target=e.target.closest('[data-contract]');if(target)inspect(target.dataset.contract);});
$('#quantity').addEventListener('input',renderDepth);$('#fee').addEventListener('input',renderDepth);
$('#event').addEventListener('change',()=>{++depthGeneration;book=null;$('#depth').textContent='Select a contract in this event to inspect its order book.';});

function renderSeries(data,isDemo){
 const s=data?.series;
 $('#settlement').textContent=isDemo?'DEMO: settlement source is not verified. Never infer official settlement from this illustration.':s?`Kalshi names ${(s.settlement_sources||[]).map(x=>x.name).join(', ')||'an unspecified source'}. The NWS chart is a separate evidence feed; source outcomes, reporting windows, and revisions still need verification.`:'Series metadata unavailable. Settlement source remains unverified.';
 $('#series').replaceChildren();
 if(!s){$('#series').textContent='Settlement-source verification and exchange fee schedule: unavailable in this view.';return;}
 const text=document.createElement('p');text.textContent=`Exchange-declared settlement source: ${(s.settlement_sources||[]).map(x=>x.name).join(', ')}. Series fee type: ${s.fee_type??'unspecified'}; multiplier: ${s.fee_multiplier??'unspecified'}. This metadata alone does not establish the current fee formula or validate an official outcome.`;$('#series').append(text);
 for(const [label,url] of [...(s.settlement_sources||[]).map(x=>[x.name,x.url]),['Contract terms',s.contract_terms_url]]){try{const u=new URL(url);if(u.protocol!=='https:')continue;const a=document.createElement('a');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';a.textContent=label+' ↗';a.style.marginRight='18px';$('#series').append(a);}catch{}}
}

function invalidateReview(){reviewedBookAt=null;const el=$('#review-result');if(el)el.textContent='Inputs or source data changed. No current trade review; run the challenge again.';}
function numeric(id){const text=$(id).value.trim();return text===''?NaN:Number(text);}
function challenge(){
 const market=currentMarkets.find(m=>m.ticker===selectedTicker);
 const result=reviewTrade({book,side:$('#review-side').value,quantity:numeric('#quantity'),probability:numeric('#review-probability')/100,probabilityHaircut:numeric('#review-haircut')/100,totalFeeCents:numeric('#fee'),slippageCents:numeric('#review-slippage'),modelAt:$('#review-model-at').value,forecastAt:currentWeather?.forecastUpdated,bookAt,isDemo:$('#mode').value==='demo',marketOpen:['open','active'].includes(market?.status)&&Date.parse(market.close_time)>Date.now()});
 reviewedBookAt=bookAt;const target=$('#review-result');target.replaceChildren();
 const verdict=document.createElement('div');verdict.className='review-verdict';verdict.textContent=`${selectedTicker||'No contract selected'} · BUY ${$('#review-side').value} · ${result.status}`;target.append(verdict);
 if(result.metrics){const m=result.metrics,metrics=document.createElement('p');metrics.className='review-metrics';metrics.textContent=`Model scenario net edge: ${m.baseEdge.toFixed(2)}¢ / contract\nHaircut + extra cost scenario: ${m.stressEdge.toFixed(2)}¢ / contract\nEfficient-market counter-hypothesis: ${m.efficientEdge===null?'unavailable':m.efficientEdge.toFixed(2)+'¢ / contract'}\nStressed break-even win probability: ${(m.breakEven*100).toFixed(2)}%\nStressed loss if the position settles at zero: $${m.worstCaseLoss.toFixed(2)}`;target.append(metrics);}
 const list=document.createElement('ul');list.className='review-reasons';for(const reason of result.reasons){const li=document.createElement('li');li.textContent=reason.message;list.append(li);}target.append(list);
 const limitations=document.createElement('p');limitations.textContent=result.limits;target.append(limitations);
}
$('#review-run').addEventListener('click',challenge);
for(const id of ['#quantity','#fee','#review-side','#review-probability','#review-model-at','#review-haircut','#review-slippage'])$(id).addEventListener('input',invalidateReview);
$('#event').addEventListener('change',invalidateReview);

setInterval(()=>{if(reviewedBookAt&&Date.now()-Date.parse(reviewedBookAt)>60000)invalidateReview();},5000);

for(const record of retrospectiveCases){
 const report=auditCase(record),details=document.createElement('details'),summary=document.createElement('summary');summary.textContent=`${record.label} · ${record.side} · ${report.status}`;details.append(summary);
 const headline=document.createElement('p');headline.textContent=record.headline;details.append(headline);
 if(report.reportedSettlement){const outcome=document.createElement('p');outcome.textContent=`Retrieved exchange record: ${record.ticker} · ${report.reportedSettlement.status} · YES result: ${report.reportedSettlement.result}. Proposed NO payout: 0¢ per contract. Outcome is hindsight, excluded from decision-time calculations.`;details.append(outcome);const a=document.createElement('a');a.href=report.reportedSettlement.sourceUrl;a.target='_blank';a.rel='noopener noreferrer';a.textContent='Exchange API evidence ↗';details.append(a);}
 const list=document.createElement('ul');for(const note of [...report.notes,...report.blockers]){const li=document.createElement('li');li.textContent=note;list.append(li);}details.append(list);$('#regression-cases').append(details);
}
const calibrationList=document.createElement('ul');for(const note of auditCalibration(calibrationSummary)){const li=document.createElement('li');li.textContent=note;calibrationList.append(li);}$('#calibration-audit').append(calibrationList);

async function loadHistory(){
 try{const response=await fetch('/api/history',{signal:AbortSignal.timeout(20000)});if(!response.ok)throw Error();const h=await response.json();const c=h.collector;const age=c?.lastSuccessAt?(Date.now()-Date.parse(c.lastSuccessAt))/60000:null;
 $('#history-status').textContent=`${c?'Timer collector: '+c.state:'No supervised collector detected in this runtime.'}\nStored runs: ${h.runs} · snapshots: ${h.snapshots} · source errors: ${h.errors}\nLast successful full collection: ${c?.lastSuccessAt?time(c.lastSuccessAt)+' CT':'not established'}${age!==null&&age>30?' — STALE (over 30 minutes)':''}\nLatest stored response: ${h.lastReceivedAt?time(h.lastReceivedAt)+' CT':'none'}\nBackup: ${h.backup?.restoreVerified?time(h.backup.createdAt)+' CT · restore verified':'not yet verified'}${c?.backupError?' — BACKUP FAILURE: '+c.backupError:''}\nHistory persists across restarts only when DATA_DIR is on retained storage.${h.diskFreeBytes!==undefined&&h.diskFreeBytes<100*1024*1024?' WARNING: less than 100 MB free; storage needs operator attention.':''}`;
 const errorLines=(h.errorSummary||[]).map(e=>`${e.source}: ${e.count} × ${e.error} (latest ${time(e.lastAt)} CT)`);if(errorLines.length)$('#history-status').textContent+='\nHistorical error breakdown:\n'+errorLines.join('\n');
 const rows=(h.observationHistory||[]).slice(-12).reverse();$('#history-observations').innerHTML=rows.length?`<table><thead><tr><th>KAUS observed (CT)</th><th>Temperature</th><th>Archived (CT)</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${escape(time(r.observedAt))}</td><td>${escape(r.temperatureF)}°F</td><td>${escape(time(r.receivedAt))}</td></tr>`).join('')}</tbody></table>`:'';
 }catch{$('#history-status').textContent='Collector health unavailable. Continuous collection is not established for this runtime.';}
}
loadHistory();setInterval(loadHistory,60000);


function invalidateValidation(){validationBookAt=null;++validationGeneration;$('#validation-status').textContent='Contract, quantity, side, or source data changed. Run a fresh server-side check.';$('#validation-checks').replaceChildren();}
async function loadValidation(){
 const id=++validationGeneration;if(!selectedTicker||$('#mode').value==='demo'){$('#validation-status').textContent='Select a live Austin contract. Demo evidence cannot verify a trade.';return;}
 const side=$('#review-side').value,quantity=numeric('#quantity');$('#validation-status').textContent='Checking protected rule evidence, applicable fees, and fresh visible depth…';$('#validation-checks').replaceChildren();
 try{const response=await fetch('/api/trading-validation/'+encodeURIComponent(selectedTicker)+'?side='+side+'&quantity='+quantity,{signal:AbortSignal.timeout(60000)});const data=await response.json();if(id!==validationGeneration)return;if(!response.ok)throw Error(data.error);validationBookAt=data.bookReceivedAt;
 $('#validation-status').textContent=`${data.ticker} · ${side} × ${quantity} · ${data.status}\nAverage visible entry: ${data.averageEntryCents??'unknown'}¢ · unfilled quantity: ${data.unfilledQuantity}\nConservative fee upper bound: ${data.feeCents===null?'unavailable':data.feeCents+'¢'} · conservative net edge: ${data.conservativeEdgeCents===null?'not established':data.conservativeEdgeCents+'¢ / contract'}\nBlocks: ${data.blockers.join(', ')||'None; eligible for further review only'}\n${data.limits}`;
 const a=data.contractAudit,fees=data.feeAudit;const rows=[['Station mapping',a.checks.stationMapping],['Measurement window',a.checks.measurementWindow],['Source precision / rounding',a.checks.rounding],['Revision / fallback rules',a.checks.revisions]];
 $('#validation-checks').innerHTML=`<table><thead><tr><th>Evidence</th><th>Status</th><th>Recorded fact</th></tr></thead><tbody>${rows.map(([name,check])=>`<tr><td>${escape(name)}</td><td>${check.verified?'Verified against pinned evidence':'Unverified'}</td><td>${escape(check.value===null?'Unknown':typeof check.value==='object'?JSON.stringify(check.value):check.value)}</td></tr>`).join('')}<tr><td>Applicable fee rate</td><td>${fees.rateVerified?'Verified rate':'Unverified'}</td><td>${escape(fees.takerCoefficient??'Unknown')} · type ${escape(fees.exchangeFeeType)} · multiplier ${escape(fees.exchangeMultiplier)}</td></tr><tr><td>Rounding mechanics</td><td>${fees.roundingMechanicsVerified?'Verified docs':'Unverified'}</td><td>${escape(fees.roundingStatus??'Unknown')}</td></tr><tr><td>Account fee scope</td><td>${fees.verified?'Verified conservative bound':'Not fully verified'}</td><td>${escape(fees.accountType??'Account type not confirmed')} · event overrides ${fees.eventFeeContextVerified?'checked':'unverified'}</td></tr></tbody></table>`;
 if(data.feeScenariosCents){const p=document.createElement('p');p.className='muted';const f=data.feeScenariosCents;p.textContent=`Maximum-fragmentation fee bounds for this quantity: direct member ${f.directUpperBound}¢; non-direct exchange-only ${f.nonDirectExchangeUpperBound}¢ (additional broker charges unknown). ${f.qualifier}`;$('#validation-checks').append(p);}
 }catch{if(id===validationGeneration)$('#validation-status').textContent='Server-side validation unavailable. Recommendations remain blocked.';}
}
async function loadResearch(){
 try{const response=await fetch('/api/research',{signal:AbortSignal.timeout(30000)});if(!response.ok)throw Error();const data=await response.json();const report=data.reports?.[0];
 $('#research-status').textContent=`${data.status} · ${data.predictionCount??0} immutable prospective forecasts\n${report?'Frozen '+time(report.frozenAt)+' CT · '+(report.firstTargetDay?'holdout '+report.firstTargetDay+' through '+report.lastTargetDay:'waiting for first eligible future event')+'\nCompleted event days: '+report.completeEventDays+' / '+report.requiredHoldoutDays+' · verified training days: '+report.trainingDays+' / '+report.requiredTrainingDays+'\n'+report.blockers.join(' · '):'No experiment has issued forecasts yet. Complete future-day coverage, sufficient lead time, and fresh source data are required.'}\nHoldout scores remain hidden until the precommitted window is complete. No real out-of-sample profitability is claimed.`;
 const predictions=data.predictions||[];$('#research-predictions').innerHTML=predictions.length?`<table><thead><tr><th>Contract</th><th>Issued (CT)</th><th>Research YES</th><th>Stress range</th><th>Evidence status</th></tr></thead><tbody>${predictions.map(p=>`<tr><td>${escape(p.ticker)}</td><td>${escape(time(p.issuedAt))}</td><td>${(p.probabilityYes*100).toFixed(1)}%</td><td>${(p.lowerYes*100).toFixed(1)}–${(p.upperYes*100).toFixed(1)}%</td><td>${escape(p.status)}</td></tr>`).join('')}</tbody></table>`:'';
 }catch{$('#research-status').textContent='Research ledger unavailable; no calibrated model or edge is established.';}
}
$('#validation-refresh').addEventListener('click',loadValidation);
for(const selector of ['#quantity','#review-side','#mode','#event'])$(selector).addEventListener('input',invalidateValidation);
$('#markets').addEventListener('click',e=>{if(e.target.closest('[data-contract]'))invalidateValidation();});
loadResearch();setInterval(loadResearch,60000);

setInterval(()=>{if(validationBookAt&&Date.now()-Date.parse(validationBookAt)>60000)invalidateValidation();},5000);
