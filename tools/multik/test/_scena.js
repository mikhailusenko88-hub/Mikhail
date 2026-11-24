// Кадры серии по сценарию каждые STEP с: node _scena.js сценарий.txt папка [STEP=1] → папка/f_XXX.png и лист sheet.jpg (через python)
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const [file,out,stepA]=process.argv.slice(2);const STEP=+(stepA||1);const txt=fs.readFileSync(file,'utf8');
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:960,height:540}});p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+path.join(__dirname,'frame.html')+'?h6list=pik,ron,topa,fila#hq');await p.waitForFunction(()=>window.ready,null,{timeout:900000});fs.mkdirSync(out,{recursive:true});
const r=await p.evaluate((txt)=>{const R=MKScript.parse(txt,{characters:{},locations:{}});const ep=R.episodes[0];ep.titleCard=false;ep.endCard=false;ep.subscribe=false;const s=setup(ep);const c=document.getElementById('c');c.width=960;c.height=540;
  const sg=TL.segs.filter(g=>g.kind==='scene');return {dur:TL.dur,t0:sg.length?sg[0].t0:0,err:(s&&s.errors)||R.errors,sp:(TL.speech||[]).map(x=>[x.who,+x.t.toFixed(2)])};},txt);
console.log(JSON.stringify(r));
let k=0;for(let t=r.t0+0.5;t<r.dur-0.2;t+=STEP){await p.evaluate(t=>{frame(Math.max(0,t-.1));frame(t);},t);await p.locator('#c').screenshot({path:path.join(out,`f_${String(k).padStart(3,'0')}_${t.toFixed(1)}.png`)});k++;}
console.log('кадров',k);await b.close();})();
