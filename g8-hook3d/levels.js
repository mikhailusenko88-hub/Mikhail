'use strict';
/* Hook Truck — 12 уровней. Дорога строится слева направо: flat — ровно, gap — яма (dy: другой край выше/ниже),
   ring — кольцо (h — высота над дорогой), ceil — потолок пещеры, boost — ускоритель, ramp — трамплин. */
(function (root) {
  const H = root.HookSim, Tr = () => H.Track().start(-300, 600);
  const L = [
    { // 1 — первый мах
      name: ['First Swing', 'Первый мах'], hint: ['', ''], // первый уровень учит рукой: «держи» у ямы, «отпусти» на взлёте (см. GUIDE)
      build: () => Tr().flat(1100).ring(240, 380).gap(450, 30).flat(700).ring(250, 400).star(420, 340).gap(480, 30).flat(300).fin().end().S,
    },
    { // 2 — на стену
      name: ['Up the Wall', 'На стену'], hint: ['At the wall: hold — the winch pulls you up', 'У стены держи — лебёдка затянет наверх'],
      build: () => Tr().flat(1000).ring(240, 380).gap(440, 30).flat(500).cp(-300).flat(300)
        .gap(0, -340).ring(140, 360, { climb: 1 }).flat(600).ring(250, 400).star(300, 470).gap(460, 40).flat(300).fin().end().S,
    },
    { // 3 — два кольца
      name: ['Double Swing', 'Два кольца'], hint: ['Let go, then hold again — the hook grabs the next ring', 'Отпусти и снова держи — крюк поймает второе кольцо'],
      build: () => Tr().flat(1000).ring(250, 410).gap(500, 30).flat(500).cp(-300).flat(500)
        .ring(290, 440).ring(660, 440).star(740, 360).gap(940, 40).flat(300).fin().end().S,
    },
    { // 4 — пробный уровень
      name: ['Swing & Climb', 'Мах и обрыв'], hint: ['', ''],
      build: () => { const b = Tr().flat(1000).hill(520, 46).flat(420); b.ring(300, 430).gap(600); b.flat(260).cp(-80).flat(420); b.gap(0, -380).ring(140, 360, { climb: 1 }); b.flat(80).cp(0).flat(820); b.ring(300, 450).ring(700, 450).star(740, 360).gap(1000); b.flat(700).slope(700, -160).flat(200).fin(100).end(); return b.S; },
    },
    { // 5 — трамплин и захват в воздухе
      name: ['Boost & Fly', 'Разгон и полёт'], hint: ['Fly off the ramp and hook in the air!', 'Слетай с трамплина и цепляйся в воздухе!'],
      build: () => Tr().flat(700).boost(0, 400).flat(500).ramp(260, 70).ring(620, 520).star(950, 600).gap(1220, 60).flat(600).cp(-400).flat(300)
        .gap(0, -340).ring(140, 360, { climb: 1 }).flat(700).boost(0, 300).flat(300).ramp(220, 60).ring(520, 520).gap(1100).flat(300).fin().end().S,
    },
    { // 6 — кольца едут
      name: ['Moving Rings', 'Кольца едут'], hint: ['The rings move — time your hook', 'Кольца ездят — лови момент'],
      build: () => Tr().flat(1000).ring(260, 420, { mv: { dx: 200, T: 3 } }).gap(560).flat(600).cp(-400).flat(300)
        .ring(300, 450, { mv: { dx: 180, T: 2.6 } }).ring(720, 450, { mv: { dy: 120, T: 2.2, ph: 4 } }).star(760, 360).gap(1050).flat(300).fin().end().S,
    },
    { // 7 — пещера
      name: ['Cave', 'Пещера'], hint: ["Cave! Don't fly into the ceiling", 'Пещера! Не влети в потолок'],
      build: () => Tr().flat(900).flat(400).ceil(0, 3300, 680).ring(300, 440).gap(520).flat(500).cp(-300).ring(300, 440).gap(520).flat(500)
        .ring(300, 440).ring(660, 440).star(480, 300).gap(900).flat(400).flat(300).fin().end().S,
    },
    { // 8 — ломкие кольца
      name: ['Snap!', 'Хрусь!'], hint: ['Cracked rings snap — don\'t hang too long!', 'Треснутые кольца рвутся — не висни долго!'],
      build: () => Tr().flat(1000).ring(260, 420, { snap: 1.4 }).gap(560).flat(600).cp(-400).flat(300)
        .ring(300, 450, { snap: 1.25 }).ring(695, 450, { snap: 1.25 }).star(740, 360).gap(1000, 12).flat(300).fin().end().S,
    },
    { // 9 — длинная цепь
      name: ['Long Chain', 'Длинная цепь'], hint: ['', ''],
      build: () => Tr().flat(1200).ring(300, 450).ring(700, 470).ring(1100, 470, { mv: { dy: 90, T: 2.4 } }).ring(1500, 450).star(1300, 420).gap(1830, 20).flat(500).fin().end().S,
    },
    { // 10 — башня: стены с треснутыми кольцами (тянуть быстрее!) и ямы между ними
      name: ['Tower', 'Башня'], hint: ['Cracked ring on the wall — the winch hurries, hold on!', 'Треснутое кольцо на стене — лебёдка спешит, держись!'],
      build: () => Tr().flat(1000).gap(0, -300).ring(140, 360, { climb: 1, snap: 2.6 }).flat(650).ring(250, 420).gap(480).flat(400)
        .gap(0, -300).ring(140, 360, { climb: 1, snap: 2.6 }).flat(600).cp(-300).ring(260, 440).gap(500).flat(400)
        .gap(0, -300).ring(140, 360, { climb: 1 }).flat(500).fin().end().S,
    },
    { // 11 — вниз по каньону
      name: ['Canyon', 'Каньон'], hint: ['', ''],
      build: () => Tr().flat(1000).ring(300, 460).gap(720, 170).flat(500).cp(-300).flat(300)
        .ring(300, 460, { mv: { dx: 200, T: 2.2, ph: 2.4 } }).gap(820, 130).flat(500).ring(280, 440, { snap: 1.1 }).gap(680, 90).flat(300).fin().end().S,
    },
    { // 12 — финал
      name: ['Grand Finale', 'Финал'], hint: ['', ''],
      build: () => Tr().flat(700).boost(0, 400).flat(500).ramp(260, 70).ring(650, 520).gap(1300).flat(500).cp(-300).flat(200)
        .gap(0, -340).ring(140, 360, { climb: 1 }).flat(500).cp(-300).flat(500)
        .ring(300, 450, { mv: { dx: 170, T: 2.4 } }).ring(710, 450, { snap: 1.15 }).ring(1120, 450).star(900, 560).gap(1440).flat(400).fin().end().S,
    },
    // ===== серия 2 — «Каньон»: уровни длиннее, появляется батут =====
    { // 13 — батут
      name: ['Trampoline', 'Батут'], hint: ['The trampoline throws you up!', 'Батут подбрасывает вверх!'],
      build: () => Tr().flat(900).spring(0, 140, 1000).flat(200).ring(300, 720).gap(600, 20).flat(600).cp(-250).flat(300).ring(250, 400).gap(480, 20).flat(500).cp(-250).flat(200)
        .spring(0, 140, 1050).flat(200).ring(330, 760).gap(720, 20).flat(400).fin().end().S,
    },
    { // 14 — через каньон
      name: ['Across the Canyon', 'Через каньон'], hint: ['', ''],
      build: () => Tr().flat(600).boost(0, 350).flat(450).ramp(240, 65).ring(560, 500).gap(1100, 40).flat(500).cp(-300).flat(300)
        .gap(0, -320).ring(140, 360, { climb: 1 }).flat(500).cp(-250).flat(250).ring(290, 440).ring(680, 440).gap(960, 120).flat(400).fin().end().S,
    },
    { // 15 — вверх и вниз
      name: ['Up & Down', 'Вверх и вниз'], hint: ['', ''],
      build: () => Tr().flat(900).spring(0, 140, 1100).flat(220).ring(340, 780).gap(760, -60).flat(500).ring(260, 430).gap(520, 140).flat(450).cp(-250).flat(250)
        .gap(0, -320).ring(140, 360, { climb: 1, snap: 2.6 }).flat(500).cp(-250).flat(200).ring(300, 450, { mv: { dx: 190, T: 2.4, ph: 4 } }).gap(800, 120).flat(400).fin().end().S,
    },
    { // 16 — трамплин и батут
      name: ['Ramp & Bounce', 'Трамплин и батут'], hint: ['', ''],
      build: () => Tr().flat(600).boost(0, 400).flat(500).ramp(260, 70).ring(640, 520).gap(1250, 40).flat(600).cp(-350).flat(250)
        .spring(0, 140, 1100).flat(220).ring(360, 800).ring(820, 560).gap(1150, 60).flat(500).cp(-300).flat(300).ring(300, 460).gap(720, 160).flat(400).fin().end().S,
    },
    { // 17 — качели
      name: ['Monkey Bars', 'Качели'], hint: ['', ''],
      build: () => Tr().flat(1100).ring(300, 450).ring(700, 480).ring(1100, 440, { mv: { dy: 100, T: 2.4 } }).ring(1500, 480).ring(1900, 450).gap(2230, 20).flat(500).fin().end().S,
    },
    { // 18 — ущелье
      name: ['Gorge', 'Ущелье'], hint: ['', ''],
      build: () => Tr().flat(900).ring(300, 460).gap(720, 170).flat(450).cp(-250).flat(250).ring(300, 460, { mv: { dx: 200, T: 2.2, ph: 2.4 } }).gap(820, 130).flat(450).cp(-250).flat(250)
        .ring(280, 440, { snap: 1.1 }).ring(660, 430, { snap: 1.1 }).gap(960, 120).flat(450).gap(0, -300).ring(140, 360, { climb: 1 }).flat(400).fin().end().S,
    },
    { // 19 — лестница
      name: ['Staircase', 'Лестница'], hint: ['', ''],
      build: () => Tr().flat(900).gap(0, -300).ring(140, 360, { climb: 1 }).flat(500).ring(250, 410).gap(470).flat(350).cp(-200).flat(150)
        .gap(0, -260).ring(140, 340, { climb: 1 }).flat(500).gap(0, -320).ring(140, 360, { climb: 1 }).flat(450).cp(-250).flat(200)
        .ring(260, 430).gap(480, -20).flat(400).fin().end().S,
    },
    { // 20 — хрупкий мост
      name: ['Fragile Bridge', 'Хрупкий мост'], hint: ['', ''],
      build: () => Tr().flat(900).ring(280, 430, { snap: 1.4 }).gap(560).flat(500).cp(-300).flat(300)
        .ring(300, 450, { snap: 1.3 }).ring(690, 450, { snap: 1.3 }).ring(1080, 450, { snap: 1.3 }).gap(1380, 20).flat(500).cp(-300).flat(200)
        .gap(0, -300).ring(140, 360, { climb: 1, snap: 2.6 }).flat(400).fin().end().S,
    },
    { // 21 — полёт
      name: ['Flight', 'Полёт'], hint: ['', ''],
      build: () => Tr().flat(600).boost(0, 400).flat(500).ramp(260, 70).ring(650, 520).gap(1300).flat(500).cp(-300).flat(200)
        .boost(0, 300).flat(300).ramp(220, 60).ring(520, 520).ring(960, 500).gap(1500, 40).flat(500).cp(-300).flat(300)
        .spring(0, 140, 1100).flat(220).ring(360, 800).gap(900, 40).flat(400).fin().end().S,
    },
    { // 22 — маятники
      name: ['Pendulums', 'Маятники'], hint: ['', ''],
      build: () => Tr().flat(900).ring(260, 420, { mv: { dx: 140, T: 2.8 } }).gap(540).flat(500).cp(-300).flat(300)
        .ring(280, 440, { mv: { dy: 110, T: 2.4 } }).gap(560, 20).flat(500).cp(-300).flat(300)
        .ring(300, 450).ring(700, 460, { mv: { dx: 120, T: 2.6 } }).ring(1080, 450).gap(1380, 30).flat(400).fin().end().S,
    },
    { // 23 — грот
      name: ['Grotto', 'Грот'], hint: ['', ''],
      build: () => Tr().flat(800).flat(300).ceil(0, 4200, 690).ring(300, 440).gap(520).flat(500).cp(-300).ring(300, 440, { mv: { dx: 90, T: 2.6 } }).gap(520).flat(500).cp(-250).flat(100)
        .ring(300, 440, { snap: 1.3 }).ring(680, 440).ring(1060, 440).gap(1300).flat(500).fin().end().S,
    },
    { // 24 — финал каньона
      name: ['Canyon Finale', 'Финал каньона'], hint: ['', ''],
      build: () => Tr().flat(700).boost(0, 400).flat(500).ramp(260, 70).ring(650, 520).gap(1300).flat(500).cp(-300).flat(200)
        .gap(0, -340).ring(140, 360, { climb: 1, snap: 2.6 }).flat(500).cp(-300).flat(500)
        .ring(300, 450, { mv: { dx: 170, T: 2.4 } }).ring(710, 450, { snap: 1.15 }).ring(1120, 450).gap(1440).flat(500).cp(-300).flat(300)
        .spring(0, 140, 1100).flat(220).ring(360, 800).ring(800, 560, { snap: 1.3 }).gap(1150, 40).flat(400).fin().end().S,
    },
  ];
  // звёзды (куда долетает ~треть удачных прохождений автопилота) и время на третью звезду — tests/g7/stars.js
  const STARS = {"0": [2610, 240], "1": [3080, -50], "2": [3300, 290], "3": [2300, 260], "4": [5520, -397], "5": [3300, 140], "6": [2640, 260], "7": [3340, 312], "8": [2880, 200], "9": [3370, -340], "10": [2920, 360], "11": [2460, 67], "12": [4380, 0], "13": [4300, -8], "14": [4900, -60], "15": [4760, 247], "16": [2940, 360], "17": [1380, 190], "18": [3680, -580], "19": [2500, 360], "20": [7080, -117], "21": [2600, 240], "22": [3720, 340], "23": [7600, -433]};
  const BEST = {"0": 3.6, "1": 7.2, "2": 4.5, "3": 10.5, "4": 9.9, "5": 4.9, "6": 6.5, "7": 4.6, "8": 3.9, "9": 11.2, "10": 6, "11": 10.1, "12": 5.5, "13": 9, "14": 7.4, "15": 7.5, "16": 4.4, "17": 9.1, "18": 13.9, "19": 7.3, "20": 8.6, "21": 6.7, "22": 10.3, "23": 11.7};
  // обучение на первых уровнях (tests/g7/tutor.js): att — за сколько до кольца держать (у края ямы), lo..hi — где отпускать, правее кольца
  const GUIDE = {"0":[{"att":300,"lo":75,"hi":325},{"att":310,"lo":150,"hi":350}],"1":[{"att":300,"lo":75,"hi":325},{"climb":1},{"att":310,"lo":50,"hi":350}]};
  L.forEach((l, i) => {
    l.guide = GUIDE[i] || null; l.ser = Math.floor(i / 12);
    const b0 = l.build, st = STARS[i];
    l.build = () => { const S = b0(); if (st) S.star = { x: st[0], y: st[1], got: false }; return S; };
    l.par = Math.ceil((BEST[i] || 10) * 1.7 + 4);
  });
  H.levels = L;
})(typeof window !== 'undefined' ? window : globalThis);
