// Проверка «Просмотра» целиком, как на телефоне: настоящая страница multik.html, нейроголос рассказчика, «как в кино».
// Ловит ошибки и следит за памятью страницы: сколько заняла озвучка и вернулась ли память перед 3D-сценами.
// Запускать перед каждой установкой на телефон.
//   node tools/multik/test/smoke.js [сценарий.txt] [--voice=папка с voice/ и ort/ (ветка multik-voice)] [--std]
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');const http=require('http');const {execSync}=require('child_process');
const args=process.argv.slice(2),opt=k=>{const a=args.find(x=>x.startsWith('--'+k+'='));return a?a.split('=').slice(1).join('='):null;};
const FORCE_GC=args.includes('--gc');
const ROOT=path.resolve(__dirname,'../../../Resources/Mebel');
const scn=path.resolve(args.find(a=>!a.startsWith('--'))||path.join(__dirname,'smoke.txt'));
const VDIR=[opt('voice'),ROOT,'/home/claude/mv'].filter(Boolean).find(d=>fs.existsSync(path.join(d,'voice','voc.onnx'))&&fs.existsSync(path.join(d,'ort','ort.wasm.min.js')));
if(!VDIR){console.log('✘ нет файлов нейроголоса: git clone -b multik-voice https://github.com/mikhailusenko88-hub/Mikhail <папка> и --voice=<папка>');process.exit(2);}
if(!fs.existsSync(path.join(ROOT,'three.module.min.js'))){console.log('✘ нет three.module.min.js в Resources/Mebel (см. README)');process.exit(2);}
const MIME={'.html':'text/html; charset=utf-8','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm'};
const srv=http.createServer((q,r)=>{const u=decodeURIComponent(q.url.split('?')[0]);const f=/^\/(voice|ort)\//.test(u)?path.join(VDIR,u):path.join(ROOT,u);
  fs.readFile(f,(e,d)=>{if(e){r.writeHead(404);r.end();return;}r.writeHead(200,{'Content-Type':MIME[path.extname(f)]||'application/octet-stream'});r.end(d);});});
