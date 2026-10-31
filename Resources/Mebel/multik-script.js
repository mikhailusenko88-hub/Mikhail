/* «Мой сценарий»: текст в виде пьесы → серии в формате движка (без интернета).
   СЦЕНА: лес, ночь · Имя: реплика · (Имя прыгает) · Имя входит справа. · ПЕРСОНАЖ: Имя — описание · СЕРИЯ: 2. Название */
'use strict';
(function (global) {
const S = {};
const low = s => String(s || '').toLowerCase().replace(/ё/g, 'е');
const has = (t, re) => re.test(t);

const PLACES = [[/(космос|планет|ракет|луна)/, 'space'], [/(пляж|мор[еяю]|берег|океан)/, 'beach'], [/(зим|снег|сугроб)/, 'winter'], [/(кухн)/, 'kitchen'],
  [/(площадк|качел|горк)/, 'playground'], [/(улиц|город|магазин|парк)/, 'street'], [/(комнат|спальн|дома(?![а-я])|в доме|гостин|квартир|детск)/, 'room'],
  [/(двор|у дома|возле дома|крыльц|сад)/, 'yard'], [/(луг|пол[ея]|поляна|полянк)/, 'meadow'], [/(лес|роща|чащ)/, 'forest']];
const TIMES = [[/(ночь|ночью|ночн|темно)/, 'night'], [/(вечер|закат)/, 'evening'], [/(утро|утром|день|дн[её]м)/, 'day']];
const MUSIC = [[/(груст|печал)/, 'sad'], [/(тревож|страшн|напряж|погон)/, 'tense'], [/(приключ|бодр)/, 'adventure'], [/(волшеб|сказоч|чудес)/, 'magic'], [/(ночн|колыбел|тих)/, 'night'], [/(спокойн|нежн|мягк)/, 'calm'], [/(весел|радост)/, 'happy'], [/(без музыки|нет|тишин)/, 'none']];
const SFX = [[/(бум|удар|бах|грох)/, 'thud'], [/(дзынь|динь)/, 'ding'], [/(волшеб|магия|чудо)/, 'magic'], [/(искр|блеск)/, 'sparkle'], [/(стук)/, 'knock'], [/(звонок|колокол)/, 'bell'],
  [/(мяу)/, 'meow'], [/(гав)/, 'bark'], [/(смех|хаха)/, 'laugh'], [/(всплеск|плюх)/, 'splash'], [/(хлоп)/, 'clap'], [/(вжух|свист|ух)/, 'whoosh'], [/(барабан)/, 'drum'], [/(прыг|боинг)/, 'boing'], [/(шаг)/, 'step'], [/(хлопок|чпок|поп)/, 'pop']];
const PROPS = [[/^мяч/, 'ball'], [/^яблок/, 'apple'], [/^рыб/, 'fish'], [/^(коробк|ящик)/, 'box'], [/^подар/, 'gift'], [/^цвет(ок|оч|к)/, 'flower'], [/^книг/, 'book'], [/^зв[её]зд/, 'star'],
  [/^торт/, 'cake'], [/^кост/, 'bone'], [/^морков/, 'carrot'], [/^сыр/, 'cheese'], [/^(шарик|шар$|шара|шаром)/, 'balloon'], [/^ключ/, 'key'], [/^(чашк|кружк)/, 'cup']];
const EMO = [[/(радост|весел|счастлив|улыба|довольн)/, 'happy'], [/(смеет|хохоч|смешн|смех|хихик)/, 'laugh'], [/(груст|печал|расстро)/, 'sad'], [/(плач|рыда|сл[её]з)/, 'cry'],
  [/(злит|сердит|зло(?![а-я])|злой|злая|гневн|обиж)/, 'angry'], [/(удивл|изумл|(^|[^а-я])ого(?![а-я]))/, 'surprised'], [/(испуг|страшн|бои|боя|дрож)/, 'scared'], [/(сонн|зева|устал)/, 'sleepy'],
  [/(влюбл|нежно|с любов)/, 'love'], [/(смущ|стесн)/, 'shy'], [/(спокойн|обычн)/, 'neutral']];
const VERBS = [ // stem → действие (порядок важен)
  [/^(катает|катают|валяет|валяют|покатил)/, 'roll'], [/^(кувырк|сальто)/, 'somersault'], [/^(ползет|ползёт|ползут|ползает|полз|ползк)/, 'crawl'],
  [/^(крадет|крадёт|крадут|подкрад|крадучись)/, 'sneak'], [/^(лежит|лежат|ложит|леж|улегл|улёгся|разлегл)/, 'lie'], [/^(обнима|обнял|обнимет)/, 'hug'],
  [/^(чешет|почесал|чешут|почёсыва|почесыва)/, 'scratch'], [/^(зева|зевнул)/, 'yawn'], [/^(потягива|потянул)/, 'stretch'], [/^(чиха|чихнул)/, 'sneeze'],
  [/^(ест$|едят|кушает|кушают|жует|жуёт|грызет|грызёт|лопает|уплета|съел|ел$|поедает)/, 'eat'], [/^(топает|топают|топнул|топочет)/, 'stomp'],
  [/^(присед|присел|пригнул|пригиба)/, 'crouch'], [/^(прячет|прячут|спрятал|спрята|прятал)/, 'hide'], [/^(поет|поёт|поют|напева|запел|спел)/, 'sing'],
  [/^(пинает|пнул|пинают|бьет|бьёт|ударил)/, 'kick'], [/^(бросает|бросил|кидает|кинул|бросают|швыря)/, 'throw'], [/^(кричит|крикнул|закричал|орет|орёт|вопит)/, 'shout'],
  [/^(вход|приход|появля|прибега|заход|прилета|выбега)/, 'enter'], [/^(уход|убега|выход|исчеза|улета|уходят|убегают)/, 'exit'],
  [/^(бежит|бегут|бега|мчит|несет|несут)/, 'run'], [/^(ид[её]т|идут|подход|шага|направля|подбега)/, 'walk'],
  [/^(прыга|подпрыг|скач)/, 'jump'], [/^(маш[еу]т|помаха)/, 'wave'], [/^(танцу|пляш)/, 'dance'], [/^(кружит|крутит|вертит)/, 'spin'], [/^(кива)/, 'nod'],
  [/^(кача|мота)/, 'shake'], [/^(хлопа|аплодир)/, 'clap'], [/^(показыва|указыва)/, 'point'], [/^(дума|размышля|мечта|задума)/, 'think'],
  [/^(смеет|смеют|хохоч|хихика)/, 'laugh'], [/^(пуга|испуга|дрож|боит)/, 'scared'], [/^(плач|рыда)/, 'cry'], [/^(кланя|поклон)/, 'bow'], [/^(удивля)/, 'surprise'],
  [/^(пада|упал|спотыка|поскальз)/, 'fall'], [/^(сад|присажива|сел$|сели$)/, 'sit'], [/^(засыпа|спит|спят|усну|ложит)/, 'sleep'], [/^(вста|просыпа|проснул|поднялс|поднима[её]тся)/, 'stand'],
  [/^(поворач|оборач|смотр|гляд|взгляну)/, 'turn'], [/^(бер[её]т|берут|поднима|хвата|наход|наш[её]л)/, 'take'], [/^(отда|дарит|передает|протягива|угоща)/, 'give'], [/^(клад|полож|ставит|роня|опуска)/, 'drop'],
];
const NARR = /^(рассказчик|автор|голос за кадром|за кадром|диктор)/;
const GENERIC = new Set('кот кошка котик котенок пес собака щенок мышонок мышка мышь медведь медвежонок заяц зайчик зайка лиса лисенок поросенок свинка мальчик девочка бабушка дедушка мама папа тетя дядя'.split(' '));

/** Индекс имён: имя → id. */
function nameIndex(chars) {
  const idx = [];
  for (const [id, c] of Object.entries(chars)) { const n = low(c.name || c.spec && c.spec.name || ''); if (!n) continue; idx.push([n, id]); const w = n.split(/\s+/); if (w.length > 1) { for (const x of w) if (x.length > 2 && !GENERIC.has(x)) idx.push([x, id]); } }
  return idx.sort((a, b) => b[0].length - a[0].length);
}
function findNameAt(text, idx) { // имя в начале строки
  const t = low(text).trim();
  for (const [n, id] of idx) { if (t.startsWith(n)) { const rest = t.slice(n.length); const m = rest.match(/^[а-яa-z]{0,3}/); if (!rest || /^[^а-яa-z]/.test(rest) || (m && /^(а|у|ом|ой|е|ы|ой|ю|я|ем|ей|ам)?(\s|$|[,.:!?()])/.test(rest))) return { id, len: n.length + ((rest.match(/^[а-я]{0,3}/) || [''])[0].length) }; } }
  return null;
}
function namesIn(text, idx) { const out = []; const t = low(text); for (const [n, id] of idx) { const re = new RegExp('(^|[^а-яa-z])' + n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[а-я]{0,3}(?=$|[^а-яa-z])', 'g'); if (re.test(t) && !out.includes(id)) out.push(id); } return out; }
function pick(list, t) { for (const [re, v] of list) if (re.test(t)) return v; return null; }

/** Разобрать текст. lib — библиотека (characters, locations). opts: {series}. → {episodes:[ep], errors, warnings, newChars} */
S.parse = function (text, lib, opts) {
  opts = opts || {};
  const errors = [], warnings = [];
  const chars = {}; for (const [id, c] of Object.entries(lib.characters || {})) chars[id] = { name: c.spec.name, spec: c.spec, old: true };
  const locs = Object.assign({}, lib.locations || {});
  const newChars = {}, newLocs = {};
  let nextC = 100, nextL = 100;
  for (const id of Object.keys(chars)) { const m = id.match(/^К(\d+)$/); if (m) nextC = Math.max(nextC, +m[1]); }
  for (const id of Object.keys(locs)) { const m = id.match(/^Л(\d+)$/); if (m) nextL = Math.max(nextL, +m[1]); }
  const lex = opts.lexicon || {};
  const userVerbs = Object.entries(lex.verbs || {}); // [слово, действие]
  const nameIndexL = () => { const i = nameIndex(chars); for (const [a, id] of Object.entries(lex.names || {})) if (chars[id] || id === 'Р') i.push([low(a), id]); return i.sort((a, b) => b[0].length - a[0].length); };
  let idx = nameIndexL();
  const unknownNames = new Set(), unknownWords = new Map();
  let series = opts.series || 'Мой мультик', music = 'happy';
  const eps = []; let ep = null, sc = null, lastSpeaker = null, sceneSpeakers = [];
  const newEp = (num, title) => { ep = { format: 'multik/1', series, episode: num, title: title || '', music, scenes: [], characters: [], locations: [] }; eps.push(ep); sc = null; };
  const ensureScene = () => { if (!sc) newScene('двор, день'); };
  const lines = String(text || '').replace(/\r/g, '').split('\n');
  // 1-й проход: персонажи
  for (const raw of lines) {
    const m = raw.trim().match(/^(?:персонаж|герой|новый персонаж)\s*[:\-—]\s*([^—–\-:]+?)\s*[—–\-:]\s*(.+)$/i);
    if (!m) continue;
    const name = m[1].trim(), desc = m[2].trim(), existing = findNameAt(name, idx);
    if (existing && low(chars[existing.id].name) === low(name)) { if (!chars[existing.id].old) continue; warnings.push(`«${name}» уже есть (${existing.id}) — беру готового, описание пропускаю.`); continue; }
    if (!global.MKMaker) { errors.push('Нет модуля создания персонажей'); continue; }
    const r = global.MKMaker.apply(null, desc + ', зовут ' + name); r.spec.name = name;
    const id = 'К' + (++nextC); const spec = global.MKMaker.finalize(r.spec, id); spec.about = desc;
    chars[id] = { name, spec }; newChars[id] = spec; idx = nameIndexL();
    if (r.unknown.length) warnings.push(`${name}: не понял слова «${r.unknown.join(', ')}» — остальное учёл.`);
  }
  const placeX = (side) => { const used = Object.values(sc._x); for (const x of (side === 'right' ? [.72, .62, .84, .52] : side === 'left' ? [.28, .38, .16, .48] : []).concat([.35, .62, .2, .78, .5, .1, .9])) if (!used.some(u => Math.abs(u - x) < .1)) return x; return .5; };
  const castOf = (id, hidden, side) => { if (id === 'Р') return; if (!sc._cast[id]) { const x = placeX(side); sc._cast[id] = { who: id, x, hidden: !!hidden }; sc._x[id] = x; sc.cast.push(sc._cast[id]); } };
  function newScene(desc) {
    if (!ep) newEp(1, '');
    const d = low(desc), type = pick(PLACES, d) || (sc && sc._type) || 'yard', time = pick(TIMES, d) || 'day', weather = /дожд/.test(d) ? 'rain' : /снег|снежн/.test(d) ? 'snow' : 'none';
    let lid = Object.keys(locs).find(id => { const s = locs[id].spec; return s.type === type && (s.time || 'day') === time && (s.weather || 'none') === weather; });
    if (!lid) { lid = 'Л' + (++nextL); const spec = { id: lid, name: desc.trim().slice(0, 40) || type, type, time, weather, seed: nextL }; locs[lid] = { spec }; newLocs[lid] = spec; }
    sc = { id: 'С' + (ep.scenes.length + 1), location: lid, cast: [], props: [], steps: [], _cast: {}, _x: {}, _type: type };
    const mu = pick(MUSIC, d); if (mu) sc.music = mu;
    ep.scenes.push(sc); lastSpeaker = null; sceneSpeakers = [];
  }
  let lineNo = 0, narrated = 0;
  for (const raw0 of lines) {
    lineNo++;
    let raw = raw0.trim(); if (!raw || /^(персонаж|герой|новый персонаж)\s*[:\-—]/i.test(raw) || /^\/\//.test(raw)) continue;
    const L = low(raw);
    let m;
    if ((m = raw.match(/^(?:сериал|мультик|мультфильм)\s*[:\-—]\s*(.+)$/i))) { series = m[1].trim(); if (ep) ep.series = series; continue; }
    if ((m = raw.match(/^серия\s*[:\-—]?\s*(\d+)?\s*[.:\-—]?\s*(.*)$/i))) { newEp(m[1] ? +m[1] : (eps.length ? eps[eps.length - 1].episode + 1 : (opts.nextEpisode || 1)), m[2].trim()); continue; }
    if ((m = raw.match(/^(?:сцена|место|локация)\s*\d*\s*[:.\-—]?\s*(.*)$/i))) { if (!ep) newEp(opts.nextEpisode || 1, ''); newScene(m[1] || ''); continue; }
    if ((m = raw.match(/^музыка\s*[:\-—]\s*(.+)$/i))) { const mu = pick(MUSIC, low(m[1])) || 'happy'; if (sc) sc.steps.push({ music: mu }); else music = mu; continue; }
    if ((m = raw.match(/^(?:звук|шум)\s*[:\-—]\s*(.+)$/i))) { ensureScene(); const s = pick(SFX, low(m[1])); if (s) sc.steps.push({ sfx: s }); else warnings.push(`Строка ${lineNo}: не знаю звук «${m[1]}»`); continue; }
    if ((m = L.match(/^пауза\s*(\d+(?:[.,]\d+)?)?/))) { ensureScene(); sc.steps.push({ wait: m[1] ? +m[1].replace(',', '.') : 1 }); continue; }
    if ((m = raw.match(/^(?:камера|план)\s*[:\-—]\s*(.+)$/i)) || /^\(?\s*(крупн|общий план|средний план|оба в кадре)/.test(L)) { ensureScene(); camera(m ? m[1] : raw); continue; }
    if (!ep) newEp(opts.nextEpisode || 1, '');
    ensureScene();
    // реплика «Имя (как): текст»
    m = raw.match(/^([^:()]{1,40}?)\s*(?:\(([^)]*)\))?\s*:\s*(.+)$/);
    if (m) {
      const who = NARR.test(low(m[1].trim())) ? 'Р' : (findNameAt(m[1], idx) || {}).id;
      if (!who) { if (/^[А-ЯЁA-Z]/.test(m[1].trim()) && m[1].trim().split(/\s+/).length <= 3) { unknownNames.add(m[1].trim()); errors.push(`Строка ${lineNo}: кто такой «${m[1].trim()}»? Выбери ниже, кто это, или добавь строку «ПЕРСОНАЖ: ${m[1].trim()} — описание».`); continue; }
        m = null; } else {
      castOf(who);
      const cl = global.MK ? global.MK.cleanSpeech(m[3].replace(/^["«]|["»]$/g, '').trim()) : { text: m[3], removed: [] };
      if (cl.removed.length) warnings.push(`Строка ${lineNo}: убрал из озвучки лишнее: ${cl.removed.join(' ')}`);
      if (!cl.text) continue;
      const step = { who, say: cl.text };
      if (m[2]) { const e = pick(EMO, low(m[2])); if (e) step.emotion = e; const v = verbOf(low(m[2])); if (v && who !== 'Р') step.do = v; }
      { const rest = low(m[1]).replace(/^\S+\s*/, ''); const v2 = rest && who !== 'Р' ? verbOf(rest) : null; if (v2 && !step.do) step.do = v2; const e2 = rest ? pick(EMO, rest) : null; if (e2 && !step.emotion) step.emotion = e2; }
      if (who !== 'Р') { const other = lastSpeaker && lastSpeaker !== who && lastSpeaker !== 'Р' ? lastSpeaker : sceneSpeakers.filter(x => x !== who && x !== 'Р').slice(-1)[0]; if (other) step.to = other;
        autoCam(who); }
      sc.steps.push(step); lastSpeaker = who; if (!sceneSpeakers.includes(who)) sceneSpeakers.push(who);
      continue; }
    }
    // диалог через тире: «— Привет! — сказал Барсик.»
    if (/^[—–-]\s*\S/.test(raw)) { if (dashLine(raw)) continue; }
    // действие: «(Барсик прыгает)», «Пик входит справа.», «Барсик и Пик танцуют»
    const bracket = /^\(.*\)$/.test(raw);
    const t = raw.replace(/^\(|\)$/g, '').trim();
    const sentences = t.match(/[^.!?…]+[.!?…]*/g) || [t];
    for (const sent0 of sentences) { const sent = sent0.trim(); if (!sent) continue;
      placeShift(sent);
      const core = sent.replace(/[.!?…]+$/, '');
      const pieces = core.split(/\s+и\s+(?=[а-яё]+(?:ет|ит|ут|ют|ат|ят|ется|ится|ал|ял|ил|ел|ла|ли)(?![а-яё]))/i).filter(x => x && !/^(ет|ит|ут|ют|ат|ят|ется|ится|ал|ял|ил|ел|ла|ли)$/.test(x));
      let did = false; let subjName = null;
      pieces.forEach((pc, k) => { let q = pc; if (k > 0 && subjName && !namesIn(low(q), idx).length) q = subjName + ' ' + q; const ok = action(q); if (ok) { did = true; if (k === 0) { const ids = namesIn(low(pc), idx); if (ids[0]) subjName = chars[ids[0]] ? chars[ids[0]].name : null; } } });
      const past = /[а-яё]+(?:ал|ял|ил|ел|ул|ыл|ла|ли|лся|лась|лись)(?![а-яё])/i.test(core) && core.split(/\s+/).length >= 3;
      if (did && past && !bracket) { sc.steps.push({ who: 'Р', say: sent, with: true }); }
      if (!did && !bracket) { sc.steps.push({ who: 'Р', say: sent }); narrated++; }
      else if (!did) warnings.push(`Строка ${lineNo}: не понял «${sent.slice(0, 50)}» — пропускаю.`);
    }
  }
  function placeShift(sent) { // «Друзья пришли в лес» → новая сцена
    const d = low(sent); const type = pick(PLACES, d); if (!type || type === sc._type) return;
    if (!/(^|\s)(в|во|на|к|у)\s/.test(d)) return;
    if (!/(пришл|приш[её]л|пош[её]л|пошли|побежал|отправил|оказал|вернул|прибежал|прилетел|полетел|поехал|приехал|^в |^на |^утром|^вечером|^ночью)/.test(d) && sc.steps.length) return;
    const time = pick(TIMES, d); const keepCast = Object.keys(sc._cast);
    newScene((type === 'forest' ? 'лес' : type) + (time ? ' ' + (time === 'night' ? 'ночь' : time === 'evening' ? 'вечер' : 'день') : ''));
    sc.location = sc.location; keepCast.forEach(id => { if (id !== 'Р') { castOf(id); } });
  }
  function dashLine(raw) { // — Реплика, — сказал Имя. — Продолжение.
    const parts = raw.replace(/^[—–-]\s*/, '').split(/\s+[—–]\s+/);
    let speech = [parts[0]], who = null, emo = null;
    for (let i = 1; i < parts.length; i++) { const d = low(parts[i]); const ids = namesIn(d, idx);
      if (!who && ids.length && /(сказал|ответил|спросил|крикнул|закричал|прошептал|воскликнул|произн[её]с|добавил|засмеял|пискнул|буркнул|улыбнул|вздохнул|обрадовал|удивил|сказала|ответила|спросила|крикнула)/.test(d)) { who = ids[0]; emo = pick(EMO, d); } else speech.push(parts[i]); }
    if (!who) { const cand = sceneSpeakers.filter(x => x !== 'Р'); who = cand.length >= 2 ? cand.find(x => x !== lastSpeaker) : (cand[0] || null); }
    if (!who) return false;
    castOf(who); const text = speech.join(' ').replace(/[,]$/, '').replace(/,\s*$/, '.').trim();
    const step = { who, say: text }; if (emo) step.emotion = emo;
    const other = sceneSpeakers.filter(x => x !== who && x !== 'Р').slice(-1)[0]; if (other) step.to = other;
    autoCam(who); sc.steps.push(step); lastSpeaker = who; if (!sceneSpeakers.includes(who)) sceneSpeakers.push(who); return true;
  }
  function verbOf(t) { if (/выход\S*\s+(во|в|на)\s/.test(t) && !/(из|прочь)/.test(t)) return 'enter'; for (const w of t.split(/[^а-яa-z]+/)) { const u = userVerbs.find(([k]) => w === k || (k.length > 4 && w.startsWith(k.slice(0, -1)))); if (u) return u[1]; const v = pick(VERBS, w); if (v) return v; } return null; }
  function camera(t) { const d = low(t); const who = namesIn(d, idx);
    if (/(крупн|лицо)/.test(d) && who[0]) sc.steps.push({ camera: 'close', on: who[0] });
    else if (/(средн)/.test(d) && who[0]) sc.steps.push({ camera: 'medium', on: who[0] });
    else if (/(оба|вдво|двое)/.test(d) && who.length >= 2) sc.steps.push({ camera: 'two', on: who.slice(0, 2) });
    else if (/(тряс|дрож)/.test(d)) sc.steps.push({ shake: .6 });
    else sc.steps.push({ camera: 'wide' }); sc._cam = 'manual'; }
  function autoCam(who) { // простая режиссура, если камера не задана вручную
    if (sc._cam === 'manual') return; const n = sc.steps.filter(s => s.say && s.who !== 'Р').length;
    if (lastSpeaker === who && sc._cam !== 'medium:' + who) { sc.steps.push({ camera: 'medium', on: who }); sc._cam = 'medium:' + who; }
    else if (lastSpeaker && lastSpeaker !== who && lastSpeaker !== 'Р' && n >= 1 && !String(sc._cam || '').startsWith('two')) { sc.steps.push({ camera: 'two', on: [lastSpeaker, who] }); sc._cam = 'two'; }
  }
  function action(sent) {
    const d = low(sent); let who = namesIn(d, idx).filter(id => { const n = findNameAt(d, idx); return true; });
    // порядок имён по позиции в предложении
    who = who.map(id => [id, d.search(low(chars[id].name).split(' ').slice(-1)[0].slice(0, 4))]).sort((a, b) => a[1] - b[1]).map(x => x[0]);
    if (!who.length) { if (/(крупн|общий план)/.test(d)) { camera(d); return true; } const s = pick(SFX, d); if (s && /(звук|слышно|раздает)/.test(d)) { sc.steps.push({ sfx: s }); return true; } return false; }
    const verb = verbOf(d); const emo = pick(EMO, d);
    if (!verb && !emo) { const words = d.split(/[^а-яa-z]+/).filter(w => w.length > 3 && !idx.some(([n]) => w.startsWith(n.slice(0, 4))) && !/^(тоже|потом|сразу|снова|очень|когда|вдруг|затем|тогда|после|перед|около|возле|вместе)$/.test(w));
      if (words[0]) unknownWords.set(words[0], sent.trim()); return false; }
    // подлежащее — первые имена до глагола; остальные — цели
    const vpos = (() => { for (const w of d.split(/[^а-яa-z]+/)) if (pick(VERBS, w)) return d.indexOf(w); return 999; })();
    const subj = who.filter(id => { const p = d.indexOf(low(chars[id].name).split(' ').slice(-1)[0].slice(0, 4)); return p < vpos; });
    const S = subj.length ? subj : [who[0]];
    const targets = who.filter(id => !S.includes(id));
    let first = true;
    for (const id of S) {
      const step = { who: id }; if (!first) step.with = true; first = false;
      if (emo) step.emotion = emo;
      const tgt = targets[0];
      if (verb === 'enter') { const side = /(слева|левой)/.test(d) ? 'left' : /(справа|правой)/.test(d) ? 'right' : null; castOf(id, true, side); step.do = 'enter'; step.from = side || (sc._x[id] > .5 ? 'right' : 'left'); step.to = tgt && sc._x[tgt] != null ? tgt : sc._x[id]; if (step.to === undefined) delete step.to; }
      else {
        castOf(id);
        if (verb === 'exit') { step.do = 'exit'; step.side = /(влево|налево|слева)/.test(d) ? 'left' : /(вправо|направо|справа)/.test(d) ? 'right' : undefined; if (!step.side) delete step.side; }
        else if (verb === 'walk' || verb === 'run') { step.do = verb; if (tgt) { castOf(tgt); step.to = tgt; } else if (/(вправо|направо)/.test(d)) step.to = Math.min(.85, (sc._x[id] || .5) + .3); else if (/(влево|налево)/.test(d)) step.to = Math.max(.15, (sc._x[id] || .5) - .3); else if (/(центр|середин)/.test(d)) step.to = .5; else { const p = propIn(d); if (p) { const pr = ensureProp(p, id); step.to = Math.max(.08, Math.min(.92, pr.x - .06)); } else step.to = (sc._x[id] || .5) > .5 ? .3 : .7; }
          if (typeof step.to === 'number') sc._x[id] = step.to; else if (sc._x[step.to] != null) sc._x[id] = sc._x[step.to] + (sc._x[step.to] > sc._x[id] ? -.12 : .12); }
        else if (verb === 'think') { step.do = 'think'; const q = sent.match(/[«"]([^»"]+)[»"]/); step.text = q ? q[1] : (d.match(/(о|об|про)\s+(\S+)/) ? '?' : '?'); }
        else if (verb === 'turn') { step.do = 'turn'; step.to = tgt || (/(на нас|в камеру|к зрител)/.test(d) ? 'camera' : /(влево|налево)/.test(d) ? 'left' : /(вправо|направо)/.test(d) ? 'right' : 'camera'); if (tgt) castOf(tgt); }
        else if (verb === 'hug') { step.do = 'hug'; if (tgt) { castOf(tgt); step.to = tgt; } }
        else if (verb === 'kick' || verb === 'throw') { step.do = verb; const p = propIn(d) || (verb === 'kick' ? 'ball' : null);
          if (verb === 'kick') { const pr = ensureProp(p, id); step.prop = pr.id; } else if (p && !sc.props.some(x => x._held === id)) { const pr = ensureProp(p, id); sc.steps.push({ who: id, do: 'take', prop: pr.id }); pr._held = id; }
          if (tgt) { castOf(tgt); step.to = tgt; } }
        else if (verb === 'crawl' || verb === 'sneak') { step.do = verb; if (tgt) { castOf(tgt); step.to = tgt; } else if (/(вправо|направо)/.test(d)) step.to = Math.min(.85, (sc._x[id] || .5) + .3); else if (/(влево|налево)/.test(d)) step.to = Math.max(.15, (sc._x[id] || .5) - .3); else step.to = (sc._x[id] || .5) > .5 ? .35 : .65; if (typeof step.to === 'number') sc._x[id] = step.to; }
        else if (verb === 'take') { const p = propIn(d) || 'ball'; const pr = ensureProp(p, id); step.do = 'take'; step.prop = pr.id; pr._held = id; }
        else if (verb === 'give') { step.do = 'give'; if (tgt) { castOf(tgt); step.to = tgt; const p = propIn(d); if (p && !sc.props.some(x => x._holder === id)) { const pr = ensureProp(p, id); sc.steps.push({ who: id, do: 'take', prop: pr.id }); } } else delete step.do; }
        else if (verb) step.do = verb;
      }
      if (!step.do && !step.emotion) { if (emo == null && !verb) return false; }
      if (!step.do) delete step.do;
      sc.steps.push(step);
      if (step.do === 'jump' || step.do === 'enter' || step.do === 'dance' || step.do === 'fall') { if (sc._cam && sc._cam !== 'manual' && sc._cam !== 'wide') { sc.steps.push({ camera: 'wide', with: true }); sc._cam = 'wide'; } }
    }
    return true;
  }
  function propIn(d) { for (const w of d.split(/[^а-яa-z]+/)) { const p = pick(PROPS, w); if (p) return p; } return null; }
  function ensureProp(type, nearId) { let p = sc.props.find(x => x.type === type && !x._used); if (!p) { const x = Math.max(.08, Math.min(.92, (sc._x[nearId] != null ? sc._x[nearId] : .5) + .15)); p = { id: 'П' + (sc.props.length + 1), type, x }; sc.props.push(p); } p._used = true; return p; }

  // чистка служебных полей, персонажи/локации в серии, автоделение длинных серий
  const out = [];
  for (const e of eps) {
    if (!e.scenes.length) continue;
    for (const s of e.scenes) { delete s._cast; delete s._x; delete s._type; delete s._cam; s.props.forEach(p => { delete p._used; delete p._holder; delete p._held; }); if (!s.props.length) delete s.props; }
    const usedC = new Set(), usedL = new Set(); e.scenes.forEach(s => { usedL.add(s.location); s.cast.forEach(c => usedC.add(c.who)); s.steps.forEach(st => st.who && usedC.add(st.who)); });
    e.characters = [...usedC].filter(id => newChars[id]).map(id => newChars[id]);
    e.locations = [...usedL].filter(id => newLocs[id]).map(id => newLocs[id]);
    e.series = e.series || series;
    e.youtube = { title: `${e.series} — Серия ${e.episode}${e.title ? '. ' + e.title : ''}`, description: `${e.series}. Серия ${e.episode}${e.title ? ': ' + e.title : ''}. Мультфильм для детей.`, tags: ['мультик', 'мультфильм', e.series] };
    out.push(e);
  }
  return { episodes: out, errors, warnings, newChars: Object.values(newChars), newLocs: Object.values(newLocs), unknownNames: [...unknownNames], unknownWords: [...unknownWords].map(([w, s]) => ({ word: w, sentence: s })), narrated };
};

/** Длинную серию делит на части ≈ target секунд по границам сцен. */
S.split = function (ep, lib, target) {
  target = target || 300; if (!global.MK) return [ep];
  const tmpLib = { characters: Object.assign({}, lib.characters), locations: Object.assign({}, lib.locations) };
  for (const c of ep.characters || []) tmpLib.characters[c.id] = { spec: c }; for (const l of ep.locations || []) tmpLib.locations[l.id] = { spec: l };
  const tl = global.MK.compile(Object.assign({}, ep, { titleCard: false, endCard: false }), tmpLib, {});
  const durs = tl.segs.filter(s => s.kind === 'scene').map(s => s.t1 - s.t0);
  const total = durs.reduce((a, b) => a + b, 0);
  if (total <= target * 1.25) return [ep];
  const parts = []; let cur = [], sum = 0;
  ep.scenes.forEach((s, i) => { if (cur.length && sum + durs[i] > target) { parts.push(cur); cur = []; sum = 0; } cur.push(s); sum += durs[i]; });
  if (cur.length) parts.push(cur);
  return parts.map((sc, k) => { const e = JSON.parse(JSON.stringify(ep)); e.episode = ep.episode + k; e.title = ep.title ? (parts.length > 1 ? `${ep.title} (часть ${k + 1})` : ep.title) : '';
    e.scenes = sc.map((s, j) => Object.assign(s, { id: 'С' + (j + 1) }));
    const usedC = new Set(), usedL = new Set(); e.scenes.forEach(s => { usedL.add(s.location); s.cast.forEach(c => usedC.add(c.who)); });
    e.characters = (ep.characters || []).filter(c => usedC.has(c.id)); e.locations = (ep.locations || []).filter(l => usedL.has(l.id));
    if (k < parts.length - 1) e.endText = 'Продолжение следует…';
    e.youtube = { title: `${e.series} — Серия ${e.episode}${e.title ? '. ' + e.title : ''}`, description: ep.youtube.description, tags: ep.youtube.tags };
    return e; });
};

S.EXAMPLE = `СЕРИАЛ: Кот Барсик
СЕРИЯ: 2. Клад в лесу
ПЕРСОНАЖ: Колючка — серый медвежонок с зелёным шарфом, голос мальчика

СЦЕНА: двор, утро
Рассказчик: Утром Барсик нашёл у крыльца старую карту.
Барсик берёт книгу.
Барсик (удивлённо): Ого! Это же карта клада!
Пик входит справа.
Пик: Клад? Бежим искать!
Барсик и Пик прыгают.

СЦЕНА: лес, день
МУЗЫКА: приключения
Барсик входит слева.
Пик входит слева.
Колючка входит справа.
Колючка: Привет! Вы куда так спешите?
Барсик: Мы ищем клад!
Колючка (радостно): Я знаю, где большой дуб. Пойдёмте!
(Колючка идёт вправо)
Рассказчик: Что же найдут друзья под большим дубом?`;

S.ACTIONS = { roll: 'катается по земле', somersault: 'кувыркается', crawl: 'ползёт', sneak: 'крадётся', lie: 'ложится', hug: 'обнимает', scratch: 'чешет голову', yawn: 'зевает', stretch: 'потягивается', sneeze: 'чихает', eat: 'ест', stomp: 'топает', crouch: 'приседает', hide: 'прячется', sing: 'поёт', kick: 'пинает', throw: 'бросает', shout: 'кричит', enter: 'входит', exit: 'уходит', walk: 'идёт', run: 'бежит', jump: 'прыгает', wave: 'машет', dance: 'танцует', spin: 'кружится', nod: 'кивает', shake: 'качает головой',
  clap: 'хлопает', point: 'показывает', think: 'думает', laugh: 'смеётся', scared: 'пугается', cry: 'плачет', bow: 'кланяется', surprise: 'удивляется', fall: 'падает', sit: 'садится',
  sleep: 'засыпает', stand: 'встаёт', turn: 'поворачивается', take: 'берёт', give: 'отдаёт', drop: 'кладёт', none: '— ничего, пусть читает рассказчик' };
global.MKScript = S;
})(typeof window !== 'undefined' ? window : globalThis);
