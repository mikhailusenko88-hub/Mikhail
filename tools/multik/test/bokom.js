// Кто стоит боком: node tools/multik/test/bokom.js сценарий.txt [шаг] [--hq] — угол героя к камере по кадрам (0 — лицом к зрителю), стоит/идёт, в кадре; стоя — не больше ~35°
const {chromium}=require('playwright');const fs=require('fs');
const file=process.argv[2],step=+(process.argv[3]||.5),hq=process.argv.includes('--hq');
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:1280,height:720}});p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+require('path').join(__dirname,'frame.html')+'?noh6'+(hq?'#hq':'#nobarsik'));await p.waitForFunction(()=>window.ready,null,{timeout:900000});
const info=await p.evaluate(t=>setupText(t),fs.readFileSync(file,'utf8'));console.error(JSON.stringify(info).slice(0,300));
await p.evaluate(()=>{const c=document.getElementById('c');c.width=192;c.height=108;});
const out=await p.evaluate(async st=>{const D=MK3D._dbg(),rc=MK3D.rigs(),names={};for(const id in TL.lib.characters)names[id]=TL.lib.characters[id].spec?TL.lib.characters[id].spec.name:TL.lib.characters[id].name;
 const prev={},res=[];for(let t=0;t<TL.dur;t+=st){frame(t);const cam=D.cam.position;const seg=TL.segs.find(s=>t>=s.t0&&t<s.t1);if(!seg||seg.kind!=='scene')continue;
  const row={t:+t.toFixed(2),sc:seg.idx,h:[]};for(const k in rc){const r=rc[k];if(!r.root.visible||!r.root.parent)continue;const wp=r.root.getWorldPosition(new D.THREE.Vector3());
   const az=Math.atan2(cam.x-wp.x,cam.z-wp.z);let d=r.yaw.rotation.y-az;d=Math.atan2(Math.sin(d),Math.cos(d));const mv=prev[k]!=null&&Math.abs(prev[k]-wp.x)>.02;prev[k]=wp.x;
   // в кадре?
   const v=wp.clone();v.y+=.5;v.project(D.cam);const inF=Math.abs(v.x)<1&&Math.abs(v.y)<1&&v.z<1;
   row.h.push([(r.spec&&r.spec.name)||k,Math.round(d*57.3),mv?1:0,inF?1:0]);}res.push(row);}return res;},step);
fs.writeFileSync(file.replace(/\.txt$/,'')+'.yaw.json',JSON.stringify(out));
// сводка: стоит (не идёт), в кадре, угол > 45°
let bad=0,tot=0;const runs=[];for(const r of out)for(const [n,a,mv,inF] of r.h){if(mv||!inF)continue;tot++;if(Math.abs(a)>45){bad++;runs.push(r.t+' '+n+' '+a);}}
console.log('стоят в кадре:',tot,'из них боком >45°:',bad,'('+Math.round(bad/Math.max(1,tot)*100)+'%)');console.log(runs.slice(0,40).join(' | '));
await b.close();})();
