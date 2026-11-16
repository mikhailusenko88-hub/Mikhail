// Оплата размещения «Одно объявление · 30 дней» из кошелька — пакетом во фрейме, одно подтверждение.
// ЗАПУСКАТЬ ТОЛЬКО ПОСЛЕ ЯВНОГО «ДА» МИХАИЛА НА КОНКРЕТНУЮ СУММУ.
// Путь Авито: /bbl/<id>/period (срок) → /performance/<id> (2 экрана продвижения — всё выключить) →
// /account/pay/step1 (итого) → /payment/page/<uuid> (выбрать «Кошелёк», «Оплатить N ₽») → /fees/success.
// Любое расхождение (цена не PRICE, включено продвижение, не тот итог) — стоп всего пакета. Журнал — sessionStorage.nd_log6.
// 16.11.2026: так же возвращается объявление с истёкшим сроком (старое 8068817087: «Истёк срок размещения» → 463 ₽ за 30 дней,
// 23 секунды, 2 подтверждения; после оплаты «опубликуется после проверки», в кабинете статус меняется не сразу).
// Автопубликация платное размещение сама не продлевает. Паузы — через MessageChannel: при скрытой панели setTimeout срабатывает раз в минуту.
const JOBS = [['старое', '8068817087']];
const PRICE = '463 ₽', CONTACTS = '18';
sessionStorage.setItem('nd_log6', '');
const L = (...a) => { const s = new Date().toTimeString().slice(0, 8) + ' ' + a.join(' '); sessionStorage.setItem('nd_log6', (sessionStorage.getItem('nd_log6') || '') + s + '\n'); };
const mc = new MessageChannel(); let wake = null;
mc.port1.onmessage = () => { const r = wake; wake = null; if (r) r(); };
const tick = () => new Promise(r => { wake = r; mc.port2.postMessage(0); });
const sleep = async ms => { const t = Date.now() + ms; while (Date.now() < t) await tick(); };
const norm = s => (s || '').replace(/[\u00a0\u202f\u2009]/g, ' ').trim();   // неразрывные и узкие пробелы в ценах
let fr;
const d = () => fr.contentDocument, w = () => fr.contentWindow;
const q = s => { try { return d().querySelector(s); } catch (e) { return null; } };
const qa = s => { try { return [...d().querySelectorAll(s)]; } catch (e) { return []; } };
const path = () => { try { return w().location.pathname; } catch (e) { return '?'; } };
const waitFor = async (fn, ms) => { for (let t = 0; t < ms; t += 500) { try { if (fn()) return true; } catch (e) {} await sleep(500); } return false; };
function open(url) {
  if (fr) fr.remove();
  fr = document.createElement('iframe'); fr.id = 'nd_pay';
  fr.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups');
  fr.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:2147483647;background:#fff;border:0';
  fr.src = url; document.body.appendChild(fr);
}
async function pay(art, id) {
  L('—', art, id);
  open('/bbl/' + id + '/period');
  if (!await waitFor(() => q('[data-marker="bbl-config/continue-btn"]'), 20000)) { L('СТОП', art, 'нет экрана срока', path()); return false; }
  await sleep(1000);
  const sel = qa('[data-marker$="/wrapper"]').find(e => /^bbl-config-\d+\/wrapper$/.test(e.getAttribute('data-marker')) && /selected|active|checked/i.test(String(e.className)));
  const p30 = norm((q('[data-marker="bbl-config-30/price"]') || {}).innerText);
  const cnt = norm((q('[data-marker="bbl-config/contacts-count"]') || {}).innerText);
  L('срок: выбран', sel ? sel.getAttribute('data-marker') : '?', '| 30 дней', p30, '| контактов', cnt);
  if (!sel || sel.getAttribute('data-marker') !== 'bbl-config-30/wrapper' || p30 !== PRICE || cnt !== CONTACTS) { L('СТОП', art, 'не 30 дней / не', PRICE); return false; }
  q('[data-marker="bbl-config/continue-btn"]').click();
  for (let step = 0; step < 6; step++) {
    if (!await waitFor(() => q('[data-marker="vas-configurator/content"]') || /\/account\/pay\//.test(path()), 20000)) { L('СТОП', art, 'нет следующего экрана', path()); return false; }
    await sleep(1500);
    if (/\/account\/pay\//.test(path())) break;
    for (const t of qa('[data-marker$="/switcher/toggle"]')) if (t.checked) { (t.closest('label') || t).click(); await sleep(1200); }
    const on = qa('[data-marker$="/switcher/toggle"]').filter(t => t.checked).length;
    const title = norm((q('[data-marker="vas-configurator/content"]') || {}).innerText).split('\n')[0];
    L('продвижение «' + title + '»: включено', on);
    if (on) { L('СТОП', art, 'продвижение не выключилось'); return false; }
    const before = title;
    q('[data-marker="bbl-config/continue-btn"]').click();
    await waitFor(() => /\/account\/pay\//.test(path()) || norm((q('[data-marker="vas-configurator/content"]') || {}).innerText).split('\n')[0] !== before, 15000);
  }
  if (!await waitFor(() => q('[data-marker="payment-btn"]'), 20000)) { L('СТОП', art, 'нет страницы итога', path()); return false; }
  await sleep(1000);
  const rows = qa('[data-marker="checkout-services-row-block"]').map(e => norm(e.innerText).replace(/\n+/g, ' / '));
  const total = norm((q('[data-marker="total/price"]') || {}).innerText);
  L('итог:', rows.join(' || '), '| ИТОГО', total);
  if (rows.length !== 1 || !/Публикация на 30 дней/.test(rows[0]) || total !== PRICE) { L('СТОП', art, 'итог не тот'); return false; }
  q('[data-marker="payment-btn"]').click();
  if (!await waitFor(() => /\/payment\/page\//.test(path()) && q('[data-marker="payButton"]'), 25000)) { L('СТОП', art, 'нет страницы оплаты', path()); return false; }
  await sleep(1500);
  const amount = norm((q('[data-marker="orderAmount"]') || {}).innerText);
  if (amount !== PRICE) { L('СТОП', art, 'к оплате', amount); return false; }
  const wal = q('[data-marker="internal-wallet"]');
  if (!wal) { L('СТОП', art, 'нет кошелька'); return false; }
  wal.closest('[data-marker="paymentVariant"]').click();
  await sleep(1800);
  const bt = norm(q('[data-marker="payButton"]').innerText);
  L('кнопка:', bt);
  if (bt !== 'Оплатить ' + PRICE) { L('СТОП', art, 'кошелёк не выбран'); return false; }
  q('[data-marker="payButton"]').click();
  if (!await waitFor(() => /\/fees\/success/.test(path()), 30000)) { L('СТОП', art, 'нет подтверждения оплаты', path(), norm(d().body.innerText).slice(0, 200)); return false; }
  await sleep(1000);
  L(art, 'ОПЛАЧЕНО:', norm(d().body.innerText).split('\n').slice(0, 2).join(' '));
  return true;
}
(async () => {
  try {
    for (const [a, id] of JOBS) { if (!await pay(a, id)) break; }
    open('/profile');
    await waitFor(() => /Активные/.test(d().body.innerText) && d().querySelectorAll('a[href*="_8"]').length > 3, 25000); await sleep(2500);
    const body = d().body.innerText || '';
    L('ИТОГ: вкладки:', [...d().querySelectorAll('[data-marker*="tab"],[role=tab]')].map(e => norm(e.innerText).replace(/\s+/g, ' ')).filter(x => x && x.length < 40).slice(0, 8).join(' · '), '|', norm((body.match(/Кошел[её]к[^₽]{0,60}₽/) || [''])[0]).replace(/\s+/g, ' ') || 'кошелёк не виден');
    fr.remove();
    L('ВСЁ');
  } catch (e) { L('ОШИБКА', String(e && e.stack || e).slice(0, 300)); }
})();
'запущена оплата: ' + JOBS.map(j => j[0]).join(', ');
