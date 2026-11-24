// Мимика героев студии (heroes6) для обложек: крупно, лицом в камеру, ровный фон. Варианты эмоций без речи и с речью.
//   NODE_PATH=/opt/npm-tools/node_modules node tools/multik/test/ulybka.js папка [герои=barsik,ron,pik,fila,topa] [ZOOM]
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const a=process.argv.slice(2);const out=a[0]||'.';const heroes=(a[1]||'barsik').split(',');const zoom=+(a[2]||3.2);
const NM={barsik:'Барсик',ron:'Рон',pik:'Пик',fila:'Филя',topa:'Топа'};
const DESC={barsik:'рыжий полосатый котёнок с синим шарфом, голос мальчика',ron:'серый щенок в белой кепке с красным ошейником, голос мальчика',pik:'маленький серый мышонок с розовым бантиком, голос девочки',fila:'маленький белый зайчонок с голубым шарфом, голос мальчика',topa:'маленький коричневый медвежонок с зелёным шарфом, голос мальчика'};
const SHOTS=JSON.parse(process.env.SHOTS||'[["udiv",{"emotion":"surprised","say":"Ого-о-о!"},0.374],["rad_say",{"emotion":"happy","say":"Ура-а-а!"},0.374],["rad",{"emotion":"happy","do":"nod"},1.2],["smeh",{"emotion":"laugh","do":"nod"},1.2],["likuet",{"emotion":"happy","do":"cheer"},0.6]]');
(async()=>{const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:1280,height:720}});p.on('pageerror',e=>console.log('ERR',e.message));p.on('console',m=>{const t=m.text();if(m.type()==='error'||/студия|ulyb/.test(t))console.log('C',t.slice(0,300))});
await p.goto('file://'+path.join(__dirname,'frame.html')+'?h6list='+heroes.join(',')+'#hq');await p.waitForFunction(()=>window.ready,null,{timeout:1800000});
console.log('h6',await p.evaluate(()=>[window.h6Ok,window.h6T]));
fs.mkdirSync(out,{recursive:true});
for(const h of heroes){const txt=`СЕРИАЛ: Тест\nСЕРИЯ: 1. Улыбка\nПЕРСОНАЖ: ${NM[h]} — ${DESC[h]}\nСЦЕНА: луг, день\n${NM[h]} стоит.\nПАУЗА 3\n`;
 for(const [tag,st,t] of SHOTS){const r=await p.evaluate(([txt,st,z])=>{const R=MKScript.parse(txt,{characters:{},locations:{}});const ep=R.episodes[0];const sc=ep.scenes[0];sc.cast.forEach(c=>{c.face='camera';c.x=.5;});const id=sc.cast[0].who;
   sc.steps=[Object.assign({who:id},st),{wait:2.5}];ep.titleCard=false;ep.endCard=false;ep.subscribe=false;const s=setup(ep);const c=document.getElementById('c');c.width=960;c.height=540;MK3D._studio='#9fa7ad';MK3D._vigOff=1;
   TL.segs.forEach(g=>{if(g.kind==='scene')g.cam=[{t:0,mode:'close',on:Object.keys(g.C)[0],zoom:z,cut:true}];});const sp=(TL.speech||[]).find(x=>x.who===id);const sg=TL.segs.find(g=>g.kind==='scene');return {dur:TL.dur,sp:sp?sp.t:null,t0:sg?sg.t0:0,err:s.errors};},[txt,st,zoom]);
  const tt=(r.sp!=null?r.sp+t:r.t0+t);await p.evaluate(t=>{frame(Math.max(0,t-.1));frame(t);},tt);
  const f=path.join(out,`${h}_${tag}.png`);await p.locator('#c').screenshot({path:f,timeout:300000});console.log(f,JSON.stringify(r),tt);}}
await b.close();})();
