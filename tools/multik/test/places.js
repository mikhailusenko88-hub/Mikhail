// Все места подряд: node places.js сценарий.txt [--hq] [--out=папка] [--at=0.5] [--only=3,5]
// снимает по кадру из середины каждой сцены (или в доле --at), печатает место и время сцены.
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const args=process.argv.slice(2);const hq=args.includes('--hq');const outA=args.find(a=>a.startsWith('--out='));const out=outA?outA.slice(6):'.';
const atA=args.find(a=>a.startsWith('--at='));const at=atA?+atA.slice(5):.5;const onA=args.find(a=>a.startsWith('--only='));const only=onA?onA.slice(7).split(',').map(Number):null;
const W=+((args.find(a=>a.startsWith('--w='))||'--w=1280').slice(4));
const file=args.filter(a=>!a.startsWith('--'))[0];
(async()=>{const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:W,height:Math.round(W*9/16)}});
p.on('pageerror',e=>console.log('ERR',e.message));p.on('console',m=>{if(m.type()==='error'||m.text().startsWith('#'))console.log('C',m.text().slice(0,300))});
await p.goto('file://'+path.join(__dirname,'frame.html')+(hq?'#hq':''));await p.waitForFunction(()=>window.ready,null,{timeout:60000});
await p.evaluate(w=>{const c=document.getElementById('c');c.width=w;c.height=Math.round(w*9/16);},W);
const info=await p.evaluate(t=>setupText(t),fs.readFileSync(file,'utf8'));console.log(JSON.stringify(info).slice(0,400));
const segs=await p.evaluate(()=>TL.segs.map((s,i)=>({i,kind:s.kind,t0:s.t0,t1:s.t1,l:s.lspec?(s.lspec.type+' '+(s.lspec.time||'day')):''})));
fs.mkdirSync(out,{recursive:true});let n=0;
for(const s of segs){if(s.kind!=='scene')continue;n++;if(only&&!only.includes(n))continue;const t=s.t0+(s.t1-s.t0)*at;const t0=Date.now();
 await p.evaluate(t=>frame(t),t);const f=path.join(out,String(n).padStart(2,'0')+'_'+s.l.replace(' ','_')+'.png');await p.locator('#c').screenshot({path:f,timeout:300000});console.log(f,((Date.now()-t0)/1000).toFixed(1)+'s');}
await b.close();})();
