// CRM «Наш декор»: мелочи без которых неудобно — автоотправка выбора и подтверждения.
document.addEventListener("change", e => {
  const el = e.target.closest("[data-autosubmit]");
  if (el && el.form) el.form.requestSubmit ? el.form.requestSubmit() : el.form.submit();
});
document.addEventListener("submit", e => {
  const b = e.submitter;
  if (b) { setTimeout(() => { b.disabled = true; }, 0); }
});
