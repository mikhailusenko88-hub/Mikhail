// Кадры сценария в заданные секунды: T="10.5,31" node _kadry.js сценарий.txt папка
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const [file,out]=process.argv.slice(2);const txt=fs.readFileSync(file,'utf8');const TS=(process.env.T||'1').split(',').map(Number);
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:960,height:540}});p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+path.join(__dirname,'frame.html')+'?h6list='+(process.env.H6||'pik,ron,topa,fila')+'#hq');await p.waitForFunction(()=>window.ready,null,{timeout:900000});fs.mkdirSync(out,{recursive:true});
await p.evaluate((txt)=>{const R=MKScript.parse(txt,{characters:{},locations:{}});const ep=R.episodes[0];ep.titleCard=false;ep.endCard=false;ep.subscribe=false;setup(ep);const c=document.getElementById('c');c.width=960;c.height=540;},txt);
for(const t of TS){await p.evaluate(t=>{frame(Math.max(0,t-.1));frame(t);},t);await p.locator('#c').screenshot({path:path.join(out,`t_${t}.png`)});console.log(t);}
await b.close();})();
