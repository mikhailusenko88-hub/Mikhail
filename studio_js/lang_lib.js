
window.sleep=ms=>new Promise(r=>setTimeout(r,ms));
window.vis=()=>[...document.querySelectorAll('tp-yt-paper-dialog')].filter(d=>d.getClientRects().length);
window.btnIn=(root,re)=>[...root.querySelectorAll('ytcp-button, button')].find(b=>b.getClientRects().length && re.test(b.innerText.trim()));
window.getBlob=async function(url){for(let i=0;i<4;i++){try{const r=await fetch(url,{credentials:'omit'}); if(r.ok) return await r.blob();}catch(e){} await sleep(1500);} return null;}
window.openLang=async function(lang){
  let row=[...document.querySelectorAll('ytgn-video-translation-row')].find(r=>r.innerText.trim().startsWith(lang));
  if(row){ [...row.querySelectorAll('button, ytcp-button')].find(b=>b.getClientRects().length).click(); await sleep(2500); return 'row'; }
  const add=[...document.querySelectorAll('ytcp-button, button')].find(b=>b.getClientRects().length && /Add language/i.test(b.innerText)); add.click(); await sleep(1500);
  const it=[...document.querySelectorAll('tp-yt-paper-item, [role=option]')].filter(x=>x.getClientRects().length).find(x=>x.innerText.trim()===lang);
  if(!it) return 'нет языка в списке'; it.click(); await sleep(2500); return 'new';
}
window.job=async function(j){
  const how=await openLang(j.lang); let log=[j.lang+':'+how];
  let dlg=vis().find(d=>d.innerText.trim().startsWith(j.lang)); if(!dlg) return log.concat('нет окна').join(' ');
  if(j.title){
    const eds=[...dlg.querySelectorAll('[contenteditable=true]')].filter(e=>e.getClientRects().length);
    const te=eds.find(e=>/Title/i.test(e.getAttribute('aria-label')||'')), de=eds.find(e=>/Description/i.test(e.getAttribute('aria-label')||''));
    for(const [e,v,nm] of [[te,j.title,'t'],[de,j.desc,'d']]){ if(!e){log.push(nm+'?');continue;} if(e.innerText.trim().length>3){log.push(nm+'=есть');continue;} e.focus(); document.execCommand('selectAll'); document.execCommand('insertText',false,v); await sleep(400); log.push(nm+'+'); }
    const tr=[...dlg.querySelectorAll('tr')].find(t=>t.getClientRects().length && /^Thumbnail/.test(t.innerText.trim()));
    const ab=tr && btnIn(tr,/^Add$/);
    if(ab){ ab.click(); await sleep(1500); const b=await getBlob(j.cover); const inp=document.querySelector('#file-loader');
      if(b && inp){ const dt=new DataTransfer(); dt.items.add(new File([b],j.cname,{type:'image/jpeg'})); inp.files=dt.files; inp.dispatchEvent(new Event('change',{bubbles:true})); await sleep(4000); log.push('обл+'+b.size);} else log.push('обл?'); }
    else log.push('обл=есть');
    dlg=vis().find(d=>d.innerText.trim().startsWith(j.lang));
    const up=btnIn(dlg,/^Update$/); if(up && up.getAttribute('aria-disabled')!=='true'){ up.click(); await sleep(3500); log.push('Update'); } else log.push('Update выкл');
  }
  if(j.audio){
    if(!vis().find(d=>d.innerText.trim().startsWith(j.lang))){ await openLang(j.lang); }
    dlg=vis().find(d=>d.innerText.trim().startsWith(j.lang));
    const tr=[...dlg.querySelectorAll('tr')].find(t=>t.getClientRects().length && /^Audio/.test(t.innerText.trim()));
    const ab=tr && btnIn(tr,/^Add$/);
    if(!ab){ log.push('дорожка=есть/нет Add'); }
    else { ab.click(); await sleep(2000); const b=await getBlob(j.audio); const inp=document.querySelector('#audio-file-loader');
      if(!b||!inp) log.push('аудио?'); else { const dt=new DataTransfer(); dt.items.add(new File([b],j.aname,{type:'audio/mpeg'})); inp.files=dt.files; inp.dispatchEvent(new Event('change',{bubbles:true})); await sleep(4000);
        const ad=vis().find(d=>/Add audio track/.test(d.innerText)); if(ad && ad.innerText.includes(j.aname)){ btnIn(ad,/^Publish$/).click(); await sleep(5000); log.push('аудио+'+b.size);} else log.push('аудио не встало'); }
      dlg=vis().find(d=>d.innerText.trim().startsWith(j.lang)); const up=dlg&&btnIn(dlg,/^Update$/); if(up){ up.click(); await sleep(3500); log.push('Update'); } }
  }
  for(const d of vis()){ const c=d.querySelector('#close-button, [aria-label=Close]'); if(c && c.getClientRects().length){ c.click(); await sleep(800);} }
  return log.join(' ');
}

window.BJ=async function(JOBS){ const out=[location.pathname]; for(const j of JOBS){ out.push(await job(j)); }
 out.push([...document.querySelectorAll('ytgn-video-translation-row')].map(x=>x.innerText.replace(/\s+/g,' ')).join(' | ')); return out; };
'BJ ok'
