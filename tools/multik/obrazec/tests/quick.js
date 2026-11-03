const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--js-flags=--max-old-space-size=6000']});
const ctx=await b.newContext({viewport:{width:420,height:900}});
for (const run of [1,2]) { const p=await ctx.newPage(); let errs=0; p.on('pageerror',e=>{errs++;console.log('ERR',e.message)});
  const t0=Date.now(); await p.goto('http://127.0.0.1:8765/pub6/local.html#test');
  await p.waitForFunction(()=>!document.getElementById('go').disabled,null,{timeout:600000});
  const r=await p.evaluate(()=>[getComputedStyle(document.getElementById('ld')).display, document.getElementById('log').innerText.split('\n').slice(0,2).join(' | ')]);
  console.log('run',run,((Date.now()-t0)/1000).toFixed(0)+'s','errors',errs,JSON.stringify(r)); if(run===2) await p.screenshot({path:'/tmp/quick2.png'}); await p.close(); }
await b.close();})();
