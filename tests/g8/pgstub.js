// Заглушка Playgama Bridge для проверки «как на площадке»: реклама открывается, досматривается или не грузится — по window.__adMode
(function () {
  const L = (window.__pg = { msgs: [], ads: [], store: Object.assign({}, window.__pgStore0 || {}), ev: [], ver: null }), hs = {}; // __pgStore0 — что уже лежит в облаке площадки до запуска
  for (const k of ['hooktruck_v1', 'mud4.save']) { try { const v = localStorage.getItem('__pgcloud:' + k) || localStorage.getItem(k); if (v && !(k in L.store)) L.store[k] = v; } catch (e) { /* */ } } // для тестов: «облако» переживает перезагрузку (__pgcloud:), а сохранение в памяти браузера считаем уже лежащим в облаке
  const emit = (ev, v) => (hs[ev] || []).forEach((f) => f(v));
  window.bridge = {
    initialize: () => new Promise((r) => setTimeout(r, 300)),
    set gameVersion(v) { L.ver = v; }, get gameVersion() { return L.ver; },
    analytics: { send: (name, data) => { L.ev.push([name, data || {}]); } },
    platform: { id: 'playgama', language: window.__pgLang || 'en', isAudioEnabled: window.__pgAudio !== false, sendMessage: (m, d) => L.msgs.push(m + (d && d.level ? ':' + d.level : '')), on: (ev, f) => { (hs[ev] = hs[ev] || []).push(f); } },
    advertisement: {
      isRewardedSupported: true, isInterstitialSupported: !window.__pgNoInter, on: (ev, f) => { (hs[ev] = hs[ev] || []).push(f); },
      showInterstitial: (p) => { L.ads.push('inter:' + p); setTimeout(() => emit('interstitial_state_changed', 'opened'), 100); setTimeout(() => emit('interstitial_state_changed', 'closed'), 900); },
      showRewarded: (p) => { L.ads.push('rew:' + p); if (window.__adMode === 'fail') { setTimeout(() => emit('rewarded_state_changed', 'failed'), 200); return; }
        setTimeout(() => emit('rewarded_state_changed', 'opened'), 100); if (window.__adMode !== 'skip') setTimeout(() => emit('rewarded_state_changed', 'rewarded'), 800); setTimeout(() => emit('rewarded_state_changed', 'closed'), 1000); },
    },
    storage: { get: (k) => Promise.resolve(Array.isArray(k) ? k.map((q) => L.store[q] || null) : L.store[k] || null), set: (k, v) => { L.store[k] = v; try { localStorage.setItem('__pgcloud:' + k, v); } catch (e) { /* */ } return Promise.resolve(); } },
  };
  window.__pgEmit = emit;
})();
