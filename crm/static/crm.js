// CRM «Наш декор»: мелочи без которых неудобно — автоотправка выбора и подтверждения.
document.addEventListener("change", e => {
  const el = e.target.closest("[data-autosubmit]");
  if (el && el.form) el.form.requestSubmit ? el.form.requestSubmit() : el.form.submit();
});
document.addEventListener("submit", e => {
  const b = e.submitter;
  if (b) { setTimeout(() => { b.disabled = true; }, 0); }
});

// Расчёт в сделке: сумма строки и «Итого» пересчитываются сразу при вводе штук или цены,
// а когда поле теряет фокус — строка сохраняется сама (кнопка «Сохранить» остаётся на всякий случай).
const rub = n => Math.round(n).toLocaleString("ru-RU") + "\u00a0₽";
function recalcLines(tbl) {
  let gross = 0;
  tbl.querySelectorAll("tbody tr").forEach(tr => {
    const q = tr.querySelector("input[name=qty]"), p = tr.querySelector("input[name=price]"), s = tr.querySelector('[data-l="Сумма"]');
    if (!q || !p || !s) return;
    const sum = (parseInt(q.value, 10) || 0) * (parseInt(p.value, 10) || 0);
    gross += sum; s.textContent = rub(sum);
  });
  const disc = parseFloat(tbl.dataset.discount || "0") || 0;
  const g = tbl.querySelector("[data-gross]"), t = tbl.querySelector("[data-total]");
  if (g) g.textContent = rub(gross);
  if (t) t.textContent = rub(gross * (1 - disc / 100));
}
document.addEventListener("input", e => {
  const tbl = e.target.closest("table[data-lines]");
  if (tbl && e.target.matches("input.ed")) recalcLines(tbl);
});
document.addEventListener("change", e => {
  if (e.target.matches("table[data-lines] input.ed") && e.target.form) {
    const f = e.target.form; f.requestSubmit ? f.requestSubmit() : f.submit();
  }
});

// «Скопировать расчёт для мессенджера» в карточке сделки
document.addEventListener("click", async e => {
  const b = e.target.closest("#copyCalc"); if (!b) return;
  const txt = (document.getElementById("calcText") || {}).textContent || "";
  try { await navigator.clipboard.writeText(txt); b.textContent = "Скопировано — вставьте в MAX, Telegram или SMS"; }
  catch (err) { const p = document.getElementById("calcText"); p.hidden = false; b.textContent = "Выделите текст ниже и скопируйте"; }
  setTimeout(() => { b.textContent = "Скопировать расчёт для мессенджера"; }, 4000);
});


// Уведомления на телефон (веб-пуши). iPhone — только из CRM, открытой со значка на экране «Домой» (iOS 16.4+).
(function () {
  const box = document.querySelector("[data-push]");
  if (!box) return;
  const key = box.dataset.key, csrf = box.dataset.csrf, compact = box.classList.contains("compact");
  const msg = t => { box.querySelector("[data-push-msg]").textContent = t; };
  const btn = n => box.querySelector("[data-push-" + n + "]");
  const show = (on, test, off) => { btn("on").hidden = !on; btn("test").hidden = !test; btn("off").hidden = !off; };
  const post = (url, data) => fetch(url, { method: "POST", credentials: "same-origin",
    headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams(Object.assign({ csrf }, data)) })
    .then(r => r.json()).catch(() => ({ ok: false, error: "нет связи с CRM" }));
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
  const standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  if (!key) { if (!compact) show(false, false, false); return; }
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
    if (ios && !standalone) {
      msg("Safari → «Поделиться» → «На экран „Домой“», откройте CRM со значка и включите уведомления там.");
      if (compact) box.hidden = false;
    } else msg("Этот браузер не умеет уведомления. На iPhone нужен iOS 16.4 или новее.");
    show(false, false, false); return;
  }
  const b64 = s => { const p = "=".repeat((4 - s.length % 4) % 4), raw = atob((s + p).replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from([...raw].map(c => c.charCodeAt(0))); };
  let reg = null;
  async function state() {
    reg = await navigator.serviceWorker.register("/sw.js");
    await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (Notification.permission === "denied") {
      msg("Уведомления запрещены в настройках телефона: Настройки → Уведомления → Наш декор → Допуск уведомлений.");
      show(false, false, false); if (compact) box.hidden = false; return;
    }
    if (sub) {
      await post("/push/subscribe", { sub: JSON.stringify(sub) });   // сервер мог забыть подписку — напомним
      msg("Включены на этом устройстве.");
      show(false, true, true); if (compact) box.hidden = true; return;
    }
    msg("Не включены на этом устройстве — заявки и письма будут приходить пушем, как сообщения.");
    show(true, false, false); if (compact) box.hidden = false;
  }
  btn("on").addEventListener("click", async () => {
    btn("on").disabled = true;
    try {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") { msg("Разрешение не дано. Можно включить позже: Настройки → Уведомления → Наш декор."); return; }
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64(key) });
      const r = await post("/push/subscribe", { sub: JSON.stringify(sub) });
      if (!r.ok) { msg("Не получилось: " + (r.error || "ошибка")); return; }
      await post("/push/test", { endpoint: sub.endpoint });
      msg("Готово — должна прийти проверка."); show(false, true, true);
      if (compact) setTimeout(() => { box.hidden = true; }, 4000);
    } catch (e) { msg("Не получилось включить: " + (e && e.message ? e.message : e)); }
    finally { btn("on").disabled = false; }
  });
  btn("test").addEventListener("click", async () => {
    const sub = reg && await reg.pushManager.getSubscription();
    const r = await post("/push/test", { endpoint: sub ? sub.endpoint : "" });
    msg(r.ok ? "Проверка отправлена — придёт через несколько секунд." : "Не ушло: " + (r.error || "ошибка"));
  });
  btn("off").addEventListener("click", async () => {
    const sub = reg && await reg.pushManager.getSubscription();
    if (sub) { await post("/push/unsubscribe", { endpoint: sub.endpoint }); await sub.unsubscribe(); }
    msg("Выключены на этом устройстве."); show(true, false, false);
  });
  state().catch(e => { msg("Не получилось проверить уведомления: " + (e && e.message ? e.message : e)); });
})();
