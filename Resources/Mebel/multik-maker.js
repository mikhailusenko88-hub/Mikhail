/* Создание и правка персонажа по описанию на русском (текст или голос → параметры движка).
   Работает без интернета: понимает виды, цвета, части тела, одежду, аксессуары, узоры, голос, размер, имя. */
'use strict';
(function (global) {
const Maker = {};

const COLORS = [
  [/^рыж/, '#f2a65a', 'рыжий'], [/^бел(ый|ая|ое|ые|ого|ой|ую|ым|ыми|ых|оснеж|еньк)/, '#f6f3ef', 'белый'], [/^ч[её]рн/, '#3b3b46', 'чёрный'],
  [/^сер(ый|ая|ое|ые|ого|ой|ую|ым|ыми|ых|еньк)/, '#a9a9b8', 'серый'], [/^серебрист/, '#c8ccd6', 'серебристый'], [/^коричнев/, '#8f5d3b', 'коричневый'],
  [/^бур(ый|ая|ого|ой|ую|ым|ые)$/, '#7a4e30', 'бурый'], [/^шоколад/, '#6b3f26', 'шоколадный'], [/^син(ий|яя|ее|ие|его|ей|юю|им|ими|их|еньк)$/, '#3d8fe0', 'синий'],
  [/^голуб/, '#7fc8ff', 'голубой'], [/^зел[её]н/, '#5fbf4a', 'зелёный'], [/^красн/, '#e8344e', 'красный'], [/^розов/, '#ff8fb1', 'розовый'],
  [/^ж[её]лт/, '#ffd23f', 'жёлтый'], [/^(фиолетов|сиренев|лилов)/, '#8d5cf6', 'фиолетовый'], [/^оранжев/, '#ff8a3d', 'оранжевый'],
  [/^золот/, '#e8b830', 'золотой'], [/^(бежев|песочн)/, '#e8cfa0', 'бежевый'], [/^кремов/, '#fff3e0', 'кремовый'], [/^бирюзов/, '#3cc8c0', 'бирюзовый'],
  [/^мятн/, '#9be7c4', 'мятный'], [/^бордов/, '#8a1f3a', 'бордовый'], [/^пятнист/, null, ''],
];
const KINDS = [
  [/^(кот|кош|кис|котен|котик|котёнок|котя|котей)/, 'cat', 'кот'], [/^(пес|пёс|пса|псу|собак|собач|щен|песик|пёсик)/, 'dog', 'пёс'],
  [/^(медвед|мишк|медвеж|мишут)/, 'bear', 'медведь'], [/^(заяц|зайч|зайк|зайц|кролик|крольч)/, 'rabbit', 'заяц'], [/^(мыш|мышон|мышк)/, 'mouse', 'мышь'],
  [/^(лис|лисен|лисичк|лисёнок)/, 'fox', 'лиса'], [/^(свин|порос|хрюш|свинк)/, 'pig', 'поросёнок'],
];
const PEOPLE = [ // stem, пол, возраст
  [/^(мальчик|мальчиш|пацан|сын)/, 'm', 'kid'], [/^(девоч|девчон|доч)/, 'f', 'kid'], [/^(ребен|ребён|малыш)/, 'm', 'kid'],
  [/^(папа|пап[уы]|отец|мужчин|дяд|парен|парн|учитель$|дедушк|дед$|деда|старик)/, 'm', 'adult'], [/^(мама|мам[уы]|мать|женщин|тет|тёт|девушк|учительниц|бабушк|бабул|старушк)/, 'f', 'adult'],
];
const OLD = /^(бабушк|бабул|старушк|дедушк|дед$|деда|старик|стар(ый|ая|ого|ой|енький|енькая))/;
const PARTS = [ // stem → часть
  [/^глаз/, 'eyes'], [/^(нос|носик)$/, 'nose'], [/^(носа|носом|носиком)$/, 'nose'], [/^уш/, 'inner'], [/^(пуз|живот|брюш|грудк|животик)/, 'belly'],
  [/^(шерст|мех|шубк|окрас|тело|туловищ)/, 'body'], [/^(кож|лицо)/, 'skin'], [/^(волос|причес|прич[её]ск|чёлк|челк|косичк|хвостик|кудр|кудряшк|пучок)/, 'hair'],
  [/^(рубаш|футболк|кофт|свитер|майк|куртк|толстовк|пиджак|жилет|кофточк)/, 'shirt'], [/^плать/, 'dress'], [/^(штан|брюк|джинс|шорт)/, 'pants'],
  [/^юбк/, 'skirt'], [/^(ботин|туфл|кроссов|сапог|обув|кед|тапк|тапоч)/, 'shoes'],
  [/^(полоск|полосы|полосам|полосами|полосок|полоса|полосу|полосой)$/, 'stripe'], [/^(пятн|пятнышк)/, 'spot'],
  [/^шарф/, 'acc:scarf'], [/^(бант|бантик)/, 'acc:bow'], [/^(шляп|кепк|шапк|панам|шапочк|кепоч)/, 'acc:hat'], [/^корон/, 'acc:crown'],
  [/^(очк|очечк|очёчк)/, 'acc:glasses'], [/^(цвет(ок|оч|ка|ком)|цветочек)/, 'acc:flower'], [/^(ошейн|колокольч)/, 'acc:collar'],
  [/^(лапк|носочк|носки|носок)/, 'socks'], [/^(хвост|хвостик)/, 'tail'], [/^маск/, 'mask'],
];
const REMOVE = /^(убер|убра|сним|снять|сними|удал|без$|не$|нет$|убрать)/;
const STOP = new Set(('и в с со на у по к ко а о об от до из за для под над при про это его её ее ему ей их он она оно они сделай сделать сделайте пусть будет был была '
  + 'добавь добавить добавьте дай дать надень надеть одень одеть поставь поменяй поменять смени сменить измени изменить замени покрась покрасить перекрась цвета цвет цветом '
  + 'такой такая такие который которая очень чуть немного побольше поменьше еще ещё тоже также как чтобы был зовут имя по имени назови назовите голос голосом голоса '
  + 'персонаж персонажа нужен нужна нужно хочу давай вот ну мне нам ты вы он сам сама весь вся все ним ней него нее неё той тот та те этот эта эти').split(' '));

function norm(s) { return String(s || '').toLowerCase().replace(/ё/g, 'е'); }
function toks(s) { return norm(s).replace(/[^a-zа-я0-9\-]+/g, ' ').split(/[\s]+/).flatMap(t => t.includes('-') ? t.split('-') : [t]).filter(Boolean); }
function hex2(h) { h = h.replace('#', ''); return [0, 2, 4].map(i => parseInt(h.substr(i, 2), 16)); }
function toHex(c) { return '#' + c.map(v => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0')).join(''); }
function mix(h, a) { const c = hex2(h); return toHex(c.map(v => a < 0 ? v * (1 + a) : v + (255 - v) * a)); }
function colorOf(t) { for (const [re, hex, name] of COLORS) if (re.test(t) && hex) return { hex, name }; return null; }
function kindOf(t) { for (const [re, k, name] of KINDS) if (re.test(t)) return { k, name }; return null; }
function personOf(t) { for (const [re, g, age] of PEOPLE) if (re.test(t)) return { g, age, old: OLD.test(t) }; return null; }
function partOf(t) { for (const [re, p] of PARTS) if (re.test(t)) return p; return null; }
const PART_NAMES = { eyes: 'глаза', nose: 'нос', inner: 'уши внутри', belly: 'живот', body: 'шерсть', skin: 'кожа', hair: 'волосы', shirt: 'кофта', dress: 'платье', pants: 'штаны', skirt: 'юбка', shoes: 'обувь', stripe: 'полоски', spot: 'пятна', tail: 'хвост', socks: 'белые лапки', mask: 'маска' };
const ACC_NAMES = { scarf: 'шарф', bow: 'бантик', hat: 'шапка', crown: 'корона', glasses: 'очки', flower: 'цветок', collar: 'ошейник с колокольчиком' };
const ACC_DEF = { scarf: '#3d8fe0', bow: '#e8344e', hat: '#e8344e', crown: '#ffd23f', glasses: '#2b1d16', flower: '#ff7ab8', collar: '#e8344e' };

const VOICE_PRESETS = {
  boy: { base: 'female', pitch: 1.38, rate: .52, n: 'мальчик' }, girl: { base: 'female', pitch: 1.62, rate: .54, n: 'девочка' },
  man: { base: 'male', pitch: 1.0, rate: .5, n: 'мужской' }, woman: { base: 'female', pitch: 1.05, rate: .5, n: 'женский' },
  grandpa: { base: 'male', pitch: .8, rate: .43, n: 'дедушка' }, grandma: { base: 'female', pitch: .86, rate: .44, n: 'бабушка' },
  baby: { base: 'female', pitch: 1.8, rate: .55, n: 'малыш' },
};

/** Новый пустой черновик. */
Maker.blank = function () { return { kind: 'cat', age: 'kid', height: 1, colors: {}, pattern: [], acc: [], voice: Object.assign({}, VOICE_PRESETS.boy), name: '' }; };

/** Применить фразу к черновику. Возвращает {spec, done:[что сделал], unknown:[непонятные слова]} */
Maker.apply = function (draft, text) {
  const s = JSON.parse(JSON.stringify(draft || Maker.blank())); s.colors = s.colors || {}; s.pattern = s.pattern || []; s.acc = s.acc || []; s.voice = s.voice || {};
  if (s.voice) delete s.voice.n;
  const done = [], unknown = [], used = new Set();
  const raw = String(text || '');
  // имя
  const nm = raw.match(/(?:зовут|по имени|имя|назови(?:те)?(?:\s+(?:его|её|ее|персонажа))?|кличка)\s+([A-Za-zА-ЯЁа-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+)?)/);
  if (nm) { s.name = nm[1].charAt(0).toUpperCase() + nm[1].slice(1); done.push('имя: ' + s.name); }
  const nameToks = new Set(nm ? toks(nm[1]) : []);
  const clauses = norm(raw).split(/[.,;!?\n]+|\s+(?:и|а|но|плюс)\s+/).map(toks).filter(c => c.length);
  let personSeen = null, lastVoice = false;
  for (const T of clauses) {
    const removing = T.some(t => REMOVE.test(t));
    const isVoice = T.some(t => /^голос/.test(t)) || (lastVoice && T.every(t => STOP.has(t) || /^(по)?(ниже|выше|быстрее|медленнее|громче|тише|медленн|быстр|низк|высок|тонк|груб)/.test(t)));
    lastVoice = isVoice;
    const consumed = new Set();
    // вид
    for (let i = 0; i < T.length; i++) {
      if (isVoice) break;
      const k = kindOf(T[i]); if (k) { if (s.kind !== k.k) { s.kind = k.k; done.push('вид: ' + k.name); } consumed.add(i); if (/(котен|щен|зайч|мышон|лисен|медвеж|порос|котик|крольч)/.test(T[i])) s.age = 'kid'; continue; }
      const p = personOf(T[i]); if (p) { personSeen = p; if (s.kind !== 'human') { s.kind = 'human'; done.push('вид: человек'); } const age = p.old ? 'old' : p.age; if (s.age !== age) { s.age = age; } s.gender = p.g;
        if (!s.hair) s.hair = { style: p.g === 'f' ? (age === 'kid' ? 'pigtails' : age === 'old' ? 'bun' : 'long') : (age === 'old' ? 'bald' : 'short') };
        if (!s.outfit) s.outfit = p.g === 'f' ? { shirt: age === 'old' ? '#b05a8a' : '#ff6fa8', skirt: age === 'kid' ? '#7a5cd6' : '#5a3a6a' } : { shirt: '#3d8fe0', pants: '#33415c' };
        if (!draft || !draft._voiceSet) s.voice = Object.assign({}, VOICE_PRESETS[age === 'old' ? (p.g === 'f' ? 'grandma' : 'grandpa') : age === 'kid' ? (p.g === 'f' ? 'girl' : 'boy') : (p.g === 'f' ? 'woman' : 'man')]);
        if (age === 'old' && !s.acc.some(a => a.type === 'glasses')) s.acc.push({ type: 'glasses' });
        done.push(p.old ? (p.g === 'f' ? 'бабушка' : 'дедушка') : age === 'kid' ? (p.g === 'f' ? 'девочка' : 'мальчик') : (p.g === 'f' ? 'женщина' : 'мужчина')); consumed.add(i); }
    }
    // голос
    if (isVoice || T.some(t => /^(басом|пискляв|шепот|быстрее|медленнее|громче)/.test(t))) {
      T.forEach((t, i) => consumed.add(i));
      const has = re => T.some(t => re.test(t));
      let preset = null;
      if (has(/^(мальчик|мальчиш|пацан|сын)/)) preset = 'boy'; if (has(/^(девоч|девчон|доч)/)) preset = 'girl'; if (has(/^(малыш|младен|детск)/)) preset = preset || 'baby';
      if (has(/^(мужск|мужчин|папин|папы|папа)/)) preset = 'man'; if (has(/^(женск|женщин|мамин|мамы|мама)/)) preset = 'woman';
      if (has(/^(дедушк|старик|стариковск|деда)/)) preset = 'grandpa'; if (has(/^(бабушк|старушеч|бабули)/)) preset = 'grandma';
      if (preset) { s.voice = Object.assign({}, VOICE_PRESETS[preset]); done.push('голос: ' + VOICE_PRESETS[preset].n); delete s.voice.n; }
      const k = (re, f, what) => { if (has(re)) { f(); done.push('голос ' + what); } };
      k(/^(низк|бас|груб|ниже|пониже)/, () => s.voice.pitch = Math.max(.5, (s.voice.pitch || 1) - (has(/^(ниже|пониже)/) ? .12 : .3)), 'ниже');
      k(/^(высок|тонк|пискляв|выше|повыше|звонк)/, () => s.voice.pitch = Math.min(2, (s.voice.pitch || 1) + (has(/^(выше|повыше)/) ? .12 : .3)), 'выше');
      k(/^(быстр|быстрее|побыстр|тараторит)/, () => s.voice.rate = Math.min(.62, (s.voice.rate || .5) + .05), 'быстрее');
      k(/^(медлен|медленнее|помедлен|спокойн|протяжн)/, () => s.voice.rate = Math.max(.38, (s.voice.rate || .5) - .05), 'медленнее');
      s.voice.pitch = Math.round(s.voice.pitch * 100) / 100; s.voice.rate = Math.round(s.voice.rate * 100) / 100;
      s._voiceSet = true;
      continue;
    }
    // части/аксессуары + цвета рядом
    const colorAt = []; T.forEach((t, i) => { const c = colorOf(t); if (c) { let hex = c.hex; const prev = T[i - 1]; if (prev === 'светло' || prev === 'светлый') hex = mix(hex, .35); if (prev === 'темно' || prev === 'темный') hex = mix(hex, -.35); colorAt.push({ i, hex, name: c.name }); } });
    const free = new Set(colorAt.map(c => c.i));
    const parts = []; T.forEach((t, i) => { const p = partOf(t); if (p) parts.push({ i, p }); });
    for (const { i, p } of parts) {
      consumed.add(i);
      // ближайший свободный цвет в окне ±3 (сначала перед словом)
      let best = null; for (const c of colorAt) { if (!free.has(c.i)) continue; const d = c.i < i ? i - c.i : (c.i - i) + .5; if (d <= 3.5 && (!best || d < best.d)) best = Object.assign({ d }, c); }
      const col = best && best.hex; if (best) { free.delete(best.i); consumed.add(best.i); }
      const cname = best ? best.name + ' ' : '';
      if (p.startsWith('acc:')) { const type = p.slice(4); const ix = s.acc.findIndex(a => (a.type || a) === type);
        if (removing) { if (ix >= 0) { s.acc.splice(ix, 1); done.push('убрал: ' + ACC_NAMES[type]); } }
        else if (ix >= 0) { if (col) { s.acc[ix] = { type, color: col }; done.push(ACC_NAMES[type] + ': ' + best.name); } }
        else { s.acc.push(col || type === 'glasses' ? { type, color: col || ACC_DEF[type] } : { type, color: ACC_DEF[type] }); done.push('добавил: ' + ACC_NAMES[type] + (best ? ' (' + best.name + ')' : '')); }
        continue; }
      if (p === 'stripe' || p === 'spot') { const pat = p === 'stripe' ? 'stripes' : 'spots';
        if (removing) { s.pattern = s.pattern.filter(x => x !== pat); done.push('убрал ' + PART_NAMES[p]); }
        else { if (!s.pattern.includes(pat)) s.pattern.push(pat); if (col) s.colors.stripe = col; done.push(PART_NAMES[p] + (best ? ' (' + best.name + ')' : '')); } continue; }
      if (p === 'socks' || p === 'mask') { if (removing) s.pattern = s.pattern.filter(x => x !== p); else if (!s.pattern.includes(p)) s.pattern.push(p); done.push((removing ? 'убрал ' : '') + PART_NAMES[p]); continue; }
      if (p === 'tail') { if (col && /^(бел|кремов)/.test(best.name)) { if (!s.pattern.includes('tailtip')) s.pattern.push('tailtip'); done.push('белый кончик хвоста'); } continue; }
      if (!col) { if (p === 'hair') hairStyle(T, s, done); continue; }
      if (s.kind === 'human' && ['shirt', 'dress', 'pants', 'skirt', 'shoes'].includes(p)) {
        s.outfit = s.outfit || {};
        if (p === 'dress') { s.outfit.shirt = col; s.outfit.skirt = col; } else s.outfit[p] = col;
        if (p === 'pants') delete s.outfit.skirt; if (p === 'skirt' && s.outfit.pants) {}
        done.push(PART_NAMES[p] + ': ' + best.name); continue; }
      if (p === 'hair') { s.colors.hair = col; s.hair = s.hair || { style: 'short' }; s.hair.color = col; hairStyle(T, s, done); done.push('волосы: ' + best.name); continue; }
      if (p === 'skin') { s.colors.skin = col; done.push('кожа: ' + best.name); continue; }
      if (p === 'body') { setBody(s, col); done.push('шерсть: ' + best.name); continue; }
      s.colors[p] = col; done.push(PART_NAMES[p] + ': ' + best.name);
    }
    // узоры словами-прилагательными
    T.forEach((t, i) => {
      if (/^полосат/.test(t)) { consumed.add(i); if (removing) s.pattern = s.pattern.filter(x => x !== 'stripes'); else if (!s.pattern.includes('stripes')) { s.pattern.push('stripes'); done.push('полосатый'); } }
      if (/^пятнист/.test(t)) { consumed.add(i); if (!s.pattern.includes('spots')) { s.pattern.push('spots'); done.push('пятнистый'); } }
    });
    // свободные цвета → шерсть (животное) или кофта (человек)
    const left = colorAt.filter(c => free.has(c.i));
    left.forEach((c, n) => { consumed.add(c.i);
      if (s.kind === 'human') { s.outfit = s.outfit || {}; s.outfit.shirt = c.hex; done.push('кофта: ' + c.name); }
      else if (n === 0) { setBody(s, c.hex); done.push('окрас: ' + c.name); }
      else { s.colors.belly = c.hex; done.push('живот: ' + c.name); } });
    // размер, возраст
    T.forEach((t, i) => {
      const nextPart = T[i + 1] && partOf(T[i + 1]);
      if (/^(маленьк|крошечн|мелк|малюсеньк)/.test(t) && !nextPart) { s.height = .82; done.push('маленький'); consumed.add(i); }
      if (/^(больш|огромн|высок|толст|крупн|здоров)/.test(t) && !nextPart && !isVoice) { s.height = 1.2; done.push('большой'); consumed.add(i); }
      if (/^(меньше|поменьше|ниже)$/.test(t) && !nextPart) { s.height = Math.max(.65, Math.round(((s.height || 1) - .1) * 100) / 100); done.push('меньше'); consumed.add(i); }
      if (/^(больше|побольше|выше)$/.test(t) && !nextPart) { s.height = Math.min(1.4, Math.round(((s.height || 1) + .1) * 100) / 100); done.push('больше'); consumed.add(i); }
      if (OLD.test(t)) consumed.add(i);
      if (/^(взросл)/.test(t)) { s.age = 'adult'; done.push('взрослый'); consumed.add(i); }
      if (/^(детеныш|детёныш|маленьк)/.test(t) && s.kind !== 'human') consumed.add(i);
      if (s.kind === 'human' && /^(кудряв|лыс|косичк|хвостик|пучок|длинноволос|коротко)/.test(t)) { hairStyle([t], s, done); consumed.add(i); }
    });
    T.forEach((t, i) => { if (!consumed.has(i) && !STOP.has(t) && !nameToks.has(t) && t.length > 2 && !colorOf(t) && !/^(светло|темно|кончик|цвет|ушк|глазк|бел)/.test(t) && !REMOVE.test(t)) unknown.push(t); });
  }
  if (!s.name) s.name = defaultName(s);
  return { spec: s, done: dedupe(done), unknown: dedupe(unknown).slice(0, 8) };
};
function dedupe(a) { return [...new Set(a)]; }
function setBody(s, col) { if (s.kind === 'human') { s.colors.skin = col; return; } s.colors.body = col; if (!s._stripeSet) s.colors.stripe = mix(col, -.3); if (!s._bellySet) s.colors.belly = mix(col, .78); if (s.kind === 'dog' || s.kind === 'bear') s.colors.inner = mix(col, -.22); }
function hairStyle(T, s, done) {
  s.hair = s.hair || { style: 'short' }; const has = re => T.some(t => re.test(t));
  const st = has(/^кудряв/) ? 'curly' : has(/^лыс/) ? 'bald' : has(/^(косичк|хвостик)/) ? 'pigtails' : has(/^пучок/) ? 'bun' : has(/^(длинн|длинноволос)/) ? 'long' : has(/^коротк/) ? 'short' : null;
  if (st && s.hair.style !== st) { s.hair.style = st; done.push('причёска: ' + { curly: 'кудрявые', bald: 'лысый', pigtails: 'хвостики', bun: 'пучок', long: 'длинные', short: 'короткие' }[st]); }
}
function defaultName(s) {
  if (s.kind === 'human') { const g = s.gender === 'f'; return s.age === 'old' ? (g ? 'Бабушка' : 'Дедушка') : s.age === 'kid' ? (g ? 'Девочка' : 'Мальчик') : (g ? 'Мама' : 'Папа'); }
  return { cat: 'Котик', dog: 'Пёсик', bear: 'Мишка', rabbit: 'Зайка', mouse: 'Мышонок', fox: 'Лисёнок', pig: 'Поросёнок' }[s.kind] || 'Персонаж';
}

/** Чистое описание для движка/кода (служебные поля убраны). */
Maker.finalize = function (s, id) {
  const out = { id, name: s.name || defaultName(s), kind: s.kind, age: s.age || 'kid', height: s.height || 1, colors: Object.assign({}, s.colors), pattern: (s.pattern || []).slice(), acc: (s.acc || []).map(a => typeof a === 'string' ? { type: a } : Object.assign({}, a)), voice: { base: s.voice.base || 'female', pitch: s.voice.pitch || 1, rate: s.voice.rate || .5 } };
  if (s.kind === 'human') { out.hair = Object.assign({}, s.hair || { style: 'short' }); out.outfit = Object.assign({}, s.outfit || {}); if (out.colors.skin == null) delete out.colors.skin; }
  if (s.about) out.about = s.about;
  return out;
};
Maker.nextId = function (lib) { let n = 100; // свои персонажи из приложения: К101, К102… (К1–К99 — из сценариев чата)
  for (const id of Object.keys(lib.characters || {})) { const m = id.match(/^К(\d+)$/); if (m) n = Math.max(n, +m[1]); } return 'К' + (n + 1); };
Maker.describe = function (s) {
  const kn = { cat: 'кот', dog: 'пёс', bear: 'медведь', rabbit: 'заяц', mouse: 'мышь', fox: 'лиса', pig: 'поросёнок', human: 'человек' }[s.kind];
  const a = (s.acc || []).map(x => ACC_NAMES[x.type || x]).filter(Boolean);
  return `${kn}${s.pattern && s.pattern.length ? ', ' + s.pattern.map(p => ({ stripes: 'полоски', spots: 'пятна', socks: 'белые лапки', mask: 'маска', tailtip: 'белый кончик хвоста', muzzle: 'белая мордочка', patch: 'пятно у глаза' }[p] || p)).join(', ') : ''}${a.length ? ', ' + a.join(', ') : ''}`;
};
Maker.ACC_NAMES = ACC_NAMES; Maker.VOICE_PRESETS = VOICE_PRESETS;
global.MKMaker = Maker;
})(typeof window !== 'undefined' ? window : globalThis);
