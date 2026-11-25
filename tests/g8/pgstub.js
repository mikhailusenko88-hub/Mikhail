// Заглушка Playgama Bridge для проверки «как на площадке»: реклама открывается, досматривается или не грузится — по window.__adMode
(function () {
  const L = (window.__pg = { msgs: [], ads: [], store: {}, ev: [], ver: null }), hs = {};
  const emit = (ev, v) => (hs[ev] || []).forEach((f) => f(v));
  window.bridge = {
    initialize: () => new Promise((r) => setTimeout(r, 300)),
    set gameVersion(v) { L.ver = v; }, get gameVersion() { return L.ver; },
    analytics: { send: (name, data) => { L.ev.push([name, data || {}]); } },
    platform: { id: 'playgama', language: window.__pgLang || 'en', isAudioEnabled: true, sendMessage: (m, d) => L.msgs.push(m + (d && d.level ? ':' + d.level : '')), on: (ev, f) => { (hs[ev] = hs[ev] || []).push(f); } },
    advertisement: {
      isRewardedSupported: true, isInterstitialSupported: true, on: (ev, f) => { (hs[ev] = hs[ev] || []).push(f); },
      showInterstitial: (p) => { L.ads.push('inter:' + p); setTimeout(() => emit('interstitial_state_changed', 'opened'), 100); setTimeout(() => emit('interstitial_state_changed', 'closed'), 900); },
      showRewarded: (p) => { L.ads.push('rew:' + p); if (window.__adMode === 'fail') { setTimeout(() => emit('rewarded_state_changed', 'failed'), 200); return; }
        setTimeout(() => emit('rewarded_state_changed', 'opened'), 100); if (window.__adMode !== 'skip') setTimeout(() => emit('rewarded_state_changed', 'rewarded'), 800); setTimeout(() => emit('rewarded_state_changed', 'closed'), 1000); },
    },
    storage: { get: (k) => Promise.resolve(L.store[k] || null), set: (k, v) => { L.store[k] = v; return Promise.resolve(); } },
  };
  window.__pgEmit = emit;
})();
