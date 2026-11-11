// Разведка форм профиля (ничего не сохраняет): /profile/extended (фото, телефоны, «Написать»),
// /profile/settings (контактное лицо, звонки), /profile/address (удаление адреса).
// Открывает окна «Добавить» и описывает их поля; журнал — sessionStorage.nd_prof2.
sessionStorage.setItem('nd_prof2', '');
const L = s => sessionStorage.setItem('nd_prof2', (sessionStorage.getItem('nd_prof2') || '') + s + '\n');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const norm = s => (s || '').replace(/ /g, ' ').replace(/[ \t]+/g, ' ').trim();
let fr;
async function open(url, ready) {
  if (fr) fr.remove();
  fr = document.createElement('iframe');
  fr.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms');
  fr.style.cssText = 'position:fixed;left:-3000px;top:0;width:1280px;height:2400px';
  fr.src = url; document.body.appendChild(fr);
  for (let i = 0; i < 30; i++) { await sleep(500); try { if (ready.test(fr.contentDocument.body.innerText)) break; } catch (e) {} }
  await sleep(2000);
  return fr.contentDocument;
}
const desc = (root) => [...root.querySelectorAll('input, textarea, select, button, [role=button], [role=switch], [role=checkbox], label, [data-marker]')]
  .filter(e => e.getClientRects().length && !e.closest('header,footer,[data-marker="profile-sidebar"],[data-marker^="header"],[data-marker^="footer"],[data-marker="mini-messenger"],[data-marker^="navigation"]'))
  .map(e => e.tagName + (e.type ? '[' + e.type + ']' : '') + (e.name ? ' name=' + e.name : '') + (e.checked ? ' ON' : '') + (e.getAttribute('aria-checked') ? ' aria=' + e.getAttribute('aria-checked') : '') + (e.placeholder ? ' ph=' + e.placeholder : '') + (e.value && e.tagName !== 'BUTTON' ? ' val=' + String(e.value).slice(0, 30) : '') + (e.getAttribute('data-marker') ? ' {' + e.getAttribute('data-marker') + '}' : '') + ' :: ' + norm(e.innerText || '').replace(/\n+/g, '/').slice(0, 50))
  .filter(s => !/ :: $/.test(s) || /\{|name=|ph=/.test(s));
const section = (d, title) => { const h = [...d.querySelectorAll('h1,h2,h3,h4,h5,p,span,div')].find(e => e.children.length === 0 && norm(e.textContent) === title); let s = h; for (let k = 0; k < 6 && s && !/Добавить|Изменить/.test(s.innerText.replace(title, '')); k++) s = s.parentElement; return s; };
const clickAdd = async (d, title) => {
  const s = section(d, title); if (!s) { L('нет секции ' + title); return null; }
  const b = [...s.querySelectorAll('button, a, [role=button]')].find(e => /^(Добавить|Изменить)$/.test(norm(e.innerText)));
  if (!b) { L('нет кнопки в ' + title); return null; }
  b.click(); await sleep(2500);
  const dlg = [...d.querySelectorAll('[role=dialog], [class*=modal], [class*=Modal], [data-marker*=modal], [data-marker*=popup]')].filter(e => e.getClientRects().length && norm(e.innerText));
  return dlg[0] || null;
};
const closeDlg = async (d) => { const x = [...d.querySelectorAll('[role=dialog] button, [class*=modal] button, [class*=Modal] button')].find(b => /close|закрыть/i.test((b.getAttribute('aria-label') || '') + (b.getAttribute('data-marker') || '') + b.innerText)); if (x) { x.click(); await sleep(1000); } else { d.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); await sleep(800); } };
(async () => {
  try {
    let d = await open('/profile/extended', /Для связи/);
    for (const t of ['Фотографии', 'Телефоны']) {
      const dlg = await clickAdd(d, t);
      L('\n=== ' + t + ' — окно: ' + (dlg ? norm(dlg.innerText).replace(/\n+/g, ' | ').slice(0, 600) : 'нет окна'));
      if (dlg) L('поля: ' + desc(dlg).slice(0, 30).join(' ; '));
      else L('страница после клика: ' + fr.contentWindow.location.pathname + ' | ' + desc(d).slice(-25).join(' ; '));
      if (!/extended/.test(fr.contentWindow.location.pathname)) d = await open('/profile/extended', /Для связи/); else await closeDlg(d);
    }
    const msg = section(d, 'Сообщения');
    L('\n=== Сообщения: ' + (msg ? norm(msg.innerText).replace(/\n+/g, ' | ').slice(0, 200) + ' :: ' + desc(msg).join(' ; ') : 'нет'));
    d = await open('/profile/settings', /Контактное лицо/);
    const t = norm(d.body.innerText).replace(/\n+/g, ' | ');
    const k = t.indexOf('Контактная информация');
    L('\n=== Настройки (текст): ' + t.slice(k, k + 900));
    L('поля: ' + desc(d).filter(s => /INPUT|SELECT|TEXTAREA|switch|checkbox|Сохранить|Изменить|звон|Звон|контакт|Контакт/i.test(s)).slice(0, 40).join(' ; '));
    d = await open('/profile/address', /Адреса/);
    L('\n=== Адреса: ' + desc(d).slice(0, 30).join(' ; '));
    const a = [...d.querySelectorAll('body *')].find(e => e.children.length === 0 && /Московский/.test(e.textContent));
    if (a) { let c = a; for (let k2 = 0; k2 < 5; k2++) c = c.parentElement; L('у адреса: ' + c.outerHTML.replace(/\s+/g, ' ').slice(0, 1200)); }
    fr.remove();
    L('\nВСЁ');
  } catch (e) { L('ОШИБКА ' + String(e && e.stack || e).slice(0, 300)); }
})();
'разведка запущена';
