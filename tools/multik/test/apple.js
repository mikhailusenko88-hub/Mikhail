// Голоса iPhone (Пик, Рон): что страница на самом деле отдаёт голосу. Настоящая multik.html, ударения по смыслу — как в телефоне
// (отдельная страница голоса), сам голос iPhone подставной: проверяем ТЕКСТ, который ему уходит.
// Правило (multik-audio.js, MK.appleRules): голос читает сам; только в словах из короткого списка и только при ударении на
// предпоследнем слоге в слово вставляется мягкий перенос (U+00AD) — голос читает его «по правилам». Транскрипции там нет.
//   node tools/multik/test/apple.js [--voice=папка с voice/ и ort/]
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');const http=require('http');
const args=process.argv.slice(2),opt=k=>{const a=args.find(x=>x.startsWith('--'+k+'='));return a?a.split('=').slice(1).join('='):null;};
const ROOT=path.resolve(__dirname,'../../../Resources/Mebel');
const VDIR=[opt('voice'),ROOT,'/home/claude/mv'].filter(Boolean).find(d=>fs.existsSync(path.join(d,'voice','homo.json'))&&fs.existsSync(path.join(d,'ort','ort.wasm.min.js')));
if(!VDIR){console.log('✘ нет файлов нейроголоса (ветка multik-voice): --voice=<папка>');process.exit(2);}
const SH='­';
// реплика Пика → что должно уйти голосу («¬» — мягкий перенос); остальное — без изменений
const CASES=[
 ['У реки стоял старый замок.','У реки стоял старый з¬амок.'],            // крепость: сам голос читает «замо́к»
 ['Смотрите, какой старый замок на двери!',null],                         // на двери — «замо́к», голос читает верно сам
 ['Кто-то мог слушать из леса.','Кто-то мог слушать из л¬еса.'],          // сам голос: «из леса́»
 ['Вокруг стояли высокие леса.',null],
 ['Может, это ключ от дома?','Может, это ключ от д¬ома?'],                // сам голос: «от дома́?»
 ['Мы весь день сидели дома, а у печи грелся кот.','Мы весь день сидели д¬ома, а у печи грелся кот.'],
 ['У неё светятся глаза!',null],                                          // глаза́ голос читает верно — не трогаем
 ['А вот это уже не пирог!',null],
 ['Смотрите! Волшебная дверь!',null],
 ['Замок стоял у самой реки.','З¬амок стоял у самой реки.'],
 ['Какой з+амок!','Какой з¬амок!'],                                       // свой «+» на слове из списка — тоже без транскрипции
 ['Привет, друзья! Пойдём к реке.',null],
];
const MIME={'.html':'text/html; charset=utf-8','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm'};
const srv=http.createServer((q,r)=>{const u=decodeURIComponent(q.url.split('?')[0]);const f=/^\/(voice|ort)\//.test(u)?path.join(VDIR,u):path.join(ROOT,u);
  fs.readFile(f,(e,d)=>{if(e){r.writeHead(404);r.end();return;}r.writeHead(200,{'Content-Type':MIME[path.extname(f)]||'application/octet-stream'});r.end(d);});});
