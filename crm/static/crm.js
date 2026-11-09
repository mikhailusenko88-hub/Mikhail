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
