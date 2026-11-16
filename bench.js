// Замер: сколько миллисекунд на кадр серии (1920×1080, как в приложении: кадр → JPEG) в разных режимах браузера.
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const ENG=process.env.ENG, FRAME='file://'+path.join(ENG,'tools/multik/test/frame.html');
const txt=fs.readFileSync(process.argv[2],'utf8');
const OUT=path.join(__dirname,'status');fs.mkdirSync(OUT,{recursive:true});
const log=o=>{const s=typeof o==='string'?o:JSON.stringify(o);console.log(s);fs.appendFileSync(path.join(OUT,'result.txt'),s+'\n');};
const F=['--allow-file-access-from-files','--ignore-gpu-blocklist'];
const CFG={
  headed_metal:{headless:false,args:F.concat(['--use-angle=metal'])},
  newheadless_metal:{channel:'chromium',headless:true,args:F.concat(['--use-angle=metal','--enable-gpu'])},
  shell_metal:{headless:true,args:F.concat(['--use-angle=metal','--enable-gpu'])},
  swiftshader:{headless:true,args:['--allow-file-access-from-files','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']},
};
async function run(name,hq,n,wait){const t0=Date.now();let b;
  try{b=await chromium.launch(Object.assign({timeout:120000},CFG[name]));
    const p=await b.newPage({viewport:{width:1280,height:720}});const errs=[];p.on('pageerror',e=>errs.push(String(e.message).slice(0,200)));
    await p.goto(FRAME+(hq?'#hq':''));
    const gl=await p.evaluate(()=>{const c=document.createElement('canvas');const g=c.getContext('webgl2')||c.getContext('webgl');if(!g)return 'нет WebGL';const e=g.getExtension('WEBGL_debug_renderer_info');return e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):'?';});
    log({cfg:name,hq,renderer:gl});
    await p.waitForFunction(()=>window.ready,null,{timeout:wait*1000});
    const prep=await p.evaluate(()=>[window.ok3d,window.barsikOk,window.h6Ok,Math.round(window.h6T||0)]);
    const info=await p.evaluate(t=>setupText(t),txt);
    await p.evaluate(()=>{const c=document.getElementById('c');c.width=1920;c.height=1080;});
    const res=await p.evaluate(async n=>{const c=document.getElementById('c');const out=[];
      for(const start of [12,95]){const ts=[];let kb=0;
        for(let i=0;i<n+2;i++){const t=start+i/25;const a=performance.now();frame(t);const d=c.toDataURL('image/jpeg',.9);ts.push(Math.round(performance.now()-a));kb=Math.round(d.length*.75/1024);await new Promise(r=>setTimeout(r,0));}
        out.push({start,ms:ts,kb});}
      return out;},n);
    log({cfg:name,hq,ready_s:Math.round((Date.now()-t0)/1000),prep,dur:Math.round(info.dur),errors:(info.errors||[]).length,res,pageErrors:errs.slice(0,3)});
    const shot=await p.evaluate(()=>document.getElementById('c').toDataURL('image/jpeg',.85));
    fs.writeFileSync(path.join(OUT,name+(hq?'_hq':'_std')+'.jpg'),Buffer.from(shot.split(',')[1],'base64'));
  }catch(e){log({cfg:name,hq,fail:String(e.message||e).slice(0,400),after_s:Math.round((Date.now()-t0)/1000)});}
  finally{try{await b.close();}catch(e){}}}
(async()=>{for(const [name,hq,n,wait] of [['headed_metal',true,10,420],['newheadless_metal',true,10,420],['headed_metal',false,10,300],['shell_metal',true,6,420],['swiftshader',true,2,600]])await run(name,hq,n,wait);})();
