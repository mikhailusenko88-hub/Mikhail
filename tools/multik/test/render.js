// Кадры мультика без телефона: node render.js серия.json|сценарий.txt [--hq] [--out=папка] 5 12.5 30
// Нужны: playwright (Chromium), three.module.min.js в Resources/Mebel.
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const args=process.argv.slice(2);const hq=args.includes('--hq');const outA=args.find(a=>a.startsWith('--out='));const out=outA?outA.slice(6):'.';
const pos=args.filter(a=>!a.startsWith('--'));const file=pos[0];const times=pos.slice(1).map(Number);
(async()=>{const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:1280,height:720}});
p.on('pageerror',e=>console.log('ERR',e.message));p.on('console',m=>{if(m.type()==='error')console.log('C',m.text().slice(0,300))});
await p.goto('file://'+path.join(__dirname,'frame.html')+(process.env.H6?'?'+process.env.H6:'')+(hq?'#hq':''));await p.waitForFunction(()=>window.ready,null,{timeout:900000});
console.log('h6',await p.evaluate(()=>[window.h6Ok,Math.round(window.h6T||0),window.BARSHeroes&&BARSHeroes.log.join(' | ')]));
console.log("3d",await p.evaluate(()=>window.ok3d),"barsik",await p.evaluate(()=>[window.barsikOk,window.MKBarsik&&MKBarsik.error]));
const src=fs.readFileSync(file,'utf8');
const info=file.endsWith('.json')?await p.evaluate(e=>setup(e),JSON.parse(src)):await p.evaluate(t=>setupText(t),src);
console.log(JSON.stringify(info).slice(0,1500));
if(process.env.EVAL)console.log('eval',await p.evaluate(process.env.EVAL));
fs.mkdirSync(out,{recursive:true});
for(const t of (times.length?times:[2,10,30])){await p.evaluate(t=>frame(t),t);const f=path.join(out,(hq?'hq_':'f_')+t+'.png');await p.locator('#c').screenshot({path:f,timeout:180000});console.log(f);}
if(process.env.EVAL2)console.log('eval2',JSON.stringify(await p.evaluate(process.env.EVAL2)));
await b.close();})();
