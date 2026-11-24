const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const out=process.argv[2];const V=JSON.parse(process.env.V);
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:960,height:540}});p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+path.join(__dirname,'frame.html')+'?h6list=pik#hq');await p.waitForFunction(()=>window.ready,null,{timeout:900000});fs.mkdirSync(out,{recursive:true});
for(const [tag,bw] of V){await p.evaluate(([bw])=>{MKBarsik.BROW.happy=bw;const txt='СЕРИАЛ: Т\nСЕРИЯ: 1. Б\nПЕРСОНАЖ: Барсик — рыжий полосатый котёнок с синим шарфом, голос мальчика\nСЦЕНА: зима, день\nБарсик стоит.\nПАУЗА 3\n';
 const R=MKScript.parse(txt,{characters:{},locations:{}});const ep=R.episodes[0];const sc=ep.scenes[0];sc.cast.forEach(c=>{c.face='camera';c.x=.5;});const id=sc.cast[0].who;sc.steps=[{who:id,emotion:'happy',do:'nod'},{wait:2.5}];setup(ep);
 const c=document.getElementById('c');c.width=960;c.height=540;MK3D._studio='#9fa7ad';MK3D._vigOff=1;TL.segs.forEach(g=>{if(g.kind==='scene')g.cam=[{t:0,mode:'close',on:id,zoom:2.6,cut:true}];});frame(1.1);frame(1.2);},[bw]);
 await p.locator('#c').screenshot({path:path.join(out,tag+'.png')});console.log(tag);}
await b.close();})();
