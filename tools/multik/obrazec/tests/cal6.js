const {chromium}=require('playwright');const fs=require('fs'),path=require('path');
const out=process.argv[2];const V=JSON.parse(process.argv[3]);const opts=JSON.parse(process.argv[4]||'{}');fs.mkdirSync(out,{recursive:true});
(async()=>{const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--js-flags=--max-old-space-size=6000']});
const p=await b.newPage({viewport:{width:1300,height:900}});
p.on('pageerror',e=>console.log('ERR',e.message));p.on('console',m=>{const t=m.text();if(m.type()==='error'||t.startsWith('OB'))console.log(m.type()[0],t.slice(0,300))});
await p.goto('http://127.0.0.1:8765/obrazec6.html');await p.waitForFunction(()=>window.ready,null,{timeout:60000});
console.log(JSON.stringify(await p.evaluate(o=>start(o),opts)));
await p.evaluate(()=>{OB.SHOTS.paw={pos:[0.5,0.45,0.78],look:[0.17,0.3,0.1],lens:70,fstop:5,focus:[0.18,0.3,0.12]};OB.SHOTS.feet={pos:[0.4,0.28,0.85],look:[0.06,0.05,0.1],lens:60,fstop:5,focus:[0.09,0.04,0.12]};OB.SHOTS.face={pos:[0.3,0.8,1.25],look:[0,0.72,0.1],lens:70,fstop:3,focus:'eye'};OB.SHOTS.front={pos:[0,0.74,1.35],look:[0,0.72,0.1],lens:70,fstop:3,focus:'eye'};});
for(const v of V){const ms=await p.evaluate(v=>{OB.DBG.value=v.dbg||0;OB.DBGS.value=v.dbgs||0;OB.showFur(v.fur!==false);const sh=v.hero?OB.heroShot(v.hero,v.kind):(v.kind==='anim'?OB.animShot(v.anim):v.kind);return OB.frame(sh,1280,720,v.anim||0,{anim:v.anim||0})},v);
 await p.locator('canvas').screenshot({path:path.join(out,v.name+'.png'),timeout:180000});console.log(v.name,Math.round(ms),'мс');}
await b.close();})();
