// Вещь на ровном фоне для вырезки (обложка): node propstudio.js тип папка  → папка/тип_k.png и тип_g.png (чёрный и серый фон), дальше cutout.py
const {chromium}=require('playwright');const path=require('path');
(async()=>{const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:1400,height:1400}});p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+path.join(__dirname,'frame.html')+'#hq');await p.waitForFunction(()=>window.ready,null,{timeout:900000});
await p.evaluate(()=>{const c=document.getElementById('c');c.width=1400;c.height=1400;c.style.width='1400px';c.style.height='1400px';});
const ty=process.argv[2],out=process.argv[3]||'.';require('fs').mkdirSync(out,{recursive:true});
for(const [bg,suf] of [['#000000','k'],['#bfbfbf','g']]){await p.evaluate(([ty,bg])=>{MK3D._studio=bg;MK3D.propSheet(document.getElementById('c'),[ty],1);MK3D._studio=null;},[ty,bg]);
 const f=path.join(out,ty+'_'+suf+'.png');await p.locator('#c').screenshot({path:f,timeout:300000});console.log(f);}
await b.close();})();
