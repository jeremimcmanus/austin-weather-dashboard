export function yesAsks(book) {
 const fp=book.orderbook_fp;
 const raw=fp?.no_dollars??book.orderbook?.no??[];
 return raw.map(([price,size])=>({price:Math.round((100-(fp?Number(price)*100:Number(price)))*10000)/10000,size:Number(size)}))
 .filter(x=>Number.isFinite(x.price)&&x.price>=0&&x.price<=100&&Number.isFinite(x.size)&&x.size>0).sort((a,b)=>a.price-b.price);
}
export function estimateFill(asks,quantity) {
 if(!Number.isInteger(quantity)||quantity<1||quantity>100000)throw Error('Invalid quantity');
 let remaining=quantity,cost=0;
 for(const level of asks){const take=Math.min(remaining,level.size);cost+=take*level.price;remaining-=take;if(remaining<=1e-9){remaining=0;break;}}
 return {remaining,cost};
}
