// Отрывок мультика кадрами подряд: node clip.js сценарий.txt --from=9 --dur=5 --fps=24 --out=папка [--fast]
// --fast — без MSAA и сглаживания (быстрее в swiftshader). Кадры: <out>/f_0000.png …, потом ffmpeg.
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const args=process.argv.slice(2),opt=(k,d)=>{const a=args.find(x=>x.startsWith('--'+k+'='));return a?a.split('=').slice(1).join('='):d;};
const file=args.find(a=>!a.startsWith('--')),from=+opt('from',0),dur=+opt('dur',5),fps=+opt('fps',24),out=opt('out','clip'),fast=args.includes('--fast');
(async()=>{const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:1280,height:720}});p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+path.join(__dirname,'frame.html')+(process.env.H6?'?'+process.env.H6:'')+'#hq');await p.waitForFunction(()=>window.ready,null,{timeout:900000});
const info=await p.evaluate(t=>setupText(t),fs.readFileSync(file,'utf8'));console.log('серия',info.dur,'с');
if(fast)await p.evaluate(()=>MK3D.lowMem(true));if(process.env.EVAL)console.log('eval',await p.evaluate(process.env.EVAL));
fs.mkdirSync(out,{recursive:true});const n=Math.round(dur*fps);const t0=Date.now();
const [pk,pn]=(opt('part','0/1')).split('/').map(Number);
for(let i=0;i<n;i++){if(i%pn!==pk)continue;const f=path.join(out,'f_'+String(i).padStart(4,'0')+'.png');if(fs.existsSync(f))continue;const t=from+i/fps;
  await p.evaluate(t=>frame(t),t);await p.locator('#c').screenshot({path:f+'.tmp.png',timeout:600000});fs.renameSync(f+'.tmp.png',f);
  const el=(Date.now()-t0)/1000;console.log('кадр',i+1,'из',n,'·',el.toFixed(0),'с');}
await b.close();})();
