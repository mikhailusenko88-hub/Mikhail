// Проверка фоновой сборки без телефона: очередь серий, обрыв куска видео (перемотка), ошибка и продолжение с того же кадра, отмена.
// node tools/multik/test/build.js   (телефонный «писатель» заменён подставным: куски по 10 кадров)
const {chromium}=require('playwright');const fs=require('fs');
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});const p=await b.newPage({viewport:{width:430,height:900}});
const errs=[];p.on('pageerror',e=>errs.push(e.message));const dialogs=[];p.on('dialog',d=>{dialogs.push(d.type()+': '+d.message().slice(0,90).replace(/\n/g,' | '));d.type()==='confirm'?d.dismiss():d.accept();});
await p.goto('file://'+require('path').resolve(__dirname,'../../../Resources/Mebel/multik.html'));await p.waitForFunction(()=>window.MK3D&&MK3D.ready,{timeout:60000});
const res=await p.evaluate(async(txt)=>{MK3D.setQuality('std');
 const add=async(n)=>{const r=MKScript.parse(txt.replace('СЕРИЯ: 1.','СЕРИЯ: '+n+'.'),Lib.data);const ep=r.episodes[0];const v=await Lib.importText(JSON.stringify(ep));return v.errors&&v.errors.length?v.errors:null;};
 const e1=await add(1),e2=await add(2),e3=await add(3);
 Lib.data.settings=Object.assign(Lib.data.settings||{},{res:720,fps:6});
 // имитация писателя на телефоне: куски по 10 кадров, перемотка при неверном номере
 const W={done:[],cur:0,frames:0,log:[],failAt:-1,throwAt:-1,ends:[]};const sum=()=>W.done.reduce((a,b)=>a+b,0);
 Object.assign(Mock,{audioChunk:()=>true,keepAwake:()=>true,buildDone:()=>{W.log.push('buildDone');return true},thermal:()=>0,share:()=>true,
  videoBegin:(a)=>{if(!a.resume){W.done=[];}W.cur=0;W.frames=sum();W.log.push('begin '+a.name+' resume='+a.resume+' from='+W.frames);return{ok:true,frames:W.frames}},
  videoFrame:(a)=>new Promise((res,rej)=>setTimeout(()=>{
   if(a.i===W.throwAt){W.throwAt=-1;rej(new Error('нет записи'));return;}
   if(a.i!==W.frames){res(-W.frames-1);return;}
   if(a.i===W.failAt){W.failAt=-1;W.cur=0;W.frames=sum();W.log.push('кусок оборвался на '+a.i+' → '+W.frames);res(-W.frames-1);return;}
   W.cur++;W.frames++;if(W.cur>=10){W.done.push(W.cur);W.cur=0;}res(1);},5)),
  videoEnd:()=>{if(W.cur)W.done.push(W.cur);W.cur=0;W.ends.push(sum());return{path:'video/x'+W.ends.length+'.mp4'}},
  videoCancel:(a)=>{if(a&&a.keep){if(W.cur)W.done.push(W.cur);W.cur=0;W.log.push('keep '+sum());}else{W.done=[];W.cur=0;W.log.push('cancel');}return true}});
 const P=Lib.data.projects[0],E=n=>P.episodes.find(e=>e.episode===n);
 const N=Math.ceil(MK.compile(E(1).script,Lib.data,{}).dur*6);
 // 1) серия 1 с обрывом куска на 25-м кадре, во время неё в очередь — серия 2
 W.failAt=25;const run=Build.run(P,E(1));await new Promise(r=>setTimeout(r,300));
 const bar1=getComputedStyle(document.getElementById('bbar')).display;Build.run(P,E(2));
 App.tab='series';App.render(true);const btns=[...document.querySelectorAll('#main [data-a]')].map(b=>b.textContent.trim()).filter(t=>/Собира|очеред|Продолж|Собрать|Пересоб/.test(t));
 const blockedPlay=(()=>{let m='';const o=window.alert;window.alert=t=>m=t;Player.open(E(3));window.alert=o;return m.slice(0,40);})();
 await run;const after1={ends:W.ends.slice(),q:Lib.data.settings.buildQueue.length,busy:Build.busy,st1:E(1).status,st2:E(2).status,bar:getComputedStyle(document.getElementById('bbar')).display};
 // 2) серия 3: ошибка на 30-м кадре → готовое сохранено → «Собрать» ещё раз → продолжение
 W.throwAt=30;await Build.run(P,E(3));const held={q:Lib.data.settings.buildQueue.map(j=>j.episode),job:!!Lib.data.settings.buildJob,state:Build.state(P,E(3)),done:sum()};
 await Build.run(P,E(3));const after3={ends:W.ends.slice(),st3:E(3).status,q:Lib.data.settings.buildQueue.length,job:!!Lib.data.settings.buildJob};
 // 3) отмена
 const r4=Build.run(P,E(1));await new Promise(r=>setTimeout(r,400));const oc=window.confirm;window.confirm=()=>true;await Build.askCancel();window.confirm=oc;await r4;
 const after4={q:Lib.data.settings.buildQueue.length,job:!!Lib.data.settings.buildJob,busy:Build.busy};
 return{N,bar1,btns,blockedPlay,after1,held,after3,after4,log:W.log};},fs.readFileSync(require('path').resolve(__dirname,'tiny.txt'),'utf8'));
console.log(JSON.stringify(res,null,1));console.log('dialogs',dialogs);console.log('errors',errs.slice(0,5));await b.close();})();
