'use strict';
/* Загрузчик сборки для площадок (Playgama): сначала мост — initialize, язык игрока и облачное сохранение, — и только потом файлы игры.
   Так требует Playgama: игра не грузится раньше моста, язык — только от площадки, прогресс — только через её облако. */
(function () {
  const FILES = ['physics.js', 'mud2d.js', 'i18n.js', 'three.min.js', 'r3d.js', 'view2d.js'];
  const boot = (window.PG_BOOT = { ok: false, save: null, lang: 'en' });
  let started = false;
  const go = () => { if (started) return; started = true; let i = 0; const next = () => { if (i >= FILES.length) return; const s = document.createElement('script'); s.src = FILES[i++]; s.async = false; s.onload = next; s.onerror = next; document.body.appendChild(s); }; next(); };
  const B = window.bridge; if (!B) { go(); return; }
  const late = new Promise((r) => setTimeout(r, 8000)); // площадка молчит — играем без неё, но не держим чёрный экран
  Promise.race([B.initialize().then(() => {
    boot.ok = true; const id = B.platform.id || '';
    let lg = B.platform.language || 'en'; // на CrazyGames мост отдаёт страну, язык — в их SDK
    if (id === 'crazy_games') { try { lg = window.CrazyGames.SDK.user.systemInfo.locale || 'en'; } catch (e) { lg = 'en'; } }
    boot.lang = String(lg).toLowerCase();
    return Promise.race([B.storage.get(['mud4.save']).then((v) => { boot.save = Array.isArray(v) ? v[0] : v; }), new Promise((r) => setTimeout(r, 4000))]);
  }), late]).catch(() => { boot.ok = false; }).then(go, go);
})();
