
window.sleep=ms=>new Promise(r=>setTimeout(r,ms));
window.vis=()=>[...document.querySelectorAll('tp-yt-paper-dialog')].filter(d=>d.getClientRects().length);
window.btnIn=(root,re)=>[...root.querySelectorAll('ytcp-button, button')].find(b=>b.getClientRects().length && re.test(b.innerText.trim()));
window.getBlob=async function(url){for(let i=0;i<4;i++){try{const r=await fetch(url,{credentials:'omit'}); if(r.ok) return await r.blob();}catch(e){} await sleep(1500);} return null;}
// Названия и описания на языках (решение Михаила 25.11.2026): к названию — главный запрос страны, к описанию — строка поиска первой и хэштеги языка.
// 26.11.2026 — добавлены French и Arabic (Михаил: «давай всё внедрять»). В Studio язык общий, без страны.
// trTitle/trDesc переводят любое название/описание в этот вид; job() применяет их сам.
window.TR_CFG={
 English:{brand:'Barsik the Cat',kw:'Cartoon for Kids',ep:'Episode',line:'Cat cartoon for kids: Barsik the Cat and friends — educational cartoons for kids and toddlers, in English.',tags:['#cartoonforkids','#catcartoon','#kidscartoon','#barsik']},
 Spanish:{brand:'Barsik el Gato',kw:'Dibujos animados para niños',ep:'Episodio',line:'Dibujos animados para niños en español: Barsik el Gato y sus amigos — caricaturas educativas para niños de 3 a 7 años.',tags:['#dibujosanimados','#caricaturas','#dibujosanimadosparaniños','#barsik']},
 Portuguese:{brand:'Barsik o Gato',kw:'Desenho animado infantil',ep:'Episódio',line:'Desenho animado infantil em português: Barsik o Gato e seus amigos — desenho educativo para crianças de 3 a 7 anos.',tags:['#desenhoanimado','#desenhoinfantil','#desenhoeducativo','#barsik']},
 German:{brand:'Barsik der Kater',kw:'Zeichentrick für Kinder',ep:'Folge',line:'Zeichentrickfilm für Kinder auf Deutsch: Barsik der Kater und seine Freunde — lehrreicher Zeichentrick für Kinder von 3 bis 7 Jahren.',tags:['#zeichentrick','#kinderfilme','#zeichentrickfürkinder','#barsik']},
 Hindi:{brand:null,kw:'Billi wala cartoon | Hindi Cartoon | बच्चों का कार्टून',ep:'एपिसोड',line:'Hindi cartoon for kids: Barsik billi wala cartoon — बच्चों का कार्टून हिंदी में, 3 से 7 साल के बच्चों के लिए शैक्षिक कहानी (cartoon hindi kahani).',tags:['#hindicartoon','#cartoonhindi','#billiwalacartoon','#barsik']},
 French:{brand:"Barsik le Chat",kw:"Dessin animé pour enfant",ep:"Épisode",line:"Dessin animé pour enfant en français : Barsik le Chat et ses amis — dessin animé éducatif pour les enfants de 3 à 7 ans.",tags:["#dessinanimé", "#dessinanimépourenfant", "#dessinaniméenfrançais", "#barsik"]},
 Arabic:{brand:"القط بارسيك",kw:"كرتون اطفال تعليمي",ep:"الحلقة",line:"كرتون اطفال تعليمي بالعربي: القط بارسيك وأصدقاؤه — كرتون قطط للاطفال الصغار من 3 إلى 7 سنوات.",tags:["#كرتون_اطفال", "#كرتون_تعليمي", "#كرتون_قطط", "#barsik"]}
};
window.TR_L=s=>[...s].length;
window.trTitle=function(lang,t){
  const c=window.TR_CFG[lang]; t=t.trim();
  if(t.includes(c.kw.split(' | ')[0])) return null;               // уже сделано
  const isSb=/5 (episodes|episodios|episódios|épisodes|Folgen|حلقات)|लगातार|متتالية|подряд/i.test(t);
  if(isSb){
    let base=t.split(' | ')[0].trim();
    let n=base+' | '+c.kw; if(window.TR_L(n)<=100) return n;
    base=base.slice(0,base.indexOf('!')+1)||base; n=base+' | '+c.kw; return window.TR_L(n)<=100?n:base;
  }
  const num=(t.match(/(\d+)\s*$/)||[])[1];
  let i=t.indexOf('?!'); let hook=i>=0?t.slice(0,i+2):t.split(' | ')[0];
  hook=hook.trim();
  const parts=[hook]; if(c.brand) parts.push(c.brand); parts.push(c.kw);
  let n=parts.join(' | ')+(num?' | '+c.ep+' '+num:'');
  if(window.TR_L(n)>100) n=parts.join(' | ');
  if(window.TR_L(n)>100) n=[hook,c.kw].join(' | ');
  return n;
}
window.trDesc=function(lang,d){
  const c=window.TR_CFG[lang]; d=(d||'').replace(/\s+$/,'');
  if(d.startsWith(c.line)) return null;
  let lines=d.split('\n'); let old=[];
  if(lines.length && /^\s*#/.test(lines[lines.length-1])){ old=lines.pop().trim().split(/\s+/).filter(x=>x.startsWith('#')); while(lines.length && !lines[lines.length-1].trim()) lines.pop(); }
  const seen=new Set(); const tags=[...c.tags,...old].filter(x=>{const k=x.toLowerCase(); if(seen.has(k))return false; seen.add(k); return true;}).slice(0,8);
  return c.line+'\n\n'+lines.join('\n').trim()+'\n\n'+tags.join(' ');
}
window.openLang=async function(lang){
  // 26–27.11: окно языка после обычной навигации открывается дольше 2,5 с («нет окна») — ждать до 10 с; уже открытое не трогать.
  // Если панель браузера на Маке скрыта, окна Studio не раскладываются (getClientRects пуст) и «нет окна» бывает и через 25 с —
  // сделать снимок экрана (computer screenshot) — окно появится — и повторить вызов (вернёт «уже открыто»).
  const dl=()=>vis().find(d=>d.innerText.trim().startsWith(lang));
  if(dl()) return 'уже открыто';
  let row=[...document.querySelectorAll('ytgn-video-translation-row')].find(r=>r.innerText.trim().startsWith(lang));
  if(row){ [...row.querySelectorAll('button, ytcp-button')].find(b=>b.getClientRects().length).click(); for(let k=0;k<20 && !dl();k++) await sleep(500); await sleep(800); return 'row'; }
  // 26.11: список языков после закрытия окна прошлого языка появляется не сразу — ждать до 6 с; если список уже открыт, «Add language» не нажимать (закроет его)
  const find=()=>[...document.querySelectorAll('tp-yt-paper-item, [role=option]')].filter(x=>x.getClientRects().length).find(x=>x.innerText.trim()===lang);
  let it=find();
  if(!it){ const add=[...document.querySelectorAll('ytcp-button, button')].find(b=>b.getClientRects().length && /Add language/i.test(b.innerText)); add.click();
    for(let k=0;k<12 && !(it=find());k++) await sleep(500); }
  if(!it) return 'нет языка в списке'; it.click(); await sleep(2500); return 'new';
}
window.job=async function(j){
  const how=await openLang(j.lang); let log=[j.lang+':'+how];
  let dlg=vis().find(d=>d.innerText.trim().startsWith(j.lang)); if(!dlg) return log.concat('нет окна').join(' ');
  if(j.title){
    const eds=[...dlg.querySelectorAll('[contenteditable=true]')].filter(e=>e.getClientRects().length);
    const te=eds.find(e=>/Title/i.test(e.getAttribute('aria-label')||'')), de=eds.find(e=>/Description/i.test(e.getAttribute('aria-label')||''));
    const TT=(window.trTitle&&window.TR_CFG[j.lang]&&window.trTitle(j.lang,j.title))||j.title, DD=(window.trDesc&&window.TR_CFG[j.lang]&&window.trDesc(j.lang,j.desc))||j.desc;
    for(const [e,v,nm] of [[te,TT,'t'],[de,DD,'d']]){ if(!e){log.push(nm+'?');continue;} if(e.innerText.trim().length>3){log.push(nm+'=есть');continue;} e.focus(); document.execCommand('selectAll'); document.execCommand('insertText',false,v); await sleep(400); log.push(nm+'+'); }
    const tr=[...dlg.querySelectorAll('tr')].find(t=>t.getClientRects().length && /^Thumbnail/.test(t.innerText.trim()));
    const ab=tr && btnIn(tr,/^Add$/);
    if(ab && j.cover){ ab.click(); await sleep(1500); const b=await getBlob(j.cover); const inp=[...document.querySelectorAll('#file-loader')].pop();   // 27.11: после перехода по SPA старый #file-loader остаётся — обложка «загружалась» в него и не вставала
      if(b && inp){ const dt=new DataTransfer(); dt.items.add(new File([b],j.cname,{type:'image/jpeg'})); inp.files=dt.files; inp.dispatchEvent(new Event('change',{bubbles:true})); await sleep(4000); log.push('обл+'+b.size);} else log.push('обл?'); }
    else log.push(j.cover?'обл=есть':'обл нет файла');
    dlg=vis().find(d=>d.innerText.trim().startsWith(j.lang));
    const up=btnIn(dlg,/^Update$/); if(up && up.getAttribute('aria-disabled')!=='true'){ up.click(); await sleep(3500); log.push('Update'); } else log.push('Update выкл');
  }
  if(j.audio){
    if(!vis().find(d=>d.innerText.trim().startsWith(j.lang))){ await openLang(j.lang); }
    dlg=vis().find(d=>d.innerText.trim().startsWith(j.lang));
    const tr=[...dlg.querySelectorAll('tr')].find(t=>t.getClientRects().length && /^Audio/.test(t.innerText.trim()));
    const ab=tr && btnIn(tr,/^Add$/);
    if(!ab){ log.push('дорожка=есть/нет Add'); }
    else { ab.click(); await sleep(2000); const b=await getBlob(j.audio); const inp=[...document.querySelectorAll('#audio-file-loader')].pop();   // после перехода по SPA старый input остаётся — нужен последний
      if(!b||!inp) log.push('аудио?'); else { const dt=new DataTransfer(); dt.items.add(new File([b],j.aname,{type:'audio/mpeg'})); inp.files=dt.files; inp.dispatchEvent(new Event('change',{bubbles:true})); await sleep(4000);
        const ad=vis().find(d=>/Add audio track/.test(d.innerText)); if(ad && ad.innerText.includes(j.aname)){ btnIn(ad,/^Publish$/).click(); await sleep(5000); log.push('аудио+'+b.size);} else log.push('аудио не встало'); }
      dlg=vis().find(d=>d.innerText.trim().startsWith(j.lang)); const up=dlg&&btnIn(dlg,/^Update$/); if(up){ up.click(); await sleep(3500); log.push('Update'); } }
  }
  for(const d of vis()){ const c=d.querySelector('#close-button, [aria-label=Close]'); if(c && c.getClientRects().length){ c.click(); await sleep(800);} }
  return log.join(' ');
}

// 26.11: замена своей же дорожки (хинди «без спешки» и т. п.): Audio «⋮» → Delete → Confirm, затем job() добавляет новый файл.
// Переход к другой серии без перезагрузки (помощники остаются в странице): history.pushState({},'',`/video/${id}/translations`); dispatchEvent(new PopStateEvent('popstate',{state:{}})); — сверять название серии (#entity-name).
// Дольше 45 с — запускать фоном: window.Rn=null; replAudio('Hindi',url,'Barsik-29-hi.mp3').then(r=>window.Rn=r)
window.replAudio=async function(lang,url,name){
  const log=[lang+' замена'];
  await openLang(lang); let dlg=vis().find(d=>d.innerText.trim().startsWith(lang)); if(!dlg) return log.concat('нет окна').join(' ');
  const opt=[...dlg.querySelectorAll('[aria-label="Show dubbed audio options"]')].find(b=>b.getClientRects().length);
  if(opt){ opt.click(); await sleep(1200);
    const del=[...document.querySelectorAll('tp-yt-paper-item, [role=menuitem], ytcp-ve, yt-formatted-string')].filter(x=>x.getClientRects().length).find(x=>/^Delete$/i.test(x.innerText.trim()));
    if(!del) return log.concat('нет Delete').join(' ');
    del.click(); await sleep(1500);
    const cd=[...document.querySelectorAll('ytcp-confirmation-dialog')].find(d=>d.getClientRects().length && /Delete track/.test(d.innerText));   // 26.11: без проверки текста попадал не в то окно
    const cb=cd && btnIn(cd,/^(Confirm|Delete)$/i); if(!cb) return log.concat('нет Confirm').join(' ');
    cb.click(); await sleep(3500); log.push('старая удалена');
  } else log.push('дорожки не было');
  for(const d of vis()){ const c=d.querySelector('#close-button, [aria-label=Close]'); if(c && c.getClientRects().length){ c.click(); await sleep(800);} }
  return log.join(' ')+' | '+await job({lang,audio:url,aname:name});
}

window.BJ=async function(JOBS){ const out=[location.pathname]; for(const j of JOBS){ out.push(await job(j)); }
 out.push([...document.querySelectorAll('ytgn-video-translation-row')].map(x=>x.innerText.replace(/\s+/g,' ')).join(' | ')); return out; };
// 26.11: пачка заданий фоном (вызов дольше 45 с обрывается): runJobs(JOBS) → через минуту-две читать window.Rn (итог) или window.Rp (по ходу); rows() — строки языков.
window.rows=()=>[...document.querySelectorAll('ytgn-video-translation-row')].map(x=>x.innerText.replace(/\s+/g,' ')).join(' | ');
window.runJobs=function(JOBS){ window.Rn=null; window.Rp=null; (async()=>{const out=[]; for(const j of JOBS){ try{ out.push(await job(j)); }catch(e){ out.push(j.lang+' ОШИБКА '+e); } window.Rp=out.slice(); } window.Rn=out; })(); return 'started'; };
'BJ ok'
