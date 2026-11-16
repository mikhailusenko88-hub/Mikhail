/* Сайт внутри MAX (мини-приложение бота «Наш декор»).
   Подключается только когда сайт открыт из MAX: в адресе есть #WebAppData=… (первый экран)
   или эти данные уже сохранены в sessionStorage (переходы по сайту). В обычном браузере не грузится.
   Делает: стрелка «Назад» MAX, раздел по параметру запуска (startapp), внешние ссылки — через MAX,
   метка источника «max» для счётчика посещений, «Отправить номер из MAX» в формах (номер с подписью MAX → CRM),
   «Отправить в MAX» на товаре и в расчёте стены. */
(function () {
  "use strict";
  var W = window.WebApp;
  if (!W) return;
  var S = window.sessionStorage;
  function get(k) { try { return S.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { S.setItem(k, v); } catch (e) {} }
  function mobile() { return W.platform === "ios" || W.platform === "android"; }

  var launch = /(^#|&)WebAppData=/.test(location.hash);
  var param = "";
  try {
    param = (W.initDataUnsafe && W.initDataUnsafe.start_param) || new URLSearchParams(location.search).get("WebAppStartParam") || "";
  } catch (e) {}

  // Куда открыть по параметру запуска: https://max.ru/<бот>?startapp=calc
  //   calc, catalog, models, order, contacts, live, pro — блоки главной; calc-<артикул> — расчёт с этой панелью (calc-3-7),
  //   calc-<артикул>_<ширина>_<высота> — ещё и с размерами стены в см (calc-a907_320_270);
  //   dostavka, oplata, stati — страницы; c-<раздел> — раздел каталога; p-<артикул> — товар (p-a907, p-3-7);
  //   s-<статья> — статья. Те же правила — в bot/channel.py (app_payload) для кнопок постов канала.
  var BLOCKS = { calc: 1, catalog: 1, models: 1, order: 1, contacts: 1, live: 1, pro: 1 };
  var PAGES = { dostavka: "/dostavka/", oplata: "/oplata/", stati: "/stati/" };
  function target(p) {
    p = String(p || "").toLowerCase();
    if (!/^[a-z0-9_-]{1,60}$/.test(p)) return "";
    if (BLOCKS[p]) return "/#" + p;
    if (PAGES[p]) return PAGES[p];
    var m = /^calc-([a-z0-9-]+?)(?:_(\d{1,4})_(\d{1,4}))?$/.exec(p);
    if (m) return "/?panel=" + m[1].toUpperCase() + (m[2] ? "&w=" + m[2] + "&h=" + m[3] : "") + "#calc";
    m = /^c-([a-z0-9-]+)$/.exec(p);
    if (m) return "/catalog/" + m[1] + "/";
    m = /^p-([a-z0-9-]+)$/.exec(p);
    if (m) return "/p/" + m[1] + "/";
    m = /^s-([a-z0-9-]+)$/.exec(p);
    if (m) return "/stati/" + m[1] + "/";
    return "";
  }

  if (launch) {
    set("mxStart", location.pathname);
    // убрать служебные данные запуска из адреса (их уже сохранила библиотека MAX)
    try { history.replaceState(history.state, "", location.pathname + location.search.replace(/([?&])WebAppStartParam=[^&]*&?/, "$1").replace(/[?&]$/, "")); } catch (e) {}
    var to = target(param);
    if (to) {
      var path = to.split("#")[0];
      if (path === location.pathname) {
        var id = to.split("#")[1];
        if (id) {
          var go = function () { var el = document.getElementById(id); if (el) el.scrollIntoView(); };
          if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { setTimeout(go, 50); });
          else setTimeout(go, 50);
        }
      } else {
        set("mxStart", path.split("?")[0]);   // перешли сразу на нужную страницу — «Назад» с неё не нужен
        location.replace(to);
        return;
      }
    }
  }

  // Стрелка «Назад» в шапке MAX: на первом экране скрыта, дальше — шаг назад по сайту
  function sync() {
    var start = get("mxStart");
    try { if (!start || location.pathname === start) W.BackButton.hide(); else W.BackButton.show(); } catch (e) {}
  }
  try { W.BackButton.onClick(function () { history.back(); }); } catch (e) {}
  sync();
  window.addEventListener("pageshow", sync);
  window.addEventListener("popstate", sync);

  // Ссылки: max.ru — внутри MAX, другие сайты — во внешнем браузере (иначе мини-приложение уходит со страницы
  // магазина и вернуться нельзя); свои страницы — здесь же, без новых вкладок; tel: и mailto: — как есть.
  function outside(u) {
    if (/(^|\.)max\.ru$/.test(u.hostname)) W.openMaxLink(u.href); else W.openLink(u.href);
  }
  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button) return;
    var a = e.target && e.target.closest ? e.target.closest("a[href]") : null;
    if (!a) return;
    var u;
    try { u = new URL(a.getAttribute("href"), location.href); } catch (x) { return; }
    if (u.protocol !== "http:" && u.protocol !== "https:") return;
    if (u.origin === location.origin) {
      if (a.hasAttribute("download") && mobile() && W.downloadFile) {
        e.preventDefault();
        var name = a.getAttribute("download") || decodeURIComponent(u.pathname.split("/").pop() || "file");
        W.downloadFile(u.href, name).catch(function () { location.href = u.href; });
      } else if (a.target === "_blank") {
        e.preventDefault();
        location.href = u.href;
      }
      return;
    }
    e.preventDefault();
    outside(u);
  }, true);
  var open0 = window.open;
  window.open = function (url) {
    try {
      var u = new URL(url, location.href);
      if (u.protocol === "http:" || u.protocol === "https:") {
        if (u.origin === location.origin) location.href = u.href; else outside(u);
        return null;
      }
    } catch (e) {}
    return open0.apply(window, arguments);
  };

  // ---------- Номер из MAX в одно касание: заявка, заказ, звонок, 3D-модели
  // requestContact отдаёт номер с подписью MAX; подпись и данные запуска (WebApp.initData) проверяет CRM.
  var BOT = "https://max.ru/id470331302505_bot";
  var signed = null;
  var user = (W.initDataUnsafe && W.initDataUnsafe.user) || null;
  window.NDMax = { lead: function () { return { init: W.initData || "", contact: signed }; } };
  function fmtPhone(p) {
    var d = String(p || "").replace(/\D/g, "");
    if (d.length === 11 && (d[0] === "7" || d[0] === "8")) return "+7 " + d.slice(1, 4) + " " + d.slice(4, 7) + "-" + d.slice(7, 9) + "-" + d.slice(9);
    return d ? "+" + d : "";
  }
  function phoneButton(inputId, nameId) {
    var inp = document.getElementById(inputId);
    if (!inp || inp.getAttribute("data-mx") || typeof W.requestContact !== "function") return;
    inp.setAttribute("data-mx", "1");
    var nm = document.getElementById(nameId);
    if (nm && !nm.value.trim() && user && user.first_name) nm.value = String(user.first_name).slice(0, 60);
    var b = document.createElement("button");
    b.type = "button"; b.className = "btn sm ghost"; b.style.cssText = "align-self:flex-start;margin-top:4px";
    b.textContent = "Отправить номер из MAX";
    b.addEventListener("click", function (e) {
      e.preventDefault();
      b.disabled = true;
      W.requestContact().then(function (r) {
        if (r && r.phone) {
          signed = { phone: String(r.phone), authDate: String(r.authDate || ""), hash: String(r.hash || "") };
          inp.value = fmtPhone(r.phone);
          inp.dispatchEvent(new Event("input", { bubbles: true }));
          b.textContent = "Номер из MAX подставлен";
        } else { b.disabled = false; }
      }).catch(function () { b.disabled = false; });
    });
    (inp.closest("label") || inp.parentNode).appendChild(b);
  }

  // ---------- «Отправить в MAX»: товар или свой расчёт — мужу, дизайнеру; у получателя откроется здесь же, в MAX
  function share(text, payload, btn, label) {
    var link = BOT + "?startapp=" + payload;
    var done = function (t) { btn.textContent = t; setTimeout(function () { btn.textContent = label; }, 2500); };
    var copy = function () {
      try { navigator.clipboard.writeText(text + "\n" + link).then(function () { done("Ссылка скопирована"); }, function () { done(label); }); }
      catch (e) { done(label); }
    };
    if (typeof W.shareMaxContent !== "function") return copy();
    W.shareMaxContent({ text: text, link: link }).then(function (r) {
      if (r && r.status === "shared") done("Отправлено");
    }).catch(copy);
  }
  function shareButton(after, label, make, style) {
    if (!after || after.parentNode.querySelector("[data-mx-share]")) return;
    var b = document.createElement("button");
    b.type = "button"; b.className = "btn ghost"; b.setAttribute("data-mx-share", "1");
    b.style.cssText = style || "width:100%;margin-top:8px";
    b.textContent = label;
    b.addEventListener("click", function () { var x = make(); if (x) share(x[0], x[1], b, label); });
    after.insertAdjacentElement("afterend", b);
  }
  function slugPanel(v) { return String(v || "").toLowerCase().replace(/[^a-z0-9-]/g, ""); }
  function setup() {
    phoneButton("lContact", "lName");
    phoneButton("mPhone", "mName");
    var pm = /^\/p\/([a-z0-9-]+)\/$/.exec(location.pathname);
    if (pm) {
      shareButton(document.getElementById("toCalc"), "Отправить в MAX", function () {
        var h1 = document.querySelector("h1");
        return [(h1 ? h1.textContent.trim() : "Наш декор") + " — фото, 3D и цена:", "p-" + pm[1]];
      });
    }
    var res = document.getElementById("rLines");
    var send = res && res.parentNode.querySelector('a.btn[href="#order"]');
    if (send) {
      shareButton(send, "Отправить расчёт в MAX", function () {
        var panel = slugPanel((document.getElementById("cPanel") || {}).value);
        var w = parseInt((document.getElementById("cW") || {}).value, 10), h = parseInt((document.getElementById("cH") || {}).value, 10);
        if (!panel) return null;
        var dims = w > 0 && w < 10000 && h > 0 && h < 10000 ? "_" + w + "_" + h : "";
        var sum = (document.getElementById("rSum") || {}).textContent || "";
        return ["Расчёт стены" + (dims ? " " + w + "×" + h + " см" : "") + ", панель " + panel.toUpperCase() +
                (sum && sum !== "—" ? ": " + sum.trim() : "") + " — посмотреть в 3D:", "calc-" + panel + dims];
      });
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup); else setup();

  // Свайп вниз на телефоне не закрывает приложение (иначе мешает листать и крутить 3D-стену)
  if (mobile() && W.disableVerticalSwipes) { try { W.disableVerticalSwipes().catch(function () {}); } catch (e) {} }
  try { W.ready(); } catch (e) {}
})();
