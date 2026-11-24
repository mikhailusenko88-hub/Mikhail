const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const out=process.argv[2];const V=JSON.parse(process.env.V);
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:960,height:540}});p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+path.join(__dirname,'frame.html')+'?h6list=pik#hq');await p.waitForFunction(()=>window.ready,null,{timeout:900000});fs.mkdirSync(out,{recursive:true});
for(const [tag,bw,tl,st,dt,sy,ll,lc] of V){await p.evaluate(([bw,tl,st,dt,sy,ll,lc])=>{if(lc!=null)MKBarsik.LAUGH_LIDC=lc;MKBarsik.BROW.happy=bw;MKBarsik.TILT.happy=tl;if(sy!=null)MKBarsik.SMILE_Y=sy;if(ll!=null)MKBarsik.LAUGH_LID=ll;if(ll===0.0001)MKBarsik.LAUGH_FLIP=false;const txt='СЕРИАЛ: Т\nСЕРИЯ: 1. Б\nПЕРСОНАЖ: Барсик — рыжий полосатый котёнок с синим шарфом, голос мальчика\nСЦЕНА: зима, день\nБарсик стоит.\nПАУЗА 3\n';
 const R=MKScript.parse(txt,{characters:{},locations:{}});const ep=R.episodes[0];const sc=ep.scenes[0];sc.cast.forEach(c=>{c.face=st._face||'camera';c.x=.5;});const id=sc.cast[0].who;const st2=Object.assign({},st);delete st2._face;sc.steps=[Object.assign({who:id},st2),{wait:2.5}];ep.titleCard=false;ep.endCard=false;ep.subscribe=false;setup(ep);
 const c=document.getElementById('c');c.width=960;c.height=540;MK3D._studio='#9fa7ad';MK3D._vigOff=1;TL.segs.forEach(g=>{if(g.kind==='scene')g.cam=[{t:0,mode:'close',on:id,zoom:2.6,cut:true}];});
 const sp=(TL.speech||[]).find(x=>x.who===id);const sg=TL.segs.find(g=>g.kind==='scene');const t=(sp?sp.t:(sg?sg.t0:0))+dt;frame(Math.max(0,t-.1));frame(t);},[bw,tl,st,dt,sy,ll,lc]);
 await p.locator('#c').screenshot({path:path.join(out,tag+'.png')});console.log(tag);}
await b.close();})();
