// Проверка озвучки без телефона: реплики → «голос» (подставной звук вместо iPhone) → смех/возгласы → сведение. Печатает каждую реплику, её время и громкость в итоговой дорожке.
// node tools/multik/test/audio.js сценарий.txt
const {chromium}=require('playwright');const fs=require('fs');
(async()=>{const b=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required','--allow-file-access-from-files']});const p=await b.newPage();p.on('pageerror',e=>console.log('ERR',e.message));p.on('console',m=>console.log('C',m.text().slice(0,200)));
await p.goto('file://'+require('path').resolve(__dirname,'frame.html'));await p.waitForFunction(()=>window.ready);
const res=await p.evaluate(async(txt)=>{const r=MKScript.parse(txt,{characters:{},locations:{}});const ep=r.episodes[0];const lib={characters:{},locations:{}};const v=MK.validate(ep,lib);for(const c of v.newChars)lib.characters[c.id]={spec:c,code:c._code};for(const l of v.newLocs)lib.locations[l.id]={spec:l,code:l._code};
 const sr=44100;const fake=(text,pitch)=>{const dur=.12+text.length*.06,n=Math.ceil(dur*sr),b=new AudioBuffer({length:n,numberOfChannels:1,sampleRate:sr}),d=b.getChannelData(0);const f0=180*(pitch||1);let ph=0;for(let i=0;i<n;i++){const t=i/sr;ph+=f0/sr;const env=Math.min(1,t/.02)*Math.min(1,(dur-t)/.03)*(.6+.4*Math.sin(t*2*Math.PI*4));let x=0;for(let h=1;h<12;h++)x+=Math.sin(2*Math.PI*ph*h)/h*(h==3||h==4?2:1);d[i]=x*.15*env;}return b;};
 const lines=MK.collectLines(ep,lib);const audio={},bufs={};const log=[];
 for(const ln of lines){ if(audio[ln.key])continue; let buf;
   if(ln.synth){ buf=await MK.makeVocal(ln,lib,async(cmd,body)=>({wav:body.text}),async w=>fake(w,(ln.voice||{}).pitch)); }
   else { buf=await MK.voiceFx(fake(ln.text,(ln.voice||{}).pitch),ln.fx||MK.VOICE_FX.natural); }
   bufs[ln.key]=buf;audio[ln.key]={dur:buf.duration,env:MK.envelope(buf)};log.push([ln.who,ln.synth||'',ln.short?'short':'',ln.text,+buf.duration.toFixed(2)]); }
 const tl=MK.compile(ep,lib,audio);const mix=await MK.mixAudio(tl,bufs);const d=mix.getChannelData(0);
 const rms=(a,b)=>{let s=0,n=0;for(let i=Math.floor(a*sr);i<Math.min(d.length,b*sr);i++){s+=d[i]*d[i];n++;}return +(Math.sqrt(s/Math.max(1,n))).toFixed(3);};
 const sp=tl.speech.map(s=>[s.who,s.vocal?'VOCAL':'',s.text.slice(0,30),+s.t.toFixed(2),+s.dur.toFixed(2),rms(s.t,s.t+s.dur)]);
 return {log,sp,sfx:tl.sfx.map(s=>s.n)};},fs.readFileSync(process.argv[2],'utf8'));
console.log(JSON.stringify(res,null,0).replace(/\],\[/g,'],\n['));await b.close();})();
