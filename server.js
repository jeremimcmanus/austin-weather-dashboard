import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const exec = promisify(execFile);
const root = fileURLToPath(new URL('./public/', import.meta.url));
// curl honors the cloud environment's HTTPS proxy and retains TLS verification.
export async function upstream(url) {
 const {stdout} = await exec('curl',['--fail-with-body','--silent','--show-error','--max-time','20','--max-filesize','5000000','-H','User-Agent: AustinWeatherDashboard/1.0',url],{maxBuffer:6000000});
 return JSON.parse(stdout);
}
export async function weather(fetcher=upstream) {
 const point = await fetcher('https://api.weather.gov/points/30.1831,-97.6799');
 const hourlyUrl = point.properties.forecastHourly;
 if (!hourlyUrl?.startsWith('https://api.weather.gov/')) throw new Error('Unexpected forecast source');
 const [forecast,observations] = await Promise.all([fetcher(hourlyUrl),fetcher('https://api.weather.gov/stations/KAUS/observations/latest')]);
 return {station:'KAUS',forecastUpdated:forecast.properties.updateTime||forecast.properties.updated||forecast.properties.generatedAt,periods:forecast.properties.periods,observation:observations.properties};
}
export async function markets(fetcher=upstream) {
 let cursor='', items=[];
 for(let page=0;page<10;page++) {
 const data=await fetcher('https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHAUS&status=open&limit=100'+(cursor?'&cursor='+encodeURIComponent(cursor):''));
 items.push(...(data.markets||[])); cursor=data.cursor;
 if(!cursor) return {markets:items};
 }
 throw new Error('Market pagination exceeded safe limit; refusing partial results');
}
export async function orderbook(ticker,fetcher=upstream) {
 if(!/^KXHIGHAUS-[A-Za-z0-9.-]+$/.test(ticker)) throw new Error('Invalid Austin market ticker');
 return fetcher('https://api.elections.kalshi.com/trade-api/v2/markets/'+encodeURIComponent(ticker)+'/orderbook?depth=20');
}
export function createServer(){return http.createServer(async(req,res)=>{
 const requestUrl=new URL(req.url,'http://localhost');const path=requestUrl.pathname;
 res.setHeader('X-Content-Type-Options','nosniff');
 if(path==='/healthz'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({status:'ok',tradingEnabled:false}));return;}
 if(path==='/api/backup/latest'){
 const directory=process.env.DATA_DIR||fileURLToPath(new URL('./data/',import.meta.url));
 try{const meta=JSON.parse(await readFile(join(directory,'backups','latest.json'),'utf8'));
 if(!/^snapshots-[0-9TZ]+\.sqlite\.gz$/.test(meta.file))throw Error('Invalid backup');
 const stream=createReadStream(join(directory,'backups',meta.file));
 stream.on('error',()=>{if(!res.headersSent){res.statusCode=503;res.end('Backup unavailable');}else res.destroy();});
 res.setHeader('Content-Type','application/gzip');res.setHeader('Content-Disposition','attachment; filename="'+meta.file+'"');res.setHeader('Cache-Control','no-store');stream.pipe(res);
 }catch{res.statusCode=503;res.end('Verified backup not yet available');}return;}
 if(path==='/api/research'){
 res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');try{const directory=process.env.DATA_DIR||fileURLToPath(new URL('./data/',import.meta.url));const {stdout}=await exec('python3',[fileURLToPath(new URL('./scripts/research.py',import.meta.url)),'status','--data-dir',directory],{timeout:20000,maxBuffer:500000});res.end(stdout);}catch{res.statusCode=503;res.end(JSON.stringify({error:'Research ledger unavailable',calibrationVerified:false}));}return;}
 if(path.startsWith('/api/trading-validation/')){
 res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');const ticker=path.slice('/api/trading-validation/'.length),side=requestUrl.searchParams.get('side')||'YES',quantity=Number(requestUrl.searchParams.get('quantity')||10);
 if(!/^KXHIGHAUS-[A-Za-z0-9.-]+$/.test(ticker)||!['YES','NO'].includes(side)||!Number.isInteger(quantity)||quantity<1||quantity>100000){res.statusCode=400;res.end(JSON.stringify({error:'Invalid Austin ticker, side, or integer quantity'}));return;}
 try{const eventTicker=ticker.split('-').slice(0,2).join('-');const [market,series,book,seriesFees,eventFees,currentWeather]=await Promise.all([upstream('https://api.elections.kalshi.com/trade-api/v2/markets/'+encodeURIComponent(ticker)),upstream('https://api.elections.kalshi.com/trade-api/v2/series/KXHIGHAUS'),upstream('https://api.elections.kalshi.com/trade-api/v2/markets/'+encodeURIComponent(ticker)+'/orderbook?depth=100').then(value=>({value,receivedAt:new Date().toISOString()})),upstream('https://api.elections.kalshi.com/trade-api/v2/series/fee_changes?series_ticker=KXHIGHAUS&show_historical=true').then(value=>({value,receivedAt:new Date().toISOString()})),upstream('https://api.elections.kalshi.com/trade-api/v2/events/fee_changes?event_ticker='+encodeURIComponent(eventTicker)+'&limit=100').then(value=>({value,receivedAt:new Date().toISOString()})),weather().then(value=>({value,receivedAt:new Date().toISOString()}))]);
 if(market.market?.ticker!==ticker||series.series?.ticker!=='KXHIGHAUS')throw Error('Unexpected source identity');
 const input={market:market.market,series:series.series,book:book.value,side,quantity,book_at:book.receivedAt,fee_context:{eventTicker,receivedAt:seriesFees.receivedAt<eventFees.receivedAt?seriesFees.receivedAt:eventFees.receivedAt,seriesChanges:seriesFees.value,eventChanges:eventFees.value},current_forecast_issued_at:currentWeather.value.forecastUpdated,forecast_received_at:currentWeather.receivedAt};const {stdout}=await exec('python3',[fileURLToPath(new URL('./scripts/trading_validation.py',import.meta.url)),'--input-json',JSON.stringify(input)],{timeout:20000,maxBuffer:300000});res.end(stdout);
 }catch{res.statusCode=502;res.end(JSON.stringify({error:'Verified-cost research quote unavailable',status:'BLOCKED',automaticTrading:false}));}return;}
 if(path==='/api/history'){res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');try{const {stdout}=await exec('python3',[fileURLToPath(new URL('./scripts/history_status.py',import.meta.url))],{timeout:15000,maxBuffer:100000});res.end(stdout);}catch{res.statusCode=503;res.end(JSON.stringify({error:'History status unavailable'}));}return;}
 if(path==='/api/weather'||path==='/api/markets'||path==='/api/series'||path.startsWith('/api/orderbook/')){
 res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
 try{const data=await(path==='/api/weather'?weather():path==='/api/markets'?markets():path==='/api/series'?upstream('https://api.elections.kalshi.com/trade-api/v2/series/KXHIGHAUS'):orderbook(decodeURIComponent(path.slice('/api/orderbook/'.length))));res.end(JSON.stringify({fetchedAt:new Date().toISOString(),...data}));}
 catch{res.statusCode=502;res.end(JSON.stringify({error:'Public source unavailable. Check network access or try again. Demo data is available separately.'}));}return;
 }
 const files={'/':'index.html','/app.js':'app.js','/math.js':'math.js','/review.js':'review.js','/cases.js':'cases.js','/style.css':'style.css'};
 if(!files[path]){res.writeHead(404);res.end('Not found');return;}
 try{res.setHeader('Content-Type',path.endsWith('.js')?'text/javascript':path.endsWith('.css')?'text/css':'text/html');res.end(await readFile(join(root,files[path])));}catch{res.writeHead(500);res.end('Unable to load application');}
 });}
if(process.argv[1]===fileURLToPath(import.meta.url)) createServer().listen(Number(process.env.PORT||3000),'0.0.0.0',()=>console.log('Austin weather dashboard listening on port '+(process.env.PORT||3000)));
