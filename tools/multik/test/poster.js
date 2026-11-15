// Обложка-постер серии в облаке (как кнопка «🖼 Обложка» в приложении): node poster.js сценарий.txt [--hq] [--out=папка]
// Для облака Барсика, Пика и Рона добавить в сценарий строками ПЕРСОНАЖ (в тестовой библиотеке их нет).
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const args=process.argv.slice(2);const hq=args.includes('--hq');const outA=args.find(a=>a.startsWith('--out='));const out=outA?outA.slice(6):'.';
const file=args.filter(a=>!a.startsWith('--'))[0];
(async()=>{const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const p=await b.newPage({viewport:{width:1280,height:720}});const T0=Date.now();
p.on('pageerror',e=>console.log('ERR',e.message));p.on('console',m=>{const t=m.text();if(m.type()==='error')console.log('C',t.slice(0,300));else if(t.startsWith('[poster]'))console.log(Math.round((Date.now()-T0)/1000)+'s',t);});
await p.goto('file://'+path.join(__dirname,'frame.html')+(process.env.H6?'?'+process.env.H6:'')+(hq?'#hq':''));await p.waitForFunction(()=>window.ready,null,{timeout:900000});
await p.addScriptTag({path:path.join(__dirname,'../../../Resources/Mebel/multik-poster.js')});
const r=await p.evaluate(async txt=>{const R=MKScript.parse(txt,{characters:{},locations:{}});const ep=R.episodes[0];const lib={characters:{},locations:{},settings:{}};
  const v=MK.validate(ep,lib);for(const c of v.newChars)lib.characters[c.id]={spec:c,code:c._code};for(const l of v.newLocs)lib.locations[l.id]={spec:l,code:l._code};
  const res=await MKPoster.make(ep,lib,(t,k)=>console.log('[poster] '+t));
  return {full:res.full.toDataURL('image/jpeg',.92),clean:res.clean.toDataURL('image/jpeg',.92),info:res.info};},fs.readFileSync(file,'utf8'));
fs.mkdirSync(out,{recursive:true});const base=path.join(out,path.basename(file).replace(/\.txt$/,''));
fs.writeFileSync(base+'_poster.jpg',Buffer.from(r.full.split(',')[1],'base64'));fs.writeFileSync(base+'_clean.jpg',Buffer.from(r.clean.split(',')[1],'base64'));
console.log(JSON.stringify(r.info),Math.round((Date.now()-T0)/1000)+'s');await b.close();})();
