'use strict';
/* Hook Truck — 12 уровней. Дорога строится слева направо: flat — ровно, gap — яма (dy: другой край выше/ниже),
   ring — кольцо (h — высота над дорогой), ceil — потолок пещеры, boost — ускоритель, ramp — трамплин. */
(function (root) {
  const H = root.HookSim, Tr = () => H.Track().start(-300, 600);
  const L = [
    { // 1 — первый мах
      name: ['First Swing', 'Первый мах'], hint: ['Hold HOOK at the pit. Let go on the way up!', 'Держи КРЮК у ямы. Отпусти на взлёте!'],
      build: () => Tr().flat(1100).ring(250, 380).gap(500).flat(700).ring(260, 400).star(420, 340).gap(540).flat(300).fin().end().S,
    },
    { // 2 — на стену
      name: ['Up the Wall', 'На стену'], hint: ['Drive into the wall and hook on — the winch pulls you up', 'Упрись в стену и цепляйся — лебёдка затянет наверх'],
      build: () => Tr().flat(1000).ring(250, 380).gap(480).flat(500).cp(-300).flat(300)
        .gap(0, -340).ring(140, 360, { climb: 1 }).flat(600).ring(260, 400).star(300, 470).gap(520).flat(300).fin().end().S,
    },
    { // 3 — два кольца
      name: ['Double Swing', 'Два кольца'], hint: ['Let go of the first ring — grab the second!', 'Отпусти первое кольцо — хватай второе!'],
      build: () => Tr().flat(1000).ring(260, 420).gap(560).flat(500).cp(-300).flat(500)
        .ring(300, 450).ring(700, 450).star(740, 360).gap(1000).flat(300).fin().end().S,
    },
    { // 4 — пробный уровень
      name: ['Swing & Climb', 'Мах и обрыв'], hint: ['', ''],
      build: () => { const b = Tr().flat(1000).hill(520, 46).flat(420); b.ring(300, 430).gap(600); b.flat(260).cp(-80).flat(420); b.gap(0, -380).ring(140, 360, { climb: 1 }); b.flat(80).cp(0).flat(820); b.ring(300, 450).ring(700, 450).star(740, 360).gap(1000); b.flat(700).slope(700, -160).flat(200).fin(100).end(); return b.S; },
    },
    { // 5 — трамплин и захват в воздухе
      name: ['Boost & Fly', 'Разгон и полёт'], hint: ['Fly off the ramp and hook in the air!', 'Слетай с трамплина и цепляйся в воздухе!'],
      build: () => Tr().flat(700).boost(0, 400).flat(500).ramp(260, 70).ring(650, 520).star(950, 600).gap(1300).flat(600).cp(-400).flat(300)
        .gap(0, -340).ring(140, 360, { climb: 1 }).flat(700).boost(0, 300).flat(300).ramp(220, 60).ring(520, 520).gap(1100).flat(300).fin().end().S,
    },
    { // 6 — кольца едут
      name: ['Moving Rings', 'Кольца едут'], hint: ['The rings move — time your hook', 'Кольца ездят — лови момент'],
      build: () => Tr().flat(1000).ring(260, 420, { mv: { dx: 200, T: 3 } }).gap(560).flat(600).cp(-400).flat(300)
        .ring(300, 450, { mv: { dx: 180, T: 2.6 } }).ring(720, 450, { mv: { dy: 120, T: 2.2, ph: 1.5 } }).star(760, 360).gap(1050).flat(300).fin().end().S,
    },
    { // 7 — пещера
      name: ['Cave', 'Пещера'], hint: ["Cave! Don't fly into the ceiling", 'Пещера! Не влети в потолок'],
      build: () => Tr().flat(900).flat(400).ceil(0, 3300, 680).ring(300, 440).gap(520).flat(500).cp(-300).ring(300, 440).gap(520).flat(500)
        .ring(300, 440).ring(660, 440).star(480, 300).gap(900).flat(400).flat(300).fin().end().S,
    },
    { // 8 — ломкие кольца
      name: ['Snap!', 'Хрусь!'], hint: ['Cracked rings snap — don\'t hang too long!', 'Треснутые кольца рвутся — не висни долго!'],
      build: () => Tr().flat(1000).ring(260, 420, { snap: 1.4 }).gap(560).flat(600).cp(-400).flat(300)
        .ring(300, 450, { snap: 1.2 }).ring(700, 450, { snap: 1.2 }).star(740, 360).gap(1000).flat(300).fin().end().S,
    },
    { // 9 — длинная цепь
      name: ['Long Chain', 'Длинная цепь'], hint: ['', ''],
      build: () => Tr().flat(1200).ring(300, 450).ring(700, 470).ring(1100, 470).ring(1500, 450).star(1300, 420).gap(1750, 100).flat(500).fin().end().S,
    },
    { // 10 — башня: стены с треснутыми кольцами (тянуть быстрее!) и ямы между ними
      name: ['Tower', 'Башня'], hint: ['Cracked ring on the wall — pull fast!', 'Треснутое кольцо на стене — тяни быстрее!'],
      build: () => Tr().flat(1000).gap(0, -300).ring(140, 360, { climb: 1, snap: 2.6 }).flat(650).ring(250, 420).gap(480).flat(400)
        .gap(0, -300).ring(140, 360, { climb: 1, snap: 2.6 }).flat(600).cp(-300).ring(260, 440).gap(500).flat(400)
        .gap(0, -300).ring(140, 360, { climb: 1 }).flat(500).fin().end().S,
    },
    { // 11 — вниз по каньону
      name: ['Canyon', 'Каньон'], hint: ['', ''],
      build: () => Tr().flat(1000).ring(300, 460).gap(700, 250).flat(500).cp(-300).flat(300)
        .ring(300, 460, { mv: { dx: 200, T: 2.2 } }).gap(800, 200).flat(500).ring(280, 440, { snap: 1.2 }).gap(650, 150).flat(300).fin().end().S,
    },
    { // 12 — финал
      name: ['Grand Finale', 'Финал'], hint: ['', ''],
      build: () => Tr().flat(700).boost(0, 400).flat(500).ramp(260, 70).ring(650, 520).gap(1300).flat(500).cp(-300).flat(200)
        .gap(0, -340).ring(140, 360, { climb: 1 }).flat(500).cp(-300).flat(500)
        .ring(300, 450, { mv: { dx: 150, T: 2.6 } }).ring(700, 450, { snap: 1.3 }).ring(1100, 450).star(900, 560).gap(1400).flat(400).fin().end().S,
    },
  ];
  // звёзды (куда долетает ~треть удачных прохождений автопилота) и время на третью звезду — tests/g7/stars.js
  const STARS = {"0": [2500, 300], "1": [3200, -120], "2": [1360, 220], "3": [4320, 0], "4": [5560, -417], "5": [1240, -20], "6": [3700, 300], "7": [1320, 220], "8": [2760, 360], "9": [3370, -300], "10": [2940, 550], "11": [2620, 187]};
  const BEST = {"0": 4.1, "1": 6.7, "2": 4.9, "3": 9.8, "4": 9.2, "5": 4.7, "6": 6.5, "7": 4.9, "8": 3.6, "9": 10.5, "10": 5.4, "11": 9};
  L.forEach((l, i) => {
    const b0 = l.build, st = STARS[i];
    l.build = () => { const S = b0(); if (st) S.star = { x: st[0], y: st[1], got: false }; return S; };
    l.par = Math.ceil((BEST[i] || 10) * 1.7 + 4);
  });
  H.levels = L;
})(typeof window !== 'undefined' ? window : globalThis);