const procs=()=>{try{return execSync("ps -eo pid,rss,args | grep -- '--type=renderer' | grep -v grep").toString().trim().split('\n').map(l=>{const a=l.trim().split(/\s+/);return{pid:+a[0],mb:+a[1]/1024|0};});}catch(e){return[];}};
let mainPids=null; // процессы страницы «Мультиков» (голос — в своём процессе, как на iPhone)
const rss=()=>{const p=procs();const m=p.filter(x=>!mainPids||mainPids.has(x.pid));return m.length?Math.max(...m.map(x=>x.mb)):0;};
const vrss=()=>{const p=procs().filter(x=>mainPids&&!mainPids.has(x.pid));return p.length?Math.max(...p.map(x=>x.mb)):0;};
const PROC=!args.includes('--iframe');
(async()=>{await new Promise(r=>srv.listen(0,r));const port=srv.address().port;
const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--js-flags=--expose-gc','--autoplay-policy=no-user-gesture-required']});
const p=await b.newPage({viewport:{width:430,height:900}});const cdp=await p.context().newCDPSession(p);
if(PROC)await p.addInitScript(()=>{window.MK_VOICE_PROC=true;});
// «отдельная скрытая страница голоса» — как MultikVoiceHost в телефоне: свой процесс, закрывается после озвучки
let vctx=null,vp=null,vpeak=0;
const ENC=`const y=await MKVoice.speak(a.text,a.opts);const n=y.length,b=new Uint8Array(n*2);for(let i=0;i<n;i++){let v=Math.max(-1,Math.min(1,y[i]));v=Math.round(v<0?v*32768:v*32767);b[2*i]=v&255;b[2*i+1]=(v>>8)&255;}let s='';for(let i=0;i<b.length;i+=32768)s+=String.fromCharCode.apply(null,b.subarray(i,i+32768));return{pcm:btoa(s),n:n,last:MKVoice.lastText||''};`;
await p.exposeFunction('__voiceSpeak',async a=>{try{if(!vp){vctx=await b.newContext();vp=await vctx.newPage();await vp.goto(`http://localhost:${srv.address().port}/voice.html`);}
  const r=await vp.evaluate(new Function('a','return (async()=>{'+ENC+'})()'),a);vpeak=Math.max(vpeak,vrss());return r;}catch(e){return{error:String(e&&e.message||e)};}});
let voiceClosedAt=null;await p.exposeFunction('__voiceUnload',async()=>{if(vctx){const c=vctx;vctx=null;vp=null;await c.close();voiceClosedAt=Date.now();await new Promise(r=>setTimeout(r,700));marks['голос закрыт']=rss();}return true;});   // замер — пока страница ждёт ответа: героев «как в кино» она начнёт строить только после
const errs=[],dialogs=[];p.on('console',m=>{const t=m.text();if(/BARS|БАРС/.test(t))console.log('  '+t.slice(0,220));});p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>{if(m.type()==='error')errs.push('console: '+m.text().slice(0,200));});
p.on('dialog',d=>{dialogs.push(d.message().slice(0,160).replace(/\n/g,' | '));d.type()==='confirm'?d.dismiss():d.accept();});
await p.goto(`http://localhost:${port}/multik.html`);await p.waitForFunction(()=>window.MK3D&&MK3D.ready&&typeof Lib!=='undefined'&&Lib.data,null,{timeout:90000});
mainPids=new Set(procs().map(x=>x.pid));
await p.evaluate(()=>{Mock.voiceSpeak=a=>window.__voiceSpeak(a);Mock.voiceUnload=()=>window.__voiceUnload();});
const gc=async()=>{try{await cdp.send('HeapProfiler.collectGarbage');}catch(e){}};
const marks={};await p.exposeFunction('memMark',k=>{marks[k]=rss();});
await gc();const base=rss();
// память — каждые 300 мс, отдельно по этапам страницы
const mem={};let stage='',run=true,voicePeak=0,both=0;const t0=Date.now();
const poll=(async()=>{while(run){const s=await p.evaluate(()=>Mock._stage||'').catch(()=>stage);stage=s||stage;const k=/озвучка/.test(stage)?'озвучка':/сцены/.test(stage)?'сцены':/показ/.test(stage)?'показ':'прочее';const m=rss();mem[k]=Math.max(mem[k]||0,m);if(vctx){const sum=m+vrss();if(sum>both)both=sum;}if(!voiceClosedAt)voicePeak=Math.max(voicePeak,m);await new Promise(r=>setTimeout(r,300));}})();
const res=await p.evaluate(async({txt,hq,forceGc})=>{MK3D.setQuality(hq?'hq':'std');
  const r=MKScript.parse(txt,Lib.data);const ep=r.episodes[0];const v=await Lib.importText(JSON.stringify(ep));if(v.errors&&v.errors.length)return{err:'импорт: '+v.errors.join('; ')};
  Lib.data.settings=Object.assign(Lib.data.settings||{},{narrator:{voice:'albina',speaker:'ru_albina',soft:true,rate:1,pitch:1}});
  const P=Lib.data.projects[Lib.data.projects.length-1],E=P.episodes[P.episodes.length-1];
  window.__frameAfterVoice=null;const c0=MK.compile;MK.compile=function(...a){if(window.__frameAfterVoice===null){window.__frameAfterVoice=document.querySelectorAll('iframe').length;if(window.gc&&forceGc)gc();memMark('после озвучки');}return c0.apply(this,a);};
  const lines=MK.collectLines(E.script,Lib.data).filter(l=>l.srv).length;
  // «▶ Послушать» в настройках рассказчика: голос звучит и показывает ударения (омографы — по смыслу)
  const box=document.createElement('div');box.id='smokeAcc';document.body.appendChild(box);let pv=0;try{pv=await SrvVoice.preview('Старый замок стоял на высокой горе.','smokeAcc');}catch(e){pv=-1;}
  const pvText=box.textContent;box.remove();
  let neural=0,fallback=0;const g=SrvVoice.get.bind(SrvVoice);SrvVoice.get=async(ln,t)=>{const x=await g(ln,t);x&&x.buf?neural++:fallback++;return x;};
  const t=Date.now();await Player.open(E);const dur=(Date.now()-t)/1000;MK.compile=c0;
  const shown=getComputedStyle(document.getElementById('player')).display==='flex';const eb=document.getElementById('errbar');
  const out={pv,pvText,lines,neural,fallback,dur,shown,tl:Player.tl?Math.round(Player.tl.dur):0,frameAfterVoice:window.__frameAfterVoice,frames:document.querySelectorAll('iframe').length,errbar:eb&&eb.style.display!=='none'?eb.textContent:'',voiceErr:MKVoice.error};
  Player.stop();return out;},{txt:fs.readFileSync(scn,'utf8'),hq:!args.includes('--std'),forceGc:FORCE_GC});
const bars=await p.evaluate(()=>({h:window.BARSHeroes?BARSHeroes.log.join(' | '):null,ready:window.BARSHeroes?Object.keys(BARSHeroes.ready).filter(k=>BARSHeroes.ready[k]):[],soty:window.BARSSoty?BARSSoty.stats:null})).catch(()=>({}));
run=false;await poll;await gc();const end=rss();await b.close();srv.close();
if(res.err){console.log('✘',res.err);process.exit(1);}
const voiceUp=voicePeak-base,keep=(marks['голос закрыт']||marks['после озвучки']||end)-base,KEEP_MAX=280,PEAK_MAX=900,BOTH_MAX=1100;
console.log(`Сценарий: ${path.basename(scn)} · серия ${res.tl} с · просмотр готов за ${res.dur.toFixed(0)} с · ${args.includes('--std')?'обычное':'как в кино'}`);
console.log(`Голос: ${PROC?'отдельный процесс (как в телефоне), он занимал до '+vpeak+' МБ и закрыт':'рамка в той же странице (--iframe)'}`);
console.log(`Память страницы «Мультиков»: в начале ${base} МБ · озвучка до ${voicePeak} МБ · после озвучки ${marks['после озвучки']||'?'} МБ · 3D-сцены до ${mem['сцены']||'?'} МБ`);
console.log('БАРС: герои '+JSON.stringify(bars.ready)+' · '+(bars.h||'—')+' · соты '+JSON.stringify(bars.soty));
const ok=[];const chk=(c,t)=>{ok.push(c);console.log((c?'✔ ':'✘ ')+t);};
chk(!errs.length&&!res.errbar,'без ошибок'+(errs.length||res.errbar?': '+[res.errbar,...errs].filter(Boolean).slice(0,4).join(' | '):''));
chk(res.pv>1&&/Читает так/.test(res.pvText),'«▶ Послушать» рассказчика: '+(res.pv>0?res.pv.toFixed(1)+' с, '+res.pvText.replace('Читает так: ',''):'не звучит'));
chk(res.shown,'просмотр открылся');
if(!args.includes('--std')&&/ПЕРСОНАЖ: (Пик|Рон)/.test(fs.readFileSync(scn,'utf8')))chk((bars.ready||[]).length>0,'БАРС: Пик и Рон образца 6.2 готовы ('+(bars.ready||[]).join(', ')+')');
chk(res.lines===0||res.neural===res.lines,`рассказчик — нейроголос: ${res.neural} из ${res.lines} реплик`+(res.voiceErr?' ('+res.voiceErr+')':''));
chk(res.frameAfterVoice===0&&res.frames===0&&!vctx,'голос выгружен перед 3D');
chk((mem['сцены']||0)<PEAK_MAX,`пик памяти на 3D-сценах ${mem['сцены']||'?'} МБ (можно до ${PEAK_MAX})`);
chk(keep<KEEP_MAX,`память после озвучки вернулась: голос закрыт — занято +${keep} МБ сверх начала (можно до +${KEEP_MAX}; на озвучке было +${voiceUp}; с героями «как в кино» перед сценами — ${marks['после озвучки']||'?'} МБ)`);
chk(!both||both<BOTH_MAX,`страница и голос одновременно — до ${both} МБ (можно до ${BOTH_MAX}; в сборке 50 герои строились до озвучки — было около 1300)`);
if(dialogs.length)console.log('окна:',dialogs.slice(0,4).join(' || '));
console.log(ok.every(Boolean)?'ИТОГ: можно ставить':'ИТОГ: НЕ СТАВИТЬ — сначала исправить');process.exit(ok.every(Boolean)?0:1);})();
