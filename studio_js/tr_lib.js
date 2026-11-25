(async()=>{
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const vis=()=>[...document.querySelectorAll('tp-yt-paper-dialog')].filter(d=>d.getClientRects().length);
const btnIn=(root,re)=>[...root.querySelectorAll('ytcp-button, button')].find(b=>b.getClientRects().length && re.test(b.innerText.trim()));
const CFG={
 English:{brand:'Barsik the Cat',kw:'Cartoon for Kids',ep:'Episode',line:'Cat cartoon for kids: Barsik the Cat and friends — educational cartoons for kids and toddlers, in English.',tags:['#cartoonforkids','#catcartoon','#kidscartoon','#barsik']},
 Spanish:{brand:'Barsik el Gato',kw:'Dibujos animados para niños',ep:'Episodio',line:'Dibujos animados para niños en español: Barsik el Gato y sus amigos — caricaturas educativas para niños de 3 a 7 años.',tags:['#dibujosanimados','#caricaturas','#dibujosanimadosparaniños','#barsik']},
 Portuguese:{brand:'Barsik o Gato',kw:'Desenho animado infantil',ep:'Episódio',line:'Desenho animado infantil em português: Barsik o Gato e seus amigos — desenho educativo para crianças de 3 a 7 anos.',tags:['#desenhoanimado','#desenhoinfantil','#desenhoeducativo','#barsik']},
 German:{brand:'Barsik der Kater',kw:'Zeichentrick für Kinder',ep:'Folge',line:'Zeichentrickfilm für Kinder auf Deutsch: Barsik der Kater und seine Freunde — lehrreicher Zeichentrick für Kinder von 3 bis 7 Jahren.',tags:['#zeichentrick','#kinderfilme','#zeichentrickfürkinder','#barsik']},
 Hindi:{brand:null,kw:'Billi wala cartoon | Hindi Cartoon | बच्चों का कार्टून',ep:'एपिसोड',line:'Hindi cartoon for kids: Barsik billi wala cartoon — बच्चों का कार्टून हिंदी में, 3 से 7 साल के बच्चों के लिए शैक्षिक कहानी (cartoon hindi kahani).',tags:['#hindicartoon','#cartoonhindi','#billiwalacartoon','#barsik']}
};
const L=s=>[...s].length;
function newTitle(lang,t){
  const c=CFG[lang]; t=t.trim();
  if(t.includes(c.kw.split(' | ')[0])) return null;               // уже сделано
  const isSb=/5 (episodes|episodios|episódios|Folgen)|लगातार|подряд/i.test(t);
  if(isSb){
    let base=t.split(' | ')[0].trim();
    let n=base+' | '+c.kw; if(L(n)<=100) return n;
    base=base.slice(0,base.indexOf('!')+1)||base; n=base+' | '+c.kw; return L(n)<=100?n:base;
  }
  const num=(t.match(/(\d+)\s*$/)||[])[1];
  let i=t.indexOf('?!'); let hook=i>=0?t.slice(0,i+2):t.split(' | ')[0];
  hook=hook.trim();
  const parts=[hook]; if(c.brand) parts.push(c.brand); parts.push(c.kw);
  let n=parts.join(' | ')+(num?' | '+c.ep+' '+num:'');
  if(L(n)>100) n=parts.join(' | ');
  if(L(n)>100) n=[hook,c.kw].join(' | ');
  return n;
}
function newDesc(lang,d){
  const c=CFG[lang]; d=(d||'').replace(/\s+$/,'');
  if(d.startsWith(c.line)) return null;
  let lines=d.split('\n'); let old=[];
  if(lines.length && /^\s*#/.test(lines[lines.length-1])){ old=lines.pop().trim().split(/\s+/).filter(x=>x.startsWith('#')); while(lines.length && !lines[lines.length-1].trim()) lines.pop(); }
  const seen=new Set(); const tags=[...c.tags,...old].filter(x=>{const k=x.toLowerCase(); if(seen.has(k))return false; seen.add(k); return true;}).slice(0,8);
  return c.line+'\n\n'+lines.join('\n').trim()+'\n\n'+tags.join(' ');
}
async function openLang(lang){
  for(const d of vis()){ const c=d.querySelector('#close-button, [aria-label=Close]'); if(c&&c.getClientRects().length){c.click(); await sleep(600);} }
  const row=[...document.querySelectorAll('ytgn-video-translation-row')].find(r=>r.innerText.trim().startsWith(lang));
  if(!row) return false;
  [...row.querySelectorAll('button, ytcp-button')].find(b=>b.getClientRects().length).click(); await sleep(2500);
  return !!vis().find(d=>d.innerText.trim().startsWith(lang));
}
window._trRun=async function(write){
  for(let i=0;i<20 && !document.querySelector('ytgn-video-translation-row');i++) await sleep(1000);
  await sleep(800);
  const out=[location.pathname.split('/')[2]];
  for(const lang of Object.keys(CFG)){
    if(!await openLang(lang)){ out.push(lang+': нет языка'); continue; }
    let dlg=vis().find(d=>d.innerText.trim().startsWith(lang));
    const eds=[...dlg.querySelectorAll('[contenteditable=true]')].filter(e=>e.getClientRects().length);
    const te=eds.find(e=>/Title/i.test(e.getAttribute('aria-label')||'')), de=eds.find(e=>/Description/i.test(e.getAttribute('aria-label')||''));
    if(!te||!de){ out.push(lang+': нет полей'); continue; }
    const ot=te.innerText.trim(), od=de.innerText;
    const nt=newTitle(lang,ot), nd=newDesc(lang,od);
    let rec={lang, old:ot, title:nt, descFirst:nd?nd.split('\n')[0].slice(0,60):null, tags:nd?nd.split('\n').pop():null, len:nt?L(nt):null};
    if(write && (nt||nd)){
      if(nt){ te.focus(); document.execCommand('selectAll'); document.execCommand('insertText',false,nt); await sleep(400); }
      if(nd){ de.focus(); document.execCommand('selectAll'); document.execCommand('insertText',false,nd); await sleep(400); }
      dlg=vis().find(d=>d.innerText.trim().startsWith(lang));
      const up=btnIn(dlg,/^(Update|Publish)$/);
      if(up && up.getAttribute('aria-disabled')!=='true'){ up.click(); await sleep(3500); rec.saved=true; } else rec.saved='кнопка выкл';
      if(vis().find(d=>d.innerText.trim().startsWith(lang))) rec.saved+=' (окно не закрылось)';
    }
    out.push(rec);
    for(const d of vis()){ const c=d.querySelector('#close-button, [aria-label=Close]'); if(c&&c.getClientRects().length){c.click(); await sleep(600);} }
  }
  return out;
};
return 'tr ok';
})()
