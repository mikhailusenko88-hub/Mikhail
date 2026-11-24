// Элементы обложки локально (как шаг «Элементы обложки» студии): герой лицом в камеру, два фона (чёрный и серый) для вырезки.
//   NODE_PATH=/opt/npm-tools/node_modules node tools/multik/test/elementy.js папка герои [W]
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const a=process.argv.slice(2);const out=a[0]||'.';const heroes=(a[1]||'barsik').split(',');const W=+(a[2]||1280),H=Math.round(W*9/16);
const NM={barsik:'Барсик',ron:'Рон',pik:'Пик',fila:'Филя',topa:'Топа'};
const DESC={barsik:'рыжий полосатый котёнок с синим шарфом, голос мальчика',ron:'серый щенок в белой кепке с красным ошейником, голос мальчика',pik:'маленький серый мышонок с розовым бантиком, голос девочки',fila:'маленький белый зайчонок с голубым шарфом, голос мальчика',topa:'маленький коричневый медвежонок с зелёным шарфом, голос мальчика'};
const SHOTS=JSON.parse(process.env.SHOTS||'[["ulyb",{"emotion":"happy","do":"nod"},"close",1.2],["ulybm",{"emotion":"happy","do":"nod"},"medium",1.2]]');
(async()=>{const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:W,height:H}});p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+path.join(__dirname,'frame.html')+'?h6list='+heroes.filter(h=>h!=='barsik').concat(['pik']).join(',')+'#hq');await p.waitForFunction(()=>window.ready,null,{timeout:1800000});
fs.mkdirSync(out,{recursive:true});
for(const h of heroes){const txt=`СЕРИАЛ: Тест\nСЕРИЯ: 1. Э\nПЕРСОНАЖ: ${NM[h]} — ${DESC[h]}\nСЦЕНА: ${process.env.LOC||'зима, день'}\n${NM[h]} стоит.\nПАУЗА 3\n`;
 for(const [tag,st,cam,t] of SHOTS){await p.evaluate(([txt,st,cam,W,H])=>{const R=MKScript.parse(txt,{characters:{},locations:{}});const ep=R.episodes[0];const sc=ep.scenes[0];sc.cast.forEach(c=>{c.face='camera';c.x=.5;});const id=sc.cast[0].who;
   sc.steps=[Object.assign({who:id},st),{wait:2.5}];Object.assign(ep,{titleCard:false,endCard:false,subscribe:false,autoCam:false,main:false,mainSet:false,subtitles:false});setup(ep);const c=document.getElementById('c');c.width=W;c.height=H;MK3D._vigOff=1;
   TL.segs.forEach(g=>{if(g.kind==='scene')g.cam=[{t:0,mode:cam,on:id,cut:true}];});},[txt,st,cam,W,H]);
  for(const [bg,suf] of [['#000000','A'],['#bfbfbf','B']]){await p.evaluate(([t,bg])=>{MK3D._studio=bg;frame(Math.max(0,t-.1));frame(t);},[t,bg]);
   const f=path.join(out,`${h}_${tag}_${suf}.png`);await p.locator('#c').screenshot({path:f,timeout:300000});console.log(f);} }}
await b.close();})();