(async()=>{await new Promise(r=>srv.listen(0,r));const port=srv.address().port;
const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--autoplay-policy=no-user-gesture-required']});
const p=await b.newPage({viewport:{width:430,height:900}});const errs=[];p.on('pageerror',e=>errs.push(e.message));
await p.addInitScript(()=>{window.MK_VOICE_PROC=true;});
let vp=null;const ENC=`const y=await MKVoice.speak(a.text,a.opts);const n=y.length,bb=new Uint8Array(n*2);for(let i=0;i<n;i++){let v=Math.max(-1,Math.min(1,y[i]));v=Math.round(v<0?v*32768:v*32767);bb[2*i]=v&255;bb[2*i+1]=(v>>8)&255;}let s='';for(let i=0;i<bb.length;i+=32768)s+=String.fromCharCode.apply(null,bb.subarray(i,i+32768));return{pcm:btoa(s),n:n,last:MKVoice.lastText||''};`;
await p.exposeFunction('__voiceSpeak',async a=>{try{if(!vp){vp=await (await b.newContext()).newPage();await vp.goto(`http://localhost:${port}/voice.html`);}
  return await vp.evaluate(new Function('a','return (async()=>{'+ENC+'})()'),a);}catch(e){return{error:String(e&&e.message||e)};}});
await p.exposeFunction('__voiceUnload',async()=>true);
await p.goto(`http://localhost:${port}/multik.html`);await p.waitForFunction(()=>typeof Lib!=='undefined'&&Lib.data&&window.MK&&MK.appleRules,null,{timeout:90000});
await p.evaluate(()=>{Mock.voiceSpeak=a=>window.__voiceSpeak(a);Mock.voiceUnload=()=>window.__voiceUnload();});
const txt='СЕРИАЛ: Кот Барсик\nСЕРИЯ: 1. Голос iPhone\nПЕРСОНАЖ: Пик — маленький серый мышонок с красным бантиком, голос девочки\nПЕРСОНАЖ: Рон — белый щенок в белой кепке, голос мальчика\nСЦЕНА: лес, день\n'+CASES.map((c,i)=>(i%2?'Рон':'Пик')+': '+c[0]).join('\n')+'\n';
const res=await p.evaluate(async({txt})=>{
  const r=MKScript.parse(txt,Lib.data);const ep=r.episodes[0];const v=await Lib.importText(JSON.stringify(ep));if(v.errors&&v.errors.length)return{err:'импорт: '+v.errors.join('; ')};
  const P=Lib.data.projects[Lib.data.projects.length-1],E=P.episodes[P.episodes.length-1];
  const sent=[];Mock.tts=a=>{sent.push({text:a.text,ipa:(a.voice&&a.voice.ipa)||null,ssml:(a.voice&&a.voice.ssml)||null,key:a.key,pitch:a.voice&&a.voice.pitch,rate:a.voice&&a.voice.rate});return null;};
  const lines=MK.collectLines(E.script,Lib.data).filter(l=>!l.srv&&!l.synth).map(l=>({text:l.text,key:l.key,pitch:l.voice.pitch,rate:l.voice.rate}));
  try{await prepare(E,null,null,true,{noHeroes:true});}catch(e){return{err:String(e&&e.message||e),sent,lines};}
  return{sent,lines};},{txt});
await b.close();srv.close();
if(res.err){console.log('✘',res.err);process.exit(1);}
let bad=0;const show=s=>s.replace(/­/g,'¬');
CASES.forEach((c,i)=>{const plain=c[0].replace(/\+/g,''),want=c[1]||plain;const s=res.sent.find(x=>x.text.replace(/­/g,'')===plain);const ln=res.lines.find(x=>x.text===plain);
  if(!s){bad++;console.log('✘ не ушло голосу:',plain);return;}
  const ok=show(s.text)===want&&!s.ssml&&!s.ipa&&ln&&s.pitch===ln.pitch&&s.rate===ln.rate&&(c[1]?s.key!==ln.key:s.key===ln.key);
  if(!ok)bad++;console.log((ok?'✔ ':'✘ ')+(c[1]?'правка:  ':'как было: ')+show(s.text)+(ok?'':'   ← ждали: '+want+(s.ipa?' (ушла транскрипция)':'')+(s.ssml?' (ушёл SSML)':'')));});
if(errs.length){bad++;console.log('✘ ошибки страницы:',errs.slice(0,3).join(' | '));}
console.log(bad?`ИТОГ: не так ${bad}`:`✔ голос iPhone: ${CASES.filter(c=>c[1]).length} реплик с правкой, ${CASES.filter(c=>!c[1]).length} без изменений — всё как задумано`);process.exit(bad?1:0);
})().catch(e=>{console.error(e);process.exit(1);});
