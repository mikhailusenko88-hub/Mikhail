// Несколько вариантов одного кадра в одной странице: node variants.js сценарий.txt t out "js1" "js2" ...
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const [file,t,out,...vars]=process.argv.slice(2);
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:1280,height:720}});p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+path.join(__dirname,'frame.html')+(process.env.H6?'?'+process.env.H6:'')+'#hq');await p.waitForFunction(()=>window.ready,null,{timeout:900000});
await p.evaluate(x=>setupText(x),fs.readFileSync(file,'utf8'));fs.mkdirSync(out,{recursive:true});
for(let i=0;i<vars.length;i++){await p.evaluate(vars[i]);await p.evaluate(t=>frame(t),+t);await p.evaluate(t=>frame(t),+t);await p.locator('#c').screenshot({path:path.join(out,'v'+i+'.png'),timeout:600000});console.log('вариант',i,vars[i]);}
await b.close();})();
