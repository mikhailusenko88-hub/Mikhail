/* «Наш декор» — окно «Чат» на всех страницах сайта.
   Сообщения уходят в CRM магазина (crm.nashdekor.ru/api/chat), сотрудникам приходит пуш, ответ появляется здесь же.
   Переписку узнаём по случайному ключу в localStorage этого браузера — без cookies и входа.
   Ссылки на ботов в MAX и Telegram появятся, когда боты будут запущены (BOTS ниже). */
(function () {
  "use strict";
  if (window.NDChat) return;
  var API = "https://crm.nashdekor.ru/api/chat";
  var BOTS = { max: "", tg: "" };                       // например {max: "https://max.ru/…_bot", tg: "https://t.me/…_bot"}
  var ON_SITE = /(^|\.)nashdekor\.ru$/.test(location.hostname);
  var me = document.currentScript && document.currentScript.src;
  var ROOT = me ? new URL("../", me).href : "/";
  var IS_TOUCH = matchMedia("(pointer: coarse)").matches;

  function ls(k, v) {
    try {
      if (v === undefined) return localStorage.getItem("ndchat." + k);
      if (v === null) localStorage.removeItem("ndchat." + k); else localStorage.setItem("ndchat." + k, String(v));
    } catch (e) { return null; }
  }
  var sid = ls("sid");
  if (!sid || !/^[A-Za-z0-9_-]{24,64}$/.test(sid)) {
    var a = new Uint8Array(24); (window.crypto || window.msCrypto).getRandomValues(a);
    sid = btoa(String.fromCharCode.apply(null, a)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    ls("sid", sid);
  }

  var css = ""
    + ".ndc-btn{position:fixed;right:max(16px,env(safe-area-inset-right));bottom:max(16px,env(safe-area-inset-bottom));z-index:1000;display:flex;align-items:center;gap:8px;"
    + "height:54px;padding:0 20px 0 16px;border:0;border-radius:999px;background:#1f1f20;color:#fff;font:600 16px/1 inherit;font-family:inherit;cursor:pointer;"
    + "box-shadow:0 6px 24px rgba(0,0,0,.22)}"
    + ".ndc-btn svg{width:24px;height:24px}"
    + ".ndc-btn .ndc-n{position:absolute;top:-4px;right:-2px;min-width:20px;height:20px;padding:0 5px;border-radius:999px;background:#c2410c;color:#fff;font-size:12px;line-height:20px;text-align:center}"
    + ".ndc-btn[hidden],.ndc-n[hidden]{display:none}"
    + ".ndc-panel{position:fixed;right:max(16px,env(safe-area-inset-right));bottom:max(16px,env(safe-area-inset-bottom));z-index:1001;width:min(380px,calc(100vw - 32px));"
    + "height:min(580px,calc(100vh - 32px));display:flex;flex-direction:column;margin:0;padding:0;box-sizing:border-box;background:#fff;color:#1f1f20;border-radius:18px;overflow:hidden;"
    + "box-shadow:0 18px 60px rgba(0,0,0,.28);font-family:inherit}"
    + ".ndc-panel[hidden]{display:none}"
    + "@media (max-width:560px){.ndc-panel{right:0;left:0;bottom:0;width:100%;height:calc(100% - env(safe-area-inset-top) - 12px);border-radius:18px 18px 0 0}}"
    + ".ndc-head{display:flex;align-items:flex-start;gap:10px;padding:14px 14px 12px 16px;background:#1f1f20;color:#fff}"
    + ".ndc-head b{display:block;font-size:17px}.ndc-head small{display:block;font-size:13px;opacity:.75;margin-top:3px;line-height:1.35}"
    + ".ndc-x{margin-left:auto;flex:0 0 auto;width:36px;height:36px;border:0;border-radius:50%;background:rgba(255,255,255,.12);color:#fff;font-size:22px;line-height:36px;cursor:pointer}"
    + ".ndc-log{flex:1;overflow-y:auto;padding:14px 12px;display:flex;flex-direction:column;gap:8px;background:#f6f5f1;-webkit-overflow-scrolling:touch}"
    + ".ndc-m{max-width:85%;padding:9px 12px;border-radius:16px;font-size:15px;line-height:1.4;white-space:pre-wrap;word-wrap:break-word}"
    + ".ndc-m small{display:block;font-size:11px;opacity:.6;margin-top:3px}"
    + ".ndc-m.staff,.ndc-m.hello{align-self:flex-start;background:#fff;border:1px solid #e6e3dc;border-bottom-left-radius:6px}"
    + ".ndc-m.me{align-self:flex-end;background:#1f1f20;color:#fff;border-bottom-right-radius:6px}"
    + ".ndc-m.sys{align-self:center;background:transparent;color:#6b6b6b;font-size:13px;text-align:center;padding:2px 8px}"
    + ".ndc-quick{display:flex;flex-wrap:wrap;gap:6px;padding:0 12px 10px;background:#f6f5f1}"
    + ".ndc-quick button{border:1px solid #d9d6cf;background:#fff;border-radius:999px;padding:7px 12px;font:inherit;font-size:14px;color:#1f1f20;cursor:pointer}"
    + ".ndc-card{margin:0 12px 10px;padding:12px;background:#fff;border:1px solid #e6e3dc;border-radius:14px;font-size:14px}"
    + ".ndc-card p{margin:0 0 8px;line-height:1.4}"
    + ".ndc-card input{width:100%;box-sizing:border-box;margin:0 0 6px;padding:10px 12px;border:1px solid #d9d6cf;border-radius:10px;font:inherit;font-size:16px}"
    + ".ndc-card .ndc-row{display:flex;gap:6px}.ndc-card .ndc-row button{flex:1}"
    + ".ndc-card button{padding:10px 12px;border-radius:10px;border:0;background:#1f1f20;color:#fff;font:inherit;font-size:15px;cursor:pointer}"
    + ".ndc-card button.ndc-ghost{background:#fff;color:#1f1f20;border:1px solid #d9d6cf}"
    + ".ndc-form{border-top:1px solid #ebe8e1;padding:10px 12px calc(10px + env(safe-area-inset-bottom));background:#fff}"
    + ".ndc-consent{display:flex;gap:8px;align-items:flex-start;font-size:12.5px;line-height:1.35;color:#555;margin:0 0 8px}"
    + ".ndc-consent input{margin-top:2px;width:16px;height:16px;flex:0 0 auto}.ndc-consent a{color:#1f1f20}"
    + ".ndc-in{display:flex;gap:8px;align-items:flex-end}"
    + ".ndc-in textarea{flex:1;resize:none;max-height:120px;min-height:44px;box-sizing:border-box;padding:11px 12px;border:1px solid #d9d6cf;border-radius:14px;font:inherit;font-size:16px;line-height:1.35}"
    + ".ndc-in button{flex:0 0 auto;width:44px;height:44px;border:0;border-radius:50%;background:#1f1f20;color:#fff;cursor:pointer}"
    + ".ndc-in button:disabled{opacity:.4}"
    + ".ndc-in svg{width:20px;height:20px}"
    + ".ndc-bots{font-size:12.5px;color:#666;margin-top:8px}.ndc-bots a{color:#1f1f20;margin-left:6px}"
    + ".ndc-err{font-size:13px;color:#b42318;margin:0 0 6px}"
    + ".ndc-panel [hidden]{display:none!important}.ndc-quick:empty{display:none}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

  var ICON_CHAT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"/></svg>';
  var ICON_SEND = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>';

  var btn = document.createElement("button");
  btn.type = "button"; btn.className = "ndc-btn"; btn.setAttribute("aria-label", "Открыть чат с магазином");
  btn.innerHTML = ICON_CHAT + "<span>Чат</span><span class=\"ndc-n\" hidden></span>";
  var panel = document.createElement("div");
  panel.className = "ndc-panel"; panel.hidden = true; panel.setAttribute("role", "dialog"); panel.setAttribute("aria-label", "Чат с магазином «Наш декор»");
  panel.innerHTML = ""
    + "<div class=\"ndc-head\"><div><b>Наш декор — чат</b><small>Ответим здесь же. Обычно в течение часа в рабочее время.</small></div>"
    + "<button type=\"button\" class=\"ndc-x\" aria-label=\"Закрыть чат\">×</button></div>"
    + "<div class=\"ndc-log\" aria-live=\"polite\"></div>"
    + "<div class=\"ndc-quick\"></div>"
    + "<div class=\"ndc-card\" hidden><p>Оставьте телефон или e-mail — ответим, даже если вы уйдёте с сайта.</p>"
    + "<input type=\"text\" class=\"ndc-name\" placeholder=\"Имя\" autocomplete=\"name\">"
    + "<input type=\"text\" class=\"ndc-contact\" placeholder=\"Телефон или e-mail\" autocomplete=\"tel\">"
    + "<div class=\"ndc-row\"><button type=\"button\" class=\"ndc-save\">Отправить</button><button type=\"button\" class=\"ndc-ghost ndc-skip\">Не сейчас</button></div></div>"
    + "<form class=\"ndc-form\" novalidate><div class=\"ndc-err\" hidden></div>"
    + "<label class=\"ndc-consent\"><input type=\"checkbox\" class=\"ndc-ok\"><span>Согласен на <a href=\"" + ROOT + "consent.html\" target=\"_blank\">обработку персональных данных</a> и с <a href=\"" + ROOT + "privacy.html\" target=\"_blank\">политикой</a></span></label>"
    + "<div class=\"ndc-in\"><textarea rows=\"1\" placeholder=\"Напишите вопрос…\" aria-label=\"Сообщение\"></textarea>"
    + "<button type=\"submit\" aria-label=\"Отправить\">" + ICON_SEND + "</button></div>"
    + ((BOTS.max || BOTS.tg) ? "<div class=\"ndc-bots\">Или в мессенджере:" + (BOTS.max ? "<a href=\"" + BOTS.max + "\" target=\"_blank\" rel=\"noopener\">MAX</a>" : "") + (BOTS.tg ? "<a href=\"" + BOTS.tg + "\" target=\"_blank\" rel=\"noopener\">Telegram</a>" : "") + "</div>" : "")
    + "</form>";
  document.body.appendChild(btn); document.body.appendChild(panel);

  var $ = function (s) { return panel.querySelector(s); };
  var log = $(".ndc-log"), ta = $("textarea"), form = $(".ndc-form"), err = $(".ndc-err"), ok = $(".ndc-ok"), card = $(".ndc-card"), quick = $(".ndc-quick");
  var badge = btn.querySelector(".ndc-n");
  var last = 0, seen = +(ls("seen") || 0), open = false, timer = 0, sending = false;
  var started = ls("started") === "1";
  if (ls("consent") === "1") $(".ndc-consent").hidden = true;

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function add(cls, text, small) {
    var d = document.createElement("div"); d.className = "ndc-m " + cls;
    d.innerHTML = esc(text) + (small ? "<small>" + esc(small) + "</small>" : "");
    log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
  }
  // Подсказки «по месту»: товар — про этот артикул, раздел — про раздел, доставка — про доставку, главная — общие.
  // Показываются только до первого сообщения и прячутся, как только клиент начал печатать сам.
  function suggestions() {
    var it = window.P && window.P.item, path = location.pathname;
    if (it && it.a) {
      var a = it.a, c = it.c;
      if (c === "panel" || c === "color") return ["Есть " + a + " в наличии?", "Сколько " + a + " нужно на мою стену?", "Доставка " + a + " в мой город"];
      if (c === "plinth") return ["Есть " + a + " в наличии?", "Сколько " + a + " нужно на комнату?", "Чем клеить и красить " + a + "?"];
      if (c === "cornice") return ["Есть " + a + " в наличии?", "Подойдёт " + a + " к натяжному потолку?", "Сколько " + a + " нужно на комнату?"];
      if (c === "mold") return ["Есть " + a + " в наличии?", "Сколько " + a + " нужно на рамки?", "Чем клеить и красить " + a + "?"];
      return ["Есть " + a + " в наличии?", "Какой уголок подойдёт к моим панелям?", "Доставка " + a + " в мой город"];
    }
    var m = path.match(/\/catalog\/([a-z-]+)\//), s = m ? m[1] : "";
    if (/stenovye-paneli|reechnye-paneli/.test(s)) return ["Какую панель выбрать для ТВ-зоны?", "Посчитайте панели на мою стену", "Что есть в наличии?"];
    if (s === "paneli-pod-derevo") return ["Какой декор ближе к дубу?", "Посчитайте панели на мою стену", "Что есть в наличии?"];
    if (s === "plintusy") return ["Какой высоты плинтус выбрать?", "Сколько плинтуса нужно на комнату?", "Что есть в наличии?"];
    if (s === "plintus-s-podsvetkoy") return ["Какая LED-лента подойдёт?", "Сколько нужно на комнату?", "Что есть в наличии?"];
    if (s === "karnizy") return ["Какой потолочный плинтус к натяжному потолку?", "Сколько нужно на комнату?", "Что есть в наличии?"];
    if (s === "moldingi") return ["Помогите разложить рамки на стене", "Сколько молдинга нужно на рамки?", "Что есть в наличии?"];
    if (s === "ugolki") return ["Какой уголок подойдёт к моим панелям?", "Сколько уголков нужно?"];
    if (/\/dostavka\//.test(path)) return ["Сколько стоит доставка в мой город?", "Когда отправите заказ?", "Можно забрать самовывозом?"];
    if (/\/stati\/[a-z]/.test(path)) return ["Вопрос по статье", "Посчитайте материал на мою комнату"];
    return ["Что есть в наличии?", "Посчитайте мою стену", "Доставка в мой город"];
  }
  function hello() {
    add("hello", "Здравствуйте! Это чат магазина «Наш декор». Спросите про наличие, цену, расчёт стены или доставку — ответим здесь же.", "Наш декор");
    if (!started) quick.innerHTML = suggestions().map(function (x) { return "<button type=\"button\">" + esc(x) + "</button>"; }).join("");
  }
  function quickShow(on) { if (quick.innerHTML) quick.hidden = !on; }
  function showErr(t) { err.textContent = t; err.hidden = !t; }
  function render(msgs) {
    msgs.forEach(function (m) {
      if (m.id <= last) return;
      last = m.id;
      if (m.who === "me") add("me", m.text);
      else { add("staff", m.text, (m.author ? m.author + ", " : "") + "Наш декор"); if (!open && m.id > seen) unread(); }
    });
    if (open) markSeen();
  }
  function unread() {
    var n = (+badge.textContent || 0) + 1; badge.textContent = n; badge.hidden = false;
  }
  function markSeen() { seen = last; ls("seen", seen); badge.hidden = true; badge.textContent = ""; }

  function req(method, body) {
    var url = API + (method === "GET" ? "?sid=" + encodeURIComponent(sid) + "&after=" + last : "");
    return fetch(url, { method: method, mode: "cors", credentials: "omit", headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) { j._status = r.status; return j; });
    });
  }
  function poll() {
    if (!ON_SITE || !started || document.hidden) return;
    req("GET").then(function (j) { if (j.ok) render(j.msgs || []); }).catch(function () {});
  }
  function schedule() {
    clearInterval(timer);
    if (!started) return;
    timer = setInterval(poll, open ? 4000 : 25000);
  }

  function send(text, extra) {
    if (sending) return;
    if (!ON_SITE) { showErr("Чат работает на сайте nashdekor.ru."); return; }
    if (ls("consent") !== "1" && !ok.checked) { showErr("Отметьте согласие на обработку данных — без него мы не можем принять сообщение."); return; }
    showErr(""); sending = true; form.querySelector("button[type=submit]").disabled = true;
    var body = { sid: sid, text: text || "", consent: true, page: location.pathname, after: last, website: "" };
    if (extra) for (var k in extra) body[k] = extra[k];
    req("POST", body).then(function (j) {
      if (j.ok) {
        ls("consent", "1"); $(".ndc-consent").hidden = true;
        if (!started) { started = true; ls("started", "1"); }
        quick.innerHTML = ""; quick.hidden = true;
        render(j.msgs || []); schedule();
        if (text && ls("contact") !== "1" && !card.dataset.skip) setTimeout(function () { card.hidden = false; log.scrollTop = log.scrollHeight; }, 600);
        return true;
      }
      showErr(j._status === 503 ? "Чат сейчас не принимает сообщения. Оставьте заявку в форме на странице или напишите на zakaz@nashdekor.ru."
        : j._status === 429 ? "Слишком много сообщений подряд — подождите пару минут."
        : "Не получилось отправить. Проверьте интернет и попробуйте ещё раз.");
      return false;
    }).catch(function () { showErr("Нет связи с магазином. Проверьте интернет и попробуйте ещё раз."); return false; })
      .then(function (good) {
        sending = false; form.querySelector("button[type=submit]").disabled = false;
        if (good && text) { ta.value = ""; grow(); }
      });
  }

  function grow() { ta.style.height = "auto"; ta.style.height = Math.min(120, ta.scrollHeight) + "px"; }
  function show(prefill) {
    open = true; panel.hidden = false; btn.hidden = true;
    if (started) poll();
    if (prefill) { ta.value = prefill; grow(); }
    markSeen(); schedule();
    if (!IS_TOUCH || prefill) setTimeout(function () { ta.focus(); }, 50);
    if (IS_TOUCH && innerWidth <= 560) document.documentElement.style.overflow = "hidden";
  }
  function hide() {
    open = false; panel.hidden = true; btn.hidden = false; schedule();
    document.documentElement.style.overflow = "";
  }

  btn.addEventListener("click", function () { show(); });
  $(".ndc-x").addEventListener("click", hide);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && open) hide(); });
  form.addEventListener("submit", function (e) { e.preventDefault(); var t = ta.value.trim(); if (t) send(t); });
  ta.addEventListener("input", function () { grow(); quickShow(!started && !ta.value.trim()); });
  ta.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey && !IS_TOUCH) { e.preventDefault(); var t = ta.value.trim(); if (t) send(t); }
  });
  quick.addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    var t = b.textContent;
    if (t === "Вопрос по статье") { var h = document.querySelector("h1"); t = "Вопрос по статье «" + (h ? h.textContent.trim() : document.title) + "»: "; }
    ta.value = t; grow(); quickShow(false);
    ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length);
  });
  $(".ndc-save").addEventListener("click", function () {
    var c = $(".ndc-contact").value.trim(), n = $(".ndc-name").value.trim();
    if (!/\d{6,}|@/.test(c.replace(/[\s()-]/g, ""))) { $(".ndc-contact").focus(); return; }
    send("", { contact: c, name: n });
    ls("contact", "1"); card.hidden = true;
    add("sys", "Спасибо! Ответим здесь, а если уйдёте с сайта — по указанному контакту.");
  });
  $(".ndc-skip").addEventListener("click", function () { card.hidden = true; card.dataset.skip = "1"; });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) poll(); });

  hello();

  // Открыть из ссылки (#chat или ?chat=1 — из письма) или кнопкой на странице: NDChat.open("текст")
  window.NDChat = { open: show, close: hide };
  if (location.hash === "#chat" || /[?&]chat=1/.test(location.search)) setTimeout(function () { show(); }, 300);
  if (started) { poll(); schedule(); }
})();
