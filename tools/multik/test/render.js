// Кадры мультика без телефона: node render.js серия.json|сценарий.txt [--hq] [--out=папка] 5 12.5 30
// Нужны: playwright (Chromium), three.module.min.js в Resources/Mebel.
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const args=process.argv.slice(2);const hq=args.includes('--hq');const outA=args.find(a=>a.startsWith('--out='));const out=outA?outA.slice(6):'.';
const pos=args.filter(a=>!a.startsWith('--'));const file=pos[0];const times=pos.slice(1).map(Number);
(async()=>{const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:1280,height:720}});
p.on('pageerror',e=>console.log('ERR',e.message));p.on('console',m=>{if(m.type()==='error')console.log('C',m.text().slice(0,300))});
await p.goto('file://'+path.join(__dirname,'frame.html')+(hq?'#hq':''));await p.waitForFunction(()=>window.ready,null,{timeout:60000});
console.log('3d',await p.evaluate(()=>window.ok3d));
const src=fs.readFileSync(file,'utf8');
const info=file.endsWith('.json')?await p.evaluate(e=>setup(e),JSON.parse(src)):await p.evaluate(t=>setupText(t),src);
console.log(JSON.stringify(info).slice(0,1500));
fs.mkdirSync(out,{recursive:true});
for(const t of (times.length?times:[2,10,30])){await p.evaluate(t=>frame(t),t);const f=path.join(out,(hq?'hq_':'f_')+t+'.png');await p.locator('#c').screenshot({path:f,timeout:180000});console.log(f);}
await b.close();})();
