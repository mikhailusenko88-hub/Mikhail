'use strict';
/* Грязь, вид сбоку — рисование и управление, версия 2. Мир рисует объёмный вид Hook Truck (r3d.js); здесь — гараж-конструктор, свой грузовик
   (каждая деталь видна), живая грязь (колея остаётся), вода с вешками, указатели, брызги и дым, кнопки. Правая рука — газ и назад, левая — остальное. */
(function () {
  const P = window.TPhys, M = window.MudSide, R3 = window.Hook3D, PX = M.PX, VER = '6.8';
  const cv = document.getElementById('c'), ctx = cv.getContext('2d'), glc = document.getElementById('gl');
  // языки: русский и английский здесь, ещё восемь — в i18n.js (es, pt, tr, de, fr, it, pl, id); чего нет в переводе — берётся из английского
  const TX = { ru: {
    garage: 'Гараж', go: 'В рейс', cont: 'С отметки', anew: 'С начала', intro: 'Собери грузовик под полигон. Что помогает в грязи, мешает в гору — а топливо общее.',
    p: { awd: 'Полный привод', lock: 'Блокировка', low: 'Пониженная', base: 'База', lift: 'Лифт', wheel: 'Размер', axles: 'Мосты', tires: 'Шины', eng: 'Форсировка', snorkel: 'Шноркель', tank: 'Бак', susp: 'Подвеска', skid: 'Защита днища', press: 'Давление', ctis: 'Подкачка', gear: 'Главная пара', winch: 'Лебёдка', trailer: 'Прицеп', paint: 'Краска' },
    tabs: ['Шасси', 'Колёса', 'Привод', 'Прочее'], soft: 'ШИНЫ',
    cg: { log: 'Брёвна', barrel: 'Бочки', melon: 'Арбузы' }, cgN: { log: 'Обычный груз. Чем больше берёшь, тем тяжелее в грязи и в гору.', barrel: 'Тяжёлые: в грязи и в гору машина тянет хуже. На ухабах с разгона вылетают.', melon: 'Лёгкие и прыгают: через ухабы — медленно.' },
    pause: 'Пауза', resume: 'Дальше', towTo: 'Тягач к флажку', towFree: 'Тягач бесплатно', quit: 'Бросить рейс', noPay: 'Груз не довезён', opened: 'Открыт заказ', hTow: 'Не вылезти? ❚❚ — тягач к флажку. Или брось рейс и поставь другую деталь', lit: 'л', x2: 'Удвоить', topUp: 'Добрать', wt: 'вес', tn: 'т',
    menu: 'Заказы', poly: 'Полигон: проба деталей, без груза', ver: 'проба', perLog: 'за штуку', lockedC: 'Сначала довези предыдущий заказ', logsN: 'Груз', payL: 'Оплата', fuelL: 'Топливо — 1 монета за литр, тягач — 60', back: 'Назад', tow: 'Тягач', giveUp: 'Бросить рейс', toMenu: 'К заказам', buyFor: 'Купить за', lack: 'Не хватает', rDeliv: 'Довёз', rFuel: 'Топливо', rTotal: 'Итого', cs: ['Довёз', 'Полный кузов', 'Без тягача'], winC: 'Заказ выполнен!', logLost: 'Груз упал!', of: 'из',
    o: { awd: ['нет', 'есть'], lock: ['нет', 'есть'], low: ['нет', 'есть'], base: ['короткая', 'длинная', 'длинная+'], lift: ['нет', '+1', '+2'], wheel: ['малые', 'средние', 'большие'], axles: ['4×4', '6×6'], tires: ['дорожные', 'универс.', 'грязевые'], eng: ['0', '1', '2', '3', '4', '5', '6', '7', '8'], trailer: ['нет', 'тележка', 'большой'], snorkel: ['нет', 'есть'], tank: ['60 л', '95 л'], susp: ['мягкая', 'средняя', 'жёсткая'], skid: ['нет', 'есть'], press: ['низкое', 'среднее', 'высокое'], ctis: ['нет', 'есть'], gear: ['тяговая', 'средняя', 'скоростная'], winch: ['15 м', '21 м'] },
    n: {
      awd: ['Задний привод: дёшево и экономно, но в грязи и в гору слабо.', 'Полный привод: кнопка 4×4 — тянут все колёса. Расход больше.'],
      lock: ['Без блокировки: в грязи одно колесо моста буксует впустую.', 'Блокировка: кнопка БЛОК — в грязи гребут оба колеса моста.'],
      low: ['Без пониженной: крутой подъём не взять.', 'Пониженная: кнопка ПОНИЖ — тяги больше, скорость меньше; в грязи не закапываешься.'],
      susp: ['Мягкая подвеска: колёса не отрываются от неровностей, но в гору машина приседает на зад.', 'Средняя подвеска.', 'Жёсткая подвеска: в гору меньше задирает нос, но на ухабах колёса висят.'],
      skid: ['Без защиты: сел брюхом — держит намертво.', 'Защита днища: стальной лист, по гребню и грязи брюхо скользит. Плюс вес.'],
      press: ['Низкое давление: шина шире — меньше тонет в песке и торфе, лучше гребёт. На твёрдом медленнее, расход больше.', 'Среднее давление.', 'Высокое давление: быстро и экономно по твёрдому, но в мягком режет грунт.'],
      ctis: ['Без подкачки: давление ставишь в гараже на весь рейс.', 'Подкачка: кнопка ШИНЫ спускает колёса на ходу — перед песком и торфом — и накачивает обратно.'],
      gear: ['Тяговая пара: тяга +25%, скорость −20%.', 'Средняя пара.', 'Скоростная пара: скорость +20%, тяга −18% — на подъёмах и в липком не вытянет.'],
      winch: ['Лебёдка: трос 15 м. Тянет от мотора — жжёт топливо, без топлива не работает.', 'Лебёдка с длинным тросом: 21 м и тянет быстрее. Топливо жжёт так же.'],
      trailer: ['Без прицепа: везёшь только в кузове.', 'Тележка: +9 брёвен или 7 бочек, запасной бак 30 л. Висит на грузовике мёртвым весом: чем сильнее мотор, тем полнее её грузишь.', 'Большой прицеп: +19 брёвен или 15 бочек, запасной бак 50 л. Мосты ведущие — гребут, пока включён полный привод. Каждая ступень мотора с 5-й — ещё две бочки.'],
      paint: ['Краска — на проходимость не влияет, зато красиво.'],
      base: ['Короткая база: легко переваливает гребни, но на крутом подъёме задирает нос. Прицеп на неё не ставится.', 'Длинная база: груза больше, в гору устойчива. Тяжелее в грязи. Гребни бери с хода — медленно сядет брюхом.', 'Очень длинная база: груза ещё больше. Тяжёлая — с полным кузовом нужна форсировка. Гребни только с хода.'],
      lift: ['Без лифта: устойчив, но брюхо низко и брод мелкий.', 'Лифт +1: брюхо и брод выше на 17 см.', 'Лифт +2: ещё выше — но на самом крутом подъёме опрокидывает.'],
      wheel: ['Малые колёса: вся тяга на земле, но тонут в грязи.', 'Средние: тонут меньше, брод глубже; в гору тяги меньше.', 'Большие: почти не тонут, но в гору без мотора не идут и жгут топливо.'],
      axles: ['4×4: легче и экономнее.', '6×6: гребёт тремя мостами, не встаёт на дыбы и везёт больше — особенно с длинной рамой. Только он тянет прицеп. Тяжелее и прожорливее.'],
      tires: ['Дорожные шины: быстрее и экономнее, в грязи скользят.', 'Универсальные шины: середина.', 'Грязевые шины: цепляют в грязи; на твёрдом медленнее, расход больше.'],
      eng: [0, 1, 2, 3, 4, 5, 6, 7, 8].map((v) => (v ? `Форсировка ${v} из 8: тяга +${12 * Math.min(v, 5) + 7 * Math.max(0, v - 5)}%, везёт на ${String(Math.round(10 * M.ENG_T(v)) / 10).replace('.', ',')} т больше, расход +${6 * v}%.${v >= 6 ? ' Короткую раму на подъёме задирает — бери длинную.' : ''}` : 'Мотор заводской: экономный, но тяжёлый груз в гору и в грязи не тянет.')),
      snorkel: ['Без шноркеля: вода выше капота — мотор заглохнет.', 'Шноркель: воздух берётся с крыши, глубокий брод не страшен.'],
      tank: ['Бак 60 л.', 'Бак 95 л: дальше едешь, чуть тяжелее.'],
    },
    sClear: 'Клиренс', sFord: 'Брод до', sPull: 'Тяга', sRange: 'Запас хода', sLoad: 'Груз до', tapBuy: 'Нажми зелёную кнопку ещё раз — купишь.', tapAd: (n) => `Не хватает ${n} монет: нажми жёлтую кнопку — доберёшь за рекламу.`, tapNo: (n) => `Не хватает ${n} монет — подзаработай на заказах.`, trNeed: 'Прицеп тянет только длинная рама с тремя мостами: короткую с ним задирает, а 4×4 встаёт в липкой грязи. Сначала вкладка «Шасси» — длинная рама и 6×6.', gain: (a, b) => `Полный рейс: ${a} → ${b} ¤ (${b > a ? '+' : '−'}${Math.abs(b - a)}).`, gainLoss: 'С этим мотором прицеп отнимает больше, чем даёт.', gainSpace: 'Заработок не вырастет: кузов и так полон — нужен прицеп побольше.', gainWeight: 'Заработок не вырастет: груз упирается в вес — нужен мотор сильнее.', gainAx: 'Сам заработка не прибавит — зато с ним можно цеплять прицеп.', mx: 'макс', m: 'м', over: (t) => `Больше не увезёт: грузоподъёмность ${t} т. Форсируй мотор, удлиняй раму или ставь 6×6.`,
    awd: '4×4', lock: 'БЛОК', low: 'ПОНИЖ', winch: 'ЛЕБЁДКА', ahead: 'Впереди', soil: { shallow: 'мелкая грязь', soft: 'мягкая грязь', medium: 'грязь', sticky: 'липкая грязь', swamp: 'болото', sand: 'песок', clay: 'глина', peat: 'торф', scree: 'осыпь' }, crest: 'гребень', ford: 'брод', climb: 'подъём', descent: 'спуск', rocks: 'камни', stepW: 'уступ', upW: 'в гору', downW: 'под гору', upTo: 'до',
    hClog: 'Шины забиты: на твёрдом разгонись на обычной передаче — слетит. Или промой в броду', hSand: 'Песок: не буксуй. Назад по своему следу и с хода — или спусти шины', hSandLow: 'Песок: выключи ПОНИЖ — с ней не разогнаться. Сдай назад по своей колее и бери с разгона', wNone: 'Лебёдке тут не за что зацепиться: она тянет только к дереву с меткой', wFar: (m) => `Лебёдка: подъедь ближе к дереву с меткой — трос ${m} м`, goAny: 'Всё равно в рейс', adNo: 'Ролик сейчас не загрузился — попробуй чуть позже', minC: (n) => `от ${n} шт.`, whyCap: (n, c) => `заказ от ${n} шт., а грузовик берёт только ${c}`, goCap: (n) => `Нужно от ${n}`, rent: (p) => `Ролик: ${p} на один рейс`, hScree: 'Осыпь: не буксуй — закапывает. Сдай назад и бери с хода', hScreeSoft: 'Осыпь: не буксуй — закапывает. Спусти шины или сдай назад и с хода', hRocks: 'Камни: включи 4×4 и БЛОК. Не идёт — сдай назад и бери с хода', hStep: 'Уступ: сдай назад и бери с хода, с 4×4', hIdle: 'Качаешься на месте — только топливо жжёшь. Сдай назад и бери с хода',
    hAwd: 'Буксуешь? Включи 4×4', hLock: 'Не гребёт? Включи БЛОК', hLow: 'Закапываешься или мало тяги? Включи ПОНИЖ', hWinch: 'Держи ЛЕБЁДКУ — подтянет к дереву', hBack: 'Сдай назад и возьми с разгона', hHung: 'Сел брюхом. Назад и с разгона — или нужен клиренс: в гараж', hHungL: 'Сел брюхом. Сдай назад и бери с разгона, без ПОНИЖ', hHungF: 'Сел брюхом, но нос уже перевалил. Газу — сползёшь вперёд', crestRun: ' — бери с хода', hGar: 'Не проходит? Загляни в гараж: продолжишь с отметки',
    hFuel: 'Топлива мало: выключай лишнее на твёрдой дороге', hFuelLow: 'Топлива меньше четверти: не буксуй, ищи канистру', hFuelEnd: 'Топливо на исходе!',
    mech: 'Механик', ready: 'Грузовик готов к этому заказу', buyPart: 'Купить', fitPart: 'Поставить', needC: (part, n, have) => `Нужно: ${part} — ¤ ${n}, у тебя ¤ ${have}. Подзаработай на прошлых заказах`,
    why: { awd: 'без полного привода здесь встанешь в грязи и на подъёме', low: 'без пониженной крутой подъём не взять', lock: 'без блокировки в этой грязи колёса буксуют впустую', tires: 'на дорожных шинах из липкой грязи не выехать', tank: 'дорога длинная, одного бака может не хватить', winch: 'в торфе и болоте можно встать намертво — лебёдка вытянет к дереву' }, whyK: { clayUp: 'на универсальных шинах гружёным мокрую глину в гору не взять', screeUp: 'на универсальных шинах гружёным на осыпи в гору закопаешься', tip6: 'короткую раму с тремя мостами, гружёную бочками, на грязном склоне опрокидывает — нужна длинная' },
    hNew: { first: 'Вези дрова в деревню: держи ▶. Встал — ◀ назад и с разгона', awd: 'Новая кнопка 4×4 слева: включай в грязи и в гору. На твёрдой дороге выключай — жжёт топливо', lock: 'Новая кнопка БЛОК: включай только в грязи', low: 'Новая кнопка ПОНИЖ: для крутых подъёмов и вязкой грязи. Едет медленно, топлива жжёт больше' }, dFuel: 'Топливо кончилось', dWater: 'Мотор залило', dFlip: 'Перевернулся', cp: 'Отметка', can: (l) => `+${l} л топлива`,
    tWater: (d, f, fix) => `Здесь брод ${d} м, а этот грузовик берёт ${f} м. На скорости не проскочить: зальёт всё равно. ${fix ? 'Хватит одного: ' + fix + '.' : 'Нужен шноркель.'}`, deep: (d, f) => `Брод ${d} м глубже, чем берёт грузовик (${f} м)`, deepFix: 'Хватит одного', tWaterG: (d, f, fix) => `Брод ${d} м, а грузовик берёт ${f} м. ${fix ? 'Хватит одного: ' + fix + '.' : 'Нужен шноркель.'}`, hDeep: (d, f) => `Стой! Впереди брод ${d} м, грузовик берёт ${f} м. На скорости не проскочить — нужна другая сборка`, orW: 'или', wheelsW: 'колёса', tFuel: 'На твёрдой дороге выключай 4×4, БЛОК и ПОНИЖ — они жгут топливо. Или поставь в гараже бак побольше.', tSpin: (n, p) => `Буксовал ${n} с${p ? ' без кнопки ' + p : ''} — топливо ушло в грязь. Встал — ${p ? 'сразу включай ' + p + ', ' : ''}сдай назад и бери с разгона.`, nextC: 'Дальше', aOff: { low: 'Выключил ПОНИЖ: песок берут с разгона' }, dStuck: 'Завяз намертво', tStuck: (p) => `Колёса закопались — отсюда уже не выбраться, тягач вытащит к флажку. ${p ? 'В следующий раз включи ' + p + ' до грунта, а не в нём.' : 'Дальше бери с разгона или поставь в гараже шины под этот грунт.'}`, tSand: 'Песок засосал: с включённой ПОНИЖ не разогнаться. Перед песком выключай ПОНИЖ и бери с хода.', aOn: { awd: 'Включил 4×4 за тебя. В грязи и в гору держи его включённым', lock: 'Включил БЛОК за тебя. В вязкой грязи — с ним', low: 'Включил ПОНИЖ за тебя. В крутую гору — с ней' }, pre: { lowoff: 'Впереди песок — выключи ПОНИЖ и бери с разгона', awd: 'Впереди грязь — включи 4×4', lock: 'Впереди вязкая грязь — включи БЛОК', low: 'Впереди крутой подъём — включи ПОНИЖ' }, tFlip: 'На крутом подъёме помогает длинная база или 6×6. Лифт мешает.', retry: 'Ещё раз', warn: (d, f) => `Брод ${d} м — грузовик берёт ${f} м!`,
    win: 'Полигон пройден!', s1: 'Доехал', s2: 'Без возвратов', s3: 'Топлива ≥ 20%', time: 'Время', fuel: 'Топливо', again: 'Ещё раз', toGar: 'В гараж',
    keys: '→ газ   ← назад   ·   1 — 4×4   2 — блок   3 — пониж   ·   Пробел — лебёдка   ·   R — на отметку   ·   G — гараж', sec: 'с',
  }, en: {
    garage: 'Garage', go: 'Drive', cont: 'From checkpoint', anew: 'From start', intro: 'Build a truck for the proving ground. What helps in mud hurts on hills — and the fuel is shared.',
    p: { awd: 'All-wheel drive', lock: 'Diff lock', low: 'Low range', base: 'Wheelbase', lift: 'Lift', wheel: 'Size', axles: 'Axles', tires: 'Tires', eng: 'Engine tune', snorkel: 'Snorkel', tank: 'Tank', susp: 'Suspension', skid: 'Skid plate', press: 'Pressure', ctis: 'Inflation', gear: 'Final drive', winch: 'Winch', trailer: 'Trailer', paint: 'Paint' },
    tabs: ['Chassis', 'Wheels', 'Drive', 'Other'], soft: 'TIRES',
    cg: { log: 'Logs', barrel: 'Barrels', melon: 'Melons' }, cgN: { log: 'Plain cargo. The more you take, the harder mud and climbs get.', barrel: 'Heavy: the truck pulls worse in mud and uphill. They fly out on bumps at speed.', melon: 'Light and bouncy: take bumps slowly.' },
    pause: 'Paused', resume: 'Resume', towTo: 'Tow to the flag', towFree: 'Free tow', quit: 'Give up', noPay: 'No cargo delivered', opened: 'New contract', hTow: 'Stuck for good? ❚❚ — tow to the flag. Or give up and fit another part', lit: 'L', x2: 'Double', topUp: 'Top up', wt: 'weight', tn: 't',
    menu: 'Contracts', poly: 'Proving ground: try parts, no cargo', ver: 'build', perLog: 'each', lockedC: 'Deliver the previous contract first', logsN: 'Cargo', payL: 'Pay', fuelL: 'Fuel — 1 coin per litre, tow — 60', back: 'Back', tow: 'Tow', giveUp: 'Give up', toMenu: 'Contracts', buyFor: 'Buy for', lack: 'Short by', rDeliv: 'Delivered', rFuel: 'Fuel', rTotal: 'Total', cs: ['Delivered', 'Full load', 'No tow'], winC: 'Contract done!', logLost: 'Cargo fell off!', of: 'of',
    o: { awd: ['no', 'yes'], lock: ['no', 'yes'], low: ['no', 'yes'], base: ['short', 'long', 'long+'], lift: ['none', '+1', '+2'], wheel: ['small', 'medium', 'large'], axles: ['4×4', '6×6'], tires: ['road', 'all-terrain', 'mud'], eng: ['0', '1', '2', '3', '4', '5', '6', '7', '8'], trailer: ['none', 'cart', 'big'], snorkel: ['no', 'yes'], tank: ['60 L', '95 L'], susp: ['soft', 'medium', 'stiff'], skid: ['no', 'yes'], press: ['low', 'medium', 'high'], ctis: ['no', 'yes'], gear: ['pull', 'medium', 'speed'], winch: ['15 m', '21 m'] },
    n: {
      awd: ['Rear-wheel drive: cheap and thrifty, weak in mud and uphill.', 'All-wheel drive: the 4×4 button — every wheel pulls. Burns more fuel.'],
      lock: ['No diff lock: in mud one wheel per axle spins uselessly.', 'Diff lock: the LOCK button — both wheels of an axle dig in mud.'],
      low: ['No low range: steep climbs are out of reach.', 'Low range: the LOW button — more pull, less speed; no digging in.'],
      susp: ['Soft suspension: wheels stay on bumpy ground, but the truck squats on climbs.', 'Medium suspension.', 'Stiff suspension: lifts the nose less uphill, but wheels hang over bumps.'],
      skid: ['No skid plate: high-centered means stuck.', 'Skid plate: a steel sheet, the belly slides over crests and mud. Adds weight.'],
      press: ['Low pressure: a wider tire sinks less in sand and peat and bites better. Slower and thirstier on firm ground.', 'Medium pressure.', 'High pressure: fast and thrifty on firm ground, but cuts into soft soil.'],
      ctis: ['No inflation system: pressure is set in the garage for the whole trip.', 'Inflation system: the TIRES button airs down on the move — before sand and peat — and back up.'],
      gear: ['Pull gearing: pull +25%, speed −20%.', 'Medium gearing.', 'Speed gearing: speed +20%, pull −18% — struggles on climbs and in sticky mud.'],
      winch: ['Winch: 15 m cable. Engine-driven: it burns fuel and will not work on an empty tank.', 'Long-cable winch: 21 m and pulls faster. Burns fuel just the same.'],
      trailer: ['No trailer: you haul only what fits the bed.', 'Cart: +9 logs or 7 barrels, a 30 L spare tank. It hangs on the truck as dead weight: the stronger the engine, the fuller you load it.', 'Big trailer: +19 logs or 15 barrels, a 50 L spare tank. Driven axles — they dig in while all-wheel drive is on. Each tune stage from 5 adds two more barrels.'],
      paint: ['Paint: no effect on off-road ability, but it looks good.'],
      base: ['Short wheelbase: rolls over crests, but lifts its nose on steep climbs. It cannot take a trailer.', 'Long wheelbase: carries more, steady uphill. Heavier in mud. Take crests at speed — go slow and it high-centers.', 'Extra long: carries the most. Heavy — a full load needs engine tuning. Crests at speed only.'],
      lift: ['No lift: stable, but low belly and shallow fording.', 'Lift +1: belly and fording depth 17 cm higher.', 'Lift +2: higher still — but tips over on the steepest climb.'],
      wheel: ['Small wheels: all the pull reaches the ground, but they sink in mud.', 'Medium: sink less, ford deeper; less pull uphill.', 'Large: barely sink, but need a bigger engine uphill and burn fuel.'],
      axles: ['4×4: lighter and thriftier.', '6×6: three axles dig in, it never rears up and carries more — most of all on a long frame. Only a 6×6 can pull a trailer. Heavier and thirstier.'],
      tires: ['Road tires: faster and thriftier, slippery in mud.', 'All-terrain tires: the middle ground.', 'Mud tires: bite in mud; slower on firm ground, thirstier.'],
      eng: [0, 1, 2, 3, 4, 5, 6, 7, 8].map((v) => (v ? `Tune ${v} of 8: pull +${12 * Math.min(v, 5) + 7 * Math.max(0, v - 5)}%, carries ${Math.round(10 * M.ENG_T(v)) / 10} t more, fuel use +${6 * v}%.${v >= 6 ? ' A short frame rears up on climbs — go long.' : ''}` : 'Stock engine: thrifty, but weak with a heavy load uphill and in mud.')),
      snorkel: ['No snorkel: water above the hood stalls the engine.', 'Snorkel: air comes from the roof, deep fords are fine.'],
      tank: ['60 L tank.', '95 L tank: more range, a bit heavier.'],
    },
    sClear: 'Clearance', sFord: 'Fords up to', sPull: 'Pull', sRange: 'Range', sLoad: 'Carries', tapBuy: 'Tap the green button again to buy.', tapAd: (n) => `Short by ${n} coins: tap the yellow button to top up with an ad.`, tapNo: (n) => `Short by ${n} coins — earn more on contracts.`, trNeed: 'A trailer needs a long frame with three axles: a short frame rears up, and a 4×4 bogs down in sticky mud. Chassis tab first — long frame and 6×6.', gain: (a, b) => `Full run: ${a} → ${b} ¤ (${b > a ? '+' : '−'}${Math.abs(b - a)}).`, gainLoss: 'With this engine the trailer costs more payload than it adds.', gainSpace: 'No extra earnings: the bed is already full — get a bigger trailer.', gainWeight: 'No extra earnings: the load is capped by weight — tune the engine.', gainAx: 'Earns nothing by itself — but it lets you hitch a trailer.', mx: 'max', m: 'm', over: (t) => `That is all it can carry: payload ${t} t. Tune the engine, lengthen the frame or fit 6×6.`,
    awd: '4×4', lock: 'LOCK', low: 'LOW', winch: 'WINCH', ahead: 'Ahead', soil: { shallow: 'shallow mud', soft: 'soft mud', medium: 'mud', sticky: 'sticky mud', swamp: 'swamp', sand: 'sand', clay: 'clay', peat: 'peat', scree: 'scree' }, crest: 'crest', ford: 'ford', climb: 'climb', descent: 'descent', rocks: 'rocks', stepW: 'ledge', upW: 'uphill', downW: 'downhill', upTo: 'up to',
    hClog: 'Tires clogged: on firm ground speed up in high range to shed it. Or wash them in a ford', hSand: 'Sand: don\'t spin. Back up along your track and take a run — or air down', hSandLow: 'Sand: turn LOW off — you can\'t build speed with it. Back up along your track and take a run', wNone: 'Nothing to hook the winch to here: it only pulls to a marked tree', wFar: (m) => `Winch: get closer to the marked tree — the cable is ${m} m`, goAny: 'Go anyway', adNo: 'The video didn\'t load right now — try again a bit later', minC: (n) => `min ${n}`, whyCap: (n, c) => `this order starts at ${n}, your truck takes only ${c}`, goCap: (n) => `Need ${n}+`, rent: (p) => `Video: ${p} for one run`, hScree: 'Scree: don\'t spin — you dig in. Back up and take a run', hScreeSoft: 'Scree: don\'t spin — you dig in. Air down, or back up and take a run', hRocks: 'Rocks: use 4×4 and LOCK. No go — back up and take a run', hStep: 'Ledge: back up and take a run, with 4×4', hIdle: 'Rocking in place only burns fuel. Back up and take a run',
    hAwd: 'Wheels spinning? Switch on 4×4', hLock: 'No bite? Switch on LOCK', hLow: 'Digging in or no pull? Switch on LOW', hWinch: 'Hold WINCH — it pulls you to the tree', hBack: 'Back up and take a run at it', hHung: 'High-centered. Back up and take a run — or get more clearance in the garage', hHungL: 'High-centered. Back up and take a run at it, LOW off', hHungF: 'High-centered, but the nose is over. Gas — you will slide forward', crestRun: ' — take it at speed', hGar: 'No way through? Visit the garage: you continue from the checkpoint',
    hFuel: 'Low fuel: switch helpers off on firm road', hFuelLow: 'Under a quarter tank: no wheelspin, look for a jerry can', hFuelEnd: 'Fuel almost gone!',
    mech: 'Mechanic', ready: 'The truck is ready for this contract', buyPart: 'Buy', fitPart: 'Fit', needC: (part, n, have) => `You need: ${part} — ¤ ${n}, you have ¤ ${have}. Earn more on earlier contracts`,
    why: { awd: 'without all-wheel drive you will stall in mud and on the climb', low: 'without low range the steep climb is out of reach', lock: 'without the diff lock the wheels just spin in this mud', tires: 'road tires will not get out of sticky mud', tank: 'the road is long, one tank may not be enough', winch: 'in peat and swamp you can get stuck for good — the winch pulls you to a tree' }, whyK: { clayUp: 'universal tires will not take a loaded truck up wet clay', screeUp: 'on universal tires a loaded truck digs into the scree climb', tip6: 'a short three-axle frame loaded with barrels tips over on a muddy climb — fit the long frame' },
    hNew: { first: 'Haul the firewood to the village: hold ▶. Stuck — ◀ back up and take a run', awd: 'New 4×4 button on the left: use it in mud and uphill. Off on firm road — it burns fuel', lock: 'New LOCK button: use it only in mud', low: 'New LOW button: for steep climbs and deep mud. Slow, and burns more fuel' }, dFuel: 'Out of fuel', dWater: 'Engine flooded', dFlip: 'Rolled over', cp: 'Checkpoint', can: (l) => `+${l} L of fuel`,
    tWater: (d, f, fix) => `This ford is ${d} m deep and this truck can take ${f} m. Speed will not help: it floods anyway. ${fix ? 'Any one of these is enough: ' + fix + '.' : 'You need a snorkel.'}`, deep: (d, f) => `The ${d} m ford is deeper than the truck can take (${f} m)`, deepFix: 'Any one is enough', tWaterG: (d, f, fix) => `The ford is ${d} m, the truck takes ${f} m. ${fix ? 'Any one is enough: ' + fix + '.' : 'You need a snorkel.'}`, hDeep: (d, f) => `Stop! A ${d} m ford ahead, the truck takes ${f} m. Speed will not help — change the build`, orW: 'or', wheelsW: 'wheels', tFuel: 'On firm road switch off 4×4, LOCK and LOW — they burn fuel. Or fit a bigger tank in the garage.', tSpin: (n, p) => `You spun the wheels for ${n} s${p ? ' without ' + p : ''} — the fuel went into the mud. Stuck? ${p ? 'Switch on ' + p + ' right away, ' : ''}back up and take a run.`, nextC: 'Next', aOff: { low: 'Switched LOW off: sand is taken with a run' }, dStuck: 'Stuck for good', tStuck: (p) => `The wheels dug in, there is no way out from here, the tow truck will pull you to the flag. ${p ? 'Next time switch on ' + p + ' before this ground, not in it.' : 'Next time take it with a run, or fit tires for this ground in the garage.'}`, tSand: 'The sand swallowed you: with LOW on the truck cannot build speed. Switch LOW off before sand and take it with a run.', aOn: { awd: 'Switched 4×4 on for you. Keep it on in mud and uphill', lock: 'Switched LOCK on for you. Use it in sticky mud', low: 'Switched LOW on for you. Use it on steep climbs' }, pre: { lowoff: 'Sand ahead — switch LOW off and take it with a run', awd: 'Mud ahead — switch on 4×4', lock: 'Sticky mud ahead — switch on LOCK', low: 'Steep climb ahead — switch on LOW' }, tFlip: 'On steep climbs a long wheelbase or 6×6 helps. Lift hurts.', retry: 'Try again', warn: (d, f) => `Ford ${d} m — the truck takes ${f} m!`,
    win: 'Proving ground cleared!', s1: 'Finished', s2: 'No returns', s3: 'Fuel ≥ 20%', time: 'Time', fuel: 'Fuel', again: 'Again', toGar: 'Garage',
    keys: '→ gas   ← reverse   ·   1 — 4×4   2 — lock   3 — low   ·   Space — winch   ·   R — checkpoint   ·   G — garage', sec: 's',
  } };
  const LANGS = ['ru', 'en', 'es', 'pt', 'tr', 'de', 'fr', 'it', 'pl', 'id'];
  const pickLang = (code) => { const c = String(code || '').toLowerCase().slice(0, 2); return LANGS.includes(c) ? c : ['uk', 'be', 'kk'].includes(c) ? 'ru' : 'en'; };
  const qLang = (location.search.match(/[?&](ru|en|es|pt|tr|de|fr|it|pl|id)\b/) || [])[1];
  let LANG = 'en', RU = false, T = TX.en;
  function setLang(code) {
    LANG = pickLang(code); RU = LANG === 'ru'; const X = (window.MUD_TXT || {})[LANG];
    if (LANG === 'ru' || LANG === 'en' || !X) { T = TX[LANG] || TX.en; if (!TX[LANG]) LANG = 'en'; RU = LANG === 'ru'; return; }
    const E = TX.en, out = Object.assign({}, E); for (const k of Object.keys(X)) { const v = X[k], e = E[k]; out[k] = v && e && typeof v === 'object' && !Array.isArray(v) && typeof e === 'object' && !Array.isArray(e) ? Object.assign({}, e, v) : v; } T = out;
    try { if (typeof note !== 'undefined' && note && (note === TX.en.intro || note === TX.ru.intro)) note = T.intro; } catch (e) { /* */ }
  }
  const BOOT = window.PG_BOOT || null; // сборка для площадки: мост уже запущен загрузчиком, язык и сохранение пришли от него
  setLang(qLang || (BOOT ? BOOT.lang || 'en' : navigator.language || 'en'));
  const NMS = () => (T.nm || null), cName = (c) => { const n = NMS(); return (n && n.c && n.c[c.id]) || c.name[RU ? 1 : 0]; }, rName = (k) => { const n = NMS(); return (n && n.r && n.r[k]) || M.REGIONS[k].name[RU ? 1 : 0]; }; // названия заказов и районов на языке игрока
  const PARTS = [['base', [0, 1, 2], 0], ['lift', [0, 1, 2], 0], ['axles', [2, 3], 0], ['susp', [0, 1, 2], 0], ['skid', [0, 1], 0], ['wheel', [0, 1, 2], 1], ['tires', [0, 1, 2], 1], ['press', [0, 1, 2], 1], ['ctis', [0, 1], 1], ['awd', [0, 1], 2], ['lock', [0, 1], 2], ['low', [0, 1], 2], ['eng', [0, 1, 2, 3, 4, 5, 6, 7, 8], 2], ['gear', [0, 1, 2], 2], ['tank', [0, 1], 3], ['snorkel', [0, 1], 3], ['winch', [0, 1], 3], ['trailer', [0, 1, 2], 3], ['paint', [0, 1, 2, 3, 4, 5], 3]];
  // цены в заказах (на полигоне всё бесплатно); настройки — давление, подвеска, главная пара — бесплатны всегда
  const PRICE = { awd: [0, 150], low: [0, 200], lock: [0, 220], tires: [0, 100, 450], wheel: [0, 400, 1500], lift: [0, 250, 900], base: [0, 600, 2000], axles: [0, 3000], skid: [0, 200], ctis: [0, 900], eng: [0, 150, 350, 800, 1400, 2400, 4000, 6500, 10000], tank: [0, 250], snorkel: [0, 300], winch: [0, 250], trailer: [0, 4000, 9000], paint: [0, 0, 100, 100, 100, 100] }, TOW = 60;
  const START = Object.assign({}, M.DEF, { awd: 0, lock: 0, low: 0, tires: 0 });
  const PAINTS = [['#ff5a36', '#c63b1f'], ['#fbc02d', '#c49000'], ['#43a047', '#2e7d32'], ['#1e88e5', '#1565c0'], ['#eceff1', '#b0bec5'], ['#7c8b3a', '#5a6628']];
  const SOILC = { mud: '#4a2f1c', sand: '#d9b25c', clay: '#8e3f1f', peat: '#1f1812', scree: '#8f8f86' };
  let W = 0, H2 = 0, DPR = 1;
  function resize() { DPR = Math.min(2, window.devicePixelRatio || 1); W = innerWidth; H2 = innerHeight; cv.width = W * DPR; cv.height = H2 * DPR; }
  addEventListener('resize', resize); resize();
  const use3d = !!(R3 && R3.init(glc));
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const rr = (x, y, w, h, r) => { ctx.beginPath(); if (!(w > 0 && h > 0)) return; r = Math.max(0, Math.min(r, w / 2, h / 2)); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); };
  let fpx = 16;
  const font = (px, w = 900) => { fpx = px; ctx.font = `${w} ${px}px system-ui, sans-serif`; };
  // значки рисуются сами, а не эмодзи: эмодзи есть не на всех телефонах, и площадки не принимают эмодзи вместо значков. В строке значок — один символ из ICON_RE
  const ICON_RE = /(¤|🔧|⛽|⚓|🚜|🔒|⚠|🔇|🔊)/u;
  function icon(ch, x, y, s) {
    const col = ctx.fillStyle; ctx.save(); ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = col; ctx.lineWidth = Math.max(1.5, s * 0.15);
    const L = (pts) => { ctx.beginPath(); pts.forEach(([a, b], i) => (i ? ctx.lineTo(x + a * s, y + b * s) : ctx.moveTo(x + a * s, y + b * s))); ctx.stroke(); };
    if (ch === '¤') { for (const [c, q] of [['#f9a825', 1], ['#ffe082', 0.6]]) { ctx.fillStyle = c; ctx.beginPath(); ctx.arc(x, y - s * 0.04, s * 0.44 * q, 0, 7); ctx.fill(); } }
    else if (ch === '🔧') { L([[-0.36, 0.36], [0.08, -0.08]]); ctx.beginPath(); ctx.arc(x + 0.2 * s, y - 0.2 * s, 0.19 * s, 0.6, 5.2); ctx.stroke(); }
    else if (ch === '⛽') { rr(x - 0.3 * s, y - 0.24 * s, 0.52 * s, 0.66 * s, 0.08 * s); ctx.fill(); L([[-0.14, -0.24], [0.02, -0.42], [0.22, -0.42]]); ctx.fillStyle = 'rgba(0,0,0,0.35)'; ctx.fillRect(x - 0.18 * s, y - 0.08 * s, 0.28 * s, 0.08 * s); }
    else if (ch === '⚓') { ctx.beginPath(); ctx.arc(x, y - 0.36 * s, 0.1 * s, 0, 7); ctx.stroke(); ctx.beginPath(); ctx.moveTo(x, y - 0.26 * s); ctx.lineTo(x, y + 0.14 * s); ctx.arc(x - 0.17 * s, y + 0.14 * s, 0.17 * s, 0, Math.PI); ctx.lineTo(x - 0.24 * s, y + 0.0 * s); ctx.stroke(); } // крюк: кольцо, стержень, загиб с жалом
    else if (ch === '🚜') { rr(x - 0.46 * s, y - 0.12 * s, 0.6 * s, 0.3 * s, 0.05 * s); ctx.fill(); rr(x + 0.06 * s, y - 0.34 * s, 0.32 * s, 0.52 * s, 0.06 * s); ctx.fill(); L([[-0.46, -0.12], [-0.3, -0.4]]); ctx.fillStyle = col; for (const a of [-0.28, 0.24]) { ctx.beginPath(); ctx.arc(x + a * s, y + 0.26 * s, 0.13 * s, 0, 7); ctx.fill(); } }
    else if (ch === '🔒') { ctx.beginPath(); ctx.arc(x, y - 0.1 * s, 0.2 * s, Math.PI, 0); ctx.stroke(); rr(x - 0.3 * s, y - 0.1 * s, 0.6 * s, 0.48 * s, 0.07 * s); ctx.fill(); }
    else if (ch === '⚠') { ctx.fillStyle = '#ffd54f'; ctx.beginPath(); ctx.moveTo(x, y - 0.44 * s); ctx.lineTo(x + 0.46 * s, y + 0.38 * s); ctx.lineTo(x - 0.46 * s, y + 0.38 * s); ctx.closePath(); ctx.fill(); ctx.strokeStyle = '#3e2723'; ctx.lineWidth = Math.max(1.5, s * 0.11); L([[0, -0.16], [0, 0.1]]); ctx.fillStyle = '#3e2723'; ctx.beginPath(); ctx.arc(x, y + 0.24 * s, 0.06 * s, 0, 7); ctx.fill(); }
    else if (ch === '🔇' || ch === '🔊') { ctx.beginPath(); ctx.moveTo(x - 0.42 * s, y - 0.14 * s); ctx.lineTo(x - 0.24 * s, y - 0.14 * s); ctx.lineTo(x, y - 0.38 * s); ctx.lineTo(x, y + 0.38 * s); ctx.lineTo(x - 0.24 * s, y + 0.14 * s); ctx.lineTo(x - 0.42 * s, y + 0.14 * s); ctx.closePath(); ctx.fill();
      if (ch === '🔊') for (const r of [0.2, 0.36]) { ctx.beginPath(); ctx.arc(x + 0.06 * s, y, r * s, -0.9, 0.9); ctx.stroke(); } else { L([[0.14, -0.16], [0.44, 0.16]]); L([[0.14, 0.16], [0.44, -0.16]]); } }
    ctx.restore();
  }
  function fillC(t, x, y, mw) {
    const ps = String(t).split(ICON_RE); if (ps.length < 2) { ctx.fillText(t, x, y, mw); return; }
    const s = fpx * 0.95, gap = fpx * 0.22, qs = ps.map((q, i) => (i % 2 ? q : i ? q.replace(/^ /, '') : q)), ws = qs.map((q, i) => (i % 2 ? s + (qs[i + 1] ? gap : 0) : ctx.measureText(q).width)), tot = ws.reduce((a, b) => a + b, 0);
    const k = mw && tot > mw ? mw / tot : 1, al = ctx.textAlign; let cx = al === 'center' ? x - (tot * k) / 2 : al === 'right' ? x - tot * k : x; ctx.textAlign = 'left';
    qs.forEach((q, i) => { if (i % 2) icon(q, cx + (s * k) / 2, y, s * k); else if (q) ctx.fillText(q, cx, y, ws[i] * k + 1); cx += ws[i] * k; });
    ctx.textAlign = al;
  }
  function cargoIcon(kind, x, y, r) {
    const disc = (c, q) => { ctx.fillStyle = c; ctx.beginPath(); ctx.arc(x, y, r * q, 0, 7); ctx.fill(); };
    if (kind === 'melon') { disc('#43a047', 1); ctx.strokeStyle = '#1b5e20'; ctx.lineWidth = r * 0.2; for (const q of [0.12, 0.55]) { ctx.beginPath(); ctx.ellipse(x, y, r * q, r * 0.9, 0, 0, 7); ctx.stroke(); } }
    else if (kind === 'barrel') { disc('#1565c0', 1); ctx.strokeStyle = '#bbdefb'; ctx.lineWidth = r * 0.16; ctx.beginPath(); ctx.arc(x, y, r * 0.64, 0, 7); ctx.stroke(); ctx.fillStyle = '#eceff1'; ctx.beginPath(); ctx.arc(x + r * 0.28, y - r * 0.22, r * 0.17, 0, 7); ctx.fill(); }
    else { disc('#7b5a3a', 1); disc('#e0c08f', 0.78); ctx.strokeStyle = '#a1887f'; ctx.lineWidth = r * 0.13; ctx.beginPath(); ctx.arc(x, y, r * 0.42, 0, 7); ctx.stroke(); }
  }
  // реклама за награду: на площадке сюда встанет её показ; в пробе награда выдаётся сразу
  // ---------- площадка (Playgama Bridge): язык, пауза, звук, реклама, облачное сохранение, отметки ----------
  // Без моста (страница для показа, артефакт) реклама — заглушка: награда сразу, межстраничной нет, отметки никуда не уходят.
  const PG = { on: false, rew: false, inter: false, ad: false, paused: false, mutedP: false, ready: false, t0: performance.now(), lastInter: -1e9, lastRew: -1e9, pend: null, got: false };
  const pgNow = () => performance.now() / 1000;
  const pgMsg = (m, d) => { if (!PG.on) return; try { window.bridge.platform.sendMessage(m, d); } catch (e) { /* */ } };
  const pgEv = (name, data) => { if (!PG.on) return; try { window.bridge.analytics.send(name, data); } catch (e) { /* */ } };
  const canAd = () => !PG.on || PG.rew; // кнопки «за ролик» — только если площадка умеет показать ролик (без моста — заглушка для показа)
  function pgDone(v) { const q = PG.pend; PG.pend = null; PG.ad = false; if (q) { clearTimeout(q.tm); q.cb(v); } }
  // межстраничная: только когда игрок уходит с экрана итога заказа; первая — не раньше 4 минут от запуска, дальше не чаще раза в 3 минуты,
  // полторы минуты тишины после ролика за награду, и никогда — после первых прохождений обучающих заказов (опыт Hook Truck, 26.11.2026)
  function pgCanInter() { return PG.on && PG.inter && !PG.pend; } // межстраничную зовём на каждой паузе, а когда её показать — решает мост площадки (правило Playgama: своих таймеров нет)
  function pgInter(cb) { PG.lastInter = pgNow(); PG.pend = { type: 'inter', cb, t0: performance.now(), tm: setTimeout(() => pgDone(false), 45000) }; const pd = PG.pend; setTimeout(() => { if (PG.pend === pd && !pd.seen) pgDone(false); }, 1500); setTimeout(() => { if (PG.pend === pd && !PG.ad) pgDone(false); }, 4000); try { window.bridge.advertisement.showInterstitial('contract_end'); } catch (e) { pgDone(false); } }
  const adBusy = () => { try { const A = window.bridge.advertisement, r = A.rewardedState, i = A.interstitialState; return ['loading', 'opened', 'rewarded'].includes(r) ? 'rew:' + r : ['loading', 'opened'].includes(i) ? 'inter:' + i : ''; } catch (e) { return ''; } };
  let adMsg = null; const adNote = (s) => { adMsg = { s, t: realT }; if (mode === 'play') toast = { s, t: realT, long: true, bad: true }; sfx('no'); }; // ролик не пришёл — игрок должен понять, что кнопка нажалась
  function pgRewarded(place, cb) {
    if (!PG.on) return cb(true); if (!PG.rew) return cb(false);
    const bs = adBusy(); if (PG.pend || bs) { adNote(T.adNo); pgEv('ad_request', { place, result: 'busy', state: bs || (PG.pend && PG.pend.type) }); return cb(false); } // мост молча пропускает ролик, пока не закончилась прошлая реклама
    PG.got = false; const pd = (PG.pend = { type: 'rew', cb, place, t0: performance.now(), tm: setTimeout(() => pgDone(PG.got), 90000) });
    setTimeout(() => { if (PG.pend === pd && !PG.ad) { pd.slow = true; adNote(T.adNo); pgEv('ad_request', { place, result: 'timeout' }); } }, 7000);
    try { window.bridge.advertisement.showRewarded(place); } catch (e) { pgDone(false); }
  }
  const adReward = (cb, place = 'reward') => pgRewarded(place, (ok) => { if (ok) cb(); }); // награда — только после «досмотрел»
  // отметки: шаг — заказ C01…C18; что игра сделала за игрока (assists) и где он застрял — то, чего мост сам не знает
  const TM = { t0: 0, deaths: 0, holds: 0, live: false };
  const stepOf = (i) => ({ step_id: 'C' + String(i + 1).padStart(2, '0'), step_index: i + 1 });
  const runData = (extra) => { const L = S.L, x0 = L.polys[0][0][0] + 320, b = S.cfg.b; return Object.assign(stepOf(Math.max(0, cur)), { x_m: Math.round(S.truck.x / PX), progress: Math.round(100 * clamp((S.truck.x - x0) / (L.fin - x0), 0, 1)), deaths: TM.deaths, duration_sec: Math.round((performance.now() - TM.t0) / 1000), assists: asst, holds: TM.holds, base: b.base, eng: b.eng, axles: b.axles, trailer: b.trailer || 0, build_version: VER }, extra); };
  const runQuit = (how) => { if (TM.live && career && S && S.state !== 'win' && mode === 'play') pgEv('progression_failed', runData({ how, reason: S.state === 'dead' ? S.why : '' })); TM.live = false; };
  const PS = { t0: 0, act: 0, ft: [], gap: true };
  function perfSample(now, ms, live) { // замер кадров по образцу Playgama: раз в ~30 с активной езды
    if (!live) { PS.gap = true; return; } if (PS.gap) { PS.gap = false; if (!PS.t0) PS.t0 = now; return; }
    if (!(ms > 0)) return; PS.ft.push(ms); PS.act += ms; if (PS.act < 30000) return;
    const a = PS.ft.sort((x, y) => x - y), n = a.length, q = (k) => a[Math.min(n - 1, Math.floor(k * n))], over = (lim) => { let c = 0; for (let i = n - 1; i >= 0 && a[i] > lim; i--) c++; return c; }, r1 = (v) => Math.round(v * 10) / 10;
    pgEv('performance_sample', { target_fps: 60, window_ms: Math.round(now - PS.t0), active_ms: Math.round(PS.act), frame_count: n, fps_avg: r1((1000 * n) / PS.act), fps_p10: r1(1000 / q(0.9)), frame_time_p50_ms: r1(q(0.5)), frame_time_p95_ms: r1(q(0.95)), frame_time_p99_ms: r1(q(0.99)), frame_time_max_ms: r1(a[n - 1]),
      frames_over_50ms: over(50), frames_over_100ms: over(100), frames_over_250ms: over(250), frames_over_500ms: over(500), frames_over_1000ms: over(1000), build_version: VER, quality: 1, dpr: DPR, step_id: cur >= 0 ? stepOf(cur).step_id : '' });
    PS.t0 = now; PS.act = 0; PS.ft = [];
  }
  const fmt = (v, d = 1) => (LANG !== 'en' ? v.toFixed(d).replace('.', ',') : v.toFixed(d)); // десятичная запятая везде, кроме английского

  // ---------- состояние ----------
  let build = Object.assign({}, M.DEF);
  if (!BOOT) try { const q = JSON.parse(localStorage.getItem('mud3.build') || 'null'); if (q) for (const [k, vals] of PARTS) if (vals.includes(q[k])) build[k] = q[k]; } catch (e) { /* */ }
  // заказы: монеты, купленные детали, собранный грузовик, звёзды
  let save = { coins: 0, own: {}, build: Object.assign({}, START), stars: {} };
  try { const q = BOOT ? (typeof BOOT.save === 'string' ? JSON.parse(BOOT.save) : BOOT.save) : JSON.parse(localStorage.getItem('mud4.save') || 'null'); if (q && q.build) { save = Object.assign(save, q); save.build = Object.assign({}, START, q.build); } } catch (e) { /* */ }
  const persist = () => { save.ts = Date.now(); const js = JSON.stringify(save); if (!BOOT) try { localStorage.setItem('mud4.save', js); localStorage.setItem('mud3.build', JSON.stringify(build)); } catch (e) { /* */ } if (PG.on || (BOOT && BOOT.ok)) { try { window.bridge.storage.set('mud4.save', js).catch(() => {}); } catch (e) { /* */ } } };
  let newKey = '', fuelLvl = 2, idleT = 0, idleX = -1e9, coach = '', asst = 0, spinT = 0, spinNeed = '', hold = '', holdT = 0, preEdge = false, ak = {}, preSg = null, trapX = -1e9, trapT = 0, stuckSand = false; // подсказка про только что купленную кнопку; ступень предупреждения о топливе
  let career = true, cur = -1, sel = -1, reg = 0, nlogs = 4, pend = null, res = null, lvlKey = 1, paused = false, adTow = 0, lostT = -9; let shownNote = '';
  const kindOf = (i) => (career && i >= 0 ? M.CONTRACTS[i].cargo : 'log'), capNow = () => M.capOf(M.spec(EB()), kindOf(Math.max(0, sel))), minOf = (i) => (career && i >= 0 && M.CONTRACTS[i].min) || 1;
  const optIdx = (k, v) => PARTS.find((q) => q[0] === k)[1].indexOf(v), priceOf = (k, v) => (PRICE[k] ? PRICE[k][optIdx(k, v)] : 0);
  let rent = null; const EB = () => (rent && rent.sel === sel ? Object.assign({}, save.build, { [rent.k]: rent.v }) : save.build); // деталь на один рейс за ролик: в сохранение не пишется
  const owns = (k, v) => !career || !priceOf(k, v) || START[k] === v || (save.own[k] || []).includes(v), BD = () => (career ? EB() : build);
  // обучение: первые четыре заказа ведут за руку — полный кузов, одна покупка, кнопка «дальше»; переключатель учится, пока игрок ни разу не включил его сам
  const GUIDE_N = 4, guided = (i) => career && i >= 0 && i < GUIDE_N && !(save.stars[M.CONTRACTS[i].id] > 0), learning = (k) => career && !((save.tl || {})[k] >= 2); // учится, пока дважды не довёз заказ, где кнопка нужна, без помощи игры с ней
  const defLoad = (i) => (guided(i) || M.CONTRACTS[i].big ? capNow() : Math.ceil(capNow() / 2)); // в первых заказах сразу полный кузов: иначе на следующую деталь не хватает и приходится повторять рейс
  const ALL = /[?&]all\b/.test(location.search), unlocked = (i) => ALL || i === 0 || (save.stars[M.CONTRACTS[i].after || M.CONTRACTS[i - 1].id] || 0) > 0; // большой заказ открывается после своего заказа района, а не по порядку // ?all в адресе — все заказы открыты (для показа новых трасс; сохранение не трогает)
  const bestRun = (bd) => { const C = M.spec(bd); let best = 0, kind = 'log'; M.CONTRACTS.forEach((c, i) => { const cp = M.capOf(C, c.cargo), g = unlocked(i) && cp >= (c.min || 1) ? cp * c.pay : 0; if (g > best) { best = g; kind = c.cargo; } }); return [best, kind, C]; };
  const GAINK = ['base', 'axles', 'eng', 'trailer'];
  function gainNote(k, v) { // примеряешь раму, мосты, мотор или прицеп — видно, сколько монет это прибавит к полному рейсу, или почему не прибавит
    if (!career || GAINK.indexOf(k) < 0) return '';
    const a = bestRun(save.build)[0], [b, kind, C] = bestRun(Object.assign({}, save.build, { [k]: v }));
    if (b > a) return T.gain(a, b); if (b < a) return T.gain(a, b) + (k === 'trailer' ? ' ' + T.gainLoss : '');
    if (k === 'axles' && v === 3 && !C.tr) return T.gainAx;
    return M.spaceOf(C, kind) * M.CARGO[kind].m <= M.payT(C) + 1e-6 ? T.gainSpace : T.gainWeight;
  }
  const regOf = () => { const n = M.CONTRACTS.findIndex((c) => !(save.stars[c.id] > 0)), k = n < 0 ? M.CONTRACTS.length - 1 : n; return Math.max(0, M.REGIONS.findIndex((r) => k >= r.from && k < r.from + r.n)); }; // район следующего недовезённого заказа
  let S = null, SV = null, mode = 'menu', resume = null, rebuilds = 0, note = T.intro, buildKey = 1, tab = 0;
  const sw = { awd: false, lock: false, low: false, soft: false }, keys = {}, ptrs = new Map(), dbg = { freeze: false };
  let realT = 0, last = performance.now(), acc = 0, camX = 0, camY = 0, Z = 0.5, buttons = [], toast = null, muted = false;
  function newSim() {
    const ri = career ? Math.max(0, cur >= 0 ? cur : sel) : -1, bd = Object.assign({}, BD(), (mode === 'garage' || mode === 'menu') && pend ? { [pend.k]: pend.v } : null); // в гараже некупленную деталь видно на грузовике — примерка
    S = M.create(ri >= 0 ? M.CONTRACTS[ri].build : 0, { build: bd, manual: true, kind: kindOf(ri), cargo: career ? nlogs : 0 }); buildKey++; lvlKey = ri + 2;
    // для картинки земля в грязи рисуется по твёрдому дну — сверху лежит живая грязь, которую продавливают колёса
    const L = S.L, xs = new Set(L.polys[0].map((q) => q[0])); for (const z of L.mud) { for (let x = z.x0; x <= z.x1; x += 45) xs.add(x); xs.add(z.x1); }
    SV = Object.create(S); SV.L = Object.assign({}, L, { polys: [[...xs].sort((a, b) => a - b).map((x) => [x, S.bedAt(x)])] });
  }
  function fordFix(dpx) {
    const bd = BD(), ok = (k, v) => v > bd[k] && M.spec(Object.assign({}, bd, { [k]: v })).ford >= dpx, out = [], lf = [1, 2].find((v) => ok('lift', v)), wh = [1, 2].find((v) => ok('wheel', v));
    if (lf) out.push([`${T.p.lift.toLowerCase()} ${T.o.lift[lf]}`, 'lift', lf]); if (wh) out.push([RU || T.nounFirst ? `${T.wheelsW} ${T.o.wheel[wh]}` : `${T.o.wheel[wh]} ${T.wheelsW}`, 'wheel', wh]); if (ok('snorkel', 1)) out.push([T.p.snorkel.toLowerCase(), 'snorkel', 1]);
    return out;
  }
  const fixText = (fx) => (fx.length > 1 ? fx.slice(0, -1).map((q) => q[0]).join(', ') + ' ' + T.orW + ' ' + fx[fx.length - 1][0] : fx.length ? fx[0][0] : '');
  // совет механика: первая деталь, без которой выбранный заказ не проехать, — чтобы новичку не разбираться во всём гараже
  const partName = (k, v) => { const vals = PARTS.find((q) => q[0] === k)[1]; return vals.length === 2 ? T.p[k] : `${T.p[k]} ${T.o[k][vals.indexOf(v)]}`; };
  function capAdvice(c, bd) { // большой заказ: самый дешёвый путь к нужной вместимости — рама, мосты, прицеп, мотор; механик называет первый шаг
    if (!c.min) return null; const cap0 = M.capOf(M.spec(bd), c.cargo); if (cap0 >= c.min) return null; let best = null;
    const cost = (k, v) => (v === bd[k] || owns(k, v) ? 0 : priceOf(k, v));
    for (let base = bd.base; base <= 2; base++) for (const axles of bd.axles === 3 ? [3] : [2, 3]) for (let trailer = bd.trailer; trailer <= 2; trailer++) for (let eng = bd.eng; eng <= 8; eng++) {
      if (trailer && !(base && axles === 3)) continue; const b2 = Object.assign({}, bd, { base, axles, trailer, eng }); if (M.capOf(M.spec(b2), c.cargo) < c.min) continue;
      let pr = cost('base', base) + cost('axles', axles) + cost('trailer', trailer); for (let e = bd.eng + 1; e <= eng; e++) pr += owns('eng', e) ? 0 : priceOf('eng', e); if (!best || pr < best.pr) best = { pr, b2 }; }
    const b2 = best ? best.b2 : Object.assign({}, bd, { base: 2, axles: 3, trailer: 2, eng: 8 }), k = ['base', 'axles', 'trailer'].find((q) => b2[q] !== bd[q]) || 'eng', v = k === 'eng' ? Math.min(8, bd.eng + 1) : b2[k];
    return { k, v, price: priceOf(k, v), own: owns(k, v), opt: false, cap: true, why: T.whyCap(c.min, cap0) };
  }
  function advice() {
    const i = sel >= 0 ? sel : cur; if (!career || i < 0) return null; const bd = EB(), ca = capAdvice(M.CONTRACTS[i], bd); if (ca) return ca;
    for (const [k, v, kind] of M.CONTRACTS[i].need || []) {
      if (bd[k] >= v || (kind === 'tip6' && bd.axles !== 3)) continue; const df = kind === 'ford' ? deepFord() : null; if (kind === 'ford' && !df) continue; // tip6: длинная рама нужна только трёхосному — короткий с бочками на грязном склоне опрокидывается
      return { k, v, price: priceOf(k, v), own: owns(k, v), opt: kind === 'opt', why: df ? T.deep(fmt(df.val), fmt(S.cfg.ford / PX, 2)).toLowerCase() : T.whyK[kind] || T.why[k] };
    }
    return null;
  }
  const fordPx = (sg) => { const w = S.L.water.find((q) => q.x1 > sg.x), z = w && S.L.mud.find((q) => q.wet && q.x0 > w.x0 && q.x1 < w.x1); return w ? w.depth + (z ? z.d : 0) : sg.val * PX; }; // настоящая глубина брода за указателем: вода плюс ил
  const tooDeep = (sg) => sg.kind === 'ford' && fordPx(sg) > S.cfg.ford; // то же сравнение, по которому заливает мотор
  const soilK = (v) => String(v).replace(/(Up|Down)$/, ''), soilDir = (v) => (/Up$/.test(v) ? 1 : /Down$/.test(v) ? -1 : 0); // «глина в гору» и «глина под гору» — та же глина, но на склоне
  const signT = (s, short) => (s.kind === 'ford' ? (short ? '' : T.ford + ' ') + fmt(s.val) + ' ' + T.m : s.kind === 'soil' ? T.soil[soilK(s.val)] + (short || !soilDir(s.val) ? '' : ' ' + (soilDir(s.val) > 0 ? T.upW : T.downW)) : s.kind === 'crest' ? T.crest : s.kind === 'rocks' ? T.rocks + (short ? '' : ` ${T.upTo} ${fmt(s.val)} ${T.m}`) : s.kind === 'step' ? T.stepW + (short ? '' : ` ${fmt(s.val)} ${T.m}`) : s.val < 0 ? T.descent : T.climb);
  const deepFord = () => S.L.signs.filter(tooDeep).sort((a, b) => b.val - a.val)[0]; // самый глубокий брод маршрута, который эта сборка не берёт
  const fordHere = () => { const w = S.L.water.find((q) => S.truck.x > q.x0 - 300 && S.truck.x < q.x1 + 300), z = w && S.L.mud.find((q) => q.wet && q.x0 > w.x0 && q.x1 < w.x1); return (w ? w.depth : 0) + (z ? z.d : 0); }; // глубина брода, в котором стоит грузовик: вода плюс ил
  function failTip() { const dpx = fordHere(); return S.why === 'water' ? T.tWater(fmt(dpx / PX), fmt(S.cfg.ford / PX, 2), fixText(fordFix(dpx))) : S.why === 'stuck' ? (stuckSand ? T.tSand : T.tStuck(spinNeed ? T[spinNeed] : '')) : S.why === 'fuel' ? (spinT > 8 || S.inMud > 0 ? T.tSpin(Math.max(1, Math.round(spinT)), spinNeed ? T[spinNeed] : '') : T.tFuel) : T.tFlip; }
  function toGarage(keep) { runQuit('garage'); rent = null; let tip = mode === 'play' && S.state === 'dead' ? failTip() : null; if (tip && S.why === 'water') { const dpx = fordHere(), fx = fordFix(dpx); tab = fx.some((q) => q[1] === 'lift') ? 0 : 3; tip = T.tWaterG(fmt(dpx / PX), fmt(S.cfg.ford / PX, 2), fixText(fx)); } paused = false; resume = !career && keep && S.cp ? { x: S.cp.x, y: S.cp.y } : null; pend = null; mode = 'garage'; newSim(); if (tip) note = tip; else { const a = advice(); if (a) { note = `${T.mech}: ${a.why}. ${partName(a.k, a.v)}${a.own ? '' : ' — ' + a.price}.`; tab = PARTS.find((q) => q[0] === a.k)[2]; } } camX = S.truck.x; camY = S.truck.y; ptrs.clear(); }
  function toMenu(keep) { runQuit('menu'); if (mode === 'play') { pgMsg('gameplay_stopped'); rent = null; } career = true; cur = -1; if (!keep) { sel = -1; reg = regOf(); } paused = false; pend = null; res = null; resume = null; mode = 'menu'; newSim(); camX = S.truck.x; camY = S.truck.y; ptrs.clear(); }
  function buy() { if (!pend) return; const pr = priceOf(pend.k, pend.v); if (save.coins < pr) { sfx('no'); return; } save.coins -= pr; pgEv('part_bought', { part: pend.k, level: pend.v, price: pr, coins_left: save.coins, where: 'garage', step_id: sel >= 0 ? stepOf(sel).step_id : '' }); (save.own[pend.k] = save.own[pend.k] || []).push(pend.v); save.build[pend.k] = pend.v; pend = null; persist(); newSim(); sfx('buy'); }
  function start(fromCp) {
    runQuit('restart'); // начал заново, не доехав
    if (career) { cur = sel >= 0 ? sel : cur; fromCp = false; } pend = null; res = null; paused = false; adTow = 0; newSim(); sw.awd = sw.lock = sw.low = sw.soft = false;
    if (fromCp && resume) { S.cp = { x: resume.x, y: resume.y, fuel: S.cfg.tank }; S.respawn(); rebuilds++; } else rebuilds = 0;
    S.events.length = 0; mode = 'play'; camX = S.truck.x + 200; camY = S.truck.y - 70; ptrs.clear(); toast = null; fuelLvl = 2; idleT = 0; idleX = -1e9; coach = ''; asst = 0; spinT = 0; spinNeed = ''; hold = ''; holdT = 0; ak = {}; trapX = -1e9; trapT = 0; stuckSand = false;
    TM.t0 = performance.now(); TM.deaths = 0; TM.holds = 0; TM.live = career;
    if (career && cur >= 0) { pgEv('progression_started', Object.assign(stepOf(cur), { first_run: !Object.keys(save.stars).length, first_time: !(save.stars[M.CONTRACTS[cur].id] > 0), load: nlogs, cap: M.capOf(S.cfg, kindOf(cur)), coins: save.coins, build_version: VER })); pgMsg('level_started', { level: cur + 1 }); }
    pgMsg('gameplay_started');
    save.seen = save.seen || {}; newKey = career ? ['first', 'awd', 'lock', 'low'].find((k) => (k === 'first' ? cur === 0 && !Object.keys(save.stars).length : S.cfg.b[k]) && !save.seen[k]) || '' : ''; if (newKey) { save.seen[newKey] = 1; persist(); }
  }
  // рейс закончен: считаем деньги и звёзды
  function finish() { rent = null;
    const c = M.CONTRACTS[cur], deliv = S.cargo, fuel = Math.round(S.used), tows = S.tows, gross = deliv * c.pay, total = Math.max(0, gross - fuel - tows * TOW), st = [deliv > 0, deliv > 0 && deliv >= M.capOf(S.cfg, c.cargo), deliv > 0 && tows + adTow === 0], n = st.filter(Boolean).length, was = save.stars[c.id] || 0;
    res = { deliv, of: S.cargo0, pay: c.pay, gross, fuel, tows, total, st, opened: !was && n > 0 ? M.CONTRACTS.filter((q, j) => (q.after ? q.after === c.id : j === cur + 1 && !c.big)).map(cName).join(', ') : '', doubled: false };
    save.coins += total; save.stars[c.id] = Math.max(was, n); save.tl = save.tl || {}; for (const q of c.need || []) if (['awd', 'lock', 'low'].includes(q[0]) && !ak[q[0]]) save.tl[q[0]] = (save.tl[q[0]] || 0) + 1; persist(); // довёз сам, без помощи с кнопкой — значит, научился
    pgEv('progression_completed', runData({ delivered: deliv, of: S.cargo0, earned: total, fuel_l: fuel, tows, stars: n, first_time: !was })); TM.live = false; pgMsg('level_completed', { level: cur + 1 }); pgMsg('gameplay_stopped');
  }
  function tow(free) { paused = false; if (mode !== 'play') return; if (S.state === 'dead') { if (!free) S.tows++; S.respawn(); } else { S.rescue(); if (free) S.tows--; } if (free) adTow++; }
  reg = regOf(); newSim(); camX = S.truck.x; camY = S.truck.y;
  let frDone = false;
  function firstRun() { // самый первый запуск — сразу в рейс, меню подождёт. С мостом — после ответа облачного сохранения: вдруг игрок уже ездил на другом устройстве
    if (frDone) return; frDone = true;
    if (!(save.seen && save.seen.first) && !save.coins && !Object.keys(save.stars || {}).length) { sel = 0; nlogs = defLoad(0); start(false); }
    if (PG.on && !PG.ready) { PG.ready = true; pgMsg('game_ready'); }
  }
  function pgSetup() { // мост уже запущен: что площадка умеет, пауза и звук от неё, состояние рекламы
    const B = window.bridge, id = B.platform.id || ''; PG.on = id !== 'mock' && id !== '';
    try { if (PG.on) B.gameVersion = VER; } catch (e) { /* */ }
    try { let lg = String(B.platform.language || '').toLowerCase(); if (id === 'crazy_games') { const si = (window.CrazyGames && window.CrazyGames.SDK && window.CrazyGames.SDK.user && window.CrazyGames.SDK.user.systemInfo) || {}; lg = String(si.locale || 'en').toLowerCase(); } if (lg && !BOOT && !qLang) setLang(lg); } catch (e) { /* */ }
    try { PG.rew = !!B.advertisement.isRewardedSupported; PG.inter = !!B.advertisement.isInterstitialSupported; } catch (e) { /* */ }
    if (window.GAME_ADS === false) { PG.rew = false; PG.inter = false; }
    try { B.platform.on('pause_state_changed', (q) => { PG.paused = !!q; }); B.platform.on('audio_state_changed', (on) => { PG.mutedP = !on; }); PG.mutedP = B.platform.isAudioEnabled === false; } catch (e) { /* */ }
    try { B.advertisement.on('interstitial_state_changed', (st) => { if (!PG.pend || PG.pend.type !== 'inter' || st === 'loading') return; PG.pend.seen = true; if (st === 'opened') PG.ad = true; else if (st === 'closed' || st === 'failed') pgDone(true); });
      B.advertisement.on('rewarded_state_changed', (st) => { if (!PG.pend || PG.pend.type !== 'rew') return; const pd = PG.pend; if (st === 'opened') { PG.ad = true; pgEv('ad_request', { place: pd.place, result: 'opened', wait_ms: Math.round(performance.now() - pd.t0) }); } else if (st === 'rewarded') PG.got = true; else if (st === 'closed' || st === 'failed') { PG.lastRew = pgNow(); if (st === 'failed') { adNote(T.adNo); pgEv('ad_request', { place: pd.place, result: 'failed' }); } pgDone(PG.got); } }); } catch (e) { /* */ }
  }
  if (BOOT) { if (BOOT.ok) pgSetup(); firstRun(); } // загрузчик дождался моста и облачного сохранения ещё до игры
  else if (window.bridge) {
    Promise.race([window.bridge.initialize(), new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 6000))]).then(() => {
      pgSetup(); const B = window.bridge;
      if (PG.on) B.storage.get('mud4.save').then((v) => { try { const q = typeof v === 'string' ? JSON.parse(v) : v; if (q && q.build && (q.ts || 0) > (save.ts || 0) && mode === 'menu') { save = Object.assign({ coins: 0, own: {}, stars: {} }, q); save.build = Object.assign({}, START, q.build); try { localStorage.setItem('mud4.save', JSON.stringify(save)); } catch (e) { /* */ } reg = regOf(); newSim(); } } catch (e) { /* */ } firstRun(); }).catch(() => firstRun()); else firstRun();
      setTimeout(firstRun, 3500); // облако молчит — не ждём дольше
    }).catch(() => { PG.on = false; firstRun(); });
  } else firstRun();
  addEventListener('pagehide', () => runQuit('left')); // закрыл игру посреди рейса

  // ---------- объёмная сцена: свои предметы поверх мира Hook Truck ----------
  let truckM = null, trailerM = null, barM = null, wheelsM = [], axM = [], paint = [], flagM = null, cloudsM = [], sunM = null, murkM = null, splat = [], puddles = [], mist = [], foam = [], trackI = null, trackN = 0, tyreMud = 0, trackX = 0, truckKey = 0, lastDirt = -1, mudM = [], lastRut = -1, canM = [], waterTop = [], blobs = [], drops = [], smoke = [], dustP = [], pAcc = 0, stackL = [0, 0];
  if (use3d) {
    const A = R3.api, lam = (h, o) => A.lam(h, o);
    const mk = (geo, mat, x, y, z, par, sh = true) => { const m = new A.T.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = sh; par.add(m); return m; };
    // много мелких деталей одного цвета склеиваем в один объект: грузовик и придорожные мелочи рисуются за десяток вызовов, а не за сотни
    function bucket(T3) {
      const bk = new Map();
      return {
        put(geo, mat, x, y, z, rx, rz) { if (rx) geo.rotateX(rx); if (rz) geo.rotateZ(rz); geo.translate(x, y, z); let q = bk.get(mat); if (!q) bk.set(mat, (q = [])); q.push(geo); },
        flush(par, noSh) { const out = []; for (const [mat, geos] of bk) { const m = new T3.Mesh(merge(T3, geos), mat); m.castShadow = !(noSh && noSh.has(mat)) && !mat.transparent; par.add(m); out.push(m); } bk.clear(); return out; },
      };
    }
    function merge(T3, geos) {
      let n = 0; const gs = geos.map((g) => { const q = g.index ? g.toNonIndexed() : g; n += q.attributes.position.count; return q; }), pos = new Float32Array(n * 3), nor = new Float32Array(n * 3); let o = 0;
      for (const g of gs) { pos.set(g.attributes.position.array, o); nor.set(g.attributes.normal.array, o); o += g.attributes.position.count * 3; g.dispose(); }
      const out = new T3.BufferGeometry(); out.setAttribute('position', new T3.BufferAttribute(pos, 3)); out.setAttribute('normal', new T3.BufferAttribute(nor, 3)); return out;
    }
    function buildTruck() {
      const T3 = A.T, sc = A.scene, c = S.cfg, b = c.b, WR = c.WR, old = [truckM, trailerM, ...wheelsM, ...axM.map((q) => q.G)];
      for (const o of old) if (o) { sc.remove(o); o.traverse((q) => { if (q.geometry) q.geometry.dispose(); }); }
      paint = []; lastDirt = -1; truckKey = buildKey;
      const pm = (h) => { const m = lam(h); paint.push({ m, base: m.color.clone() }); return m; };
      const [pa, pb] = PAINTS[b.paint] || PAINTS[0], red = pm(pa), dark = pm(pb), hubM = b.ctis ? pm('#ffca28') : null, fr = pm('#455a64'), blk = pm('#263238'), grey = pm('#90a4ae'), woodA = pm('#8d6e63'), woodB = pm('#795548'), fur = lam('#e8892f'), capM = lam('#ffb300');
      const gl = new T3.MeshLambertMaterial({ color: A.C('#b3e5fc'), transparent: true, opacity: 0.32 }), lamp = new T3.MeshBasicMaterial({ color: A.C('#fff59d') });
      const white = pm('#fafafa'), amber = new T3.MeshBasicMaterial({ color: A.C('#ffb300') }), mudS = lam('#4a2f1c'), BK = bucket(T3), put = BK.put, noSh = new Set([gl, lamp, amber]), flush = (par) => BK.flush(par, noSh);
      const bx = (w, h, d, mat, x, y, z) => put(new T3.BoxGeometry(w, h, d), mat, x, y, z);
      const g = (truckM = new T3.Group()); sc.add(g);
      const yF = -(c.belly - 10), xf = c.xf, cabX1 = xf - 64, cabX0 = cabX1 - 60, cm = (cabX0 + cabX1) / 2, fa = c.ax[c.ax.length - 1];
      bx(c.len - 14, 10, 62, fr, (c.xr + xf) / 2, yF - 5, 0);                                               // рама
      if (b.skid) bx(c.len - 76, 3.5, 74, grey, (c.xr + xf) / 2 + 10, yF - 12, 0);                          // защита днища
      bx(58, 38, 86, red, xf - 35, yF + 19, 0); bx(60, 30, 90, red, cm, yF + 15, 0);                        // капот, низ кабины
      for (const x of [cabX0 + 3, cabX1 - 3]) for (const z of [-42, 42]) bx(6, 40, 6, red, x, yF + 50, z);  // стойки
      bx(64, 6, 94, red, cm, yF + 73, 0); bx(4, 44, 90, dark, cabX0 + 2, yF + 50, 0);                       // крыша, задняя стенка
      bx(2, 38, 82, gl, cabX1 - 1, yF + 50, 0); for (const z of [-45, 45]) bx(50, 38, 2, gl, cm, yF + 50, z);
      bx(12, 16, 96, blk, xf - 3, yF + 4, 0); put(new T3.CylinderGeometry(b.winch ? 10 : 7, b.winch ? 10 : 7, b.winch ? 40 : 30, 8), grey, xf + 3, yF + 12, 0, Math.PI / 2); // бампер, лебёдка
      for (const z of [-30, 30]) bx(4, 10, 16, lamp, xf - 5, yF + 26, z);
      for (const z of [-50, 50]) bx(2 * WR + 14, 5, 22, dark, fa, -(c.hW - WR - 11), z);                    // крылья
      const bx0 = c.xr + 6, bx1 = cabX0 - 8, bl = bx1 - bx0, bm = (bx0 + bx1) / 2;                          // кузов с брёвнами
      const stk = S.stakeH, fh = stk + 14;                                                                    // стойки по высоте груза — как в расчёте: что выше стоек, то вылетает
      bx(bl, 6, 92, dark, bm, yF + 3, 0); for (const z of [-45, 45]) bx(bl, 5, 4, dark, bm, yF + 8.5, z);   // пол и низкий борт: груз видно сбоку
      bx(4, fh, 92, dark, bx1 - 2, yF + 6 + fh / 2, 0);                                                     // передний щит
      for (const z of [-45, 45]) { bx(5, stk, 5, fr, bx0 + 2.5, yF + 6 + stk / 2, z); bx(5, fh, 5, fr, bx1 - 5, yF + 6 + fh / 2, z); }
      for (const q of [0.5, 1]) bx(3, 3.5, 92, fr, bx0 + 2.5, yF + 6 + stk * q - 2, 0);                      // задняя решётка
      put(new T3.CylinderGeometry(4, 4, 56, 6), grey, cabX0 - 4, yF + 62, -40); stackL = [cabX0 - 4, -(yF + 92)];
      if (b.eng >= 2) put(new T3.CylinderGeometry(4, 4, 56, 6), grey, cabX0 - 4, yF + 62, 40);              // форсировка видна: вторая труба,
      if (b.eng >= 4) { bx(28, 9, 34, blk, xf - 38, yF + 42.5, 0); bx(3, 6, 28, grey, xf - 23.5, yF + 42.5, 0); } // потом воздухозаборник на капоте
      if (b.eng >= 5) for (const z of [-40, 40]) bx(4, 10, 4, lamp, cabX0 - 4, yF + 93, z);   // выхлопная труба
      if (b.snorkel) { put(new T3.CylinderGeometry(4.5, 4.5, 72, 6), blk, cabX1 + 3, yF + 56, 46); bx(12, 9, 10, blk, cabX1 + 1, yF + 94, 46); }
      put(new T3.CylinderGeometry(11, 11, b.tank ? 76 : 46, 8), grey, (c.ax[0] + fa) / 2 - 10, yF - 16, 40, 0, Math.PI / 2); // бак под рамой
      const hx = cm + 4, hy = yF + 52;                                                                                       // Барсик за рулём
      put(new T3.SphereGeometry(14, 12, 9), fur, hx, hy, 12); for (const z of [4, 20]) put(new T3.ConeGeometry(5, 10, 4), fur, hx - 2, hy + 14, z); put(new T3.CylinderGeometry(10, 12, 6, 10), capM, hx, hy + 11, 12);
      for (let k = 0; k < 4; k++) bx(2, 4, 58, blk, xf - 5.5, yF + 9 + k * 7, 0);                                         // решётка радиатора
      for (const z of [-43.8, 43.8]) { bx(52, 5, 1.5, white, xf - 35, yF + 24, z); bx(1.5, 26, 1.5, dark, cm - 9, yF + 15, z * 1.035); bx(16, 2.5, 2, blk, cm + 12, yF + 23, z * 1.04); }
      for (const z of [-50, 50]) { bx(4, 12, 7, blk, cabX1 + 2, yF + 46, z); bx(3, 24, 24, blk, c.ax[0] - WR - 8, -(c.hW - 4), z); } // зеркала, брызговики
      for (const z of [-30, 0, 30]) bx(5, 4, 8, amber, cabX1 - 7, yF + 78, z);                                             // огни на крыше
      put(new T3.CylinderGeometry(1, 1, 64, 4), blk, cabX0 + 7, yF + 106, 36);                                              // антенна
      flush(g);
      flagM = mk(new T3.PlaneGeometry(24, 13), new T3.MeshBasicMaterial({ color: A.C('#ff6d00'), side: T3.DoubleSide }), cabX0 - 5, yF + 130, 36, g, false); flagM.geometry.translate(-12, 0, 0); flagM.position.x = cabX0 + 7;
      // грязь налипает пятнами в три захода: чем дольше месишь, тем больше
      let sd = 7; const rn = () => ((sd = (sd * 16807) % 2147483647) / 2147483647);
      splat = [0, 1, 2].map(() => { for (let k = 0; k < 9; k++) { const a = rn(), x = a < 0.4 ? bx0 + rn() * bl : a < 0.7 ? cabX0 + rn() * 60 : xf - 62 + rn() * 54, y = yF + (a < 0.4 ? 8 + rn() * 14 : 2 + rn() * 30), r = 4 + rn() * 6, q = new T3.IcosahedronGeometry(r, 0); q.scale(1.3, 1, 0.22); put(q, mudS, x, y, 46.2); } const m = flush(g)[0]; m.castShadow = false; m.visible = false; return m; });
      // прицеп: рама, кузов со стойками по высоте груза, дышло к сцепке
      trailerM = null; if (barM) { sc.remove(barM); barM.geometry.dispose(); barM = null; }
      if (c.tr) { const TR = c.tr, h2 = TR.bed / 2, tg = (trailerM = new T3.Group()); sc.add(tg);
        bx(TR.bed + 8, 8, 56, fr, 0, yF - 4, 0); bx(TR.bed, 6, 92, dark, 0, yF + 3, 0); for (const z of [-45, 45]) bx(TR.bed, 5, 4, dark, 0, yF + 8.5, z);
        bx(4, fh, 92, dark, h2 - 2, yF + 6 + fh / 2, 0); for (const z of [-45, 45]) { bx(5, stk, 5, fr, -h2 + 2.5, yF + 6 + stk / 2, z); bx(5, fh, 5, fr, h2 - 5, yF + 6 + fh / 2, z); }
        for (const q of [0.5, 1]) bx(3, 3.5, 92, fr, -h2 + 2.5, yF + 6 + stk * q - 2, 0);
        if (TR.rod) bx(TR.tx - TR.rod - h2 + 6, 6, 10, fr, (h2 + TR.tx - TR.rod) / 2, -TR.ty, 0); else { bx(TR.tx - h2 + 6, 6, 10, fr, (h2 + TR.tx) / 2, -TR.ty, 0); put(new T3.CylinderGeometry(5, 5, 14, 8), grey, TR.tx, -TR.ty, 0); }
        for (const z of [-34, 34]) { bx(3, 8, 14, amber, -h2 - 4, yF - 2, z); bx(3, 22, 24, blk, -h2 - 3, -(c.hW - 6), z * 1.45); }
        for (const lx of TR.ax) for (const z of [-50, 50]) bx(2 * WR + 12, 4, 22, dark, lx, -(c.hW - WR - 11), z);
        flush(tg);
        if (TR.rod) barM = mk(new T3.BoxGeometry(TR.rod, 5, 8), fr, 0, 0, 0, sc, false); }
      // колёса: шина с грунтозацепами по виду шин — одной «шестернёй», диск; мост и стойка (с лифтом её видно)
      const lug = [0, 8, 10][b.tires], lh = [0, 4, 7][b.tires], sh = new T3.Shape();
      if (lug) for (let k = 0; k < lug * 4; k++) { const a = (k / (lug * 4)) * Math.PI * 2, r = WR + ((k & 3) < 2 ? lh : 0); if (k) sh.lineTo(Math.cos(a) * r, Math.sin(a) * r); else sh.moveTo(r, 0); }
      wheelsM = S.allw.map(() => {
        const G = new T3.Group(); sc.add(G);
        for (const z of [-50, 50]) {
          if (lug) put(new T3.ExtrudeGeometry(sh, { depth: 26, bevelEnabled: false, curveSegments: 1 }), blk, 0, 0, z - 13); else put(new T3.CylinderGeometry(WR, WR, 26, 18), blk, 0, 0, z, Math.PI / 2);
          put(new T3.CylinderGeometry(WR * 0.48, WR * 0.48, 29, 8), hubM || grey, 0, 0, z, Math.PI / 2);
        }
        flush(G);
        const ra = new T3.CylinderGeometry(WR + lh + 3, WR + lh + 3, 30, 16), rb = ra.clone(); ra.rotateX(Math.PI / 2); ra.translate(0, 0, 50); rb.rotateX(Math.PI / 2); rb.translate(0, 0, -50);
        const rg = new T3.Mesh(merge(T3, [ra, rb]), mudS); rg.visible = false; G.add(rg); G.userData.ring = rg; // грязевой «бублик»: растёт, когда протектор забивается
        return G;
      });
      axM = S.allw.map(() => { const G = new T3.Group(); sc.add(G); mk(new T3.BoxGeometry(11, 11, 96), fr, 0, 0, 0, G, false); return { G, st: mk(new T3.BoxGeometry(9, 1, 9), fr, 0, 0, 0, G, false) }; });
    }
    function sign(q, s) { // указатель: что впереди
      const T3 = A.T, cn = document.createElement('canvas'); cn.width = 192; cn.height = 128; const g = cn.getContext('2d');
      g.fillStyle = '#fff8e1'; g.fillRect(0, 0, 192, 128); g.lineWidth = 8; g.strokeStyle = '#37474f'; g.strokeRect(4, 4, 184, 120); g.lineCap = 'round'; g.lineJoin = 'round';
      if (s.kind === 'ford') { g.strokeStyle = '#1e88e5'; g.lineWidth = 7; for (let k = 0; k < 2; k++) { g.beginPath(); for (let x = 30; x <= 162; x += 6) g.lineTo(x, 34 + k * 18 + Math.sin(x / 9) * 6); g.stroke(); } }
      else if (s.kind === 'soil') { // грязь — кружками по тяжести, песок, глина и торф — полосой своего цвета
        const sk = soilK(s.val), dir = soilDir(s.val), ty = (M.ZONES[sk] && M.ZONES[sk].t) || 'mud', lv = { soft: 1, medium: 2, sticky: 3, swamp: 4 }[sk] || 0, tilt = (x) => -dir * (x - 96) * 0.2; g.fillStyle = ty === 'mud' ? '#5d4037' : SOILC[ty]; // на склоне рисунок наклонён: в гору — вправо вверх
        if (lv) { for (let k = 0; k < 4; k++) { g.globalAlpha = k < lv ? 1 : 0.18; g.beginPath(); g.arc(42 + k * 36, 44 + tilt(42 + k * 36), 13, 0, 7); g.fill(); } g.globalAlpha = 1; }
        else { g.beginPath(); g.moveTo(24, 68); for (let x = 24; x <= 168; x += 6) g.lineTo(x, 38 + tilt(x) + Math.sin(x / 10) * (dir ? 4 : 8)); g.lineTo(168, 68); g.closePath(); g.fill(); }
      }
      else if (s.kind === 'rocks') { g.fillStyle = '#78909c'; for (const [cx, r] of [[50, 17], [98, 26], [146, 20]]) { g.beginPath(); g.arc(cx, 68, r, Math.PI, 0); g.closePath(); g.fill(); } g.strokeStyle = '#37474f'; g.lineWidth = 7; g.beginPath(); g.moveTo(22, 68); g.lineTo(170, 68); g.stroke(); }
      else { g.strokeStyle = '#37474f'; g.lineWidth = 9; g.beginPath(); if (s.kind === 'crest') { g.moveTo(40, 66); g.lineTo(96, 22); g.lineTo(152, 66); } else if (s.kind === 'step') { g.moveTo(34, 66); g.lineTo(96, 66); g.lineTo(96, 32); g.lineTo(158, 32); } else if (s.val < 0) { g.moveTo(40, 24); g.lineTo(152, 66); } else { g.moveTo(40, 66); g.lineTo(152, 24); } g.stroke(); }
      g.fillStyle = '#263238'; g.font = '900 34px system-ui, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText(signT(s, true), 96, 98, 170);
      const tx = new T3.CanvasTexture(cn); tx.encoding = T3.sRGBEncoding; const gy = -S.groundAt(s.x), z = -q.ROAD - 30;
      q.cyl(5, 150, 6, lam('#6d4c41'), s.x, gy + 75, z, q.lvlG); const m = new T3.Mesh(new T3.PlaneGeometry(132, 88), new T3.MeshBasicMaterial({ map: tx })); m.position.set(s.x, gy + 150, z + 6); q.lvlG.add(m);
    }
    R3.onBuild = (q) => {
      const T3 = q.T, L = S.L, lvlG = q.lvlG, box = q.box, cyl = q.cyl, ROAD = q.ROAD, ZF = q.ZF, ZB = q.ZB;
      waterTop = [];
      for (const w of L.water) { // брод: вода поперёк всей сцены, у дороги — мерная вешка с полосами по полметра
        const h = w.depth + 16, m = new T3.Mesh(new T3.BoxGeometry(w.x1 - w.x0, h, ZF - ZB), new T3.MeshLambertMaterial({ color: q.C('#4fc3f7'), transparent: true, opacity: 0.58, depthWrite: false }));
        m.position.set((w.x0 + w.x1) / 2, -w.y - h / 2, (ZF + ZB) / 2); m.renderOrder = 3; lvlG.add(m); waterTop.push({ m, y: m.position.y });
        const px = (w.x0 + w.x1) / 2, by = -(w.y + w.depth), n = Math.ceil((w.depth + 60) / 27);
        for (let k = 0; k < n; k++) box(9, 27, 9, lam(k & 1 ? '#fafafa' : '#e53935'), px, by + 13.5 + k * 27, -ROAD - 14, lvlG);
      }
      for (const a of L.trees) { const gy = -a.gy; q.tree(a.x, gy, -ROAD - 46, 2.1); cyl(13, 150, 7, lam('#6d4c33'), a.x, gy + 75, -ROAD - 46, lvlG); box(30, 10, 30, lam('#ffca28'), a.x, -a.y, -ROAD - 46, lvlG); } // дерево со стропой для лебёдки
      canM = L.cans.map((c) => { const g = new T3.Group(), k = c.k || 1; for (let j = 0; j < k; j++) { const dx = (j - (k - 1) / 2) * 30; box(26, 34, 16, lam('#e53935'), dx, 0, 0, g); box(10, 6, 10, lam('#ffeb3b'), dx + 6, 20, 0, g); } g.position.set(c.x, -c.y - 26, 0); lvlG.add(g); return g; });
      (L.rocks || []).forEach((r, i) => { const sh = new T3.Shape(), col = ['#8d959b', '#7c858b', '#9aa1a6'][i % 3]; sh.moveTo(-r.w / 2 - 3, -8); sh.lineTo(-r.w * 0.2 - 2, r.h + 1.5); sh.lineTo(r.w * 0.2 + 2, r.h + 1.5); sh.lineTo(r.w / 2 + 3, -8); sh.closePath();
        const m = new T3.Mesh(new T3.ExtrudeGeometry(sh, { depth: ZF + ROAD + 30, bevelEnabled: false }), lam(col)); m.position.set(r.x, -r.y, -ROAD - 28); m.castShadow = true; m.receiveShadow = true; lvlG.add(m);
        const d = new T3.Mesh(new T3.DodecahedronGeometry(1, 0), lam(col)), f = 0.7 + 0.3 * Math.abs(Math.sin(r.x * 0.37)); d.scale.set(r.w * 0.45 * f, r.h * 1.2 * f, 30 * f); d.rotation.y = r.x * 0.13; d.position.set(r.x + 8, -r.y + r.h * 0.3, -ROAD - 44); d.castShadow = true; lvlG.add(d); }); // камень — серая глыба точно по кочке под колесом, за дорогой — валун
      for (const k of L.marks) {
        const gy = -k.y, z = -ROAD - 150;
        if (k.kind === 'garage') { box(300, 150, 180, lam('#90a4ae'), k.x, gy + 75, z, lvlG); box(320, 16, 200, lam('#c62828'), k.x, gy + 158, z, lvlG); box(120, 110, 6, lam('#37474f'), k.x, gy + 55, z + 92, lvlG); }
        else { box(340, 130, 200, lam('#a1887f'), k.x, gy + 65, z, lvlG); box(360, 18, 220, lam('#5d4037'), k.x, gy + 139, z, lvlG); for (let i = 0; i < 5; i++) cyl(15, 170, 8, lam(i & 1 ? '#8d6e63' : '#795548'), k.x - 250 + (i % 3) * 32 + (i > 2 ? 16 : 0), gy + 15 + (i > 2 ? 27 : 0), z + 120, lvlG, true); }
      }
      for (const s of L.signs) sign(q, s);
      // живая грязь: лента от твёрдого дна до поверхности; поверхность опускается там, где прошли колёса
      mudM = L.mud.map((z, zi) => {
        const n = z.rut.length, pos = new Float32Array(n * 12), col = new Float32Array(n * 12), nor = new Float32Array(n * 12), idx = [];
        for (let i = 0; i < n; i++) { nor[i * 12 + 1] = nor[i * 12 + 4] = 1; nor[i * 12 + 8] = nor[i * 12 + 11] = 1; if (i < n - 1) { const a = i * 4, b = a + 4; idx.push(a, b + 1, a + 1, a, b, b + 1, a + 2, a + 3, b + 3, a + 2, b + 3, b + 2); } }
        const g = new T3.BufferGeometry(); g.setAttribute('position', new T3.BufferAttribute(pos, 3)); g.setAttribute('color', new T3.BufferAttribute(col, 3)); g.setAttribute('normal', new T3.BufferAttribute(nor, 3)); g.setIndex(idx);
        const m = new T3.Mesh(g, new T3.MeshLambertMaterial({ vertexColors: true, side: T3.DoubleSide })); m.receiveShadow = true; m.frustumCulled = false; lvlG.add(m);
        return { zi, n, pos, col, g, zf: ZF + 2, zb: -ROAD - 8 }; // чуть ближе передней стенки земли, чтобы они не мерцали друг сквозь друга
      });
      lastRut = -1;
      // тайга живёт: столбы с проводами, камыши у бродов, пеньки, штабеля, столбики, лужи после дождя, туман в низинах
      const BK = bucket(T3); let sd = 4242; const rnd = () => ((sd = (sd * 16807) % 2147483647) / 2147483647);
      const xA = L.polys[0][0][0] + 200, xB = L.fin + 700, inW = (x, p) => L.water.some((w) => x > w.x0 - p && x < w.x1 + p), firm = (x) => !inW(x, 90) && !L.mud.some((z) => x > z.x0 - 70 && x < z.x1 + 70), flatAt = (x) => Math.abs(S.groundAt(x + 45) - S.groundAt(x - 45)) < 12;
      const poleM = lam('#6d4c41'), reedM = lam('#5a9a32'), headM = lam('#5d4037'), stumpM = lam('#7b5a3a'), topM = lam('#d9bc8c'), logB = lam('#8d6e63'), postM = lam('#fafafa'), capM = lam('#263238');
      const pudM = new T3.MeshBasicMaterial({ color: q.C('#b5e0fa'), transparent: true, opacity: 0.85 }), wp = [];
      for (let x = xA; x < xB; x += 640) { if (inW(x, 50)) continue; const gy = -S.bedAt(x), z = -ROAD - 130; BK.put(new T3.CylinderGeometry(5, 6, 250, 6), poleM, x, gy + 125, z); BK.put(new T3.BoxGeometry(8, 6, 76), poleM, x, gy + 234, z); wp.push([x, gy + 240]); }
      const wl = []; for (let i = 1; i < wp.length; i++) { const a = wp[i - 1], b = wp[i], n = 6; for (const z of [-ROAD - 100, -ROAD - 160]) for (let k = 0; k < n; k++) { const t0 = k / n, t1 = (k + 1) / n, sg = (t) => 4 * 30 * t * (1 - t); wl.push(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0 - sg(t0), z, a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1 - sg(t1), z); } }
      const wg = new T3.BufferGeometry(); wg.setAttribute('position', new T3.Float32BufferAttribute(wl, 3)); lvlG.add(new T3.LineSegments(wg, new T3.LineBasicMaterial({ color: q.C('#455a64') })));
      for (const w of L.water) for (const [xa, xb] of [[w.x0 + 10, w.x0 + 190], [w.x1 - 190, w.x1 - 10]]) for (let i = 0; i < 30; i++) { // камыши по берегам
        const x = xa + rnd() * (xb - xa), z = rnd() < 0.55 ? -ROAD - 14 - rnd() * 260 : ROAD + 8 + rnd() * (ZF - ROAD - 16), gy = -S.groundAt(x), hh = 44 + rnd() * 44;
        BK.put(new T3.CylinderGeometry(1.4, 1.9, hh, 4), reedM, x, gy + hh / 2, z); if (rnd() < 0.65) BK.put(new T3.CylinderGeometry(3.3, 3.3, 14, 5), headM, x, gy + hh - 3, z);
      }
      puddles = [];
      for (let x = xA; x < xB; x += 140 + rnd() * 170) {
        if (rnd() < 0.55 && !inW(x, 30)) { const z = -ROAD - 34 - rnd() * 340, r = 9 + rnd() * 9, gy = -S.bedAt(x); BK.put(new T3.CylinderGeometry(r, r * 1.15, 14, 7), stumpM, x, gy + 7, z); BK.put(new T3.CylinderGeometry(r * 0.85, r * 0.85, 1.6, 7), topM, x, gy + 14.6, z); }
        if (firm(x) && flatAt(x) && rnd() < 0.5) { const r = 30 + rnd() * 26, g = new T3.CircleGeometry(r, 10); g.rotateX(-Math.PI / 2); g.scale(1, 1, 0.7); BK.put(g, pudM, x, -S.groundAt(x) + 0.9, (rnd() - 0.5) * 60); puddles.push({ x, r, t: -9 }); }
      }
      for (let x = Math.ceil(xA / 540) * 540; x < xB; x += 540) if (firm(x)) { const gy = -S.groundAt(x); BK.put(new T3.BoxGeometry(7, 26, 7), postM, x, gy + 13, ROAD + 24); BK.put(new T3.BoxGeometry(7.2, 7, 7.2), capM, x, gy + 29, ROAD + 24); }
      for (let x = xA + 700; x < xB; x += 2300 + rnd() * 900) if (firm(x) && flatAt(x)) { const gy = -S.groundAt(x); [[0, 0], [23, 0], [46, 0], [11.5, 20], [34.5, 20], [23, 40]].forEach(([dx, dy], i) => { BK.put(new T3.CylinderGeometry(11, 11, 130, 8), i & 1 ? stumpM : logB, x + dx, gy + 11 + dy, -ROAD - 90, Math.PI / 2); BK.put(new T3.CylinderGeometry(8.5, 8.5, 1.5, 8), topM, x + dx, gy + 11 + dy, -ROAD - 24.5, Math.PI / 2); }); }
      // облака над дорогой (плывут двумя стаями) и тёплое солнце в дымке
      const cloudM = new T3.MeshLambertMaterial({ color: q.C('#ffffff'), emissive: q.C('#9fb6c4'), fog: false });
      cloudsM = [0, 1].map((gi) => { for (let x = xA - 1500 + gi * 500; x < xB + 2500; x += 1000 + rnd() * 700) { const gy = -S.bedAt(clamp(x, xA, xB)) + 640 + rnd() * 520, z = -1500 - rnd() * 2600, sc = 1.6 + rnd() * 1.6; for (const [dx, dy, r] of [[0, 0, 60], [62, -8, 46], [-58, -10, 42], [22, 26, 44], [-24, 22, 36]]) { const g = new T3.IcosahedronGeometry(r * sc, 1); g.scale(1.25, 0.8, 1); BK.put(g, cloudM, x + dx * sc, gy + dy * sc, z); } } const m = BK.flush(lvlG)[0]; m.castShadow = false; m.frustumCulled = false; return { m, v: 9 + gi * 7 }; });
      { const cs = document.createElement('canvas'); cs.width = cs.height = 128; const g = cs.getContext('2d'), gr = g.createRadialGradient(64, 64, 4, 64, 64, 64); gr.addColorStop(0, 'rgba(255,250,225,1)'); gr.addColorStop(0.18, 'rgba(255,244,200,0.75)'); gr.addColorStop(0.5, 'rgba(255,236,170,0.22)'); gr.addColorStop(1, 'rgba(255,236,170,0)'); g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
        sunM = new T3.Mesh(new T3.PlaneGeometry(2600, 2600), new T3.MeshBasicMaterial({ map: new T3.CanvasTexture(cs), transparent: true, depthWrite: false, fog: false, blending: T3.AdditiveBlending })); sunM.renderOrder = 0; sunM.frustumCulled = false; lvlG.add(sunM); }
      BK.flush(lvlG);
      // туман: три полупрозрачные ленты за дорогой, идут вдоль рельефа и медленно плывут
      const cn = document.createElement('canvas'); cn.width = 8; cn.height = 64; { const g = cn.getContext('2d'), gr = g.createLinearGradient(0, 0, 0, 64); gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(0.5, 'rgba(255,255,255,1)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, 8, 64); }
      const mt = new T3.CanvasTexture(cn);
      mist = [[-420, 0.17, 150, 45], [-1150, 0.24, 230, 85]].map(([z, op, hh, off], i) => {
        const pos = [], uv = [], idx = []; let n = 0;
        for (let x = xA - 2500; x <= xB + 2500; x += 180, n++) { const gy = -S.bedAt(clamp(x, xA, xB)) + off + Math.sin(x / 700 + i * 2) * 40; pos.push(x, gy - hh / 2, z, x, gy + hh / 2, z); uv.push(0, 0, 0, 1); if (n) { const a = (n - 1) * 2; idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); } }
        const g = new T3.BufferGeometry(); g.setAttribute('position', new T3.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new T3.Float32BufferAttribute(uv, 2)); g.setIndex(idx);
        const m = new T3.Mesh(g, new T3.MeshBasicMaterial({ map: mt, transparent: true, opacity: op, depthWrite: false, fog: false, side: T3.DoubleSide })); m.renderOrder = 1; m.frustumCulled = false; lvlG.add(m); return { m, v: 5 + i * 3 };
      });
      // вода: светлая плёнка по поверхности и полоски пены, которые сносит течением
      foam = []; const foamM = new T3.MeshBasicMaterial({ color: q.C('#ffffff'), transparent: true, opacity: 0.7 });
      for (const w of L.water) {
        const sh = new T3.Mesh(new T3.PlaneGeometry(w.x1 - w.x0 - 6, ZF + ROAD + 300), new T3.MeshBasicMaterial({ color: q.C('#e1f5fe'), transparent: true, opacity: 0.22, depthWrite: false })); sh.rotation.x = -Math.PI / 2; sh.position.set((w.x0 + w.x1) / 2, -w.y + 1.2, (ZF - ROAD - 300) / 2); sh.renderOrder = 4; lvlG.add(sh); waterTop.push({ m: sh, y: sh.position.y });
        for (let k = 0; k < 5; k++) { const f = new T3.Mesh(new T3.BoxGeometry(34 + rnd() * 50, 1, 4), foamM); f.position.set(w.x0 + 90 + rnd() * (w.x1 - w.x0 - 180), -w.y + 2, ZF - 6 - k * 34); f.renderOrder = 5; lvlG.add(f); foam.push({ m: f, w, v: 12 + rnd() * 18 }); }
      }
      const sc = A.scene;
      if (!murkM) { const mg = new T3.CircleGeometry(90, 14); mg.rotateX(-Math.PI / 2); murkM = new T3.Mesh(mg, new T3.MeshBasicMaterial({ color: q.C('#6d4c33'), transparent: true, opacity: 0.42, depthWrite: false })); murkM.renderOrder = 6; murkM.visible = false; sc.add(murkM); }
      if (!trackI) { const tg = new T3.PlaneGeometry(26, 24); tg.rotateX(-Math.PI / 2); trackI = new T3.InstancedMesh(tg, new T3.MeshBasicMaterial({ color: q.C('#3b2616'), transparent: true, opacity: 0.6, depthWrite: false }), 80); trackI.count = 0; trackI.frustumCulled = false; trackI.renderOrder = 2; sc.add(trackI); }
      if (!blobs.length) {
        for (let i = 0; i < 30; i++) { const m = new T3.Mesh(new T3.IcosahedronGeometry(1, 0), lam('#4a2f1c')); m.visible = false; sc.add(m); blobs.push({ m, life: 0, v: [0, 0, 0], r: 1 }); }
        for (let i = 0; i < 18; i++) { const m = new T3.Mesh(new T3.IcosahedronGeometry(1, 0), new T3.MeshBasicMaterial({ color: q.C('#e1f5fe'), transparent: true, opacity: 0.8 })); m.visible = false; sc.add(m); drops.push({ m, life: 0, v: [0, 0, 0], r: 1 }); }
        for (let i = 0; i < 12; i++) { const m = new T3.Mesh(new T3.IcosahedronGeometry(1, 1), new T3.MeshBasicMaterial({ color: q.C('#78909c'), transparent: true, opacity: 0.5, depthWrite: false })); m.visible = false; sc.add(m); smoke.push({ m, life: 0, v: [0, 0, 0], r: 1 }); }
        for (let i = 0; i < 16; i++) { const m = new T3.Mesh(new T3.IcosahedronGeometry(1, 1), new T3.MeshBasicMaterial({ color: q.C('#ecd9a6'), transparent: true, opacity: 0.5, depthWrite: false })); m.visible = false; sc.add(m); dustP.push({ m, life: 0, v: [0, 0, 0], r: 1 }); }
      }
    };
    const dum = new A.T.Object3D(); let trackKey = 0;
    // груз — настоящие тела: лежит поперёк кузова, катается и вылетает. Один вид груза — два-три объекта на все штуки сразу
    const cargoI = {};
    function cargoMeshes(kind) {
      const T3 = A.T, r = M.CARGO[kind].r, out = [], add = (geos, col) => { const m = new T3.InstancedMesh(merge(T3, geos), lam(col), 48); m.count = 0; m.frustumCulled = false; m.castShadow = true; A.scene.add(m); out.push(m); };
      const cyl = (rad, len, seg, z = 0) => { const g = new T3.CylinderGeometry(rad, rad, len, seg); g.rotateX(Math.PI / 2); g.translate(0, 0, z); return g; }, disc = (rad, x, y, z, seg = 10) => { const g = new T3.CircleGeometry(rad, seg); g.translate(x, y, z); return g; };
      if (kind === 'melon') {
        add([new T3.SphereGeometry(r, 14, 10)], '#43a047');
        add([0, 1, 2, 3].map((k) => { const g = new T3.TorusGeometry(r + 0.15, 1.05, 4, 18); g.rotateY((k * Math.PI) / 4 + 0.3); return g; }), '#1b5e20'); // полосы от макушки к макушке — видно, как катится
      } else if (kind === 'barrel') {
        const rim = new T3.RingGeometry(r - 2.4, r + 0.5, 14); rim.translate(0, 0, 39.4);
        add([cyl(r, 78, 14)], '#0d47a1'); add([cyl(r + 0.8, 4, 14, 19), cyl(r + 0.8, 4, 14, -19), rim], '#42a5f5'); add([disc(2.3, r * 0.42, r * 0.28, 39.6, 8)], '#fafafa'); // синяя бочка: обручи, ободок крышки и пробка — по пробке видно, как катится
      } else {
        add([cyl(r, 84, 9)], '#7b5a3a'); add([disc(r - 1.3, 0, 0, 42.3, 9)], '#e0c08f');
        const ring = new T3.RingGeometry(r * 0.4, r * 0.52, 10); ring.translate(0.6, 0.4, 42.6); add([ring, disc(1.7, r * 0.5, r * 0.35, 42.6, 6)], '#a1887f');
      }
      return out;
    }
    // цвета грунтов до освещения: нетронутый и продавленный; в глубокой колее (кроме песка) стоит вода
    const PAL = { mud: [[0.125, 0.06, 0.028], [0.04, 0.02, 0.01]], sand: [[0.62, 0.41, 0.15], [0.4, 0.25, 0.09]], clay: [[0.37, 0.11, 0.045], [0.19, 0.055, 0.022]], peat: [[0.05, 0.038, 0.024], [0.016, 0.012, 0.008]], scree: [[0.36, 0.36, 0.33], [0.24, 0.24, 0.22]] }, WATER = [0.11, 0.21, 0.3];
    function updMud() {
      const L = S.L;
      for (const q of mudM) {
        const z = L.mud[q.zi], P3 = q.pos, Cc = q.col;
        for (let i = 0; i < q.n; i++) {
          const x = Math.min(z.x0 + 30 * i, z.x1), r = S.rutAt(x), yT = -(S.groundAt(x) + r), yB = -S.bedAt(x) - 3, k = clamp(r / (0.5 * z.d), 0, 1), o = i * 12, sh = z.wet ? 0.75 : 1;
          P3[o] = P3[o + 3] = P3[o + 6] = P3[o + 9] = x; P3[o + 1] = P3[o + 4] = P3[o + 7] = yT; P3[o + 10] = Math.min(yB, yT - 2); P3[o + 2] = P3[o + 8] = P3[o + 11] = q.zf; P3[o + 5] = q.zb;
          const pa = PAL[z.t] || PAL.mud, wt = z.t === 'sand' || z.t === 'scree' || z.wet ? 0 : clamp((S.dugAt(x) - 8) / 16, 0, 0.8);
          for (let c = 0; c < 3; c++) { let top = (pa[0][c] + (pa[1][c] - pa[0][c]) * k) * sh; const fc = top * 0.55; top += (WATER[c] - top) * wt; Cc[o + c] = top * 1.15; Cc[o + 3 + c] = top * 0.8; Cc[o + 6 + c] = fc; Cc[o + 9 + c] = pa[1][c] * 0.7 * sh; } // продавленное место темнее и мокрее
        }
        q.g.attributes.position.needsUpdate = true; q.g.attributes.color.needsUpdate = true;
      }
    }
    const emit = (pool, x, y, z, v, r, life) => { const p = pool[(pool.i = ((pool.i | 0) + 1) % pool.length)]; p.life = p.L = life; p.r = r; p.v = v; p.m.position.set(x, y, z); p.m.visible = true; return p; };
    function fly(pool, dt, grav, grow) { for (const p of pool) if (p.life > 0) { p.life -= dt; if (p.life <= 0) { p.m.visible = false; continue; } p.v[1] -= grav * dt; p.m.position.x += p.v[0] * dt; p.m.position.y += p.v[1] * dt; p.m.position.z += p.v[2] * dt; const s = p.r * (1 + grow * (1 - p.life / p.L)); p.m.scale.set(s, s, s); if (grow) p.m.material.opacity = 0.5 * (p.life / p.L); } }
    R3.onDraw = (S2, v, dt) => {
      A.truck.visible = false; for (const g of A.wheels) g.visible = false;
      if (truckKey !== buildKey) buildTruck();
      const tr = S.truck, c = S.cfg, WR = c.WR; truckM.position.set(tr.x, -tr.y, 0); truckM.rotation.z = -tr.a;
      if (trailerM && S.trailer) { trailerM.position.set(S.trailer.x, -S.trailer.y, 0); trailerM.rotation.z = -S.trailer.a; if (barM) { const TR = c.tr, a = P.wpt(tr, TR.hx, TR.hy), q = P.wpt(S.trailer, TR.tx - TR.rod, TR.ty); barM.position.set((a[0] + q[0]) / 2, -(a[1] + q[1]) / 2, 0); barM.rotation.z = Math.atan2(-(a[1] - q[1]), a[0] - q[0]); } }
      S.allw.forEach((w, i) => { const bd = i < S.wheels.length ? tr : S.trailer;
        wheelsM[i].position.set(w.x, -w.y, 0); wheelsM[i].rotation.z = -w.a;
        const rg = wheelsM[i].userData.ring, cl = S.clog[i]; rg.visible = cl > 0.12; if (rg.visible) { const sc = 0.84 + 0.16 * cl; rg.scale.set(sc, sc, 1); }
        const ly = P.local(bd, w.x, w.y)[1], gap = Math.max(2, ly - (c.belly - 10)), q = axM[i]; q.G.position.set(w.x, -w.y, 0); q.G.rotation.z = -bd.a; q.st.scale.y = gap; q.st.position.y = gap / 2;
      });
      const kd = S.logs.length ? S.kind : ''; if (kd && !cargoI[kd]) cargoI[kd] = cargoMeshes(kd);
      for (const k in cargoI) for (const m of cargoI[k]) m.count = k === kd ? Math.min(26, S.logs.length) : 0;
      if (kd) { S.logs.forEach((q, i) => { if (i > 25) return; dum.position.set(q.b.x, -q.b.y, 0); dum.rotation.set(0, 0, -q.b.a); dum.scale.set(1, 1, 1); dum.updateMatrix(); for (const m of cargoI[kd]) m.setMatrixAt(i, dum.matrix); }); for (const m of cargoI[kd]) m.instanceMatrix.needsUpdate = true; }
      if (Math.abs(S.dirt - lastDirt) > 0.02) { lastDirt = S.dirt; const mc = A.C('#5b3d27'); for (const q of paint) q.m.color.copy(q.base).lerp(mc, S.dirt * 0.72); } // грязь налипает, вода смывает
      splat.forEach((m, i) => { m.visible = S.dirt > 0.18 + i * 0.26; });
      if (flagM) flagM.rotation.y = Math.sin(realT * 9) * 0.45 - clamp(tr.vx / 900, -0.6, 0.6);
      if (lastRut !== S.rutV + buildKey * 1e6) { lastRut = S.rutV + buildKey * 1e6; updMud(); }
      // с грязными колёсами на твёрдой дороге остаются следы — и постепенно сходят на нет
      if (trackKey !== buildKey) { trackKey = buildKey; trackN = 0; trackI.count = 0; tyreMud = 0; }
      const rw = S.wheels[0];
      if (S.sunk[0] > 3) { tyreMud = 1; trackX = rw.x; } else if (tyreMud > 0.05 && S.grounded && Math.abs(rw.x - trackX) > 24 && !S.waterAt(rw.x)) {
        trackX = rw.x; const gy = -S.groundAt(rw.x) + 1.1;
        for (const z of [-50, 50]) { dum.position.set(rw.x, gy, z); dum.rotation.set(0, 0, Math.atan2(S.groundAt(rw.x - 12) - S.groundAt(rw.x + 12), 24)); dum.scale.set(1, 1, 0.4 + 0.6 * tyreMud); dum.updateMatrix(); trackI.setMatrixAt(trackN % 80, dum.matrix); trackN++; }
        trackI.count = Math.min(80, trackN); trackI.instanceMatrix.needsUpdate = true; tyreMud -= 0.028;
      } else if (S.waterAt(rw.x)) tyreMud = 0;
      for (const pd of puddles) if (realT - pd.t > 0.5) for (const w of S.wheels) if (Math.abs(w.x - pd.x) < pd.r && Math.abs(w.vx) > 70 && S.grounded) { pd.t = realT; for (let k = 0; k < 6; k++) emit(drops, w.x + (Math.random() - 0.5) * 30, -w.y - WR + 4, (Math.random() - 0.5) * 80, [(Math.random() - 0.5) * 260 + w.vx * 0.2, 150 + Math.random() * 190, (Math.random() - 0.5) * 220], 3 + Math.random() * 4, 0.5); break; }
      for (const q of mist) { q.m.position.x += q.v * dt; if (q.m.position.x > 700) q.m.position.x -= 700; }
      for (const q of cloudsM) { q.m.position.x += q.v * dt; if (q.m.position.x > 1400) q.m.position.x -= 1400; }
      if (sunM) sunM.position.set(tr.x + 1500, -tr.y + 1500, -6500);
      for (const f of foam) { f.m.position.x += f.v * dt; if (f.m.position.x > f.w.x1 - 70) f.m.position.x = f.w.x0 + 70; }
      const wzt = S.waterAt(tr.x - 40); murkM.visible = !!wzt && S.wade > 0.1 && S.dirt > 0.08; if (murkM.visible) { const k = 0.6 + S.dirt; murkM.position.set(tr.x - 70, -wzt.y + 1.6, 10); murkM.scale.set(k * 1.7, 1, k); } // грязный грузовик мутит воду — и отмывается
      S.L.cans.forEach((cn, i) => { if (canM[i]) { canM[i].visible = !cn.got; canM[i].rotation.y = realT * 2; } });
      for (const wt of waterTop) wt.m.position.y = wt.y + Math.sin(realT * 1.7 + wt.y) * 1.2;
      // брызги грязи, воды и дым из трубы
      pAcc += dt; const play = mode === 'play' && S.state === 'play';
      if (play && pAcc > 0.03) {
        pAcc = 0;
        S.wheels.forEach((w, i) => {
          if (S.slip[i] > 110 && S.sunk[i] > 3 && Math.random() < 0.6) emit(blobs, w.x - 10, -w.y - WR * 0.4, (Math.random() < 0.5 ? -50 : 50) + (Math.random() - 0.5) * 20, [-110 - Math.random() * 240, 150 + Math.random() * 280, (Math.random() - 0.5) * 150], 4 + Math.random() * 6, 0.7).m.material.color.copy(A.C(SOILC[S.soil] || SOILC.mud));
          if ((S.soil === 'sand' || S.soil === 'scree') && S.sunk[i] > 2 && Math.abs(w.vx) > 80 && Math.random() < 0.5) emit(dustP, w.x - 24, -w.y - WR + 8, (Math.random() - 0.5) * 110, [-50 - Math.random() * 90 - w.vx * 0.12, 30 + Math.random() * 50, (Math.random() - 0.5) * 60], 10 + Math.random() * 9, 1.1); // пыль из-под колёс на песке
          const wz = S.waterAt(w.x); if (wz && w.y + WR > wz.y + 4 && Math.abs(w.vx) > 50 && Math.random() < 0.5) emit(drops, w.x + (Math.random() - 0.5) * WR, -wz.y, (Math.random() < 0.5 ? -50 : 50), [-w.vx * 0.3 + (Math.random() - 0.5) * 120, 120 + Math.random() * 200, (Math.random() - 0.5) * 160], 3 + Math.random() * 5, 0.55);
        });
        if (S.inMud === 0 && !S.wade && S.dirt > 0.3 && Math.abs(tr.vx) > 220 && Math.random() < 0.12) emit(blobs, tr.x + (Math.random() - 0.5) * c.len * 0.8, -tr.y - 20, Math.random() < 0.5 ? -47 : 47, [-tr.vx * 0.25, 30 + Math.random() * 60, (Math.random() - 0.5) * 40], 3 + Math.random() * 3, 0.6).m.material.color.copy(A.C(SOILC.mud)); // на дороге грязь отваливается комьями
        if (v.gasOn && Math.random() < (S.stuckT > 0.3 || sw.low ? 0.9 : 0.35)) { const e = P.wpt(tr, stackL[0], stackL[1]); emit(smoke, e[0], -e[1], -40, [-30 - Math.random() * 40 - tr.vx * 0.1, 60 + Math.random() * 50, (Math.random() - 0.5) * 30], 5 + Math.random() * 4, 0.9); }
      }
      fly(blobs, dt, 900, 0); fly(drops, dt, 900, 0); fly(smoke, dt, -40, 2.2); fly(dustP, dt, -15, 2.6);
    };
  }

  // ---------- звук ----------
  // ---------- звук: записи из папки snd (mp3), а не синтез кодом — площадки синтезированный звук не принимают ----------
  // мотор и чавканье грязи — петли, громкость и высота от езды; музыка — тихая петля; остальное — короткие звуки по событиям
  const SND = {}, LOOPS = ['engine', 'music'], SFX = ['mud1', 'mud2', 'mud3', 'mud4', 'click', 'on', 'off', 'no', 'buy', 'coin', 'can', 'thud', 'splash', 'win', 'fail', 'warn', 'hook', 'cp'];
  let AC = null, out = null, eng = null, mus = null, wasWet = false, mudNext = 0;
  const silent = () => muted || PG.mutedP || PG.ad || PG.paused || document.hidden;
  function loopOf(name, vol) { const b = SND[name]; if (!b || !AC) return null; const s = AC.createBufferSource(), g = AC.createGain(); s.buffer = b; s.loop = true; s.loopStart = 0.03; s.loopEnd = b.duration - 0.03; g.gain.value = vol; s.connect(g); g.connect(out); s.start(); return { s, g }; }
  function audio() {
    if (AC) { if (AC.state === 'suspended' && !document.hidden) AC.resume().catch(() => {}); return; }
    try { AC = new (window.AudioContext || window.webkitAudioContext)(); out = AC.createGain(); out.gain.value = silent() ? 0 : 1; out.connect(AC.destination); } catch (e) { AC = null; return; }
    if (location.protocol === 'file:') return; // страница открыта с диска: браузер не даст прочитать файлы звука — играем молча, без ошибок
    for (const n of LOOPS.concat(SFX)) {
      fetch('snd/' + n + '.mp3').then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(r.status))).then((ab) => new Promise((ok, no) => AC.decodeAudioData(ab, ok, no))).then((buf) => {
        SND[n] = buf; if (n === 'engine') eng = loopOf('engine', 0); else if (n === 'music') mus = loopOf('music', 0);
      }).catch(() => {}); // нет файла (страница открыта с диска) — просто без этого звука
    }
  }
  function sfx(n, vol = 1, rate = 1) { if (!AC || !SND[n] || silent()) return; try { const s = AC.createBufferSource(), g = AC.createGain(); s.buffer = SND[n]; s.playbackRate.value = rate; g.gain.value = vol; s.connect(g); g.connect(out); s.start(); } catch (e) { /* */ } }
  document.addEventListener('visibilitychange', () => { if (!AC) return; if (document.hidden) AC.suspend().catch(() => {}); else AC.resume().catch(() => {}); }); // свернул игру — тишина сразу, не ждём кадра
  function soundTick(inp) { // каждый кадр: общая громкость, мотор, грязь, музыка; страница спрятана — звук стоит совсем
    if (!AC) return; const t = AC.currentTime, q = silent(); out.gain.setTargetAtTime(q ? 0 : 1, t, 0.05);
    if (document.hidden && AC.state === 'running') AC.suspend().catch(() => {}); else if (!document.hidden && AC.state === 'suspended') AC.resume().catch(() => {});
    const drive = mode === 'play' && S.state === 'play' && !paused, wsp = Math.abs(S.wheels[0].w) * S.WR, gas = drive && inp.gas && S.fuel > 0;
    if (eng) { eng.s.playbackRate.setTargetAtTime(clamp(0.62 + 0.03 * S.cfg.b.eng + wsp / (sw.low ? 520 : 900) + (gas ? 0.16 : 0), 0.55, 1.9), t, 0.12); eng.g.gain.setTargetAtTime(drive ? 0.22 + (gas ? 0.2 : 0) : 0, t, 0.12); }
    const spin = drive && S.inMud > 0 ? clamp((wsp - Math.abs(S.truck.vx)) / 260 + (gas ? 0.25 : 0), 0, 1) : 0;
    if (spin > 0.12 && t > mudNext && !q) { sfx('mud' + (1 + ((Math.random() * 4) | 0)), 0.25 + 0.55 * spin, 0.85 + 0.3 * Math.random()); mudNext = t + 0.34 - 0.18 * spin; } // чавканье: колёса крутятся в грязи быстрее, чем едет грузовик
    if (mus) mus.g.gain.setTargetAtTime(drive ? 0.22 : 0.34, t, 0.6);
    const wet = drive && S.wade > 0; if (wet && !wasWet && Math.abs(S.truck.vx) > 60) sfx('splash', clamp(Math.abs(S.truck.vx) / 400, 0.35, 1)); wasWet = wet;
  }

  // ---------- управление ----------
  const TOG = ['awd', 'lock', 'low', 'soft'];
  function flip(k) { if (mode !== 'play' || paused || S.state !== 'play' || !(k === 'soft' ? S.cfg.b.ctis : S.cfg.b[k])) return; sw[k] = !sw[k]; sfx(sw[k] ? 'on' : 'off'); if (sw[k] && career) { save.tg = save.tg || {}; save.tg[k] = (save.tg[k] || 0) + 1; persist(); } if (coach === k || coach === 'pre:' + k) coach = ''; if (hold === k) hold = ''; }
  function setPart(k, v) {
    const nt = k === 'paint' ? T.n.paint[0] : T.n[k][optIdx(k, v)], bd = BD(), had = pend; tab = PARTS.find((q) => q[0] === k)[2]; note = nt;
    if (k === 'trailer' && v > 0 && (!bd.base || bd.axles !== 3)) { note = T.trNeed; sfx('no'); return; } // прицеп — только на длинную раму с тремя мостами
    if (!owns(k, v)) { pend = { k, v, t: realT }; newSim(); sfx('click'); return; } // не куплено — примеряем и предлагаем купить
    pend = null; if (bd[k] === v) { if (had) newSim(); return; } bd[k] = v; persist(); newSim(); sfx('click');
  }
  let goWarn = null; const rentable = (a) => a && !a.own && !a.opt && !a.cap && save.coins < a.price && a.price <= 1000 && !['base', 'axles', 'trailer', 'eng'].includes(a.k) && canAd() && !(rent && rent.sel === sel); // ролик — только за недорогую деталь; мощность покупается
  function press(id) {
    if (PG.pend && (PG.ad || !PG.pend.slow) && performance.now() - (PG.pend.t0 || 0) < 8000) return true; // идёт реклама; если ролик не открылся за 8 с — экран не держим
    if (mode === 'win' && career && res && !res.interDone && (id === 'menu' || id === 'nextc' || id === 'again') && pgCanInter()) { res.interDone = true; pgInter(() => press(id)); return true; }
    if (id === 'go' && mode === 'menu' && sel >= 0 && capNow() < minOf(sel)) { goWarn = { sel, t: realT }; sfx('no'); return true; } // большой заказ: столько груза не влезет — не пускаем
    if (id === 'go' && mode === 'menu' && sel >= 0 && !(goWarn && goWarn.sel === sel && realT - goWarn.t < 8)) { const a = advice(); if (a && !a.opt) { goWarn = { sel, t: realT }; sfx('no'); return true; } } // механик сказал «без этого не взять»: первое нажатие — предупредить, второе — ехать
    if (id === 'go') start(false); else if (id === 'cont') start(true); else if (id === 'gar') toGarage(mode === 'play'); else if (id === 'again') start(false);
    else if (id === 'menu') toMenu(mode === 'garage' && career); else if (id === 'pause') { if (mode === 'play' && S.state === 'play') paused = true; } else if (id === 'resume') paused = false; else if (id === 'quit') toMenu(true);
    else if (id === 'towad') adReward(() => tow(true), 'free_tow'); else if (id === 'x2') adReward(() => { if (res && !res.doubled) { res.doubled = true; save.coins += res.total; persist(); sfx('buy'); } }, 'double_pay');
    else if (id === 'adv') { const a = advice(); if (a && (a.own || save.coins >= a.price)) { if (!a.own) { save.coins -= a.price; pgEv('part_bought', { part: a.k, level: a.v, price: a.price, coins_left: save.coins, where: 'mechanic', step_id: stepOf(sel >= 0 ? sel : cur).step_id }); (save.own[a.k] = save.own[a.k] || []).push(a.v); } save.build[a.k] = a.v; if (rent && rent.k === a.k) rent = null; if (sel >= 0 && M.CONTRACTS[sel].big) nlogs = Math.max(minOf(sel), capNow()); persist(); newSim(); sfx('buy'); } else sfx('no'); }
    else if (id === 'rent') { const a = advice(); if (a && rentable(a)) adReward(() => { rent = { k: a.k, v: a.v, sel }; pgEv('part_rented', Object.assign(stepOf(sel), { part: a.k, level: a.v, price: a.price, coins: save.coins })); newSim(); sfx('buy'); }, 'rent_part'); else sfx('no'); }
    else if (id === 'adcoins') adReward(() => { if (pend) { save.coins = Math.max(save.coins, priceOf(pend.k, pend.v)); persist(); sfx('coin'); } }, 'top_up');
    else if (id === 'poly') { career = false; cur = -1; sel = -1; toGarage(false); } else if (id === 'buy') { if (pend && realT - (pend.t || 0) > 0.25) buy(); } else if (id === 'unsel') { sel = -1; newSim(); }
    else if (id.slice(0, 4) === 'reg:') { reg = +id.slice(4); if (M.REGIONS[reg].big) { save.seen = save.seen || {}; if (!save.seen.big) { save.seen.big = 1; persist(); } } sfx('click'); }
    else if (id.slice(0, 2) === 'c:') { const i = +id.slice(2); if (unlocked(i)) { if (rent && rent.sel !== i) rent = null; sel = i; nlogs = defLoad(i); newSim(); sfx('click'); } else sfx('no'); }
    else if (id === 'lg-' || id === 'lg+') { nlogs = Math.min(capNow(), Math.max(minOf(sel), nlogs + (id === 'lg+' ? 1 : -1))); newSim(); sfx('click', 0.7); }
    else if (id === 'lg=') { nlogs = capNow(); newSim(); sfx('click', 0.8, 1.15); }
    else if (id === 'tow') tow(false);
    else if (id === 'nextc') { const c0 = M.CONTRACTS[cur], nb = M.CONTRACTS.findIndex((q, j) => q.big && unlocked(j) && !(save.stars[q.id] > 0)), nx = !c0.big && M.CONTRACTS[cur + 1] && !M.CONTRACTS[cur + 1].big ? cur + 1 : nb; toMenu(); if (nx >= 0 && M.CONTRACTS[nx] && unlocked(nx)) { sel = nx; reg = Math.max(0, M.REGIONS.findIndex((r) => nx >= r.from && nx < r.from + r.n)); nlogs = defLoad(nx); newSim(); } sfx('click'); } // сразу карточка следующего заказа: меню и гараж новичку не нужны
    else if (id === 'rescue') { if (mode === 'play') { if (S.state === 'dead') S.respawn(); else S.rescue(); } } else if (id === 'retry') { if (S.state === 'dead') S.respawn(); } else if (id === 'mute') muted = !muted;
    else if (id[0] === 'p') { const [, k, v] = id.split(':'); setPart(k, +v); } else if (id.slice(0, 4) === 'tab:') { tab = +id.slice(4); sfx('click', 0.7); } else if (TOG.includes(id)) flip(id); else return false;
    return true;
  }
  addEventListener('keydown', (e) => {
    if (e.repeat) return; keys[e.code] = true; audio();
    if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) e.preventDefault();
    if (mode === 'play') {
      if (career && ['KeyP', 'KeyR', 'KeyG'].includes(e.code)) { if (S.state === 'play') paused = !paused; return; }
      if (paused) { if (e.code === 'Enter') paused = false; return; }
      if (e.code === 'Digit1' || e.code === 'KeyQ') flip('awd'); else if (e.code === 'Digit2' || e.code === 'KeyE') flip('lock'); else if (e.code === 'Digit3' || e.code === 'ShiftLeft') flip('low'); else if (e.code === 'Digit4') flip('soft');
      else if (!career && (e.code === 'KeyR' || (e.code === 'Enter' && S.state === 'dead'))) { if (S.state === 'dead') S.respawn(); else S.rescue(); } else if (!career && e.code === 'KeyG') toGarage(true);
    }
    else if (e.code === 'Enter') { if (mode === 'menu') { if (sel >= 0) start(false); } else if (mode === 'garage') { if (!career) start(!!resume); } else if (mode === 'win' && career) toMenu(); else if (mode !== 'play') start(false); }
  });
  addEventListener('keyup', (e) => { keys[e.code] = false; });
  const hit = (x, y) => buttons.find((b) => x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h);
  const held = (id) => { for (const p of ptrs.values()) if (p === id) return true; return false; };
  cv.addEventListener('pointerdown', (e) => { audio(); try { cv.setPointerCapture(e.pointerId); } catch (er) { /* */ } const b = hit(e.clientX, e.clientY); if (b && !press(b.id)) ptrs.set(e.pointerId, b.id); });
  const up = (e) => ptrs.delete(e.pointerId);
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up); cv.addEventListener('contextmenu', (e) => e.preventDefault());
  function input() {
    const k = keys;
    return { gas: !!(k.ArrowRight || k.KeyD) || held('gas'), brake: !!(k.ArrowLeft || k.KeyA) || held('brake'), winch: !!(k.Space || k.KeyW || k.ArrowUp) || held('winch'), awd: sw.awd, lock: sw.lock, low: sw.low, soft: sw.soft };
  }

  // ---------- рисование поверх ----------
  function lines(t, mw, px, wt = 800) { font(px, wt); const out = []; let cur = ''; for (const w of t.split(' ')) { const q = cur ? cur + ' ' + w : w; if (ctx.measureText(q).width > mw && cur) { out.push(cur); cur = w; } else cur = q; } if (cur) out.push(cur); return out; }
  function bubble(t, y, col = 'rgba(0,0,0,0.5)', cx = W / 2, mw = Math.min(W - 40, 620), pxo) { const px = pxo || (Math.min(W, H2) < 430 ? 15 : 18), L = lines(t, mw - 30, px), w = Math.min(mw, Math.max(...L.map((q) => ctx.measureText(q).width)) + 34), h = L.length * (px + 6) + 16; ctx.fillStyle = col; rr(cx - w / 2, y, w, h, 16); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; L.forEach((q, i) => ctx.fillText(q, cx, y + 8 + (px + 6) * (i + 0.5), w - 20)); return h; }
  function btn(b, txt, col, on, px) {
    ctx.globalAlpha = on ? 0.97 : 0.78; ctx.fillStyle = 'rgba(0,0,0,0.25)'; rr(b.x, b.y + 4, b.w, b.h, 14); ctx.fill(); ctx.fillStyle = col; rr(b.x, b.y + (on ? 3 : 0), b.w, b.h, 14); ctx.fill();
    ctx.globalAlpha = 1; ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; font(px || Math.round(Math.min(b.h * 0.44, b.w * 0.34, (b.w * 1.45) / Math.max(3, txt.length))));
    fillC(txt, b.x + b.w / 2, b.y + b.h / 2 + (on ? 3 : 0) + 1, b.w - 8);
  }
  const B = (id) => buttons.find((b) => b.id === id);
  function ring(id) { const b = id && B(id); if (!b) return; const p = 0.5 + 0.5 * Math.sin(realT * 6), d = 4 + 4 * p; ctx.strokeStyle = `rgba(255,214,0,${0.6 + 0.4 * p})`; ctx.lineWidth = 4 + 2 * p; rr(b.x - d, b.y - d, b.w + d * 2, b.h + d * 2, 16 + d); ctx.stroke(); } // жёлтое пульсирующее кольцо: «нажми сюда»
  const land = () => W > H2 * 1.15;

  // общая рамка гаража и списка заказов: слева (или сверху) грузовик, справа (или снизу) панель
  function panel(title) {
    const L = land(), px = L ? Math.max(240, W * 0.38) : 0, pw = W - px - 10, top = L ? 8 : Math.round(H2 * 0.33);
    ctx.fillStyle = '#fffdf7'; rr(px + (L ? 0 : 8), top, L ? pw : W - 16, H2 - top - 8, 18); ctx.fill();
    buttons = [{ id: 'mute', x: 10, y: 10, w: 44, h: 44 }];
    const mb = buttons[0]; ctx.fillStyle = 'rgba(0,0,0,0.34)'; rr(mb.x, mb.y, mb.w, mb.h, 12); ctx.fill(); ctx.fillStyle = '#fff'; font(21); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; fillC(muted ? '🔇' : '🔊', mb.x + 22, mb.y + 23);
    const small = H2 - top < 500; ctx.fillStyle = '#fff'; ctx.strokeStyle = 'rgba(0,0,0,0.35)'; ctx.lineWidth = 4; font(small ? 20 : 26); ctx.textAlign = 'left'; ctx.strokeText(title, 64, 33); ctx.fillText(title, 64, 33);
    if (career) { const t = '¤ ' + save.coins; font(18); const tw = ctx.measureText(String(save.coins)).width + 48, cx = (L ? px : W) - tw - 10; ctx.fillStyle = 'rgba(0,0,0,0.5)'; rr(cx, 12, tw, 38, 19); ctx.fill(); ctx.fillStyle = '#ffe082'; ctx.textAlign = 'center'; fillC(t, cx + tw / 2, 32); } // монеты
    ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.strokeStyle = 'rgba(0,0,0,0.3)'; ctx.lineWidth = 3; font(11, 800); ctx.textAlign = 'left'; ctx.strokeText(`${T.ver} ${VER}`, 12, 66); ctx.fillText(`${T.ver} ${VER}`, 12, 66);
    return { L, px, x0: px + (L ? 12 : 20), ww: (L ? pw : W - 16) - 24, top, small, view: { px: L ? px / 2 : W / 2, py: L ? H2 * 0.56 : top * 0.62, zw: L ? px : W, zh: L ? H2 : top } };
  }
  const statsOf = (c) => { const pr = c.PR[c.b.press]; return [c.clear / PX, c.ford / PX, (100 * c.tqLow / c.WR) / (264000 / 27), ((c.tank / (0.1 + c.burn * pr.bn * M.F_AWD)) * c.spHigh * pr.sp * c.WR * 0.8) / PX, M.payT(c)]; };
  function drawGarage() {
    const pn = panel(T.garage), { top, small, L } = pn, c = S.cfg, bd = BD(); let { x0, ww, view } = pn;
    // покупка там же, где нажал: первое нажатие — примерка, кнопка детали сама становится зелёной «Купить»; второе нажатие по ней — покупка
    const pb = career && pend ? pend : null, prc = pb ? priceOf(pb.k, pb.v) : 0, okB = !!pb && save.coins >= prc, nearB = !!pb && !okB && save.coins >= prc / 2 && canAd(), gn = pb ? gainNote(pb.k, pb.v) : '', noteT = !pb ? note : (gn ? gn + ' ' : '') + (okB ? (gn ? '' : T.tapBuy + ' ') : (nearB ? T.tapAd(prc - save.coins) : T.tapNo(prc - save.coins)) + ' ') + note; shownNote = noteT; // есть строка про заработок — «нажми ещё раз» не повторяем: на кнопке и так «Купить»
    const buyBtn = (b, big) => { b.id = okB ? 'buy' : nearB ? 'adcoins' : b.id; ctx.fillStyle = okB ? '#43a047' : '#f9a825'; rr(b.x, b.y, b.w, b.h, 10); ctx.fill(); ctx.fillStyle = 'rgba(0,0,0,0.16)'; rr(b.x, b.y + b.h - 5, b.w, 5, 4); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; const t1 = okB ? T.buyPart : '▶ ' + T.topUp; font(Math.min(big, b.h * 0.34, (b.w * 1.55) / t1.length), 900); ctx.fillText(t1, b.x + b.w / 2, b.y + b.h * 0.34, b.w - 4); font(Math.min(big - 1, b.h * 0.3), 900); fillC('¤ ' + (okB ? prc : prc - save.coins), b.x + b.w / 2, b.y + b.h * 0.68, b.w - 4); };
    // сводка: четыре числа, которые сравниваешь с указателями на дороге. При примерке видно, что изменится: зелёное — лучше, красное — хуже
    const sv = statsOf(c), s0 = pend ? statsOf(M.spec(bd)) : sv, sf = [(v) => fmt(v, 2) + ' ' + T.m, (v) => fmt(v, 2) + ' ' + T.m, (v) => Math.round(v) + '%', (v) => Math.round(v) + ' ' + T.m, (v) => fmt(v) + ' ' + T.tn];
    const NM = [T.sClear, T.sFord, T.sPull, T.sRange, T.sLoad];
    const stat = (i, cx, yy, mw, f1, f2, dy) => { const d = sv[i] - s0[i], ch = Math.abs(d) > Math.abs(s0[i]) * 0.004; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#78909c'; font(f1, 800); ctx.fillText(NM[i], cx, yy + 8, mw); const low = i === 1 && !!deepFord() && (career ? sel >= 0 || cur >= 0 : true); ctx.fillStyle = low ? '#c62828' : !ch ? '#263238' : d > 0 ? '#2e7d32' : '#c62828'; font(f2); fillC(sf[i](sv[i]) + (ch ? (d > 0 ? ' ▲' : ' ▼') : low ? ' ⚠' : ''), cx, yy + dy, mw + 1); };
    const tabBtn = (i, x, yy, w, h) => { const n = T.tabs[i], b = { id: 'tab:' + i, x, y: yy, w, h }, on = tab === i; buttons.push(b); ctx.fillStyle = on ? '#37474f' : '#eceff1'; rr(b.x, b.y, b.w, b.h, 10); ctx.fill(); ctx.fillStyle = on ? '#fff' : '#546e7a'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; font(Math.min(16, (w * 1.7) / n.length), 900); ctx.fillText(n, b.x + w / 2, b.y + h / 2 + 1, w - 6); };
    let y = top + 10;
    if (L) { // телефон лёжа: числа и подсказка — слева под грузовиком, вкладки — столбиком, а вся высота справа отдана крупным кнопкам деталей
      const cw = pn.px - 16, nl0 = lines(noteT, cw - 20, 12, 700).slice(0, 5), ch = 78 + (nl0.length ? nl0.length * 15 + 8 : 0), cy0 = H2 - 8 - ch;
      ctx.fillStyle = 'rgba(255,253,247,0.95)'; rr(8, cy0, cw, ch, 14); ctx.fill();
      for (let i = 0; i < 5; i++) stat(i, 8 + (cw / 3) * ((i % 3) + 0.5), cy0 + 6 + Math.floor(i / 3) * 35, cw / 3 - 8, 10.5, 16, 24);
      ctx.fillStyle = '#546e7a'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; font(12, 700); nl0.forEach((q, i) => ctx.fillText(q, 18, cy0 + 86 + i * 15, cw - 20));
      const zh = Math.max(110, (cy0 - 40) * 1.2), zg = Math.min(pn.px / (c.len + (c.tr ? c.tr.len : 0) + 190), zh / 330); view = { px: pn.px / 2, py: Math.max(52, Math.min(56 + (cy0 - 56) * 0.58, cy0 - 10 - 78 * zg)), zw: pn.px, zh };
      const tw = Math.min(96, ww * 0.21), n = T.tabs.length, th = (H2 - 8 - 10 - y - (n - 1) * 6) / n;
      for (let i = 0; i < n; i++) tabBtn(i, x0, y + i * (th + 6), tw, th);
      x0 += tw + 10; ww -= tw + 10;
    } else {
      const sw4 = ww / 5; for (let i = 0; i < 5; i++) stat(i, x0 + sw4 * (i + 0.5), y, sw4 - 4, small ? 10 : 12, small ? 14 : 17, small ? 26 : 30);
      y += small ? 40 : 48;
      const th = small ? 32 : 38, tw = (ww - 18) / 4; // вкладки
      for (let i = 0; i < 4; i++) tabBtn(i, x0 + i * (tw + 6), y, tw, th);
      y += th + 8;
    }
    const goH = small ? 46 : 56, noteH = L ? 0 : small ? 62 : 76, fine = !career || (save.stars.creek || 0) > 0, rows = PARTS.filter((q) => q[2] === tab && (fine || !['press', 'susp', 'gear'].includes(q[0]))), rh = Math.min(L ? 60 : 52, (H2 - 8 - y - goH - noteH - (L ? 14 : 22)) / 5), lw = Math.min(124, ww * 0.31);
    for (const [k, vals] of rows) {
      if (k === 'paint') { // краска — кружки с цветом
        const bw = Math.min(rh - 6, (ww - 5 * 8 - 64) / 6); // справа от кружков — место под кнопку «Купить»
        vals.forEach((v, i) => { const b = { id: `p:paint:${v}`, x: x0 + i * (bw + 8), y: y + 3, w: bw, h: bw }, own = owns(k, v); buttons.push(b); ctx.globalAlpha = own ? 1 : 0.45; ctx.fillStyle = PAINTS[v][0]; rr(b.x, b.y, bw, bw, bw / 2); ctx.fill(); ctx.globalAlpha = 1; if (bd.paint === v || (pend && pend.k === k && pend.v === v)) { ctx.strokeStyle = bd.paint === v ? '#263238' : '#1e88e5'; ctx.lineWidth = 4; rr(b.x - 3, b.y - 3, bw + 6, bw + 6, bw / 2 + 3); ctx.stroke(); } });
        if (pb && pb.k === 'paint' && (okB || nearB)) { const qx = x0 + 6 * (bw + 8), b = { id: 'p:paint:' + pb.v, x: qx, y: y + 3, w: x0 + ww - qx, h: rh - 6 }; buttons.push(b); buyBtn(b, 13); }
        y += rh; continue;
      }
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#37474f'; font(Math.min(L ? 17 : 16, rh * 0.36, (lw * 1.75) / T.p[k].length), 900); ctx.fillText(T.p[k], x0, y + rh / 2, lw - 6);
      if (vals.length > 4) { // ступени (форсировка): полоски и кнопки «−» «+»; следующая ступень — за монеты
        const n = vals.length - 1, lv = bd[k], pv = pend && pend.k === k ? pend.v : lv, nx = Math.min(n, lv + 1), bq = Math.min(58, Math.max(44, rh + 4)), bx = x0 + lw, pw = ww - lw - bq * 2 - 14;
        for (let i = 0; i < n; i++) { ctx.fillStyle = i < lv ? '#fb8c00' : i < pv ? '#42a5f5' : '#cfd8dc'; rr(bx + (i * pw) / n, y + rh * 0.3, pw / n - 4, rh * 0.4, 5); ctx.fill(); }
        const bm = { id: `p:${k}:${Math.max(0, lv - 1)}`, x: x0 + ww - bq * 2 - 6, y: y + 3, w: bq, h: rh - 6 }, bp = { id: `p:${k}:${nx}`, x: x0 + ww - bq, y: y + 3, w: bq, h: rh - 6 }, own = owns(k, nx), top2 = lv >= n; buttons.push(bm, bp);
        ctx.fillStyle = lv > 0 ? '#cfd8dc' : '#eceff1'; rr(bm.x, bm.y, bm.w, bm.h, 10); ctx.fill(); ctx.fillStyle = lv > 0 ? '#455a64' : '#b0bec5'; ctx.textAlign = 'center'; font(Math.min(24, rh * 0.5)); ctx.fillText('−', bm.x + bq / 2, bm.y + bm.h / 2);
        if (pb && pb.k === k && !own && !top2 && (okB || nearB)) buyBtn(bp, 13);
        else { ctx.fillStyle = top2 ? '#eceff1' : pend && pend.k === k ? '#42a5f5' : '#fb8c00'; rr(bp.x, bp.y, bp.w, bp.h, 10); ctx.fill(); ctx.fillStyle = top2 ? '#b0bec5' : '#fff'; font(Math.min(own || top2 ? 24 : 17, rh * 0.5)); ctx.fillText(top2 ? '✓' : '+', bp.x + bq / 2, bp.y + bm.h / 2 + (own || top2 ? 0 : -7));
          if (!own && !top2) { font(Math.min(12, rh * 0.26), 900); fillC('¤ ' + priceOf(k, nx), bp.x + bq / 2, bp.y + bm.h / 2 + 9, bq - 4); } }
        y += rh; continue;
      }
      const bw = (ww - lw - (vals.length - 1) * 6) / vals.length;
      vals.forEach((v, i) => {
        const b = { id: `p:${k}:${v}`, x: x0 + lw + i * (bw + 6), y: y + 3, w: bw, h: rh - 6 }, on = bd[k] === v, own = owns(k, v), pd = pend && pend.k === k && pend.v === v; buttons.push(b);
        if (pd && pb && (okB || nearB)) { buyBtn(b, L ? 16 : 14); return; }
        ctx.fillStyle = on ? '#fb8c00' : own ? '#cfd8dc' : '#eceff1'; rr(b.x, b.y, b.w, b.h, 10); ctx.fill(); if (pd) { ctx.strokeStyle = '#1e88e5'; ctx.lineWidth = 3; rr(b.x + 1.5, b.y + 1.5, b.w - 3, b.h - 3, 9); ctx.stroke(); }
        ctx.fillStyle = on ? '#fff' : own ? '#455a64' : '#90a4ae'; ctx.textAlign = 'center'; font(Math.min(L ? 17 : 15, rh * 0.36, (bw * 1.6) / Math.max(3, T.o[k][i].length)), 900); ctx.fillText(T.o[k][i], b.x + b.w / 2, b.y + b.h / 2 + (own ? 1 : -rh * 0.14), b.w - 6);
        if (!own) { ctx.fillStyle = '#ef6c00'; font(Math.min(L ? 14 : 12, rh * 0.26), 900); fillC('¤ ' + priceOf(k, v), b.x + b.w / 2, b.y + b.h / 2 + Math.max(9, rh * 0.2), b.w - 4); } // цена некупленной детали
      });
      y += rh;
    }
    const gy = H2 - 8 - goH - 10, lhN = small ? 15 : 18, nl = lines(noteT, ww - 8, small ? 12 : 14, 700).slice(0, clamp(Math.floor((gy - y - 10) / lhN), 4, 6)), ny = Math.max(y + 4, gy - Math.max(noteH, nl.length * lhN + 6)); ctx.fillStyle = '#546e7a'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; if (!L) nl.forEach((q, i) => ctx.fillText(q, x0, ny + 10 + i * (small ? 15 : 18), ww));
    const fs = small ? 15 : 18;
    if (career) {
      { const b1 = { id: 'menu', x: x0, y: gy, w: ww, h: goH }; buttons.push(b1); btn(b1, '◀ ' + T.toMenu, pb ? '#78909c' : '#43a047', false, small ? 18 : 22); }
    } else {
      const mw = Math.min(120, ww * 0.3), b0 = { id: 'menu', x: x0, y: gy, w: mw, h: goH }; buttons.push(b0); btn(b0, '◀ ' + T.menu, '#78909c', false, fs - 2);
      if (resume) { const hw = (ww - mw - 16) / 2, b1 = { id: 'cont', x: x0 + mw + 8, y: gy, w: hw, h: goH }, b2 = { id: 'go', x: x0 + mw + 16 + hw, y: gy, w: hw, h: goH }; buttons.push(b1, b2); btn(b1, '▶ ' + T.cont, '#43a047', false, fs - 1); btn(b2, '↺ ' + T.anew, '#78909c', false, fs - 1); }
      else { const b1 = { id: 'go', x: x0 + mw + 8, y: gy, w: ww - mw - 8, h: goH }; buttons.push(b1); btn(b1, '▶ ' + T.go, '#43a047', false, small ? 20 : 24); }
    }
    return view;
  }
  // заказы: список, а по нажатию — карточка заказа: что на дороге, какой груз и сколько взять, сколько заплатят
  function drawMenu() {
    const { x0, ww, top, small, view, L, px: PXL } = panel(T.menu), CT = M.CONTRACTS, goH = small ? 46 : 56, gy = H2 - 8 - goH - 10, fs = small ? 15 : 18; let y = top + 12;
    ctx.textBaseline = 'middle';
    if (sel < 0) {
      // районы: стоя — две вкладки над списком, лёжа — под грузовиком слева, чтобы строки заказов остались крупными
      const RG = M.REGIONS, R = RG[reg] || RG[0], nr = RG.length;
      RG.forEach((q, k) => { const lock = !unlocked(q.from), on = k === reg, bw = L ? (PXL - 16 - 6 * (nr - 1)) / nr : (ww - 6 * (nr - 1)) / nr, b = L ? { id: 'reg:' + k, x: 8 + k * (bw + 6), y: H2 - 54, w: bw, h: 46 } : { id: 'reg:' + k, x: x0 + k * (bw + 6), y, w: bw, h: 36 }; buttons.push(b);
        ctx.fillStyle = on ? '#37474f' : L ? 'rgba(255,253,247,0.94)' : '#eceff1'; rr(b.x, b.y, b.w, b.h, 11); ctx.fill(); ctx.fillStyle = on ? '#fff' : '#546e7a'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; font(Math.min(16, b.w * 0.135), 900); fillC(`${k + 1}. ${rName(k)}${lock ? ' 🔒' : ''}`, b.x + b.w / 2, b.y + b.h / 2 + 1, b.w - 10); });
      if (!L) y += 42;
      const bi = RG.findIndex((q) => q.big); if (bi >= 0 && bi !== reg && unlocked(RG[bi].from) && !(save.seen && save.seen.big)) ring('reg:' + bi); // открылись большие заказы — вкладка мигает, пока её не откроют
      const rh = Math.min(62, (gy - y - 8) / R.n);
      CT.slice(R.from, R.from + R.n).forEach((c, j) => { const i = R.from + j;
        const ok = unlocked(i), st = save.stars[c.id] || 0, b = { id: 'c:' + i, x: x0, y: y + (rh * j) + 2, w: ww, h: rh - 5 }; buttons.push(b);
        ctx.fillStyle = ok ? '#eceff1' : '#f5f5f5'; rr(b.x, b.y, b.w, b.h, 12); ctx.fill();
        ctx.fillStyle = ok ? '#fb8c00' : '#cfd8dc'; ctx.beginPath(); ctx.arc(b.x + 22, b.y + b.h / 2, Math.min(15, b.h * 0.34), 0, 7); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; font(15); fillC(ok ? String(i + 1) : '🔒', b.x + 22, b.y + b.h / 2 + 1);
        if (L) { // лёжа панель широкая, а строки низкие: название и цена в одну строку, зато крупно
          const pt = (c.min ? T.minC(c.min) + ' · ' : '') + `¤ ${c.pay} ${T.perLog}`, cy = b.y + b.h / 2 + 1; font(Math.min(14, rh * 0.34), 800); const tw = ctx.measureText(pt).width + 6, px = b.x + ww - 92 - tw;
          ctx.textAlign = 'left'; ctx.fillStyle = ok ? '#ef6c00' : '#cfd8dc'; fillC(pt, px, cy, tw); ctx.globalAlpha = ok ? 1 : 0.4; cargoIcon(c.cargo, px - 13, cy, Math.min(9, rh * 0.2)); ctx.globalAlpha = 1;
          ctx.textAlign = 'left'; ctx.fillStyle = ok ? '#263238' : '#b0bec5'; font(Math.min(18, rh * 0.42), 900); ctx.fillText(cName(c), b.x + 46, cy, px - 26 - (b.x + 46));
        } else {
          ctx.textAlign = 'left'; ctx.fillStyle = ok ? '#263238' : '#b0bec5'; font(Math.min(17, rh * 0.3), 900); ctx.fillText(cName(c), b.x + 46, b.y + b.h * 0.34, ww - 136);
          ctx.globalAlpha = ok ? 1 : 0.4; cargoIcon(c.cargo, b.x + 53, b.y + b.h * 0.7, Math.min(8, rh * 0.14)); ctx.globalAlpha = 1;
          ctx.fillStyle = ok ? '#ef6c00' : '#cfd8dc'; font(Math.min(13, rh * 0.24), 800); fillC((c.min ? T.minC(c.min) + ' · ' : '') + `¤ ${c.pay} ${T.perLog}`, b.x + 66, b.y + b.h * 0.7, ww - 160);
        }
        for (let k = 0; k < 3; k++) star5(b.x + ww - 74 + k * 25, b.y + b.h / 2, 10.5, k < st ? '#ffc107' : '#cfd8dc');
      });
      const gi = M.CONTRACTS.findIndex((c, i) => i < GUIDE_N && unlocked(i) && !(save.stars[c.id] > 0)); if (gi >= R.from && gi < R.from + R.n) ring('c:' + gi);
      const hw = (ww - 8) * 0.42, b1 = { id: 'gar', x: x0, y: gy, w: hw, h: goH }, b2 = { id: 'poly', x: x0 + hw + 8, y: gy, w: ww - hw - 8, h: goH }; buttons.push(b1, b2); btn(b1, '🔧 ' + T.garage, '#fb8c00', false, fs); btn(b2, T.poly, '#78909c', false, Math.min(fs - 2, (b2.w * 1.75) / T.poly.length));
    } else {
      const c = CT[sel], cap = M.capOf(S.cfg, c.cargo), n = S.cargo0, CG = M.CARGO[c.cargo], tiny = H2 < 330, adv = advice(); // tiny — телефон лёжа в окне площадки: всё в одну колонку покороче
      ctx.textAlign = 'left'; ctx.fillStyle = '#263238'; font(small ? 19 : 23); ctx.fillText(`${sel + 1}. ${cName(c)}`, x0, y + 14, ww); y += small ? 32 : 38;
      // что на дороге: значки по указателям маршрута
      const chips = [], badC = new Set(), df = deepFord(), top = {}; for (const sg of S.L.signs) { const key = sg.kind === 'soil' ? 's:' + soilK(sg.val) : sg.kind === 'climb' ? (sg.val < 0 ? 'down' : 'up') : sg.kind, o = top[key], rank = sg.kind === 'soil' ? soilDir(sg.val) * soilDir(sg.val) + (soilDir(sg.val) > 0 ? 1 : 0) : sg.kind === 'ford' ? fordPx(sg) : Math.abs(sg.val) || 0; if (!o) { top[key] = { sg, rank, bad: tooDeep(sg) }; chips.push(key); } else { o.bad = o.bad || tooDeep(sg); if (rank > o.rank) { o.sg = sg; o.rank = rank; } } }
      for (let i = 0; i < chips.length; i++) { const o = top[chips[i]]; chips[i] = signT(o.sg); if (o.bad) badC.add(chips[i]); }
      if (c.min) { const t = T.minC(c.min); chips.unshift(t); if (cap < c.min) badC.add(t); } // большой заказ: минимум груза
      if (tiny && adv) chips.length = 0; // на низком экране совет механика важнее значков дороги
      let cx = x0; font(small ? 11 : 13, 800); const chH = small ? 22 : 25; for (const t of chips) { const tw = ctx.measureText(t).width + 18; if (cx + tw > x0 + ww) { if (tiny) break; cx = x0; y += chH + 4; } ctx.fillStyle = badC.has(t) ? '#c62828' : '#eceff1'; rr(cx, y, tw, chH, 12); ctx.fill(); ctx.fillStyle = badC.has(t) ? '#fff' : '#455a64'; ctx.fillText(t, cx + 9, y + chH / 2 + 1); cx += tw + 6; }
      if (chips.length) y += chH + (small ? 8 : 14); // что поставить: одна деталь, цена и кнопка — в гараж идти не обязательно
      if (adv) {
        const can = adv.own || save.coins >= adv.price, rnt = !can && rentable(adv), bhA = tiny ? 28 : small ? 34 : 40, col = adv.opt ? '#ef6c00' : '#c62828', wl = lines(`${T.mech}: ${adv.why}.` + (can || rnt ? '' : ' ' + T.needC(partName(adv.k, adv.v), adv.price, save.coins)), ww - 20, small ? 12 : 13, 800).slice(0, tiny ? (can || rnt ? 1 : 2) : 3), lhA = small ? 15 : 17, wh = wl.length * lhA + 12 + (can || rnt ? bhA + (tiny ? 12 : 8) : 0);
        ctx.fillStyle = adv.opt ? '#fff3e0' : '#ffebee'; rr(x0, y - 4, ww, wh, 10); ctx.fill(); ctx.fillStyle = col; ctx.textAlign = 'left'; wl.forEach((q, i) => fillC(q, x0 + 10, y + 9 + i * lhA, ww - 20));
        if (can) { const bA = { id: 'adv', x: x0 + 10, y: y + wl.length * lhA + (tiny ? 10 : 6), w: ww - 20, h: bhA }; buttons.push(bA); btn(bA, adv.own ? `${T.fitPart}: ${partName(adv.k, adv.v)}` : `${T.buyPart}: ${partName(adv.k, adv.v)} — ¤ ${adv.price}`, '#43a047', false, small ? 14 : 16); ctx.textAlign = 'left'; }
        else if (rnt) { const bR = { id: 'rent', x: x0 + 10, y: y + wl.length * lhA + (tiny ? 10 : 6), w: ww - 20, h: bhA }; buttons.push(bR); btn(bR, `▶ ${T.rent(partName(adv.k, adv.v))}`, '#f9a825', false, small ? 14 : 16); ctx.textAlign = 'left'; } // нет денег на недорогую деталь — ролик, и она стоит на один рейс
        y += wh + (small ? 4 : 8);
      } else if (df) { // брод глубже, чем берёт сборка, а в списке заказа этого нет (полигон или своя сборка)
        const fx = fixText(fordFix(fordPx(df))), wl = lines(`${T.deep(fmt(df.val), fmt(S.cfg.ford / PX, 2))}. ${fx ? T.deepFix + ': ' + fx + '.' : ''}`, ww - 20, small ? 12 : 13, 800).slice(0, 3), wh = wl.length * (small ? 15 : 17) + 12;
        ctx.fillStyle = '#ffebee'; rr(x0, y - 4, ww, wh, 10); ctx.fill(); ctx.fillStyle = '#c62828'; wl.forEach((q, i) => ctx.fillText(q, x0 + 10, y + 9 + i * (small ? 15 : 17), ww - 20)); y += wh + (small ? 4 : 8);
      } else { ctx.fillStyle = '#2e7d32'; font(small ? 12 : 13, 800); ctx.fillText('✓ ' + T.ready, x0, y + 5, ww); y += small ? 18 : 22; }
      if (tiny) y -= 6; cargoIcon(c.cargo, x0 + 13, y + 22, 13); ctx.fillStyle = '#37474f'; font(small ? 15 : 17, 900); ctx.fillText(`${T.cg[c.cargo]}: ${n} ${T.of} ${cap}`, x0 + 34, y + 14, ww - 216);
      ctx.fillStyle = '#78909c'; font(small ? 11 : 12, 800); const payT = M.payT(S.cfg), byW = n >= cap && cap < M.spaceOf(S.cfg, c.cargo); ctx.fillText(`${T.wt} ${fmt(n * CG.m)} ${T.of} ${fmt(payT)} ${T.tn}`, x0 + 34, y + 33, ww - 216);
      const lgH = tiny ? 36 : 44, bm = { id: 'lg-', x: x0 + ww - 116, y, w: 52, h: lgH }, bp = { id: 'lg+', x: x0 + ww - 56, y, w: 52, h: lgH }; const bx = { id: 'lg=', x: x0 + ww - 176, y, w: 52, h: lgH }; buttons.push(bm, bp, bx); btn(bm, '−', n > 1 ? '#546e7a' : '#cfd8dc', false, 26); btn(bp, '+', n < cap ? '#546e7a' : '#cfd8dc', false, 26); btn(bx, T.mx, n < cap ? '#2e7d32' : '#cfd8dc', false, 14); y += tiny ? 40 : small ? 50 : 56; ctx.textAlign = 'left'; // «макс» — полный кузов одним нажатием: с прицепом это два с лишним десятка штук
      const nl = (gy - y > (adv ? 150 : 110) ? lines(byW ? T.over(fmt(payT)) : T.cgN[c.cargo], ww - 4, small ? 12 : 13, 700).slice(0, 2) : []); ctx.fillStyle = byW ? '#e65100' : '#546e7a'; nl.forEach((q, i) => ctx.fillText(q, x0, y + 7 + i * (small ? 15 : 17), ww)); y += nl.length * (small ? 15 : 17) + (small ? 8 : 12);
      ctx.fillStyle = '#ef6c00'; font(tiny ? 14 : small ? 16 : 19, 900); fillC(`${T.payL}: ${n} × ¤ ${c.pay} = ¤ ${n * c.pay}`, x0, y + (tiny ? 4 : 8), ww); y += small ? 22 : 28;
      if (y + 16 < gy) { ctx.fillStyle = '#90a4ae'; font(small ? 11 : 13, 700); ctx.fillText(T.fuelL, x0, y + 8, ww); }
      const w3 = (ww - 16) / 3, b0 = { id: 'unsel', x: x0, y: gy, w: w3 * 0.6, h: goH }, b1 = { id: 'gar', x: x0 + w3 * 0.6 + 8, y: gy, w: w3 * 1.05, h: goH }, b2 = { id: 'go', x: x0 + w3 * 1.65 + 16, y: gy, w: ww - w3 * 1.65 - 16, h: goH }; buttons.push(b0, b1, b2);
      btn(b0, '◀', '#78909c', false, 22); btn(b1, '🔧 ' + T.garage, '#fb8c00', false, fs - 1); const noCap = cap < minOf(sel), gw = !noCap && goWarn && goWarn.sel === sel && realT - goWarn.t < 8 && adv && !adv.opt; btn(b2, noCap ? T.goCap(c.min) : gw ? T.goAny : '▶ ' + T.go, noCap ? '#90a4ae' : gw ? '#e53935' : '#43a047', false, gw || noCap ? (small ? 14 : 17) : small ? 18 : 22);
      if (gw || (noCap && goWarn && goWarn.sel === sel && realT - goWarn.t < 3)) ring(B('rent') ? 'rent' : 'adv'); else if (guided(sel)) ring(adv && !adv.opt ? 'adv' : 'go');
    }
    return view;
  }

  function layout() {
    const sm = Math.min(W, H2) < 430, g = sm ? 8 : 12, bw = sm ? 86 : 104, bh = sm ? 74 : 86, by = H2 - bh - g - 4, th = sm ? 50 : 56, c = S.cfg.b;
    buttons = [{ id: 'gas', x: W - bw - g, y: by, w: bw, h: bh }, { id: 'brake', x: W - bw * 2 - g * 2, y: by, w: bw, h: bh }].concat(career ? [{ id: 'pause', x: W - 56, y: 10, w: 46, h: 44 }, { id: 'mute', x: W - 108, y: 10, w: 46, h: 44 }] : [{ id: 'gar', x: W - 116, y: 10, w: 106, h: 44 }, { id: 'rescue', x: W - 168, y: 10, w: 46, h: 44 }, { id: 'mute', x: W - 220, y: 10, w: 46, h: 44 }]); // в заказах — пауза (там тягач и «бросить рейс»), на полигоне — гараж
    const tg = TOG.filter((k) => (k === 'soft' ? c.ctis : c[k])), one = W - (bw * 2 + g * 3) - g >= 130 + tg.length * 70;               // лёжа всё в один ряд слева, стоя — лебёдка внизу, переключатели над ней
    if (one) { const ww = sm ? 112 : 130, tw = Math.min(sm ? 70 : 86, (W - (bw * 2 + g * 3) - g - ww - 8 - tg.length * 6) / Math.max(1, tg.length)); buttons.push({ id: 'winch', x: g, y: by, w: ww, h: bh }); tg.forEach((k, i) => buttons.push({ id: k, x: g + ww + 8 + i * (tw + 6), y: by, w: tw, h: bh })); }
    else { const ww = W - (bw * 2 + g * 3) - g, tw = (W - g * 2 - (tg.length - 1) * 6) / Math.max(1, tg.length); buttons.push({ id: 'winch', x: g, y: by, w: ww, h: bh }); tg.forEach((k, i) => buttons.push({ id: k, x: g + i * (tw + 6), y: by - th - 10, w: tw, h: th })); }
  }
  const needTog = () => { const c = S.cfg.b, mud = S.inMud > 0; return c.awd && !sw.awd ? 'awd' : mud && c.lock && !sw.lock ? 'lock' : c.low && !sw.low && S.soil !== 'sand' ? 'low' : ''; }; // в песке ПОНИЖ только закапывает — её не предлагаем и сами не включаем
  function preTog() { // пока переключатель не освоен — заранее, за ~13 м до участка, где он нужен
    const c = S.cfg.b, sg = S.L.signs.find((q) => q.x > S.truck.x - 40 && q.x < S.truck.x + 700); preEdge = false; preSg = sg || null; if (!sg) return '';
    preEdge = S.truck.x > sg.x - 60; // до участка пара метров: дальше без кнопки въедешь и сядешь
    const k = sg.kind === 'soil' ? soilK(sg.val) : '', want = (t) => c[t] && !sw[t] && career; // подсказка — всем; остановка у края — только тем, кто ещё учится
    if (k === 'sand' && c.low && sw.low) return 'pre:lowoff'; // в песок с пониженной не разогнаться — это видно всем, не только новичкам
    if (want('awd') && ((k && k !== 'shallow') || (sg.kind === 'climb' && sg.val >= 18))) return 'pre:awd';
    if (want('low') && ((sg.kind === 'climb' && sg.val >= 24) || sg.kind === 'crest')) return 'pre:low';
    if (want('lock') && ['medium', 'sticky', 'clay', 'peat', 'swamp'].includes(k)) return 'pre:lock';
    return '';
  }
  // помощник новичка: забуксовал без нужной кнопки — кольцо на ней и подсказка; не нажал за ~2,5 с — игра включает сама и говорит об этом
  const treeNear = () => !!S.rope || !!S.target || S.L.trees.some((a) => a.x > S.truck.x - 60 && a.x < S.truck.x + S.cfg.wrange + 900);
  let wPrev = false;
  function winchTick(inp) { if (inp.winch && !wPrev && !S.rope && !S.target) { toast = { s: treeNear() ? T.wFar(Math.round(S.cfg.wrange / PX)) : T.wNone, t: realT, long: true, bad: true }; sfx('no'); } wPrev = inp.winch; } // нажал лебёдку, а цепляться не за что — сказать почему
  function coachTick(inp, dt) {
    if (career && !hold && !S.rope && S.inMud > 0 && (inp.gas || inp.brake)) { // закопался: 12 с газа и заднего без метра хода — честная авария с тягачом, а не бак в песок
      if (S.truck.x > trapX + 65) { trapX = S.truck.x; trapT = 0; } else trapT += dt; // мерим от самой дальней точки: раскачка взад-вперёд — не ход
      if (trapT > 12) { stuckSand = S.soil === 'sand' && sw.low; trapT = 0; trapX = -1e9; S.state = 'dead'; S.deadT = 0; S.why = 'stuck'; S.rescues++; S.events.push({ e: 'dead', why: 'stuck' }); return; }
    } else if (S.inMud === 0) trapT = 0;
    if (hold) { holdT += dt; if (holdT > 2.5) { pgEv('assist', Object.assign(stepOf(cur), { part: hold, how: 'edge', x_m: Math.round(S.truck.x / PX) })); sw[hold] = true; asst++; toast = { s: T.aOn[hold], t: realT, long: true }; sfx('on'); ak[hold] = 1; hold = ''; coach = ''; } return; } // игра стоит у края и ждёт; не нажал — включает сама
    const stuck = S.stuckT > 1.1 || (idleT > 3.5 && !S.rope), nd = stuck ? needTog() : '';
    if (stuck && inp.gas) { spinT += dt; if (nd) spinNeed = nd; } // сколько секунд колёса крутились впустую — для честной причины, если кончится топливо
    if (nd && career && !S.hung) { const lr = learning(nd); coach = nd; if (lr ? S.stuckT > 3.5 || idleT > 6 : S.stuckT > 7 || idleT > 9) { pgEv('assist', Object.assign(stepOf(cur), { part: nd, how: lr ? 'stuck' : 'stuck_late', x_m: Math.round(S.truck.x / PX) })); sw[nd] = true; asst++; ak[nd] = 1; coach = ''; toast = { s: T.aOn[nd], t: realT, long: true }; sfx('on'); } }
    else { coach = stuck ? '' : preTog();
      if (coach === 'pre:lowoff') { if (career && (learning('low') || cur < GUIDE_N) && preSg && S.truck.x > preSg.x - 420) { sw.low = false; asst++; coach = ''; toast = { s: T.aOff.low, t: realT, long: true }; sfx('off'); pgEv('assist', Object.assign(stepOf(cur), { part: 'low_off', how: 'sand', x_m: Math.round(S.truck.x / PX) })); } } // новичку игра сама выключает пониженную перед песком
      else if (coach && preEdge && inp.gas && learning(coach.slice(4))) { hold = coach.slice(4); holdT = 0; TM.holds++; } } // перед первой грязью без 4×4 игра останавливается: въехать без неё — значит сесть до конца бака
  }
  function hint() {
    if (S.state === 'dead') return [S.why === 'fuel' ? T.dFuel : S.why === 'water' ? T.dWater : S.why === 'stuck' ? T.dStuck : T.dFlip, 'rgba(183,28,28,0.88)'];
    const nf = S.L.signs.find((q) => q.x + 200 > S.truck.x && q.x - 700 < S.truck.x && tooDeep(q)); if (nf && S.depth < 6) return [T.hDeep(fmt(nf.val), fmt(S.cfg.ford / PX, 2)), Math.sin(realT * 6) > 0 ? 'rgba(198,40,40,0.95)' : 'rgba(230,81,0,0.95)'];
    if (toast && realT - toast.t < (toast.long ? 3.2 : 1.6)) return [toast.s, toast.bad ? 'rgba(183,28,28,0.9)' : 'rgba(46,125,50,0.88)'];
    if (newKey && S.t < 7 && S.stuckT < 1) return [T.hNew[newKey], 'rgba(21,101,192,0.94)'];
    if (S.hung && S.stuckT > 0.8) return [S.truck.a > 0.06 ? T.hHungF : S.cfg.b.base ? T.hHungL : T.hHung, 'rgba(230,81,0,0.92)'];
    const nt = S.stuckT > 1 ? needTog() : ''; if (nt && !S.hung) return [nt === 'awd' ? T.hAwd : nt === 'lock' ? T.hLock : T.hLow, 'rgba(230,81,0,0.92)']; // есть выключенная кнопка, которая вытащит, — сначала про неё, а не «назад и с хода»
    if (S.soil === 'sand' && S.stuckT > 1 && sw.low) return [T.hSandLow, 'rgba(230,81,0,0.92)'];
    if (S.soil === 'sand' && S.stuckT > 1 && !sw.soft && S.cfg.b.press > 0) return [T.hSand, 'rgba(230,81,0,0.92)'];
    if (S.soil === 'scree' && S.stuckT > 1) return [S.cfg.b.ctis && !sw.soft ? T.hScreeSoft : T.hScree, 'rgba(230,81,0,0.92)'];
    const rg = (S.L.rough || []).find((q) => S.truck.x > q.x0 - 140 && S.truck.x < q.x1 + 180), idle = idleT > 3.5 && !S.rope; // на камнях грузовик может качаться в яме: скорость есть, хода нет
    if (rg && (S.stuckT > 1.1 || idle)) { const c = S.cfg.b; return [c.awd && !sw.awd ? T.hAwd : c.lock && !sw.lock ? T.hLock : rg.t === 'rocks' ? T.hRocks : T.hStep, 'rgba(230,81,0,0.92)']; }
    if (S.inMud === 0 && Math.max(...S.clog) > 0.6 && S.wade === 0) return [T.hClog, S.stuckT > 0.6 ? 'rgba(230,81,0,0.92)' : 'rgba(0,0,0,0.5)'];
    if (S.stuckT > 1.1) { const c = S.cfg.b, mud = S.inMud > 0; return [c.awd && !sw.awd ? T.hAwd : mud && c.lock && !sw.lock ? T.hLock : c.low && !sw.low && S.soil !== 'sand' ? T.hLow : S.target ? T.hWinch : S.stuckT > 5 ? (career ? T.hTow : T.hGar) : T.hBack, 'rgba(230,81,0,0.92)']; }
    if (idle && S.stuckT <= 1.1) return [T.hIdle, 'rgba(230,81,0,0.92)'];
    if (coach.slice(0, 4) === 'pre:') return [T.pre[coach.slice(4)], 'rgba(21,101,192,0.94)'];
    if (S.fuel < 0.22 * S.cfg.tank && S.inMud === 0 && (sw.awd || sw.lock || sw.low)) return [T.hFuel, 'rgba(0,0,0,0.5)'];
    return null;
  }
  let vig = null;
  function vignette() { if (!vig || vig.width !== W || vig.height !== H2) { vig = document.createElement('canvas'); vig.width = W; vig.height = H2; const g = vig.getContext('2d'), r = Math.hypot(W, H2) / 2, gr = g.createRadialGradient(W / 2, H2 * 0.48, r * 0.55, W / 2, H2 * 0.48, r * 1.02); gr.addColorStop(0, 'rgba(10,20,10,0)'); gr.addColorStop(1, 'rgba(10,20,10,0.3)'); g.fillStyle = gr; g.fillRect(0, 0, W, H2); } ctx.drawImage(vig, 0, 0); }
  function drawHud(inp) {
    layout(); vignette(); if (hold) { ctx.fillStyle = 'rgba(10,20,40,0.28)'; ctx.fillRect(0, 0, W, H2); }
    const fw = Math.min(190, W - (career ? 216 : 244)), fx = 12, fy = 14, k = S.fuel / S.cfg.tank, c = S.cfg;
    ctx.fillStyle = 'rgba(0,0,0,0.4)'; rr(fx, fy, fw, 24, 12); ctx.fill(); ctx.fillStyle = k < 0.22 ? '#e53935' : k < 0.45 ? '#ffb300' : '#7cb342'; rr(fx + 3, fy + 3, Math.max(8, (fw - 6) * k), 18, 9); ctx.fill();
    font(13); ctx.fillStyle = '#fff'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; fillC('⛽ ' + Math.round(k * 100) + '%  ≈ ' + Math.round(S.range / PX) + ' ' + T.m, fx + 10, fy + 13, fw - 16); // запас хода в этом режиме: включил привод — цифра упала
    if (career && S.cargo0) { const cx = fx + fw + 8, bad = realT - lostT < 1.5; ctx.fillStyle = bad ? 'rgba(198,40,40,0.95)' : 'rgba(0,0,0,0.4)'; rr(cx, fy, 74, 24, 12); ctx.fill(); cargoIcon(S.kind, cx + 14, fy + 12, 8); ctx.fillStyle = '#fff'; font(14); ctx.textAlign = 'left'; ctx.fillText(`${S.cargo}/${S.cargo0}`, cx + 28, fy + 13); } // груз: сколько ещё в кузове
    // мосты: серое — не ведёт, зелёное — держит, красное — буксует
    const n = S.wheels.length, wx = fx + 4, wy = fy + 34, wl = 30 + n * 20; ctx.fillStyle = 'rgba(0,0,0,0.35)'; rr(wx, wy, wl, 30, 10); ctx.fill(); ctx.fillStyle = 'rgba(255,255,255,0.5)'; rr(wx + 8, wy + 5, wl - 16, 8, 3); ctx.fill();
    S.wheels.forEach((w, i) => { const drv = i < n - 1 || S.awd; ctx.fillStyle = !drv ? '#90a4ae' : S.slip[i] > 150 || (inp.gas && S.stuckT > 0.4) ? '#ff5252' : '#69f0ae'; const cx = wx + 18 + (i * (wl - 36)) / Math.max(1, n - 1); ctx.beginPath(); ctx.arc(cx, wy + 19, 7, 0, 7); ctx.fill(); if (S.clog[i] > 0.25) { ctx.strokeStyle = '#6d4c41'; ctx.lineWidth = 1.5 + 3 * S.clog[i]; ctx.beginPath(); ctx.arc(cx, wy + 19, 8.5, 0, 7); ctx.stroke(); } }); // коричневый ободок — протектор забит
    // что впереди: ближайший указатель и сколько до него
    const nx = S.L.signs.find((s) => s.x > S.truck.x - 60 && s.x < S.truck.x + 2200);
    if (nx) { const d = Math.max(0, Math.round((nx.x + 200 - S.truck.x) / PX)), deep = tooDeep(nx), t = deep ? '⚠ ' + T.warn(fmt(nx.val), fmt(c.ford / PX, 2)) + (d > 2 ? ' · ' + d + ' ' + T.m : '') : `${T.ahead}: ${signT(nx)}${nx.kind === 'crest' && c.b.base ? T.crestRun : ''}${d > 2 ? ' · ' + d + ' ' + T.m : ''}`; font(13, 800); const tw = ctx.measureText(t).width + 22, tx = wx + wl + 8; ctx.fillStyle = deep ? (Math.sin(realT * 6) > 0 ? 'rgba(198,40,40,0.95)' : 'rgba(230,81,0,0.95)') : 'rgba(0,0,0,0.4)'; rr(tx, wy + 2, Math.min(tw, W - tx - 8), 26, 13); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textAlign = 'left'; fillC(t, tx + 11, wy + 16, W - tx - 30); }
    btn(B('gas'), '▶', '#43a047', inp.gas); btn(B('brake'), '◀', '#e53935', inp.brake);
    if (treeNear()) btn(B('winch'), '⚓ ' + T.winch, S.target || S.rope ? '#5c6bc0' : '#78909c', inp.winch); else { const i = buttons.findIndex((b) => b.id === 'winch'); if (i >= 0) buttons.splice(i, 1); } // кнопка лебёдки — только когда впереди есть дерево с меткой
    TOG.forEach((q) => { const b = B(q); if (!b) return; btn(b, q === 'soft' ? T.soft + (sw.soft ? ' ▼' : '') : T[q], sw[q] ? '#fb8c00' : '#546e7a', sw[q]); ctx.fillStyle = sw[q] ? '#b9f6ca' : 'rgba(0,0,0,0.35)'; ctx.beginPath(); ctx.arc(b.x + b.w - 11, b.y + 11 + (sw[q] ? 3 : 0), 4.5, 0, 7); ctx.fill(); }); // лампочка: включено
    for (const [id, ch] of [['gar', '🔧 ' + T.garage], ['rescue', '↺'], ['pause', '❚❚'], ['mute', muted ? '🔇' : '🔊']]) { const b = B(id); if (!b) continue; ctx.fillStyle = id === 'gar' ? 'rgba(239,108,0,0.92)' : 'rgba(0,0,0,0.34)'; rr(b.x, b.y, b.w, b.h, 12); ctx.fill(); ctx.fillStyle = '#fff'; font(id === 'gar' ? 16 : id === 'pause' ? 15 : 21); ctx.textAlign = 'center'; fillC(ch, b.x + b.w / 2, b.y + b.h / 2 + 1, b.w - 8); }
    const h = hint(); if (h) { if (H2 < 330 && W > 560) { const l = Math.max(fx + fw + 90, W * 0.42), r = W - 124; bubble(h[0], 6, h[1], (l + r) / 2, r - l, 13); } else bubble(h[0], wy + 40, h[1]); } // низкий экран (телефон лёжа в окне площадки): подсказка справа вверху, грузовик не закрывает
    ring(coach ? (coach === 'pre:lowoff' ? 'low' : coach.replace('pre:', '')) : newKey && newKey !== 'first' && S.t < 7 ? newKey : '');
    if (!matchMedia('(pointer: coarse)').matches && !ptrs.size && S.t < 14 && !rebuilds) { font(13, 800); const tw = Math.min(ctx.measureText(T.keys).width + 36, W - 16), ky = h ? wy + 96 : wy + 40; ctx.fillStyle = 'rgba(0,0,0,0.45)'; rr(W / 2 - tw / 2, ky, tw, 30, 15); ctx.fill(); ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.fillText(T.keys, W / 2, ky + 15, tw - 24); }
  }
  function drawFail() {
    ctx.fillStyle = 'rgba(40,10,10,0.4)'; ctx.fillRect(0, 0, W, H2);
    const sm = Math.min(W, H2) < 430, w = Math.min(W - 24, 470), tip = lines(failTip(), w - 44, sm ? 15 : 17, 700), bh = sm ? 46 : 54, h = Math.min(H2 - 16, 96 + tip.length * 23 + (career ? bh * 2 + 12 : bh)), x = W / 2 - w / 2, y = Math.max(8, H2 / 2 - h / 2 - (career ? 0 : 20));
    ctx.fillStyle = '#fffdf7'; rr(x, y, w, h, 22); ctx.fill(); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = '#c62828'; font(sm ? 22 : 25); ctx.fillText(S.why === 'fuel' ? T.dFuel : S.why === 'water' ? T.dWater : S.why === 'stuck' ? T.dStuck : T.dFlip, W / 2, y + 34, w - 24);
    ctx.fillStyle = '#37474f'; font(sm ? 15 : 17, 700); tip.forEach((q, i) => ctx.fillText(q, W / 2, y + 70 + i * 23, w - 30));
    const bw = (w - 60) / 2, by = y + h - bh - 16;
    if (career && S.why === 'water') { // залило: тягач вернул бы к тому же броду — предлагаем сразу гараж
      const b1 = { id: 'gar', x: x + 24, y: by - bh - 10, w: w - 48, h: bh }, b3 = { id: 'quit', x: x + 24, y: by, w: w - 48, h: bh }; buttons = [b1, b3];
      btn(b1, '🔧 ' + T.toGar, '#fb8c00', false, sm ? 17 : 19); btn(b3, '✕ ' + T.quit, '#78909c', false, sm ? 15 : 17);
    } else if (career) { // в заказе: тягач к флажку за монеты (или один раз бесплатно — за рекламу) либо бросить рейс и идти в гараж
      const b1 = { id: 'tow', x: x + 24, y: by - bh - 10, w: adTow ? w - 48 : bw, h: bh }, b2 = { id: 'towad', x: x + 36 + bw, y: by - bh - 10, w: bw, h: bh }, b3 = { id: 'quit', x: x + 24, y: by, w: w - 48, h: bh }; const noAd = adTow || !canAd(); buttons = noAd ? [b1, b3] : [b1, b2, b3]; if (noAd) b1.w = w - 48;
      btn(b1, `🚜 ${T.tow} — ¤ ${TOW}`, '#5c6bc0', false, sm ? 15 : 17); if (!noAd) btn(b2, '▶ ' + T.towFree, '#f9a825', false, sm ? 14 : 16); btn(b3, '✕ ' + T.quit, '#78909c', false, sm ? 15 : 17);
    } else { const b1 = { id: 'gar', x: x + 24, y: by, w: bw, h: bh }, b2 = { id: 'retry', x: x + 36 + bw, y: by, w: bw, h: bh }; buttons = [b1, b2]; btn(b1, '🔧 ' + T.toGar, '#fb8c00', false, 18); btn(b2, '↺ ' + T.retry, '#78909c', false, 18); }
  }
  function drawPause() {
    ctx.fillStyle = 'rgba(10,25,40,0.45)'; ctx.fillRect(0, 0, W, H2);
    const sm = H2 < 440, bh = sm ? 46 : 56, w = Math.min(W - 24, 400), h = 64 + (bh + 10) * 3 + 8, x = W / 2 - w / 2, y = Math.max(8, H2 / 2 - h / 2);
    ctx.fillStyle = '#fffdf7'; rr(x, y, w, h, 22); ctx.fill(); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#263238'; font(24); ctx.fillText(T.pause, W / 2, y + 34);
    const bs = [['resume', '▶ ' + T.resume, '#43a047'], ['tow', `🚜 ${T.towTo} — ¤ ${TOW}`, '#5c6bc0'], ['quit', '✕ ' + T.quit, '#78909c']]; buttons = [];
    bs.forEach(([id, t, col], i) => { const b = { id, x: x + 24, y: y + 62 + i * (bh + 10), w: w - 48, h: bh }; buttons.push(b); btn(b, t, col, false, sm ? 16 : 18); });
  }
  function star5(x, y, r, col) { ctx.fillStyle = col; ctx.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, q = i & 1 ? r * 0.45 : r; ctx.lineTo(x + Math.cos(a) * q, y + Math.sin(a) * q); } ctx.closePath(); ctx.fill(); }
  function drawWin() {
    ctx.fillStyle = 'rgba(10,40,70,0.45)'; ctx.fillRect(0, 0, W, H2);
    const w = Math.min(W - 28, 460), h = Math.min(H2 - 24, 330), x = W / 2 - w / 2, y = H2 / 2 - h / 2, k = S.fuel / S.cfg.tank, clean = S.rescues === 0 && rebuilds === 0, st = [true, clean, clean && k >= 0.2];
    ctx.fillStyle = '#fffdf7'; rr(x, y, w, h, 22); ctx.fill();
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#2e7d32'; font(26); ctx.fillText(T.win, W / 2, y + 38, w - 24);
    [T.s1, T.s2, T.s3].forEach((s, i) => { const cx = W / 2 + (i - 1) * w * 0.3; star5(cx, y + 104, i === 1 ? 40 : 33, st[i] ? '#ffc107' : '#cfd8dc'); ctx.fillStyle = '#546e7a'; font(13, 800); ctx.fillText(s, cx, y + 158, w * 0.29); });
    ctx.fillStyle = '#37474f'; font(17, 800); ctx.fillText(`${T.time}: ${S.t.toFixed(0)} ${T.sec}   ·   ${T.fuel}: ${Math.round(k * 100)}%`, W / 2, y + 198, w - 24);
    const bw = (w - 60) / 2, b1 = { id: 'gar', x: x + 24, y: y + h - 78, w: bw, h: 56 }, b2 = { id: 'again', x: x + 36 + bw, y: y + h - 78, w: bw, h: 56 }; buttons = [b1, b2]; btn(b1, '🔧 ' + T.toGar, '#fb8c00', false, 18); btn(b2, '↻ ' + T.again, '#43a047', false, 18);
  }
  // итог на низком экране (телефон лёжа в окне площадки): слева звёзды и счёт, справа кнопки — ничто ни на что не налезает
  function drawWinShort() {
    const r = res, nxt = !!r.opened && unlocked(cur + 1), xa = r.total > 0 && !r.doubled && canAd() && !(cur < GUIDE_N && r.opened), w = Math.min(W - 16, 780), h = H2 - 12, x = W / 2 - w / 2, y = 6, lw = w * 0.54, rx = x + lw + 6, rw = w - lw - 18;
    ctx.fillStyle = '#fffdf7'; rr(x, y, w, h, 18); ctx.fill(); ctx.textBaseline = 'middle';
    ctx.textAlign = 'center'; ctx.fillStyle = r.deliv ? '#2e7d32' : '#c62828'; font(18); ctx.fillText(r.deliv ? T.winC : T.noPay, x + lw / 2, y + 20, lw - 20);
    T.cs.forEach((t, i) => { const cx = x + lw / 2 + (i - 1) * lw * 0.32; star5(cx, y + 48, i === 1 ? 15 : 13, r.st[i] ? '#ffc107' : '#cfd8dc'); ctx.fillStyle = '#546e7a'; font(10, 800); ctx.fillText(t, cx, y + 70, lw * 0.3); });
    const rows = [[`${T.rDeliv}: ${r.deliv} ${T.of} ${r.of} × ¤ ${r.pay}`, '+' + r.gross, '#2e7d32'], [`${T.rFuel}: ${r.fuel} ${T.lit}`, '−' + r.fuel, '#c62828']]; if (r.tows) rows.push([`${T.tow} × ${r.tows}`, '−' + r.tows * TOW, '#c62828']);
    const lh = Math.min(19, (h - 128) / (rows.length + (r.opened ? 2 : 1.4))); let yy = y + 92; font(13, 800);
    for (const [a, b, col] of rows) { ctx.textAlign = 'left'; ctx.fillStyle = '#455a64'; fillC(a, x + 16, yy, lw - 80); ctx.textAlign = 'right'; ctx.fillStyle = col; ctx.fillText(b, x + lw - 8, yy); yy += lh; }
    ctx.fillStyle = '#cfd8dc'; ctx.fillRect(x + 14, yy - lh / 2 + 2, lw - 20, 2); yy += 4;
    font(16); ctx.textAlign = 'left'; ctx.fillStyle = '#263238'; ctx.fillText(T.rTotal, x + 16, yy + 4); ctx.textAlign = 'right'; ctx.fillStyle = '#ef6c00'; fillC(`¤ ${r.total * (r.doubled ? 2 : 1)}`, x + lw - 8, yy + 4); yy += lh + 6;
    if (r.opened && yy < y + h - 8) { ctx.textAlign = 'left'; ctx.fillStyle = '#2e7d32'; font(11, 800); fillC(`${T.opened}: ${r.opened}`, x + 16, yy, lw - 24); }
    const n = xa ? 3 : 2, g = 8, bh = Math.min(52, (h - 16 - g * (n - 1)) / n); let by = y + (h - (bh * n + g * (n - 1))) / 2; buttons = [];
    if (xa) { const b0 = { id: 'x2', x: rx, y: by, w: rw, h: bh }; buttons.push(b0); btn(b0, `▶ ${T.x2}: +¤ ${r.total}`, '#f9a825', false, 15); by += bh + g; }
    const b2 = { id: nxt ? 'nextc' : 'again', x: rx, y: by, w: rw, h: bh }, b1 = { id: 'menu', x: rx, y: by + bh + g, w: rw, h: bh }; buttons.push(b1, b2);
    btn(b2, nxt ? '▶ ' + T.nextC : '↻ ' + T.again, nxt ? '#43a047' : '#78909c', false, 16); btn(b1, '◀ ' + T.toMenu, nxt ? '#78909c' : '#43a047', false, 15);
    if (nxt && cur < GUIDE_N) ring('nextc');
  }
  // итог заказа: звёзды, откуда деньги и на что ушли
  function drawWinC() {
    ctx.fillStyle = 'rgba(10,40,70,0.45)'; ctx.fillRect(0, 0, W, H2);
    if (H2 < 330 && W > 560) return drawWinShort();
    const r = res, sm = H2 < 470, lh = sm ? 20 : 25, bh = sm ? 44 : 54, nxt = !!r.opened && unlocked(cur + 1), xh = r.total > 0 && !r.doubled && canAd() && !(cur < GUIDE_N && r.opened) ? (sm ? 40 : 48) + 8 : 0, rows = [[`${T.rDeliv}: ${r.deliv} ${T.of} ${r.of} × ¤ ${r.pay}`, '+' + r.gross, '#2e7d32'], [`${T.rFuel}: ${r.fuel} ${T.lit}`, '−' + r.fuel, '#c62828']]; if (r.tows) rows.push([`${T.tow} × ${r.tows}`, '−' + r.tows * TOW, '#c62828']);
    const sy = sm ? 58 : 92, ly = sy + (sm ? 40 : 62), w = Math.min(W - 24, sm ? 520 : 460), h = Math.min(H2 - 12, ly + rows.length * lh + lh + 14 + (r.opened ? lh : 0) + xh + bh + 18), x = W / 2 - w / 2, y = Math.max(6, H2 / 2 - h / 2);
    ctx.fillStyle = '#fffdf7'; rr(x, y, w, h, 22); ctx.fill(); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = r.deliv ? '#2e7d32' : '#c62828'; font(sm ? 20 : 26); ctx.fillText(r.deliv ? T.winC : T.noPay, W / 2, y + (sm ? 26 : 36), w - 24);
    T.cs.forEach((t, i) => { const cx = W / 2 + (i - 1) * w * 0.3; star5(cx, y + sy, sm ? 16 : i === 1 ? 30 : 25, r.st[i] ? '#ffc107' : '#cfd8dc'); ctx.fillStyle = '#546e7a'; font(sm ? 11 : 13, 800); ctx.fillText(t, cx, y + sy + (sm ? 25 : 42), w * 0.29); });
    let yy = y + ly + lh / 2; font(sm ? 14 : 16, 800);
    for (const [a, b, col] of rows) { ctx.textAlign = 'left'; ctx.fillStyle = '#455a64'; fillC(a, x + 26, yy, w - 130); ctx.textAlign = 'right'; ctx.fillStyle = col; ctx.fillText(b, x + w - 26, yy); yy += lh; }
    ctx.fillStyle = '#cfd8dc'; ctx.fillRect(x + 24, yy - lh / 2 + 3, w - 48, 2); yy += 8;
    font(sm ? 18 : 22); ctx.textAlign = 'left'; ctx.fillStyle = '#263238'; ctx.fillText(T.rTotal, x + 26, yy + 2); ctx.textAlign = 'right'; ctx.fillStyle = '#ef6c00'; fillC(`¤ ${r.total * (r.doubled ? 2 : 1)}`, x + w - 26, yy + 2); yy += lh + 4;
    if (r.opened) { ctx.textAlign = 'center'; ctx.fillStyle = '#2e7d32'; font(sm ? 13 : 15, 800); ctx.fillText(`${T.opened}: ${r.opened}`, W / 2, yy, w - 30); }
    const by = y + h - bh - 14, bw = (w - 60) / 2, b1 = { id: 'menu', x: x + 24, y: by, w: bw, h: bh }, b2 = { id: nxt ? 'nextc' : 'again', x: x + 36 + bw, y: by, w: bw, h: bh }; buttons = [b1, b2];
    if (xh) { const b0 = { id: 'x2', x: x + 24, y: by - xh, w: w - 48, h: xh - 8 }; buttons.push(b0); btn(b0, `▶ ${T.x2}: +¤ ${r.total}`, '#f9a825', false, sm ? 16 : 19); } // ×2 за рекламу
    btn(b1, '◀ ' + T.toMenu, nxt ? '#78909c' : '#43a047', false, sm ? 16 : 18); btn(b2, nxt ? '▶ ' + T.nextC : '↻ ' + T.again, nxt ? '#43a047' : '#78909c', false, sm ? 16 : 18);
    if (nxt && cur < GUIDE_N) ring('nextc');
  }

  // ---------- кадр ----------
  function frame(now) { try { frame1(now); } catch (e) { if (!frame.err) { frame.err = 1; try { console.error(e); } catch (q) { /* */ } } } requestAnimationFrame(frame); }
  function frame1(now) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now; realT += dt;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0); ctx.clearRect(0, 0, W, H2);
    let inp = { gas: false, brake: false, winch: false, awd: sw.awd, lock: sw.lock, low: sw.low, soft: sw.soft };
    const idle = mode === 'garage' || mode === 'menu';
    const pgHold = PG.ad || PG.paused || !!PG.pend; perfSample(now, dt * 1000, mode === 'play' && S.state === 'play' && !paused && !pgHold && !document.hidden);
    if (!dbg.freeze && !document.hidden && !pgHold && !(paused && mode === 'play')) {
      if (mode === 'play') inp = input();
      acc += dt; let n = 0; if (hold && mode === 'play') acc = 0; while (acc >= P.DT && n < 8) { S.step(idle ? {} : inp); acc -= P.DT; n++; }
      if (idle) S.fuel = S.cfg.tank;
      if (mode !== 'play' || hold || S.state !== 'play') { idleX = S.truck.x; idleT = 0; } else if (S.truck.x > idleX + 60 || inp.brake) { idleX = S.truck.x; idleT = 0; } else if (inp.gas) idleT += dt; // газ без нового метра вперёд: стоит, буксует или скатывается назад и снова — всё одно, хода нет
      if (mode === 'play' && S.state === 'play') { winchTick(inp); coachTick(inp, dt); } // сколько секунд газ нажат, а грузовик не сдвинулся и на метр
      if (mode === 'play' && S.state === 'play') { const fk = S.fuel / S.cfg.tank; if (fk > 0.3) fuelLvl = 2; else if (fk < 0.1 && fuelLvl > 0) { fuelLvl = 0; toast = { s: T.hFuelEnd, t: realT, bad: true, long: true }; sfx('warn'); } else if (fk < 0.25 && fuelLvl > 1) { fuelLvl = 1; toast = { s: T.hFuelLow, t: realT, bad: true, long: true }; sfx('warn', 0.8); } }
      for (const e of S.events) {
        if (idle) continue;
        if (e.e === 'respawn') { trapX = -1e9; trapT = 0; idleX = -1e9; idleT = 0; }
        else if (e.e === 'cp') { toast = { s: T.cp, t: realT }; sfx('cp'); } else if (e.e === 'can') { toast = { s: T.can(e.l || M.CAN), t: realT }; sfx('can'); }
        else if (e.e === 'dead') { sfx('fail'); TM.deaths++; if (career && TM.deaths <= 30) pgEv('crash', runData({ reason: S.why || 'flip', soil: S.soil || '', in_mud: S.inMud, awd: sw.awd, lock: sw.lock, low: sw.low, spin_sec: Math.round(spinT), need: spinNeed })); } else if (e.e === 'hook') sfx('hook', 0.8); else if (e.e === 'log') { lostT = realT; toast = { s: T.logLost, t: realT, bad: true }; sfx('thud'); }
        else if (e.e === 'win') { mode = 'win'; sfx('win'); if (career && cur >= 0) finish(); }
      }
      S.events.length = 0;
    }
    soundTick(inp);
    const tr = S.truck, port = !land();
    if (idle) {
      const g = mode === 'menu' ? drawMenu() : drawGarage(), tl = S.cfg.tr ? S.cfg.tr.len : 0, zg = Math.min(g.zw / (S.cfg.len + tl + 190), g.zh / 330); camX = tr.x - tl / 2; camY = tr.y;
      if (use3d) R3.draw(SV, { camX, camY, Z: zg, W, H: H2, DPR, t: realT, lvl: lvlKey, duo: false, shake: 0, gas: false, gasOn: false, theme: 2, g: { tilt: 0.14, yaw: 0.42, px: g.px, py: g.py } });
      return;
    }
    // камера: ближе, когда ползёшь в грязи; дальше на скорости
    const zb = clamp(port ? W / 700 : W / 1500, 0.46, 0.82), zt = dbg.Z || zb * (S.inMud && Math.abs(tr.vx) < 200 ? 1.1 : Math.abs(tr.vx) > 520 ? 0.92 : 1); Z += (zt - Z) * Math.min(1, dt * 1.5); // dbg.Z, dbg.dx, dbg.oy, dbg.clean — кадр для обложки
    camX += (tr.x + (dbg.dx != null ? dbg.dx : port ? 110 : 240) - camX) * Math.min(1, dt * 4); camY += (tr.y - 70 - camY) * Math.min(1, dt * 3);
    // земля под колёсами встаёт чуть выше кнопок — на любом экране грузовик виден целиком
    layout(); const yb = Math.min(...buttons.filter((q) => q.y > H2 / 2).map((q) => q.y)), oy = clamp((yb - 30 - (S.cfg.hW + S.WR) * Z) / H2 - 0.5 - (70 * Z) / H2, -0.2, 0.3);
    if (use3d) R3.draw(SV, { camX, camY, Z, W, H: H2, DPR, t: realT, lvl: lvlKey, duo: false, shake: 0, gas: inp.gas && !S.inMud && !S.wade, gasOn: inp.gas && S.fuel > 0, oy: dbg.oy != null ? dbg.oy : oy, theme: 2 });
    if (dbg.clean) buttons = []; else if (mode === 'win' && S.wonT > 0.9) { if (career && res) drawWinC(); else drawWin(); } else if (S.state === 'dead' && S.deadT > 0.9) drawFail(); else if (paused) drawPause(); else drawHud(inp);
    if (adMsg && realT - adMsg.t < 3.2 && mode !== 'play') bubble(adMsg.s, 8, 'rgba(183,28,28,0.94)', W / 2, Math.min(W - 40, 560), H2 < 330 ? 13 : 0); // ролик не пришёл — сказать сверху
  }
  window.__mud = { hintText: () => { const h = hint(); return h ? h[0] : ''; }, snd: () => ({ loaded: Object.keys(SND).sort(), ac: AC ? AC.state : null, gain: out ? +out.gain.value.toFixed(2) : null, eng: eng ? +eng.g.gain.value.toFixed(2) : null, rate: eng ? +eng.s.playbackRate.value.toFixed(2) : null, mus: mus ? +mus.g.gain.value.toFixed(2) : null }), get S() { return S; }, sw, keys, dbg, get mode() { return mode; }, get buttons() { return buttons; }, get build() { return BD(); }, get save() { return save; }, get career() { return career; }, get res() { return res; }, get paused() { return paused; }, press, setPart, start, toGarage, toMenu, flip, get note() { return shownNote; }, gainNote, get coach() { return coach; }, get asst() { return asst; }, get hold() { return hold; }, pg: PG, get sel() { return sel; }, get cur() { return cur; }, get adv() { return mode === 'menu' && sel >= 0 ? advice() : null; }, get fail() { return mode === 'play' && S && S.state === 'dead' ? failTip() : ''; }, get spinT() { return spinT; }, get hintNow() { return mode === 'play' && S ? (hint() || [''])[0] : ''; } };
  requestAnimationFrame(frame);
})();
