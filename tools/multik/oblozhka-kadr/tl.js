const fs=require('fs'),vm=require('vm');const M=require('path').resolve(__dirname,'../../../Resources/Mebel')+'/';
const ctx={console,setTimeout,clearTimeout,Math,Date,JSON,performance:{now:()=>Date.now()}};ctx.globalThis=ctx;vm.createContext(ctx);
for(const f of ['multik-engine.js','multik-audio.js','multik-maker.js','multik-script.js'])try{vm.runInContext(fs.readFileSync(M+f,'utf8'),ctx)}catch(e){}
const r=ctx.MKScript.parse(fs.readFileSync(process.argv[2],'utf8'),{characters:{},locations:{}},{});
const ep=r.episodes[0];const tl=ctx.MK.compile(ep,{characters:Object.assign({},...(r.newChars||[]).map(c=>({[c.id]:{spec:c}}))),locations:{}},{});
console.log('intro',JSON.stringify(tl.intro));
tl.segs.forEach((s,i)=>console.log('seg',i,(s.t0||0).toFixed(1),(s.t1||0).toFixed(1),JSON.stringify(s.cam||'').slice(0,400)));
for(const sp of tl.speech)console.log('speech',sp.t.toFixed(1),(sp.t+sp.dur).toFixed(1),sp.who,sp.text.slice(0,40));
