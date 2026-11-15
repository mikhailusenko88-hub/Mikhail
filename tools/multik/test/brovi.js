// Брови Барсика по эмоции («как в кино», multik-barsik.js → MKBarsik.BROW): крупно, лицом в камеру, ровный фон.
//   node tools/multik/test/brovi.js [папка] [время …]   (по умолчанию: brovi.txt, кадры 2.6 — «радостно», 4.6 — «удивлённо», 9.5 — без ремарки)
//   BROW='{}' — сравнить «как было» (без бровей); ZOOM=4 — крупность.
// Радостно — брови ровные или чуть дугой вверх; удивлённо — подняты целиком, без наклона к переносице; ни при одной — внутренние концы не выше наружных.
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const a=process.argv.slice(2);const out=a[0]||'.';const times=(a.length>1?a.slice(1):['2.6','4.6','9.5']).map(Number);
(async()=>{const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:1280,height:720}});p.on('pageerror',e=>console.log('ERR',e.message));p.on('console',m=>{if(m.type()==='error')console.log('C',m.text().slice(0,300))});
await p.goto('file://'+path.join(__dirname,'frame.html')+'?noh6#hq');await p.waitForFunction(()=>window.ready,null,{timeout:900000});
console.log(await p.evaluate(t=>{const r=MKScript.parse(t,{characters:{},locations:{}});const ep=r.episodes[0];(ep.scenes[0].cast||[]).forEach(c=>{c.face='camera';c.x=.5;});return JSON.stringify(setup(ep));},fs.readFileSync(path.join(__dirname,'brovi.txt'),'utf8')));
await p.evaluate(z=>{const c=document.getElementById('c');c.width=960;c.height=540;MK3D._studio='#9fa7ad';MK3D._vigOff=1;TL.segs[0].cam=[{t:0,mode:'close',on:Object.keys(TL.segs[0].C)[0],zoom:z,cut:true}];},+(process.env.ZOOM||4));
if(process.env.BROW)await p.evaluate(B=>{MKBarsik.BROW=B;},JSON.parse(process.env.BROW));
fs.mkdirSync(out,{recursive:true});
for(const t of times){await p.evaluate(t=>frame(t),t);const st=await p.evaluate(()=>{const rc=MK3D.rigs();for(const k in rc)if(rc[k].bars){const B=rc[k].bars;return {brow:[B.U.uBrow.value.x,B.U.uBrow.value.y,B.U.uBrow.value.z].map(v=>+v.toFixed(4)),lid:+B.lid.toFixed(2)};}return null;});
 const f=path.join(out,'brovi_'+t+'.png');await p.locator('#c').screenshot({path:f,timeout:180000});console.log(f,JSON.stringify(st));}
await b.close();})();
