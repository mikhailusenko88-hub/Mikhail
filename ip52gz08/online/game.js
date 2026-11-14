'use strict';
/* Flagball Arena — онлайн-«Шарики»: живые игроки + боты, страны соревнуются в раундах.
   Свой шарик двигается сразу (без задержки), сервер только проверяет его.
   Монеты, украшения, подарок по таймеру, возрождение и «x2» за рекламу — по правилам CrazyGames. */
(function () {
  const C = window.Core;
  const q = new URLSearchParams(location.search);
  const SERVER = q.get('server') || window.FB_SERVER || ((location.protocol === 'https:' ? 'wss://' : 'ws://') + (location.hostname || 'localhost') + ':8091/ws');
  const SPEC = q.has('spec'); // камера для роликов: смотрит арену без своего шарика
  const cleanRoom = (r) => String(r || '').replace(/[^a-z0-9_-]/gi, '').slice(0, 24).toLowerCase();
  let ROOM = cleanRoom(q.get('room')) || 'main';
  const steer = { x: 0, y: 0, on: false };
  const LEASH = 26, DEAD = 7, TURN = 10, SAW_R = 50;
  const PCOL = ['#ff5252', '#ffca28', '#69f0ae', '#40c4ff', '#e040fb', '#ff9100', '#b2ff59', '#18ffff'];
  const POW = [{ icon: 'bolt', col: '#ffd600' }, { icon: 'magnet', col: '#ff4081' }, { icon: 'shield', col: '#40c4ff' }];
  const PREY = '#00e676', DANGER = '#ff1744';
  const rOf = (m) => 20 + 5 * Math.sqrt(m);
  const speedOf = (r) => 440 * Math.pow(40 / r, 0.32);
  const nowS = () => performance.now() / 1000;

  // ---------- тексты (английский — основной, CrazyGames требует) ----------
  const TX = {
    en: {
      conn: 'Connecting to the arena…', att: 'try', slow: 'Taking long? Check the internet or switch Wi-Fi / mobile',
      ateBy: 'You were eaten by', again: 'Play again', players: 'Players', grow: 'The arena grows!', joined: 'joined', left: 'left',
      bolt: 'Speed!', magnet: 'Magnet!', shield: 'Shield!', countries: 'Countries', round: 'Round', roundWon: 'Round won by',
      yourTeam: 'Your country won!', today: 'Today', yourCountry: 'Your country', best: 'Best', eats: 'Eaten', revive: 'Revive',
      half: '50% size', x2: 'Coins x2', shop: 'Shop', free: 'Free', owned: 'Owned', on: 'On', gift: 'Free gift!', giftIn: 'Gift in',
      openNow: 'Open now', noCoins: 'Not enough coins', tomorrow: 'More coins tomorrow', close: 'Close', pick: 'Pick your country',
      name: 'Your name', play: 'Play', hint: 'Green ring — you can eat it, red — run! Yellow name — a real player. Every point you grow counts for your country.',
      adsOff: 'Ads are blocked — coin options still work', title: 'Flagball Arena', team: 'for', change: 'Country', invite: 'Invite', copied: 'Invite link copied — send it to a friend', room: 'Private room',
      noAd: 'No ad available right now — try again later', copyHint: 'Copy this link and send it to a friend:', search: 'Search country', botsWon: 'Bots won the round — beat them!',
    },
    ru: {
      conn: 'Подключаюсь к арене…', att: 'попытка', slow: 'Долго? Проверь интернет или переключись Wi-Fi ↔ мобильный',
      ateBy: 'Тебя съел', again: 'Заново', players: 'Игроков', grow: 'Арена растёт!', joined: 'в игре', left: 'вышел',
      bolt: 'Ускорение!', magnet: 'Магнит!', shield: 'Щит!', countries: 'Страны', round: 'Раунд', roundWon: 'Раунд выиграла',
      yourTeam: 'Твоя страна победила!', today: 'Сегодня', yourCountry: 'Твоя страна', best: 'Рекорд', eats: 'Съел', revive: 'Вернуться',
      half: 'с половиной массы', x2: 'Монеты x2', shop: 'Магазин', free: 'Даром', owned: 'Есть', on: 'Надето', gift: 'Подарок!', giftIn: 'Подарок через',
      openNow: 'Открыть сейчас', noCoins: 'Не хватает монет', tomorrow: 'Ещё монеты — завтра', close: 'Закрыть', pick: 'Выбери страну',
      name: 'Твоё имя', play: 'Играть', hint: 'Зелёное кольцо — можно съесть, красное — беги. Жёлтое имя — живой игрок. Всё, что ты наберёшь, идёт в зачёт твоей стране.',
      adsOff: 'Реклама недоступна — за монеты всё работает', title: 'Flagball Arena', team: 'за', change: 'Страна', invite: 'Позвать', copied: 'Ссылка скопирована — отправь другу', room: 'Своя комната',
      noAd: 'Рекламы сейчас нет — попробуй чуть позже', copyHint: 'Скопируй ссылку и отправь другу:', search: 'Поиск страны', botsWon: 'Раунд за ботами — обгони их!',
    },
  };
  let LANG = (C.lang || 'en').slice(0, 2) === 'ru' ? 'ru' : 'en';
  let T = TX[LANG];
  const CN = {
    en: { RU: 'Russia', KZ: 'Kazakhstan', UZ: 'Uzbekistan', KG: 'Kyrgyzstan', UA: 'Ukraine', BY: 'Belarus', TR: 'Turkey', US: 'USA', GB: 'UK', DE: 'Germany', FR: 'France', IT: 'Italy', ES: 'Spain', PT: 'Portugal', BR: 'Brazil', AR: 'Argentina', MX: 'Mexico', CN: 'China', JP: 'Japan', KR: 'Korea', IN: 'India', ID: 'Indonesia', VN: 'Vietnam', TH: 'Thailand',
      PL: 'Poland', NL: 'Netherlands', SE: 'Sweden', NO: 'Norway', FI: 'Finland', CA: 'Canada', EG: 'Egypt', AE: 'UAE', NG: 'Nigeria', PK: 'Pakistan', AZ: 'Azerbaijan', GE: 'Georgia', AM: 'Armenia', TJ: 'Tajikistan', MN: 'Mongolia',
      CO: 'Colombia', PH: 'Philippines', RO: 'Romania', HU: 'Hungary', CZ: 'Czechia', AT: 'Austria', BE: 'Belgium', CH: 'Switzerland', DK: 'Denmark', IE: 'Ireland', GR: 'Greece', PE: 'Peru', CL: 'Chile', VE: 'Venezuela', EC: 'Ecuador', UY: 'Uruguay',
      AU: 'Australia', NZ: 'New Zealand', MY: 'Malaysia', SG: 'Singapore', BD: 'Bangladesh', SA: 'Saudi Arabia', IR: 'Iran', MA: 'Morocco', DZ: 'Algeria', TN: 'Tunisia', ZA: 'South Africa', KE: 'Kenya',
      LT: 'Lithuania', LV: 'Latvia', EE: 'Estonia', BG: 'Bulgaria', RS: 'Serbia', HR: 'Croatia', SK: 'Slovakia', MD: 'Moldova', TM: 'Turkmenistan', BOT: 'Bots' },
    ru: { RU: 'Россия', KZ: 'Казахстан', UZ: 'Узбекистан', KG: 'Киргизия', UA: 'Украина', BY: 'Беларусь', TR: 'Турция', US: 'США', GB: 'Британия', DE: 'Германия', FR: 'Франция', IT: 'Италия', ES: 'Испания', PT: 'Португалия', BR: 'Бразилия', AR: 'Аргентина', MX: 'Мексика', CN: 'Китай', JP: 'Япония', KR: 'Корея', IN: 'Индия', ID: 'Индонезия', VN: 'Вьетнам', TH: 'Таиланд',
      PL: 'Польша', NL: 'Нидерланды', SE: 'Швеция', NO: 'Норвегия', FI: 'Финляндия', CA: 'Канада', EG: 'Египет', AE: 'ОАЭ', NG: 'Нигерия', PK: 'Пакистан', AZ: 'Азербайджан', GE: 'Грузия', AM: 'Армения', TJ: 'Таджикистан', MN: 'Монголия',
      CO: 'Колумбия', PH: 'Филиппины', RO: 'Румыния', HU: 'Венгрия', CZ: 'Чехия', AT: 'Австрия', BE: 'Бельгия', CH: 'Швейцария', DK: 'Дания', IE: 'Ирландия', GR: 'Греция', PE: 'Перу', CL: 'Чили', VE: 'Венесуэла', EC: 'Эквадор', UY: 'Уругвай',
      AU: 'Австралия', NZ: 'Новая Зеландия', MY: 'Малайзия', SG: 'Сингапур', BD: 'Бангладеш', SA: 'Саудовская Аравия', IR: 'Иран', MA: 'Марокко', DZ: 'Алжир', TN: 'Тунис', ZA: 'ЮАР', KE: 'Кения',
      LT: 'Литва', LV: 'Латвия', EE: 'Эстония', BG: 'Болгария', RS: 'Сербия', HR: 'Хорватия', SK: 'Словакия', MD: 'Молдова', TM: 'Туркменистан', BOT: 'Боты' },
  };
  const cname = (f) => (CN[LANG][f] || f);
  const PICK_FLAGS = C.FLAGS.map((f) => f.id); // все 76 стран; в окне выбора — поиск по названию

  // ---------- украшения: цены в монетах, рисуются поверх шарика ----------
  const ACC = [
    { id: 0, price: 0 }, { id: 1, price: 60 }, { id: 2, price: 120 }, { id: 3, price: 150 }, { id: 4, price: 180 }, { id: 5, price: 200 },
    { id: 6, price: 220 }, { id: 7, price: 250 }, { id: 8, price: 300 }, { id: 9, price: 350 }, { id: 10, price: 400 }, { id: 11, price: 500 },
  ];
  function heart(ctx, x, y, s) { ctx.beginPath(); ctx.moveTo(x, y + s * 0.35); ctx.bezierCurveTo(x - s * 1.1, y - s * 0.35, x - s * 0.45, y - s * 1.05, x, y - s * 0.4); ctx.bezierCurveTo(x + s * 0.45, y - s * 1.05, x + s * 1.1, y - s * 0.35, x, y + s * 0.35); ctx.fill(); }
  function drawAcc(ctx, id, x, y, r) {
    if (!id || r < 6) return;
    ctx.save(); ctx.translate(x, y);
    const L = (w) => { ctx.lineWidth = Math.max(1, r * w); };
    switch (id) {
      case 1: // глазки
        for (const s of [-1, 1]) { ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.ellipse(s * r * 0.32, -r * 0.12, r * 0.22, r * 0.26, 0, 0, 7); ctx.fill(); ctx.strokeStyle = '#222'; L(0.04); ctx.stroke(); ctx.fillStyle = '#111'; ctx.beginPath(); ctx.arc(s * r * 0.32 + r * 0.05, -r * 0.08, r * 0.11, 0, 7); ctx.fill(); ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(s * r * 0.32 + r * 0.09, -r * 0.13, r * 0.04, 0, 7); ctx.fill(); }
        break;
      case 2: // бантик
        ctx.fillStyle = '#ff4fa3'; ctx.translate(r * 0.45, -r * 0.78); ctx.rotate(0.3);
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(-r * 0.42, -r * 0.26); ctx.lineTo(-r * 0.42, r * 0.26); ctx.closePath(); ctx.fill();
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(r * 0.42, -r * 0.26); ctx.lineTo(r * 0.42, r * 0.26); ctx.closePath(); ctx.fill();
        ctx.fillStyle = '#c2185b'; ctx.beginPath(); ctx.arc(0, 0, r * 0.12, 0, 7); ctx.fill();
        break;
      case 3: // кепка
        ctx.fillStyle = '#1e88e5'; ctx.beginPath(); ctx.arc(0, -r * 0.62, r * 0.62, Math.PI, 0); ctx.fill();
        ctx.fillStyle = '#1565c0'; ctx.beginPath(); ctx.ellipse(r * 0.42, -r * 0.62, r * 0.55, r * 0.13, 0, 0, 7); ctx.fill();
        ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(0, -r * 1.22, r * 0.08, 0, 7); ctx.fill();
        break;
      case 4: // усы
        ctx.fillStyle = '#4e342e';
        for (const s of [-1, 1]) { ctx.beginPath(); ctx.moveTo(0, r * 0.22); ctx.quadraticCurveTo(s * r * 0.3, r * 0.05, s * r * 0.55, r * 0.28); ctx.quadraticCurveTo(s * r * 0.7, r * 0.18, s * r * 0.62, r * 0.08); ctx.quadraticCurveTo(s * r * 0.75, r * 0.4, s * r * 0.3, r * 0.36); ctx.quadraticCurveTo(s * r * 0.12, r * 0.34, 0, r * 0.3); ctx.fill(); }
        break;
      case 5: // солнечные очки
        ctx.fillStyle = '#111'; for (const s of [-1, 1]) { C.rr(ctx, s * r * 0.33 - r * 0.25, -r * 0.3, r * 0.5, r * 0.3, r * 0.1); ctx.fill(); }
        ctx.strokeStyle = '#111'; L(0.06); ctx.beginPath(); ctx.moveTo(-r * 0.1, -r * 0.2); ctx.lineTo(r * 0.1, -r * 0.2); ctx.stroke();
        ctx.fillStyle = 'rgba(255,255,255,0.35)'; for (const s of [-1, 1]) { ctx.fillRect(s * r * 0.33 - r * 0.18, -r * 0.26, r * 0.12, r * 0.06); }
        break;
      case 6: // рожки
        ctx.fillStyle = '#e53935'; for (const s of [-1, 1]) { ctx.beginPath(); ctx.moveTo(s * r * 0.28, -r * 0.85); ctx.quadraticCurveTo(s * r * 0.45, -r * 1.35, s * r * 0.62, -r * 1.42); ctx.quadraticCurveTo(s * r * 0.55, -r * 1.05, s * r * 0.62, -r * 0.68); ctx.closePath(); ctx.fill(); }
        break;
      case 7: // глаза-сердечки
        ctx.fillStyle = '#ff1744'; heart(ctx, -r * 0.32, -r * 0.08, r * 0.24); heart(ctx, r * 0.32, -r * 0.08, r * 0.24);
        break;
      case 8: // нимб
        ctx.strokeStyle = '#ffd600'; L(0.1); ctx.shadowColor = '#fff59d'; ctx.shadowBlur = r * 0.3; ctx.beginPath(); ctx.ellipse(0, -r * 1.18, r * 0.55, r * 0.16, 0, 0, 7); ctx.stroke();
        break;
      case 9: // повязка ниндзя
        ctx.fillStyle = '#d32f2f'; ctx.fillRect(-r * 0.98, -r * 0.5, r * 1.96, r * 0.24);
        ctx.beginPath(); ctx.moveTo(r * 0.9, -r * 0.42); ctx.lineTo(r * 1.45, -r * 0.62); ctx.lineTo(r * 1.35, -r * 0.4); ctx.lineTo(r * 1.5, -r * 0.18); ctx.closePath(); ctx.fill();
        ctx.fillStyle = '#fff'; for (const s of [-1, 1]) { ctx.beginPath(); ctx.ellipse(s * r * 0.3, -r * 0.08, r * 0.14, r * 0.07, 0, 0, 7); ctx.fill(); }
        break;
      case 10: // цилиндр
        ctx.fillStyle = '#212121'; ctx.fillRect(-r * 0.42, -r * 1.6, r * 0.84, r * 0.85); ctx.beginPath(); ctx.ellipse(0, -r * 0.76, r * 0.75, r * 0.14, 0, 0, 7); ctx.fill();
        ctx.fillStyle = '#c62828'; ctx.fillRect(-r * 0.42, -r * 0.98, r * 0.84, r * 0.14);
        break;
      case 11: { // корона
        const g = ctx.createLinearGradient(0, -r * 1.5, 0, -r * 0.7); g.addColorStop(0, '#fff59d'); g.addColorStop(1, '#ffb300');
        ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(-r * 0.55, -r * 0.78); ctx.lineTo(-r * 0.62, -r * 1.42); ctx.lineTo(-r * 0.3, -r * 1.12); ctx.lineTo(0, -r * 1.55); ctx.lineTo(r * 0.3, -r * 1.12); ctx.lineTo(r * 0.62, -r * 1.42); ctx.lineTo(r * 0.55, -r * 0.78); ctx.closePath(); ctx.fill();
        ctx.strokeStyle = '#ff8f00'; L(0.04); ctx.stroke();
        ctx.fillStyle = '#e53935'; ctx.beginPath(); ctx.arc(0, -r * 0.98, r * 0.1, 0, 7); ctx.fill(); ctx.fillStyle = '#1e88e5'; ctx.beginPath(); ctx.arc(-r * 0.32, -r * 0.92, r * 0.07, 0, 7); ctx.arc(r * 0.32, -r * 0.92, r * 0.07, 0, 7); ctx.fill();
        break;
      }
      default: break;
    }
    ctx.restore();
  }

  // ---------- сохранение (через ядро: localStorage + хранилище площадки) ----------
  const X = () => { const e = C.save.extra; if (!e.fb) e.fb = { owned: [0], on: 0, giftAt: 0, giftAd: 0, adc: { d: '', n: 0, t: 0 }, nick: '', skin: '' }; return e.fb; };

  let ws = null, status = 'idle', lostT = 0, connT = 0, attempt = 0, lastMsgT = 0, myId = 0, R = 1200, Rshow = 1200, joined = false, nick = '', skin = 'US';
  const balls = new Map(), dots = new Map(), knownHumans = new Set();
  let powers = [], saws = [], sawSpin = 0;
  let me = { x: 0, y: 0, vx: 0, vy: 0, r: rOf(10), m: 10, alive: false, shield: 0, boost: 0, magnet: 0, ang: 0 };
  let cam = { x: 0, y: 0, z: 1 }, joy = null, feed = [], floats = [], toasts = [], dead = null, sendT = 0, pingMs = 0, best = 10, growFx = 0, reT = 0;
  let cs = [], rt = 180, rl = 180, dayTopL = [], banner = null, lifeEats = 0, shop = null, adFails = 0, busy = false;
  let lastReviveAt = -1e9, lastDoubleAt = -1e9, pending = null;
  let adFailAt = -1e9;
  const adsOk = () => C.rewardedSupported && nowS() - adFailAt > 180;

  function connect() {
    if (ws) { const o = ws; ws = null; o.onclose = null; o.onmessage = null; try { o.close(); } catch (e) { /* */ } }
    status = 'conn'; connT = 0; attempt++;
    let sock; try { sock = new WebSocket(SERVER); } catch (e) { status = 'lost'; lostT = 0; return; }
    ws = sock;
    sock.onopen = () => { if (ws === sock) sock.send(JSON.stringify(SPEC ? { t: 'hello', spec: 1, room: ROOM } : { t: 'hello', name: nick, skin, room: ROOM, acc: X().on })); };
    sock.onmessage = (e) => { if (ws !== sock) return; lastMsgT = nowS(); let m; try { m = JSON.parse(e.data); } catch (er) { return; } onMsg(m); };
    sock.onclose = () => { if (ws !== sock) return; status = 'lost'; lostT = 0; };
    sock.onerror = () => { /* onclose сработает */ };
  }
  function send(o) { if (ws && ws.readyState === 1) { try { ws.send(JSON.stringify(o)); } catch (e) { /* */ } } }
  document.addEventListener('visibilitychange', () => { if (!document.hidden && joined && nowS() - lastMsgT > 2) connect(); });
  // связь держим и во время рекламы (игра в это время на паузе, а сервер закрывает «молчащих» через 12 с)
  setInterval(() => { if (status === 'ok') send({ t: 'ping', c: performance.now() }); }, 2000);

  // ---------- CrazyGames: комнаты, приглашения, «сразу в мультиплеер» ----------
  const CG = () => { try { const sdk = window.CrazyGames && window.CrazyGames.SDK; return sdk && sdk.game && (sdk.environment === 'crazygames' || sdk.environment === 'local') ? sdk : null; } catch (e) { return null; } };
  const randRoom = () => 'p' + Math.random().toString(36).slice(2, 9);
  function pickRoomOnPlatform() {
    const sdk = CG(); if (!sdk) return;
    try {
      const ip = sdk.game.inviteParams;
      if (ip && cleanRoom(ip.room)) ROOM = cleanRoom(ip.room);                  // пришёл по приглашению
      else if (sdk.game.isInstantMultiplayer) ROOM = randRoom();                // «играть с друзьями»: своя комната
      // друг позвал, когда игра уже открыта — переходим к нему без перезагрузки
      if (sdk.game.addJoinRoomListener) sdk.game.addJoinRoomListener((p) => { const r = cleanRoom(p && p.room); if (r && r !== ROOM) { ROOM = r; if (joined) connect(); } });
      // вошёл в аккаунт CrazyGames во время игры — дальше играем под его ником
      if (sdk.user && sdk.user.addAuthListener) sdk.user.addAuthListener((u) => { if (u && u.username) { nick = String(u.username).slice(0, 14); const x = X(); x.nick = nick; C.persist(); } });
    } catch (e) { /* */ }
  }
  function reportRoom(joinable) {
    const sdk = CG(); if (!sdk) return;
    try {
      if (sdk.game.updateRoom) sdk.game.updateRoom(joinable ? { roomId: ROOM, isJoinable: true, inviteParams: { room: ROOM } } : { roomId: ROOM, isJoinable: false });
      else if (joinable && sdk.game.showInviteButton) sdk.game.showInviteButton({ room: ROOM });
    } catch (e) { /* */ }
  }
  function inviteLink() {
    const sdk = CG();
    try { if (sdk) return sdk.game.inviteLink({ room: ROOM }); } catch (e) { /* */ }
    return location.origin + location.pathname + '?room=' + encodeURIComponent(ROOM);
  }
  async function copyText(t) {
    try { if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(t); return true; } } catch (e) { /* */ }
    try {
      const a = document.createElement('textarea'); a.value = t; a.setAttribute('readonly', ''); a.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
      document.body.appendChild(a); a.select(); const ok = document.execCommand('copy'); a.remove(); return !!ok;
    } catch (e) { return false; }
  }
  // скопировать не дали (браузер запретил) — показываем ссылку в поле, чтобы скопировать руками
  function showLinkBox(link) {
    let el = document.getElementById('lnk');
    if (!el) {
      el = document.createElement('div'); el.id = 'lnk';
      el.style.cssText = 'position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(10,10,40,.75);z-index:6;touch-action:auto';
      el.innerHTML = '<div style="width:min(92vw,520px);background:#221d45;border-radius:20px;padding:18px;color:#fff;text-align:center;font:600 17px system-ui,Arial,sans-serif"><div id="lnkT" style="margin-bottom:10px"></div><input id="lnkI" readonly style="width:100%;box-sizing:border-box;background:#14112b;border:2px solid #4a4380;color:#fff;border-radius:12px;padding:10px;font-size:15px;user-select:text;-webkit-user-select:text"><button id="lnkB" style="margin-top:12px;width:100%;border:0;border-radius:14px;padding:12px;font-size:20px;font-weight:800;color:#fff;background:#1e88e5">OK</button></div>';
      document.body.appendChild(el);
      el.querySelector('#lnkB').onclick = () => { el.style.display = 'none'; };
    }
    el.querySelector('#lnkT').textContent = T.copyHint; const i = el.querySelector('#lnkI'); i.value = link; el.style.display = 'flex';
    setTimeout(() => { try { i.focus(); i.select(); } catch (e) { /* */ } }, 50);
  }
  async function shareInvite() {
    const link = inviteLink();
    if (await copyText(link)) toasts.push({ text: T.copied, t: 0, col: '#69f0ae' });
    else showLinkBox(link);
  }

  function setMeta(list) {
    for (const [id, name, sk, hum, acc] of list) {
      let b = balls.get(id); if (!b) { b = mkB(id); balls.set(id, b); }
      b.name = name; b.skin = sk; b.human = !!hum; b.acc = acc | 0;
      if (hum && !knownHumans.has(id)) { knownHumans.add(id); if (id !== myId && myId) toasts.push({ text: name + ' ' + T.joined, t: 0, col: '#69f0ae' }); }
    }
  }
  function mkB(id) { return { id, x: 0, y: 0, sx: 0, sy: 0, pvx: 0, pvy: 0, st: 0, m: 10, r: rOf(10), alive: false, fl: 0, name: '', skin: 'US', human: false, ang: 0, fresh: true, acc: 0 }; }

  function onMsg(m) {
    const now = nowS();
    if (m.t === 'w') {
      status = 'ok'; attempt = 0; myId = m.id; R = m.R; Rshow = m.R; balls.clear(); dots.clear(); knownHumans.clear();
      setMeta(m.mt);
      for (const [id, x, y, c] of m.dots) dots.set(id, { x, y, c: PCOL[c], r: 9 + (id % 5) });
      me = { x: m.x, y: m.y, vx: 0, vy: 0, r: rOf(18), m: 18, alive: !m.spec, shield: 4, boost: 0, magnet: 0, ang: 0 }; dead = null; best = 18; reT = 0; lifeEats = 0;
      cam.x = me.x; cam.y = me.y; steer.on = false;
      if (m.cs) cs = m.cs; if (m.rt) rt = m.rt; if (m.rl) rl = m.rl; if (m.day) dayTopL = m.day;
      if (!m.spec) { C.msg('gameplay_started'); reportRoom(true); }
      return;
    }
    if (m.t === 's') {
      if (m.R > R + 30) growFx = 2.2;
      R = m.R;
      if (m.mt && m.mt.length) setMeta(m.mt);
      if (m.cs) cs = m.cs; if (m.rt) rt = m.rt;
      const seen = new Set();
      for (const [id, x, y, m10, al, fl] of m.b) {
        seen.add(id);
        let b = balls.get(id); if (!b) { b = mkB(id); balls.set(id, b); }
        const dts = Math.max(0.03, now - b.st);
        if (al && b.alive && !b.fresh) { b.pvx = C.clamp((x - b.sx) / dts, -1400, 1400); b.pvy = C.clamp((y - b.sy) / dts, -1400, 1400); }
        else { b.x = x; b.y = y; b.pvx = 0; b.pvy = 0; }
        b.fresh = false; b.sx = x; b.sy = y; b.st = now; b.m = m10 / 10; b.r = rOf(b.m); b.alive = !!al; b.fl = fl;
        if (id === myId) { me.m = b.m; me.r = b.r; me.shield = fl & 1; me.boost = fl & 2; me.magnet = fl & 4; if (al && me.alive) best = Math.max(best, me.m); }
      }
      for (const id of Array.from(balls.keys())) if (!seen.has(id)) { const b = balls.get(id); if (b.human && id !== myId) toasts.push({ text: b.name + ' ' + T.left, t: 0, col: '#fff' }); balls.delete(id); }
      for (const [id, x, y, c] of m.da) dots.set(id, { x, y, c: PCOL[c], r: 9 + (id % 5) });
      for (const id of m.dd) dots.delete(id);
      if (m.pw) { const old = new Map(powers.map((p) => [p.id, p])); powers = m.pw.map(([id, x, y, k]) => ({ id, x, y, k, a: old.has(id) ? old.get(id).a : 0 })); }
      if (m.sw) { const prev = saws; saws = m.sw.map(([x, y], i) => ({ tx: x, ty: y, x: prev[i] ? prev[i].x : x, y: prev[i] ? prev[i].y : y })); }
      for (const [a, b, k] of m.ev) {
        if (k === 1) {
          const A = balls.get(a), B = balls.get(b);
          feed.unshift({ a: A ? A.skin : 'US', b: B ? B.skin : 'US', an: A && A.human ? A.name : '', bn: B && B.human ? B.name : '', t: 0, me: a === myId || b === myId }); feed.length = Math.min(feed.length, 4);
          if (a === myId && B) { lifeEats++; C.sfx('pop'); floats.push({ x: me.x, y: me.y - me.r, text: '+' + Math.round(B.m * 0.85), t: 0, col: '#ffeb3b' }); C.burst(...toScr(B.x, B.y), '#ffd54f', 16, 380); }
          if (B && !B.alive) { B.eatenBy = a; B.eatK = 0; }
          if (SPEC) { dir.lastEat.set(a, nowS()); if (B) dir.log.push({ t: nowS(), k: 'eat', m: Math.round(B.m), a: A ? A.skin : '', b: B.skin }); }
        } else if (k === 3) {
          const A = balls.get(a);
          if (a === myId) { C.sfx('crash', 0.6); floats.push({ x: me.x, y: me.y - me.r, text: '−' + b, t: 0, col: '#ff5252' }); C.burst(...toScr(me.x, me.y), '#b0bec5', 24, 520); }
          else if (A) C.burst(...toScr(A.x, A.y), '#b0bec5', 10, 300);
        } else if (k === 4 && a === myId) {
          C.sfx('buy'); const name = [T.bolt, T.magnet, T.shield][b] || ''; floats.push({ x: me.x, y: me.y - me.r - 20, text: name, t: 0, col: POW[b] ? POW[b].col : '#fff' });
        }
      }
      return;
    }
    if (m.t === 'rw') { // раунд стран окончен
      cs = []; rt = rl; if (m.day) dayTopL = m.day;
      if (SPEC) dir.log.push({ t: nowS(), k: 'round', win: m.win, top: m.top });
      if (m.win) {
        const mine = !SPEC && m.win === skin && joined;
        banner = { win: m.win, top: m.top || [], t: 0, mine };
        if (mine) { C.sfx('win'); C.confetti(C.W / 2, C.H * 0.25, 70); C.addCoins(25); }
      }
      return;
    }
    if (m.t === 'fix') {
      me.x = m.x; me.y = m.y; me.vx = 0; me.vy = 0;
      if (m.re) { const mm = m.m || 18; me.alive = true; me.m = mm; me.r = rOf(mm); me.shield = 4; dead = null; best = mm; lifeEats = 0; steer.on = false; reT = 0; cam.x = me.x; cam.y = me.y; C.msg('gameplay_started'); }
      return;
    }
    if (m.t === 'dead') { if (m.day) dayTopL = m.day; onDeath(m); return; }
    if (m.t === 'pong') { pingMs = Math.round(performance.now() - m.c); return; }
    if (m.t === 'full') { reportRoom(false); if (ROOM !== 'main' && !SPEC) ROOM = 'main'; status = 'lost'; lostT = 0; return; }
  }

  // ---------- смерть: монеты за жизнь и предложение (возрождение / x2 / ничего — тогда межстраничная) ----------
  function onDeath(m) {
    me.alive = false; joy = null; C.msg('gameplay_stopped');
    const k = balls.get(m.by);
    const coins = Math.max(1, Math.floor(best / 10) + lifeEats * 3);
    const t = nowS();
    let offer = null;
    if (best >= 40 && t - lastReviveAt > 240 && (adsOk() || C.save.coins + coins >= 150)) offer = 'revive';
    else if (adsOk() && coins >= 6 && t - lastDoubleAt > 120) offer = 'double';
    dead = { by: k ? (k.human ? k.name : cname(k.skin)) : '', skin: k ? k.skin : 'US', acc: k ? k.acc : 0, human: k && k.human, t: 0, killer: m.by, best: Math.round(best), eats: lifeEats, coins, offer, revived: false, doubled: false };
    C.addCoins(coins);
    C.sfx('crash', 0.6);
  }
  function respawnMsg(keep) { const o = { t: 're', skin, name: nick, acc: X().on }; if (keep) o.keep = 1; return o; }
  function doRespawn(keep) { if (reT > 0) return; send(respawnMsg(keep)); reT = 1.6; pending = keep ? 'keep' : 're'; }
  async function playAgain() {
    if (busy || reT > 0) return;
    // межстраничная — только если в этом окне не было рекламы за награду (правило CrazyGames)
    if (dead && !dead.offer) { busy = true; await C.ads.interstitial('death'); busy = false; }
    doRespawn(false);
  }
  async function rewarded(pl) {
    busy = true; const ok = await C.ads.rewarded(pl); busy = false;
    if (ok) adFails = 0; else { adFails++; adFailAt = nowS(); toasts.push({ text: T.noAd, t: 0, col: '#ffd54f' }); }
    return ok;
  }

  function toScr(x, y) { return [(x - cam.x) * cam.z + C.W / 2, (y - cam.y) * cam.z + C.H / 2]; }
  const relOf = (b) => (!me.alive ? 0 : me.r > b.r * 1.12 ? 1 : b.r > me.r * 1.12 ? -1 : 0);

  // ---------- вход: на площадках — сразу в игру; на своём сайте в первый раз — имя и страна ----------
  function startJoin(n, s) {
    nick = n; skin = PICK_FLAGS.indexOf(s) >= 0 ? s : 'US'; joined = true;
    const x = X(); x.nick = nick; x.skin = skin; C.persist();
    try { localStorage.setItem('ballio_nick', nick); localStorage.setItem('ballio_skin', skin); } catch (e) { /* */ }
    connect();
  }
  window.__join = (n, s) => {
    if (joined) { // смена страны/имени между жизнями
      nick = n || nick; if (PICK_FLAGS.indexOf(s) >= 0) skin = s; const x = X(); x.nick = nick; x.skin = skin; C.persist();
      try { localStorage.setItem('ballio_nick', nick); localStorage.setItem('ballio_skin', skin); } catch (e) { /* */ }
      return;
    }
    startJoin(n, s);
  };
  function guestName() { return (LANG === 'ru' ? 'Гость' : 'Guest') + (100 + ((Math.random() * 900) | 0)); }
  function platformName() { try { const p = window.bridge && window.bridge.player; if (p && p.isAuthorized && p.name) return String(p.name).slice(0, 14); } catch (e) { /* */ } return ''; }
  function showJoin(first) { if (window.__showJoin) window.__showJoin({ first, nick: nick || X().nick || '', skin: skin || X().skin || C.homeCountry(), home: C.homeCountry(), T, flags: PICK_FLAGS, names: CN[LANG], names2: CN[LANG === 'ru' ? 'en' : 'ru'] }); }

  function drawSaw(ctx, x, y, r, spin, danger) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(spin);
    if (danger) { ctx.fillStyle = 'rgba(255,23,68,0.18)'; ctx.beginPath(); ctx.arc(0, 0, r * 1.35, 0, 7); ctx.fill(); }
    ctx.fillStyle = '#90a4ae'; ctx.strokeStyle = '#37474f'; ctx.lineWidth = 3; ctx.beginPath();
    const n = 16; for (let i = 0; i < n; i++) { const a0 = (i / n) * Math.PI * 2, a1 = ((i + 0.6) / n) * Math.PI * 2; ctx.lineTo(Math.cos(a0) * r * 0.82, Math.sin(a0) * r * 0.82); ctx.lineTo(Math.cos(a1) * r * 1.08, Math.sin(a1) * r * 1.08); }
    ctx.closePath(); ctx.fill(); ctx.stroke();
    const g = ctx.createRadialGradient(-r * 0.2, -r * 0.2, 2, 0, 0, r * 0.8); g.addColorStop(0, '#eceff1'); g.addColorStop(1, '#78909c');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, r * 0.74, 0, 7); ctx.fill();
    ctx.fillStyle = '#455a64'; ctx.beginPath(); ctx.arc(0, 0, r * 0.2, 0, 7); ctx.fill();
    ctx.strokeStyle = 'rgba(55,71,79,0.6)'; ctx.lineWidth = 3; for (let i = 0; i < 3; i++) { const a = (i / 3) * Math.PI * 2; ctx.beginPath(); ctx.moveTo(Math.cos(a) * r * 0.28, Math.sin(a) * r * 0.28); ctx.lineTo(Math.cos(a) * r * 0.62, Math.sin(a) * r * 0.62); ctx.stroke(); }
    ctx.restore();
  }
  // обрезать строку под ширину (длинные ники и страны не наезжают на цифры)
  function fit(str, maxW, size) { const ctx = C.ctx || document.getElementById('c').getContext('2d'); ctx.save(); ctx.font = C.font(size); let t = String(str); if (ctx.measureText(t).width > maxW) { while (t.length > 1 && ctx.measureText(t + '…').width > maxW) t = t.slice(0, -1); t += '…'; } ctx.restore(); return t; }
  const fmtT = (s) => { s = Math.max(0, Math.ceil(s)); const h = Math.floor(s / 3600), mi = Math.floor((s % 3600) / 60), se = s % 60; return (h ? h + ':' + String(mi).padStart(2, '0') : mi) + ':' + String(se).padStart(2, '0'); };

  // ---------- подарок по таймеру и монеты за рекламу ----------
  const GIFT_EVERY = 3 * 3600;
  const giftLeft = () => Math.max(0, GIFT_EVERY - (Date.now() / 1000 - (X().giftAt || 0)));
  function claimGift(x, y) { const n = 40 + ((Math.random() * 7) | 0) * 10; const f = X(); f.giftAt = Date.now() / 1000; f.giftAd = 0; C.addCoins(n, x, y); C.confetti(x, y, 50); C.sfx('win'); }
  const AD_COINS = [60, 40, 25];
  function adCoinsState() { const f = X(); const d = C.today(); if (f.adc.d !== d) f.adc = { d, n: 0, t: 0 }; return f.adc; }

  const game = {
    id: 'ballio_online', startState: 'play', noLevels: true, hasSkip: false, reviveIcon: null, noPauseBtn: true, noGift: true, landscapeBase: true, noPlatformPause: true, manualGameplay: true,
    startLevel() {}, toHome() {}, revive() {},
    canInter(sess, sinceInter, sinceReward) { return ((C.bridgeOk && !C.mockAds) || q.has('inter')) && sess > 60 && sinceReward > 30; },
    init() {
      LANG = (C.lang || 'en').slice(0, 2) === 'ru' ? 'ru' : 'en'; T = TX[LANG];
      if (SPEC) { skin = ''; joined = true; connect(); return; }
      const f = X();
      let n = '', s = '';
      try { n = localStorage.getItem('ballio_nick') || ''; s = localStorage.getItem('ballio_skin') || ''; } catch (e) { /* */ }
      n = f.nick || n; s = f.skin || s;
      const pn = platformName(); if (pn) n = pn;
      if (!s || PICK_FLAGS.indexOf(s) < 0) s = PICK_FLAGS.indexOf(C.homeCountry()) >= 0 ? C.homeCountry() : 'US';
      nick = n; skin = s;
      // на площадке (CrazyGames, Playgama…) — сразу в игру, без окна; на своём сайте — окно только в первый раз
      pickRoomOnPlatform();
      if (C.bridgeOk || n || q.has('auto')) startJoin(n || guestName(), s);
      else showJoin(true);
    },
    onDown(x, y) { if (!me.alive || shop) return; joy = { ax: x, ay: y, x, y, rx: 0, ry: 0 }; },
    onMove(x, y) {
      if (!joy) return;
      const mx = x - joy.x, my = y - joy.y, ml = Math.hypot(mx, my); joy.x = x; joy.y = y;
      if (ml < 0.01) return;
      if (steer.on) {
        if (mx * steer.x + my * steer.y < ml * 0.5) { joy.rx += mx; joy.ry += my; } else { joy.rx = 0; joy.ry = 0; }
        const rl2 = Math.hypot(joy.rx, joy.ry);
        if (rl2 > TURN && joy.rx * steer.x + joy.ry * steer.y < rl2 * 0.5) { steer.x = joy.rx / rl2; steer.y = joy.ry / rl2; joy.ax = x - steer.x * LEASH; joy.ay = y - steer.y * LEASH; joy.rx = joy.ry = 0; return; }
      }
      const vx = x - joy.ax, vy = y - joy.ay; let d = Math.hypot(vx, vy);
      if (d > LEASH) { joy.ax = x - (vx / d) * LEASH; joy.ay = y - (vy / d) * LEASH; d = LEASH; }
      if (d > DEAD) { const l = Math.hypot(vx, vy); steer.x = vx / l; steer.y = vy / l; steer.on = true; }
    },
    onUp() { joy = null; },
    onHover(x, y) {
      if (!me.alive) return;
      const [sx, sy] = toScr(me.x, me.y), vx = x - sx, vy = y - sy, d = Math.hypot(vx, vy);
      if (d > Math.max(16, me.r * cam.z * 0.4)) { steer.x = vx / d; steer.y = vy / d; steer.on = true; }
    },
    onKey(k, down) { if (down && (k === 'Space' || k === 'Enter') && dead && !me.alive && dead.t > 0.4 && !shop) playAgain(); },

    update(dt) {
      const now = nowS();
      for (const f of feed) f.t += dt; feed = feed.filter((f) => f.t < 3.5);
      for (const f of floats) f.t += dt; floats = floats.filter((f) => f.t < 1.1);
      for (const f of toasts) f.t += dt; toasts = toasts.filter((f) => f.t < 3); if (toasts.length > 3) toasts.splice(0, toasts.length - 3);
      if (banner) { banner.t += dt; if (banner.t > (SPEC ? 8 : 4.5)) banner = null; }
      rt = Math.max(0, rt - dt);
      growFx = Math.max(0, growFx - dt); Rshow += (R - Rshow) * Math.min(1, dt * 2);
      sawSpin += dt * 7; for (const p of powers) p.a += dt;
      for (const s of saws) { s.x += (s.tx - s.x) * Math.min(1, dt * 8); s.y += (s.ty - s.y) * Math.min(1, dt * 8); }
      if (dead) dead.t += dt;
      if (joined) {
        if (status === 'conn') { connT += dt; if (connT > 6) connect(); }
        else if (status === 'lost') { lostT += dt; if (lostT > 1.5) connect(); }
        else if (status === 'ok' && now - lastMsgT > 4) connect();
      }
      if (reT > 0) { reT -= dt; if (reT <= 0 && !me.alive) connect(); }
      if (me.alive && status === 'ok') {
        let dx = 0, dy = 0, pw = 0;
        if (steer.on) { dx = steer.x; dy = steer.y; pw = 1; }
        const kx = C.keyDir(), ky = C.keyDirY(); if (kx || ky) { const d = Math.hypot(kx, ky); dx = kx / d; dy = ky / d; pw = 1; }
        if (window.__bot) { const t = window.__bot(me, balls); dx = t[0]; dy = t[1]; pw = 1; }
        const sp = speedOf(me.r) * (me.boost ? 1.6 : 1), k = Math.min(1, dt * 30);
        me.vx += (dx * sp * pw - me.vx) * k; me.vy += (dy * sp * pw - me.vy) * k;
        me.x += me.vx * dt; me.y += me.vy * dt;
        const d = Math.hypot(me.x, me.y), lim = R - me.r * 0.6; if (d > lim) { me.x *= lim / d; me.y *= lim / d; }
        me.ang += (Math.hypot(me.vx, me.vy) / me.r) * dt * (me.vx >= 0 ? 1 : -1);
        const pr = me.magnet ? me.r + 170 : me.r, rr = pr * pr;
        for (const p of dots.values()) { const ax = p.x - me.x, ay = p.y - me.y; if (ax * ax + ay * ay < rr && !p.hid) { p.hid = true; if (Math.random() < 0.25) C.sfx('coin'); } }
        sendT -= dt; if (sendT <= 0) { sendT = 0.05; send({ t: 'p', x: Math.round(me.x), y: Math.round(me.y) }); }
      }
      for (const b of balls.values()) {
        if (b.id === myId) { b.x = me.x; b.y = me.y; continue; }
        const age = Math.min(0.12, now - b.st), tx = b.sx + b.pvx * age, ty = b.sy + b.pvy * age, k = Math.min(1, dt * 14);
        b.x += (tx - b.x) * k; b.y += (ty - b.y) * k;
        b.ang += (Math.hypot(b.pvx, b.pvy) / b.r) * dt * (b.pvx >= 0 ? 1 : -1);
        if (!b.alive && b.eatenBy) b.eatK = Math.min(1, (b.eatK || 0) + dt * 5);
      }
      if (SPEC) { directorUpdate(dt); return; }
      let tgt = me;
      if (!me.alive && dead) { const k = balls.get(dead.killer); if (k && k.alive) tgt = k; }
      cam.x += (tgt.x - cam.x) * Math.min(1, dt * 12); cam.y += (tgt.y - cam.y) * Math.min(1, dt * 12);
      const base = C.H < 1000 ? 1.1 : 1.25; // в альбоме и на телефоне видно примерно одинаковую площадь арены — честно для всех
      const z = C.clamp(base * Math.pow(40 / Math.max(40, me.r), 0.55), 0.24, base); cam.z += (z - cam.z) * Math.min(1, dt * 2);
    },

    draw(ctx) {
      ctx.fillStyle = '#2b2d6e'; ctx.fillRect(0, 0, C.W, C.H);
      ctx.save(); ctx.translate(C.W / 2, C.H / 2); ctx.scale(cam.z, cam.z); ctx.translate(-cam.x, -cam.y);
      const vw = C.W / cam.z / 2 + 120, vh = C.H / cam.z / 2 + 120, x0 = cam.x - vw, x1 = cam.x + vw, y0 = cam.y - vh, y1 = cam.y + vh;
      const RR = Rshow;
      const fg = ctx.createRadialGradient(0, 0, RR * 0.1, 0, 0, RR); fg.addColorStop(0, '#e3fbff'); fg.addColorStop(1, '#c9ecff');
      ctx.fillStyle = fg; ctx.beginPath(); ctx.arc(0, 0, RR, 0, 7); ctx.fill();
      ctx.save(); ctx.beginPath(); ctx.arc(0, 0, RR, 0, 7); ctx.clip();
      ctx.strokeStyle = 'rgba(41,121,255,0.16)'; ctx.lineWidth = 4 / cam.z; const gs = 90; ctx.beginPath();
      for (let x = Math.floor(x0 / gs) * gs; x < x1; x += gs) { ctx.moveTo(x, y0); ctx.lineTo(x, y1); }
      for (let y = Math.floor(y0 / gs) * gs; y < y1; y += gs) { ctx.moveTo(x0, y); ctx.lineTo(x1, y); }
      ctx.stroke(); ctx.restore();
      const gk = Math.min(1, growFx), pul = gk * (0.5 + 0.5 * Math.sin(C.realT * 10));
      ctx.strokeStyle = gk > 0 ? 'rgba(0,230,118,' + (0.5 + 0.5 * pul) + ')' : '#7c4dff'; ctx.lineWidth = 28 + 30 * pul; ctx.beginPath(); ctx.arc(0, 0, RR + 14, 0, 7); ctx.stroke();
      ctx.strokeStyle = gk > 0 ? '#b9f6ca' : '#b388ff'; ctx.lineWidth = 8; ctx.stroke();
      for (const p of dots.values()) { if (p.hid || p.x < x0 || p.x > x1 || p.y < y0 || p.y > y1) continue; ctx.fillStyle = p.c; ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 7); ctx.fill(); ctx.fillStyle = 'rgba(255,255,255,0.6)'; ctx.beginPath(); ctx.arc(p.x - p.r * 0.3, p.y - p.r * 0.3, p.r * 0.35, 0, 7); ctx.fill(); }
      for (const p of powers) {
        if (p.x < x0 || p.x > x1 || p.y < y0 || p.y > y1) continue;
        const s = 1 + Math.sin(p.a * 5) * 0.08, P = POW[p.k] || POW[0];
        ctx.fillStyle = 'rgba(255,255,255,0.5)'; ctx.beginPath(); ctx.arc(p.x, p.y, 40 * s, 0, 7); ctx.fill();
        ctx.fillStyle = P.col; ctx.beginPath(); ctx.arc(p.x, p.y, 32 * s, 0, 7); ctx.fill(); C.icon(P.icon, p.x, p.y, 42, '#fff');
      }
      const list = Array.from(balls.values()).filter((b) => b.alive || (b.eatenBy && b.eatK < 1)).sort((a, b) => a.r - b.r);
      for (const b of list) {
        let x = b.x, y = b.y, r = b.r; const mine = b.id === myId;
        if (!b.alive && b.eatenBy) { const k = balls.get(b.eatenBy); if (k) { x = C.lerp(b.x, k.x, b.eatK); y = C.lerp(b.y, k.y, b.eatK); } r = b.r * (1 - b.eatK); }
        if (mine && me.alive) { x = me.x; y = me.y; r = me.r; }
        if (x + r * 1.6 < x0 || x - r * 1.6 > x1 || y + r * 1.6 < y0 || y - r * 1.6 > y1 || r < 1) continue;
        const fl = mine ? (me.shield ? 1 : 0) | (me.boost ? 2 : 0) | (me.magnet ? 4 : 0) : b.fl;
        ctx.fillStyle = 'rgba(30,40,80,0.18)'; ctx.beginPath(); ctx.ellipse(x + r * 0.12, y + r * 0.2, r, r * 0.95, 0, 0, 7); ctx.fill();
        if (fl & 2) { const vx = mine ? me.vx : b.pvx, vy = mine ? me.vy : b.pvy; ctx.fillStyle = 'rgba(255,214,0,0.4)'; ctx.beginPath(); ctx.arc(x - vx * 0.07, y - vy * 0.07, r * 0.95, 0, 7); ctx.fill(); }
        C.drawBall(x, y, r, b.skin, (mine ? me.ang : b.ang) * 0.15, ctx, mine ? 'rgba(255,255,255,0.95)' : b.human ? 'rgba(255,235,59,0.85)' : null);
        drawAcc(ctx, mine ? X().on : b.acc, x, y, r);
        if (!mine && b.alive) { const rl2 = relOf(b); if (rl2) { ctx.strokeStyle = rl2 > 0 ? PREY : DANGER; ctx.lineWidth = 7 / cam.z; ctx.beginPath(); ctx.arc(x, y, r + 4 / cam.z, 0, 7); ctx.stroke(); } }
        if (b.alive && (fl & 1)) { ctx.strokeStyle = 'rgba(64,196,255,' + (0.5 + 0.4 * Math.sin(C.realT * 12)) + ')'; ctx.lineWidth = 8 / cam.z; ctx.beginPath(); ctx.arc(x, y, r + 10 / cam.z, 0, 7); ctx.stroke(); }
        if (b.alive && (fl & 4)) { ctx.strokeStyle = 'rgba(255,64,129,0.45)'; ctx.lineWidth = 4 / cam.z; ctx.setLineDash([12, 12]); ctx.beginPath(); ctx.arc(x, y, r + 170 - ((C.realT * 80) % 40), 0, 7); ctx.stroke(); ctx.setLineDash([]); }
      }
      for (const s of saws) { if (s.x < x0 - 60 || s.x > x1 + 60 || s.y < y0 - 60 || s.y > y1 + 60) continue; drawSaw(ctx, s.x, s.y, SAW_R, sawSpin, me.alive && me.r >= SAW_R * 1.15); }
      for (const f of floats) { ctx.globalAlpha = Math.max(0, 1 - f.t); C.text(f.text, f.x, f.y - f.t * 80, (34 / Math.max(0.5, cam.z)) * 0.8, f.col || '#ffeb3b'); ctx.globalAlpha = 1; }
      ctx.restore();
      for (const b of balls.values()) {
        if (!b.alive) continue;
        const mine = b.id === myId, [sx, sy] = mine ? toScr(me.x, me.y) : toScr(b.x, b.y), sr = (mine ? me.r : b.r) * cam.z;
        if (sx < -120 || sx > C.W + 120 || sy < -120 || sy > C.H + 120) continue;
        const rl2 = mine ? 2 : relOf(b), col = rl2 === 2 ? '#ffeb3b' : rl2 > 0 ? '#69f0ae' : rl2 < 0 ? '#ff5252' : '#ffffff';
        C.text(String(Math.round(b.m)), sx, sy + sr + 20, C.clamp(sr * 0.5, 24, 42), col, 'center', 'rgba(0,0,0,0.8)');
        // в роликах ники живых игроков не показываем (это их личные данные): пишем «PLAYER · страна»
        if (b.human && SPEC) C.text('PLAYER · ' + cname(b.skin), sx, sy - sr - (b.acc >= 6 ? sr * 0.55 + 24 : 20), C.clamp(sr * 0.36, 22, 40), '#ffeb3b', 'center', 'rgba(0,0,0,0.85)');
        else if (b.human) C.text(b.name, sx, sy - sr - (b.acc >= 6 || (mine && X().on >= 6) ? sr * 0.55 + 26 : 22), C.clamp(sr * 0.42, 24, 38), mine ? '#ffeb3b' : '#fff', 'center', 'rgba(0,0,0,0.85)');
        else if (SPEC && sr > 30) C.text(cname(b.skin), sx, sy - sr - (b.acc >= 6 ? sr * 0.55 + 24 : 20), C.clamp(sr * 0.36, 22, 40), b.id === dir.id ? '#ffeb3b' : '#fff', 'center', 'rgba(0,0,0,0.85)');
      }
      if (me.alive && (steer.on || C.keyDir() || C.keyDirY()) && Math.hypot(me.vx, me.vy) > 40) {
        const a = Math.atan2(me.vy, me.vx), [sx, sy] = toScr(me.x, me.y), rr = me.r * cam.z + 22;
        ctx.save(); ctx.translate(sx + Math.cos(a) * rr, sy + Math.sin(a) * rr); ctx.rotate(a);
        ctx.fillStyle = 'rgba(255,255,255,0.9)'; ctx.strokeStyle = 'rgba(40,40,90,0.6)'; ctx.lineWidth = 3;
        ctx.beginPath(); ctx.moveTo(16, 0); ctx.lineTo(-8, -13); ctx.lineTo(-3, 0); ctx.lineTo(-8, 13); ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.restore();
      }
      if (joy) {
        ctx.fillStyle = 'rgba(40,40,110,0.16)'; ctx.strokeStyle = 'rgba(255,255,255,0.75)'; ctx.lineWidth = 5; ctx.beginPath(); ctx.arc(joy.ax, joy.ay, 62, 0, 7); ctx.fill(); ctx.stroke();
        ctx.fillStyle = 'rgba(255,255,255,0.85)'; ctx.strokeStyle = 'rgba(40,40,110,0.5)'; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(joy.x, joy.y, 30, 0, 7); ctx.fill(); ctx.stroke();
      }
    },

    hud(ctx) {
      if (!joined) return;
      if (SPEC) { drawSpecHud(ctx); return; }
      const L = C.H < 1000; // альбомный экран: всё плотнее
      let nh = 0; for (const b of balls.values()) if (b.human) nh++;
      const showPlay = me.alive || !dead || status !== 'ok';
      if (showPlay) {
        const sf = C.safeU ? C.safeU() : { t: 0, r: 0, b: 0, l: 0 };
        if (sf.t || sf.l || sf.r || sf.b) { const W0 = C.W, H0 = C.H; ctx.save(); ctx.translate(sf.l, sf.t); C.W = W0 - sf.l - sf.r; C.H = H0 - sf.t - sf.b; try { drawPlayHud(ctx, L, nh); } finally { ctx.restore(); C.W = W0; C.H = H0; } }
        else drawPlayHud(ctx, L, nh);
      }
      if (status === 'conn' || status === 'lost') {
        ctx.fillStyle = 'rgba(10,10,40,0.6)'; ctx.fillRect(0, 0, C.W, C.H);
        C.text(T.conn, C.W / 2, C.H * 0.42, 40, '#fff');
        if (attempt > 1) C.text(T.att + ' ' + attempt, C.W / 2, C.H * 0.47, 28, '#cfd8dc');
        const a = C.realT * 5; ctx.strokeStyle = '#fff'; ctx.lineWidth = 8; ctx.beginPath(); ctx.arc(C.W / 2, C.H * 0.55, 34, a, a + 4); ctx.stroke();
        if (attempt >= 3) { const w = Math.min(680, C.W - 30); ctx.fillStyle = 'rgba(0,0,0,0.4)'; C.rr(ctx, C.W / 2 - w / 2, C.H * 0.62, w, 60, 20); ctx.fill(); C.text(T.slow, C.W / 2, C.H * 0.62 + 30, 21, '#ffd54f'); }
      } else if (dead && !me.alive) {
        if (shop) drawShop(ctx, L); else drawDeath(ctx, L);
      }
    },
  };

  let hudBottom = 300;
  function drawPlayHud(ctx, L, nh) {
      const all = Array.from(balls.values()).filter((b) => b.alive).sort((a, b) => b.m - a.m);
      const mine = balls.get(myId);
      // таблица шариков — справа сверху
      const rows = all.slice(0, L ? 5 : 6); if (mine && mine.alive && !rows.includes(mine)) rows.push(mine);
      const TW = L ? 296 : 232, bx = C.W - TW - 18, by = 24; // в альбоме шире — ники видно целиком
      ctx.fillStyle = 'rgba(0,0,0,0.38)'; C.rr(ctx, bx, by, TW, rows.length * 44 + 60, 20); ctx.fill();
      C.text(T.players + ': ' + nh, bx + TW / 2, by + 28, 23, '#b9f6ca', 'center', null);
      rows.forEach((b, i) => {
        const y = by + 74 + i * 44, rank = all.indexOf(b) + 1;
        if (b.id === myId) { ctx.fillStyle = 'rgba(255,235,59,0.35)'; C.rr(ctx, bx + 6, y - 20, TW - 12, 40, 14); ctx.fill(); }
        C.text(String(rank), bx + 22, y, 24, rank === 1 ? '#ffc107' : '#fff', 'center', null);
        C.drawBall(bx + 56, y, 16, b.skin, 0, ctx);
        C.text(fit(b.human ? b.name : cname(b.skin), TW - 148, 21), bx + 80, y, 21, b.human ? '#ffeb3b' : '#e0e0e0', 'left', null);
        C.text(String(Math.round(b.m)), bx + TW - 20, y, 23, '#fff', 'right', null);
      });
      // зачёт стран — слева сверху: таймер раунда и тройка лидеров
      const cx0 = 18, cy0 = 24, cw = L ? 312 : 270, myRow = cs.findIndex((c) => c[0] === skin);
      const crow = cs.slice(0, 3); const extra = myRow >= 3 ? 1 : 0; const ch = 54 + Math.max(1, crow.length + extra) * 40;
      ctx.fillStyle = 'rgba(0,0,0,0.42)'; C.rr(ctx, cx0, cy0, cw, ch, 20); ctx.fill();
      C.icon('trophy', cx0 + 28, cy0 + 27, 30, '#ffd54f'); C.text(T.countries, cx0 + 50, cy0 + 28, 24, '#fff', 'left', null);
      C.text(fmtT(rt), cx0 + cw - 16, cy0 + 28, 24, rt < 20 ? '#ff8a80' : '#b9f6ca', 'right', null);
      const team = {}; for (const b of balls.values()) if (b.human) team[b.skin] = (team[b.skin] || 0) + 1;
      const crowRow = (c, i, y) => {
        const isMe = c[0] === skin, n = team[c[0]] || 0, bot = c[0] === 'BOT';
        if (isMe) { ctx.fillStyle = 'rgba(255,235,59,0.3)'; C.rr(ctx, cx0 + 6, y - 18, cw - 12, 36, 12); ctx.fill(); }
        C.text(String(i + 1), cx0 + 22, y, 22, i === 0 ? '#ffc107' : '#fff', 'center', null); C.drawBall(cx0 + 52, y, 14, c[0], 0, ctx);
        const tail = n > 1 ? ' ×' + n : '';
        C.text(fit(cname(c[0]), cw - 140 - (tail ? 30 : 0), 21) + tail, cx0 + 74, y, 21, isMe ? '#ffeb3b' : bot ? '#b0bec5' : '#fff', 'left', null);
        C.text(String(c[1]), cx0 + cw - 16, y, 21, bot ? '#b0bec5' : '#fff', 'right', null);
      };
      crow.forEach((c, i) => crowRow(c, i, cy0 + 72 + i * 40));
      if (extra) crowRow(cs[myRow], myRow, cy0 + 72 + crow.length * 40);
      if (!crow.length) C.text('…', cx0 + cw / 2, cy0 + 72, 24, '#cfd8dc');
      hudBottom = Math.max(by + rows.length * 44 + 60, cy0 + ch) + 20;
      if (mine && mine.alive) {
        const myRank = all.indexOf(mine) + 1, top = myRank <= 3, py = 24;
        ctx.fillStyle = top ? 'rgba(255,179,0,0.92)' : 'rgba(0,0,0,0.45)'; C.rr(ctx, C.W / 2 - 70, py, 140, 50, 25); ctx.fill();
        C.icon('trophy', C.W / 2 - 34, py + 25, 30, top ? '#fff' : '#ffd54f'); C.text('#' + myRank, C.W / 2 + 24, py + 26, 32, '#fff');
      }
      // своя комната — внизу по центру (сверху на узком телефоне налезало на таблицы)
      if (ROOM !== 'main') C.text(fit(T.room + ': ' + ROOM.toUpperCase(), C.W - 2 * (L ? 260 : 200), 20), C.W / 2, C.H - 28, 20, '#b9f6ca', 'center', 'rgba(0,0,0,0.6)');
      let ix = C.W / 2 - 56; for (const [on, P] of [[me.boost, POW[0]], [me.magnet, POW[1]], [me.shield, POW[2]]]) { if (!on || !me.alive) continue; ctx.fillStyle = P.col; ctx.beginPath(); ctx.arc(ix, 110, 24, 0, 7); ctx.fill(); C.icon(P.icon, ix, 110, 28, '#fff'); ix += 56; }
      const fy0 = cy0 + ch + 30;
      feed.forEach((f, i) => {
        const y = fy0 + i * 44; ctx.globalAlpha = Math.min(1, (3.5 - f.t) * 2);
        ctx.fillStyle = f.me ? 'rgba(255,82,82,0.55)' : 'rgba(0,0,0,0.32)'; C.rr(ctx, 18, y - 19, 250, 38, 19); ctx.fill();
        C.drawBall(40, y, 14, f.a, 0, ctx); C.text(f.an.slice(0, 6), 58, y, 20, '#fff', 'left', null);
        C.icon('next', 146, y, 20, '#fff'); C.drawBall(174, y, 12, f.b, 0, ctx); C.text(f.bn.slice(0, 6), 190, y, 20, '#fff', 'left', null);
        ctx.globalAlpha = 1;
      });
      // мини-карта
      const mR = C.clamp(95 * (Rshow / 2000), 50, L ? 90 : 120), mx = 26 + mR, my = C.H - 30 - mR, k = mR / Rshow;
      ctx.fillStyle = 'rgba(10,12,50,0.55)'; ctx.beginPath(); ctx.arc(mx, my, mR + 8, 0, 7); ctx.fill();
      ctx.fillStyle = 'rgba(201,236,255,0.35)'; ctx.beginPath(); ctx.arc(mx, my, mR, 0, 7); ctx.fill();
      ctx.strokeStyle = growFx > 0 ? '#00e676' : '#b388ff'; ctx.lineWidth = growFx > 0 ? 5 : 3; ctx.stroke();
      ctx.fillStyle = '#90a4ae'; for (const s of saws) { ctx.beginPath(); ctx.arc(mx + s.x * k, my + s.y * k, 4, 0, 7); ctx.fill(); }
      for (const b of balls.values()) { if (!b.alive || b.id === myId) continue; ctx.fillStyle = b.human ? '#ffffff' : 'rgba(255,255,255,0.35)'; ctx.beginPath(); ctx.arc(mx + b.x * k, my + b.y * k, b.human ? 5 : 3, 0, 7); ctx.fill(); }
      if (me.alive) { ctx.fillStyle = '#ffeb3b'; ctx.beginPath(); ctx.arc(mx + me.x * k, my + me.y * k, 7, 0, 7); ctx.fill(); ctx.strokeStyle = '#000'; ctx.lineWidth = 2; ctx.stroke(); }
      toasts.forEach((t, i) => { const y = C.H * 0.74 - i * 54; ctx.globalAlpha = Math.max(0, Math.min(1, (3 - t.t) * 2, t.t * 6)); ctx.fillStyle = 'rgba(0,0,0,0.55)'; C.rr(ctx, C.W / 2 - 310, y - 24, 620, 48, 24); ctx.fill(); C.text(t.text, C.W / 2, y, 28, t.col); ctx.globalAlpha = 1; });
      if (growFx > 0 && !toasts.length && me.alive) { ctx.globalAlpha = Math.min(1, growFx); C.text(T.grow, C.W / 2, C.H * 0.74, 40, '#69f0ae', 'center', 'rgba(0,0,0,0.8)'); ctx.globalAlpha = 1; }
      if (pingMs) C.text(pingMs + ' ms', C.W - 24, C.H - 26, 22, 'rgba(255,255,255,0.6)', 'right', null);
      // итог раунда стран
      if (banner && me.alive) drawBanner(ctx, L);
  }

  // ---------- режиссёр камеры (зритель): следит за самым интересным шариком ----------
  const dir = { id: 0, held: 0, evalT: 0, x: 0, y: 0, z: 0.7, lastEat: new Map(), log: [], partner: 0 };
  function pairOf(t) {
    let best = null, bd = 1e9;
    for (const o of balls.values()) {
      if (!o.alive || o === t) continue;
      const d = Math.hypot(o.x - t.x, o.y - t.y) - o.r - t.r;
      if (d < 340 && (t.r > o.r * 1.12 || o.r > t.r * 1.12) && d < bd) { bd = d; best = o; }
    }
    return best;
  }
  function directorUpdate(dt) {
    dir.held += dt; dir.evalT -= dt;
    let cur = balls.get(dir.id);
    if (cur && !cur.alive) { // съели — камера переходит на того, кто съел
      const k = cur.eatenBy && balls.get(cur.eatenBy);
      if (k && k.alive) { dir.id = k.id; dir.held = 0; cur = k; } else cur = null;
    }
    if (dir.evalT <= 0 || !cur) {
      dir.evalT = 0.5;
      const now = nowS(); let best = null, bs = 0, curS = 0;
      for (const b of balls.values()) {
        if (!b.alive) continue;
        const p = pairOf(b);
        const action = p ? Math.min(p.m, b.m) * 2.5 : 0;
        const hot = now - (dir.lastEat.get(b.id) || -99) < 5 ? 1.5 : 1;
        const sc = (b.m + action) * hot * (b.human ? 1.3 : 1);
        if (b.id === dir.id) curS = sc;
        if (sc > bs) { bs = sc; best = b; }
      }
      if (best && (!cur || (best.id !== dir.id && dir.held > 6 && bs > curS * 1.4))) { dir.id = best.id; dir.held = 0; }
    }
    const t = balls.get(dir.id);
    if (!t) return;
    let fx = t.x, fy = t.y, span = t.r * 2.6 + 260;
    const p = pairOf(t);
    if (p) { fx = (t.x + p.x) / 2; fy = (t.y + p.y) / 2; span = Math.max(span, Math.hypot(p.x - t.x, p.y - t.y) + (p.r + t.r) * 1.3 + 120); }
    dir.partner = p ? p.id : 0;
    const k = Math.min(1, dt * 2.6); dir.x += (fx - dir.x) * k; dir.y += (fy - dir.y) * k;
    const zz = C.clamp(Math.min(C.W * 1.05, C.H * 0.6) / span, 0.3, 1.3);
    dir.z += (zz - dir.z) * Math.min(1, dt * 1.2);
    // сверху кадра — таблица, снизу — подписи YouTube: героя держим чуть ниже середины
    cam.x = dir.x; cam.y = dir.y - (C.H * 0.03) / dir.z; cam.z = dir.z;
  }
  // подписи для ролика: window.__cap = { top: 'WHICH COUNTRY WINS?', bottom: '…' }
  function drawSpecHud(ctx) {
    const cap = window.__cap || {};
    // кольцо вокруг главного героя кадра
    const t = balls.get(dir.id);
    if (t && t.alive) { const [sx, sy] = toScr(t.x, t.y); ctx.strokeStyle = 'rgba(255,235,59,0.85)'; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(sx, sy, t.r * cam.z + 10, 0, 7); ctx.stroke(); }
    const capSize = (txt, want) => { ctx.save(); ctx.font = C.font(want); const w = ctx.measureText(txt).width; ctx.restore(); return w > C.W - 40 ? want * (C.W - 40) / w : want; };
    // подпись — узкой строкой по самому верху
    if (cap.top) { ctx.save(); ctx.globalAlpha = cap.topA === undefined ? 1 : cap.topA; C.text(cap.top, C.W / 2, 54, capSize(cap.top, cap.topSize || 44), '#ffeb3b', 'center', 'rgba(20,20,70,0.95)'); ctx.restore(); }
    if (banner) { drawSpecFinal(ctx, cap, capSize); return; }
    // таймер раунда — слева сверху
    const ty = 96;
    ctx.fillStyle = rt <= 10 ? 'rgba(229,57,53,0.9)' : 'rgba(20,20,70,0.6)'; C.rr(ctx, 18, ty, 156, 52, 26); ctx.fill();
    C.icon('clock', 48, ty + 26, 30, '#fff'); C.text(fmtT(rt), 108, ty + 28, 32, '#fff', 'center', null);
    // зачёт стран — компактно справа сверху, как таблица в игре
    const rows = cs.slice(0, 5), pw = 252, px = C.W - pw - 14, py = ty, rh = 38;
    ctx.fillStyle = 'rgba(20,20,70,0.55)'; C.rr(ctx, px, py, pw, 12 + Math.max(1, rows.length) * rh, 18); ctx.fill();
    rows.forEach((c, i) => {
      const y = py + 6 + rh / 2 + i * rh;
      C.text(String(i + 1), px + 20, y, 22, i === 0 ? '#ffc107' : '#fff', 'center', null);
      C.drawBall(px + 52, y, 14, c[0], 0, ctx);
      C.text(fit(cname(c[0]), 112, 22), px + 74, y, 22, i === 0 ? '#ffeb3b' : '#fff', 'left', null);
      C.text(String(c[1]), px + pw - 14, y, 22, '#fff', 'right', null);
    });
    if (!rows.length) C.text('…', px + pw / 2, py + 6 + rh / 2, 22, '#cfd8dc');
    // кто кого съел — маленькой строкой слева под таймером
    feed.slice(0, 2).forEach((f, i) => {
      const y = ty + 86 + i * 42; ctx.globalAlpha = Math.max(0, Math.min(1, (3.5 - f.t) * 2));
      ctx.fillStyle = 'rgba(0,0,0,0.32)'; C.rr(ctx, 18, y - 17, 156, 34, 17); ctx.fill();
      C.drawBall(46, y, 13, f.a, 0, ctx); C.icon('next', 96, y, 20, '#ffeb3b'); C.drawBall(146, y, 11, f.b, 0, ctx);
      ctx.globalAlpha = 1;
    });
  }
  // итог раунда: победитель крупно и места 2–3
  function drawSpecFinal(ctx, cap, capSize) {
    const b = banner, a = Math.max(0, Math.min(1, b.t * 4)), w = Math.min(660, C.W - 30), y = 170;
    ctx.globalAlpha = a;
    ctx.fillStyle = 'rgba(255,160,0,0.96)'; C.rr(ctx, C.W / 2 - w / 2, y, w, 250, 34); ctx.fill();
    C.text(T.roundWon.toUpperCase(), C.W / 2, y + 48, 40, '#fff', 'center', 'rgba(0,0,0,0.35)');
    C.drawBall(C.W / 2 - 170, y + 150, 66, b.win, 0, ctx); C.text(fit(cname(b.win), 340, 68), C.W / 2 - 84, y + 152, 68, '#fff', 'left', 'rgba(0,0,0,0.45)');
    const rest = (b.top || []).slice(1, 3);
    rest.forEach((c, i) => {
      const yy = y + 290 + i * 70;
      ctx.fillStyle = 'rgba(20,20,70,0.8)'; C.rr(ctx, C.W / 2 - w / 2 + 40, yy - 30, w - 80, 60, 30); ctx.fill();
      C.text(String(i + 2), C.W / 2 - w / 2 + 80, yy, 36, '#fff', 'center', null);
      C.drawBall(C.W / 2 - w / 2 + 140, yy, 24, c[0], 0, ctx);
      C.text(fit(cname(c[0]), 300, 36), C.W / 2 - w / 2 + 180, yy, 36, '#fff', 'left', null);
      C.text(String(c[1]), C.W / 2 + w / 2 - 70, yy, 36, '#fff', 'right', null);
    });
    ctx.globalAlpha = 1;
    if (!b.conf) { b.conf = 1; C.confetti(C.W / 2, y + 100, 140); }
    if (cap.bottom) { ctx.save(); ctx.globalAlpha = cap.bottomA === undefined ? 1 : cap.bottomA; C.text(cap.bottom, C.W / 2, C.H * 0.7, capSize(cap.bottom, cap.bottomSize || 46), '#fff', 'center', 'rgba(20,20,70,0.95)'); ctx.restore(); }
  }

  function drawBanner(ctx, L) {
    const b = banner, a = Math.min(1, b.t * 4, (4.5 - b.t) * 2), y = L ? C.H * 0.3 : hudBottom + 80, w = Math.min(560, C.W - 40);
    ctx.globalAlpha = Math.max(0, a);
    ctx.fillStyle = b.mine ? 'rgba(255,160,0,0.92)' : 'rgba(20,20,60,0.82)'; C.rr(ctx, C.W / 2 - w / 2, y - 70, w, b.mine ? 160 : 130, 26); ctx.fill();
    C.text(b.win === 'BOT' ? T.botsWon : T.roundWon, C.W / 2, y - 38, 28, '#fff');
    C.drawBall(C.W / 2 - 120, y + 12, 32, b.win, 0, ctx); C.text(fit(cname(b.win), w / 2 + 40, 38), C.W / 2 - 74, y + 14, 38, '#fff', 'left');
    if (b.mine) { C.text(T.yourTeam + '  +25', C.W / 2 - 16, y + 62, 28, '#fff'); C.icon('coin', C.W / 2 + 150, y + 60, 34); }
    ctx.globalAlpha = 1;
  }

  // ---------- окно смерти ----------
  function drawDeath(ctx, L) {
    const d = dead;
    ctx.fillStyle = 'rgba(10,10,40,' + Math.min(0.74, d.t * 2) + ')'; ctx.fillRect(0, 0, C.W, C.H);
    if (d.t < 0.25) return;
    UI.block();
    C.drawCoinsHud();
    const BW = Math.min(480, C.W - 60), BH = L ? 80 : 100, GAP = L ? 12 : 16, bx = C.W / 2 - BW / 2;
    let y = (L ? 46 : C.H * 0.12) + (C.safeU ? C.safeU().t : 0);
    C.text(T.ateBy, C.W / 2, y, L ? 30 : 38, '#fff');
    const kr = L ? 34 : 46; C.drawBall(C.W / 2, y + kr + 22, kr, d.skin, 0, ctx); drawAcc(ctx, d.acc, C.W / 2, y + kr + 22, kr);
    y += kr * 2 + 50;
    C.text(d.by, C.W / 2, y, L ? 28 : 34, d.human ? '#ffeb3b' : '#fff');
    y += L ? 44 : 56;
    // итог жизни: рекорд · съел · монеты
    const sw = Math.min(560, C.W - 40); ctx.fillStyle = 'rgba(255,255,255,0.12)'; C.rr(ctx, C.W / 2 - sw / 2, y - 28, sw, 56, 28); ctx.fill();
    C.icon('star', C.W / 2 - sw / 2 + 40, y, 32, '#ffd54f'); C.text(String(d.best), C.W / 2 - sw / 2 + 64, y + 2, 28, '#fff', 'left', null);
    C.text(T.eats + ' ' + d.eats, C.W / 2, y + 2, 26, '#fff', 'center', null);
    C.icon('coin', C.W / 2 + sw / 2 - 110, y, 34); C.text('+' + d.coins * (d.doubled ? 2 : 1), C.W / 2 + sw / 2 - 86, y + 2, 28, '#ffeb3b', 'left', null);
    y += L ? 44 : 58;
    // страны за сегодня
    const myD = dayTopL.findIndex((c) => c[0] === skin);
    if (dayTopL.length) {
    let tx = C.W / 2 - 230; C.text(T.today + ':', tx, y, 22, '#cfd8dc', 'left', null); tx += LANG === 'ru' ? 110 : 82;
    dayTopL.slice(0, 3).forEach((c, i) => { C.drawBall(tx + 14, y, 13, c[0], 0, ctx); C.text(String(i + 1), tx + 34, y + 1, 20, i === 0 ? '#ffd54f' : '#fff', 'left', null); tx += 64; });
    if (myD >= 0) C.text(T.yourCountry + ' #' + (myD + 1), C.W / 2 + 230, y, 22, '#ffeb3b', 'right', null);
    y += L ? 34 : 46;
    }
    // кнопки: предложение за рекламу (если есть) и «Заново» — того же размера и цвета (правило CrazyGames: отказ не прячем)
    const off = d.offer, GREEN = '#43a047';
    let adShown = false;
    if (off === 'revive' && !d.revived) {
      const left = Math.max(0, 5 - (d.t - 0.25));
      if (left > 0) {
        if (adsOk()) {
          adShown = true;
          if (C.button('revAd', bx, y, BW, BH, { color: GREEN, draw: () => { C.icon('ad', -BW / 2 + 54, 0, BH * 0.52); C.text(T.revive, -BW / 2 + 96, -BH * 0.14, BH * 0.32, '#fff', 'left'); C.text(T.half, -BW / 2 + 96, BH * 0.2, BH * 0.22, '#e8f5e9', 'left', null); ringT(BW / 2 - 50, 0, BH * 0.32, left / 5); } }) && !busy) {
            rewarded('revive').then((ok) => { if (ok) { d.revived = true; lastReviveAt = nowS(); C.sfx('buy'); doRespawn(true); } });
          }
          y += BH + GAP;
        }
        const price = 150, can = C.save.coins >= price, ring = !adShown;
        if (can || adShown) {
          if (C.button('revCoin', bx, y, BW, BH, { color: can ? '#fb8c00' : '#8d6e63', draw: () => { C.icon('coin', -BW / 2 + 54, 0, BH * 0.5); C.text(String(price), -BW / 2 + 86, 0, BH * 0.34, '#fff', 'left'); C.text(T.revive, ring ? BW / 2 - 110 : BW / 2 - 30, 0, BH * 0.3, '#fff', 'right'); if (ring) ringT(BW / 2 - 50, 0, BH * 0.32, left / 5); } }) && !busy) {
            if (C.spend(price)) { d.revived = true; lastReviveAt = nowS(); C.sfx('buy'); doRespawn(true); } else { C.sfx('hit'); C.toast('coin', String(price - C.save.coins)); }
          }
          y += BH + GAP;
        }
      }
    } else if (off === 'double' && !d.doubled && adsOk()) {
      adShown = true;
      if (C.button('dblAd', bx, y, BW, BH, { color: GREEN, draw: () => { C.icon('ad', -BW / 2 + 54, 0, BH * 0.52); C.text(T.x2, 6, 0, BH * 0.34, '#fff'); C.icon('coin', BW / 2 - 92, 0, BH * 0.44); C.text('+' + d.coins, BW / 2 - 66, 0, BH * 0.3, '#fff', 'left'); } }) && !busy) {
        rewarded('double').then((ok) => { if (ok) { d.doubled = true; lastDoubleAt = nowS(); C.addCoins(d.coins, C.W / 2, C.H / 2); C.sfx('win'); } });
      }
      y += BH + GAP;
    }
    if (C.button('again', bx, y, BW, BH, { color: adShown ? GREEN : '#1e88e5', label: T.again, pulse: !adShown && (!off || d.revived || d.doubled) })) playAgain();
    y += BH + GAP + 6;
    // магазин · страна · подарок
    const s = L ? 84 : 100, gx = C.W / 2 - (s * 4 + 60) / 2;
    if (C.button('invBtn', gx + 3 * (s + 20), y, s, s, { color: '#1e88e5', draw: () => { C.icon('plus', 0, -s * 0.12, s * 0.42, '#fff'); C.text(T.invite, 0, s * 0.27, s * 0.19, '#fff', 'center', null); } })) { C.sfx('tap'); shareInvite(); }
    if (C.button('shopBtn', gx, y, s, s, { color: '#7c4dff', draw: () => { C.drawBall(0, 4, s * 0.3, skin, 0, ctx); drawAcc(ctx, 11, 0, 4, s * 0.3); } })) { shop = { t: 0 }; C.sfx('tap'); }
    if (C.button('flagBtn', gx + s + 20, y, s, s, { color: '#00897b', draw: () => C.drawBall(0, 0, s * 0.32, skin, 0, ctx) })) showJoin(false);
    const gl = giftLeft(), gReady = gl <= 0, gAd = !gReady && adsOk() && !X().giftAd;
    if (C.button('giftBtn', gx + 2 * (s + 20), y, s, s, { color: gReady ? '#ff7a90' : gAd ? '#43a047' : '#78909c', pulse: gReady, badge: gReady, draw: () => { if (gAd) C.icon('ad', -s * 0.2, -s * 0.18, s * 0.34); C.icon('gift', gAd ? s * 0.12 : 0, gReady ? 0 : -s * 0.12, s * (gReady ? 0.6 : 0.42)); if (!gReady) C.text(fmtT(gl), 0, s * 0.26, s * 0.2, '#fff'); } }) && !busy) {
      if (gReady) claimGift(C.W / 2, y);
      else if (gAd) rewarded('gift').then((ok) => { if (ok) { claimGift(C.W / 2, y); X().giftAd = 1; X().giftAt = Date.now() / 1000; C.persist(); } });
    }
    toasts.slice(-1).forEach((t) => { const ty = Math.min(C.H - 40, y + s + 70); ctx.globalAlpha = Math.max(0, Math.min(1, (3 - t.t) * 2)); ctx.fillStyle = 'rgba(0,0,0,0.6)'; C.rr(ctx, C.W / 2 - 320, ty - 24, 640, 48, 24); ctx.fill(); C.text(fit(t.text, 600, 24), C.W / 2, ty, 24, t.col); ctx.globalAlpha = 1; });
    function ringT(x, yy, r, k) { ctx.strokeStyle = 'rgba(255,255,255,0.35)'; ctx.lineWidth = 7; ctx.beginPath(); ctx.arc(x, yy, r, 0, 7); ctx.stroke(); ctx.strokeStyle = '#fff'; ctx.beginPath(); ctx.arc(x, yy, r, -Math.PI / 2, -Math.PI / 2 + k * Math.PI * 2); ctx.stroke(); C.text(String(Math.ceil(k * 5)), x, yy + 1, r * 1.1, '#fff', 'center', null); }
  }

  // ---------- магазин украшений ----------
  function drawShop(ctx, L) {
    shop.t += C.dt || 0.016;
    ctx.fillStyle = 'rgba(8,8,30,0.82)'; ctx.fillRect(0, 0, C.W, C.H); UI.block();
    C.drawCoinsHud();
    const cols = L ? 6 : 4, rows = Math.ceil(ACC.length / cols), cell = Math.min(L ? 150 : 160, (Math.min(C.W, 900) - 60) / cols);
    const gw = cols * cell, gx = C.W / 2 - gw / 2, gy = L ? 100 : C.H * 0.16;
    C.text(T.shop, C.W / 2, gy - 44, L ? 36 : 44, '#fff');
    const f = X();
    ACC.forEach((a, i) => {
      const cx = gx + (i % cols) * cell, cy = gy + Math.floor(i / cols) * cell, own = f.owned.indexOf(a.id) >= 0, on = f.on === a.id;
      if (C.button('acc' + i, cx + 6, cy + 6, cell - 12, cell - 12, { color: on ? '#43a047' : own ? '#5c6bc0' : '#37474f', draw: () => {
        C.drawBall(0, -cell * 0.08, cell * 0.22, skin, 0, ctx); drawAcc(ctx, a.id, 0, -cell * 0.08, cell * 0.22);
        if (on) C.text(T.on, 0, cell * 0.3, cell * 0.14, '#fff');
        else if (own || !a.price) C.text(a.price ? T.owned : T.free, 0, cell * 0.3, cell * 0.14, '#e8eaf6');
        else { C.icon('coin', -cell * 0.14, cell * 0.3, cell * 0.16); C.text(String(a.price), cell * 0.02, cell * 0.31, cell * 0.15, C.save.coins >= a.price ? '#fff' : '#ff8a80', 'left', null); }
      } })) {
        if (own || !a.price) { f.on = a.id; if (f.owned.indexOf(a.id) < 0) f.owned.push(a.id); C.persist(); C.sfx('tap'); }
        else if (C.spend(a.price)) { f.owned.push(a.id); f.on = a.id; C.persist(); C.sfx('buy'); C.confetti(cx + cell / 2, cy + cell / 2, 40); }
        else { C.sfx('hit'); C.toast('coin', String(a.price - C.save.coins)); }
      }
    });
    let y = gy + rows * cell + (L ? 14 : 30);
    const BW = Math.min(480, C.W - 60), BH = L ? 76 : 96, bx = C.W / 2 - BW / 2;
    const st = adCoinsState(), n = AD_COINS[st.n], cool = Math.max(0, 90 - (Date.now() / 1000 - st.t));
    if (adsOk() && n) {
      if (cool > 0) { C.text(fmtT(cool), C.W / 2, y + BH / 2, BH * 0.3, '#cfd8dc'); }
      else if (C.button('adCoins', bx, y, BW, BH, { color: '#43a047', draw: () => { C.icon('ad', -BW / 2 + 54, 0, BH * 0.5); C.icon('coin', 0, 0, BH * 0.46); C.text('+' + n, 30, 0, BH * 0.34, '#fff', 'left'); } }) && !busy) {
        rewarded('coins').then((ok) => { if (ok) { const s2 = adCoinsState(); s2.n++; s2.t = Date.now() / 1000; C.addCoins(n, C.W / 2, y); C.sfx('win'); C.persist(); } });
      }
      y += BH + 14;
    } else if (adsOk()) { C.text(T.tomorrow, C.W / 2, y + BH / 2, BH * 0.26, '#cfd8dc'); y += BH + 14; }
    if (C.button('shopClose', bx, y, BW, BH, { color: '#1e88e5', label: T.close })) { shop = null; C.sfx('tap'); }
  }

  const UI = C.UI;
  window.__objs = () => ({ saws, powers, dots });
  window.__send = (o) => send(o);
  window.__respawn = () => playAgain();
  window.__dir = () => { let h = 0; for (const b of balls.values()) if (b.human && b.alive) h++; dir.humansMax = Math.max(dir.humansMax || 0, h); return { id: dir.id, log: dir.log, rt, cs, humans: h, humansMax: dir.humansMax, banner: banner && { win: banner.win, top: banner.top } }; };
  window.__dbgOnline = () => ({ status, myId, me, R, balls: balls.size, dots: dots.size, powers: powers.length, saws: saws.length, pingMs, dead, attempt, cs, rt, dayTopL, banner: !!banner, coins: C.save.coins, fb: X(), shop: !!shop });
  window.FBArt = { drawAcc };
  if (q.has('art')) return; // страница обложек: только рисунки, без игры
  C.run(game);
})();
