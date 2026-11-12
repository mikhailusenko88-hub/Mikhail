"""Проверка «головы» Помощника на настоящей нейросети (llama.cpp на сервере GitHub):
тот же формат подсказки, что в iPhone (основа, знания, действия Qwen), настоящий поиск DuckDuckGo/Bing
и разбор страниц, CRM — подставные ответы. Пишет разговоры в status/brain-test-<модель>.md."""
import html as H
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

MODEL = sys.argv[1]            # qwen3 | qwen35
OUT = sys.argv[2]
SERVER = "http://127.0.0.1:8080"
HERE = __file__.rsplit("/", 1)[0]
CORE = open(f"{HERE}/core.txt", encoding="utf-8").read()
CRM = json.load(open(f"{HERE}/crm_tools.json", encoding="utf-8"))

LOCAL = [
    {"name": "web_search", "desc": "Поиск в интернете. Возвращает список ссылок с кратким текстом. Для проверки фактов ищи 2–3 разными запросами.",
     "params": [{"name": "query", "type": "string", "desc": "короткий запрос, 2–6 слов", "required": True}]},
    {"name": "open_page", "desc": "Открыть страницу и прочитать её текст (после web_search, чтобы проверить подробности).",
     "params": [{"name": "url", "type": "string", "desc": "адрес страницы", "required": True},
                {"name": "find", "type": "string", "desc": "слова, которые нужно найти на странице", "required": False}]},
    {"name": "remember", "desc": "Запомнить надолго в свою базу знаний (то, что сказал хозяин, или проверенный факт с источником).",
     "params": [{"name": "title", "type": "string", "desc": "короткая тема", "required": True}, {"name": "text", "type": "string", "desc": "что запомнить", "required": True}]},
    {"name": "recall", "desc": "Найти в своей базе знаний.", "params": [{"name": "query", "type": "string", "desc": "о чём", "required": True}]},
    {"name": "forget", "desc": "Удалить из базы знаний запись по теме.", "params": [{"name": "title", "type": "string", "desc": "тема записи", "required": True}], "danger": True},
    {"name": "skill_improve", "desc": "Улучшить навык: дописать урок «в следующий раз делать так» (после поправки хозяина или удачного нового способа).",
     "params": [{"name": "skill", "type": "string", "desc": "название навыка", "required": True}, {"name": "lesson", "type": "string", "desc": "урок одной строкой", "required": True}]},
    {"name": "skill_rollback", "desc": "Вернуть прошлую версию навыка.", "params": [{"name": "skill", "type": "string", "desc": "название навыка", "required": True}], "danger": True},
    {"name": "reminder", "desc": "Напоминание на телефоне в нужное время.",
     "params": [{"name": "text", "type": "string", "desc": "о чём напомнить", "required": True},
                {"name": "when", "type": "string", "desc": "ГГГГ-ММ-ДД ЧЧ:ММ или «через 30 минут», «через 2 часа»", "required": True}]},
    {"name": "calc", "desc": "Точный расчёт по формуле: + - * / ^ ( ) %. Все расчёты денег и площадей делай только им.",
     "params": [{"name": "expr", "type": "string", "desc": "например (2.8*3.1-1.2)*1.1", "required": True}]},
    {"name": "open_link", "desc": "Открыть на телефоне ссылку: сайт, карта, звонок tel:+7…, письмо mailto:…",
     "params": [{"name": "url", "type": "string", "desc": "ссылка", "required": True}], "danger": True},
]
TOOLS = LOCAL + [{**t, "params": [{"name": p["name"], "type": p["type"], "desc": p["desc"], "required": p["required"]} for p in t["params"]]} for t in CRM]


def tool_json(t):
    props = {p["name"]: {"type": p["type"], "description": p["desc"]} for p in t["params"]}
    fn = {"name": t["name"], "description": t["desc"],
          "parameters": {"type": "object", "properties": props, "required": [p["name"] for p in t["params"] if p["required"]]}}
    return json.dumps({"type": "function", "function": fn}, ensure_ascii=False, sort_keys=True)


PINNED = """## Кто хозяин
Хозяин — Михаил, Санкт-Петербург. Интернет-магазин декора «Наш декор» (nashdekor.ru): реечные панели, молдинги, плинтусы; CRM crm.nashdekor.ru; мебель на заказ.
## Правила
- Домашний адрес нигде не писать. Документы — в Word. Отвечать по-русски."""
KB = [("ПЭК", "Отправляем ПЭКом по России; по СПб — Яндекс Доставка «Грузовой»."),
      ("Цены панелей", "Цены — только из CRM (crm_stock) или с сайта.")]

WEEK = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


def system(question):
    now = datetime.now()
    s = CORE + f"\nСейчас: {WEEK[now.weekday()]}, {now:%d.%m.%Y, %H:%M} (время телефона)."
    s += "\n\n# Основа (правила и сведения хозяина)\n" + PINNED
    q = question.lower()
    found = [f"## {t} [пакет]\n{x}" for t, x in KB if t.lower()[:4] in q]
    if found:
        s += "\n\n# Из базы знаний (по теме)\n" + "\n\n".join(found)
    s += "\n\n# Tools\n\nYou may call one or more functions to assist with the user query.\n\nYou are provided with function signatures within <tools></tools> XML tags:\n<tools>\n"
    s += "\n".join(tool_json(t) for t in TOOLS)
    s += "\n</tools>\n\nFor each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:\n<tool_call>\n{\"name\": <function-name>, \"arguments\": <args-json-object>}\n</tool_call>"
    return s


def render(msgs):
    out = ""
    for m in msgs:
        if m["role"] == "user":
            out += f"<|im_start|>user\n{m['text']}<|im_end|>\n"
        elif m["role"] == "assistant":
            body = m["text"] + (("\n" if m["text"] else "") + f"<tool_call>\n{m['call']}\n</tool_call>" if m.get("call") else "")
            out += f"<|im_start|>assistant\n{body}<|im_end|>\n"
        elif m["role"] == "tool":
            out += f"<|im_start|>user\n<tool_response>\n{m['text']}\n</tool_response><|im_end|>\n"
    return out


def complete(prompt):
    body = json.dumps({"prompt": prompt, "n_predict": 600, "temperature": 0.4, "top_k": 20, "top_p": 0.8, "repeat_penalty": 1.05,
                       "repeat_last_n": 64, "stop": ["</tool_call>", "<|im_end|>"], "cache_prompt": True}).encode()
    r = urllib.request.Request(SERVER + "/completion", data=body, headers={"Content-Type": "application/json"})
    t = time.time()
    d = json.load(urllib.request.urlopen(r, timeout=900))
    out = d.get("content", "")
    if d.get("stop_type") == "word" and d.get("stopping_word") == "</tool_call>":
        out += "</tool_call>"
    return out, time.time() - t, d.get("timings", {})


def strip_think(s):
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S)
    return re.sub(r"<think>.*", "", s, flags=re.S)


def parse(out):
    t = strip_think(out).replace("<|im_end|>", "")
    if "<tool_call>" not in t:
        return t.strip(), None
    before, rest = t.split("<tool_call>", 1)
    rest = rest.split("</tool_call>", 1)[0]
    a, b = rest.find("{"), rest.rfind("}")
    if a < 0 or b < 0:
        return before.strip(), None
    raw = rest[a:b + 1]
    try:
        o = json.loads(raw)
        args = o.get("arguments") or {}
        if isinstance(args, str):
            args = json.loads(args)
        return before.strip(), (o.get("name", ""), args, raw)
    except ValueError:
        return before.strip(), ("", {}, raw)


UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"


def get(url):
    r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    with urllib.request.urlopen(r, timeout=20) as f:
        raw = f.read()
    return raw.decode("utf-8", errors="replace")


def clean(h):
    t = re.sub(r"<[^>]+>", " ", h)
    t = H.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def web_search(q):
    hits = []
    try:
        page = get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q) + "&kl=ru-ru")
        links = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S | re.I)
        snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', page, re.S | re.I)
        for i, (u, t) in enumerate(links):
            u = H.unescape(u)
            if "uddg=" in u:
                u = urllib.parse.unquote(u.split("uddg=", 1)[1].split("&", 1)[0])
            if "duckduckgo.com/y.js" in u:
                continue
            hits.append((clean(t), u, clean(snips[i]) if i < len(snips) else ""))
        src = "ddg"
    except Exception as e:  # noqa: BLE001
        src = f"ddg ошибка {e}"
    if not hits:
        try:
            page = get("https://www.bing.com/search?q=" + urllib.parse.quote(q) + "&setlang=ru&cc=RU")
            for b in re.findall(r'<li class="b_algo"(.*?)</li>', page, re.S | re.I):
                a = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.S | re.I)
                p = re.search(r"<p[^>]*>(.*?)</p>", b, re.S | re.I)
                if a:
                    hits.append((clean(a.group(2)), H.unescape(a.group(1)), clean(p.group(1)) if p else ""))
            src += " → bing"
        except Exception as e:  # noqa: BLE001
            src += f" → bing ошибка {e}"
    if not hits:
        return f"[{src}] Поиск ничего не дал."
    return f"[{src}]\n" + "\n".join(f"{i + 1}. {t} — {urllib.parse.urlparse(u).netloc}\n   {s[:300]}\n   {u}" for i, (t, u, s) in enumerate(hits[:6]))


def open_page(url, find=""):
    try:
        page = get(url)
    except Exception as e:  # noqa: BLE001
        return f"Страница не открылась: {e}"
    title = clean((re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I) or [None, ""])[1])
    for tag in ["script", "style", "noscript", "svg", "nav", "footer", "header", "form"]:
        page = re.sub(rf"(?is)<{tag}[^>]*>.*?</{tag}>", " ", page)
    text = clean(page)
    if find:
        keys = [w[:5].lower() for w in re.findall(r"\w{3,}", find)]
        sents = re.split(r"(?<=[.!?])\s+", text)
        pick = [s for s in sents if any(k in s.lower() for k in keys)]
        body = " … ".join(pick)[:2400] or text[:2400]
    else:
        body = text[:2600]
    return f"Страница: {title}\nАдрес: {url}\n\n{body}"


def calc(expr):
    e = expr.replace(",", ".").replace("×", "*").replace("÷", "/").replace("^", "**")
    if not re.fullmatch(r"[0-9.+\-*/() %]+", e):
        return f"Не поняла формулу: {expr}"
    e = re.sub(r"(\d+(?:\.\d+)?)%", r"(\1/100)", e)
    try:
        v = eval(e, {"__builtins__": {}})  # noqa: S307 — только цифры и знаки
    except Exception:  # noqa: BLE001
        return f"Не поняла формулу: {expr}"
    return f"{expr} = {round(v, 4):g}"


CRM_FAKE = {
    "crm_today": "Сегодня 12.11. Новых заявок: 2, задач на сегодня: 3, просрочено: 1, оплачено и ждёт отгрузки: 1, непрочитанных чатов: 1.\n\nНовые заявки:\n• №41 Ольга — Новая · панели на стену 3 м\n• №42 Игорь — Новая · плинтус 20 м\n\nЗадачи (сегодня и просроченные):\n• [17] Связаться с клиентом — до 12.11 · №41 Ольга\n• [15] Отправить расчёт клиенту — до 11.11 · №39 Анна",
    "crm_find": "• №39 Анна — В работе · 18 400 ₽ · реечные панели в спальню",
    "crm_stock": "• AD-101 Панель реечная 2700 мм: на складе 40, отложено 6, свободно 34, цена 1 290 ₽",
}


def run_tool(name, args):
    if name == "web_search":
        return web_search(str(args.get("query", "")))
    if name == "open_page":
        return open_page(str(args.get("url", "")), str(args.get("find", "")))
    if name == "calc":
        return calc(str(args.get("expr", "")))
    if name == "remember":
        return f"Запомнила: «{args.get('title', '')}»."
    if name == "reminder":
        return f"Напомню {args.get('when', '')}: {args.get('text', '')}"
    if name == "skill_improve":
        return f"Навык «{args.get('skill', '')}» улучшен, теперь версия 3. Записан урок: {args.get('lesson', '')}"
    if name == "recall":
        return "В базе ничего нет по этой теме."
    if name.startswith("crm_"):
        if name == "crm_new_deal":
            return f"Создана заявка №43 ({args.get('name', '')}). Задача «Связаться с клиентом» поставлена."
        return CRM_FAKE.get(name, f"(CRM, тест) выполнено {name}")
    return f"Нет такого действия: {name}"


def need_tool(q, used):
    t = q.lower().replace("ё", "е")
    crm = any(w in t for w in ["заявк", "клиент", "склад", "остат", "задач", "crm", "срм", "оплат", "почт", "письм"])
    search = any(w in t for w in ["найди", "поищи", "узнай", "в интернете", "сколько стоит", "какая цена", "цена на", "цены на", "где купить",
                                  "курс ", "погод", "новост", "проверь компан", "кто такой", "что такое", "расписани", "адрес "])
    if search and not crm and "web_search" not in used:
        return "Подсказка: это нужно искать в интернете. Сначала вызови web_search коротким запросом, потом открой лучшую ссылку через open_page. По памяти цифры не называй."
    nums = len(re.findall(r"\d+(?:[.,]\d+)?", t))
    words = ["посчитай", "сколько будет", "рассчитай", "расчитай", "площад", "умнож", "сумм", "итого", "квадрат", "по ", "×", "*"]
    if nums >= 2 and any(w in t for w in words) and "calc" not in used and not crm:
        return "Подсказка: здесь нужен расчёт. Вызови calc с одной формулой, в уме не считай."
    return None


QUESTIONS = [
    "Привет! Ты кто и что умеешь?",
    "Что у нас сегодня по заявкам?",
    "Посчитай: стена 3,2 на 2,7 метра, минус дверь 0,9 на 2,1. Сколько квадратов и сколько это по 1290 рублей за метр?",
    "Создай заявку: Ольга, +7 999 111-22-33, хочет реечные панели на стену 3 метра, звонила сама.",
    "Запомни: поставщик отгружает по вторникам.",
    "Найди, сколько стоит доставка ПЭК 300 кг из Москвы в Санкт-Петербург.",
    "Напомни завтра в 10 утра позвонить Анне про расчёт.",
    "Узнай, какой сейчас курс доллара к рублю по ЦБ.",
    "Проверь компанию ООО «Яндекс», ИНН 7736207543: действует ли?",
    "Нет, клиенту так не пиши: всегда в конце предлагай прислать размеры стены. Запомни это для ответов клиентам.",
]

log = [f"# Проверка «головы» Помощника — {MODEL} — {datetime.now():%Y-%m-%d %H:%M} UTC\n"]
total_ok = 0
for q in QUESTIONS:
    msgs = [{"role": "user", "text": q}]
    log.append(f"\n## Вопрос: {q}\n")
    final = None
    used, nudged = set(), False
    for step in range(7):
        prompt = f"<|im_start|>system\n{system(q)}<|im_end|>\n" + render(msgs) + "<|im_start|>assistant\n" + ("<think>\n\n</think>\n\n" if MODEL == "qwen35" else "")
        out, secs, tm = complete(prompt)
        text, call = parse(out)
        log.append(f"- шаг {step + 1} ({secs:.0f} с, подсказка {tm.get('prompt_n', '?')} частей, ответ {tm.get('predicted_n', '?')}, "
                   f"{tm.get('predicted_per_second', 0):.1f} част/с)")
        if not call:
            hint = None if nudged else need_tool(q, used)
            if hint:
                nudged = True
                log.append(f"  - (ответила без действия: {text[:200]}) → подсказка")
                msgs.append({"role": "tool", "text": hint})
                continue
            final = text
            log.append(f"  - **ответ:** {text}")
            break
        name, args, raw = call
        used.add(name)
        msgs.append({"role": "assistant", "text": text, "call": raw})
        res = run_tool(name, args) if name else "Ошибка: неверный формат вызова."
        log.append(f"  - действие `{name}` {json.dumps(args, ensure_ascii=False)}" + (f" (сначала сказала: {text})" if text else ""))
        log.append("  - результат: " + res[:500].replace("\n", " ⏎ "))
        msgs.append({"role": "tool", "text": res[:3000]})
    if final:
        total_ok += 1
    else:
        log.append("  - **без ответа за 6 шагов**")

# «прочитай навык и скажи, что поняла» — как в телефоне после обновления
old = "Вежливо, на «Вы», коротко. Цены — из CRM."
new = "Вежливо, на «Вы», коротко. Цены — только из CRM (crm_stock) или с сайта. В конце всегда следующий шаг: попросить размеры стены или предложить оформить заказ. Сроки доставки не обещать, пока не проверила склад."
ask = f"Тебе обновили навык «Как отвечать клиенту», версия 2.\nБыло:\n{old}\n\nСтало:\n{new}\n\nПрочитай внимательно и ответь хозяину 2–4 предложениями: что поняла и что теперь будешь делать иначе, чем раньше."
p = ("<|im_start|>system\nТы — «Помощник», личный помощник хозяина в его iPhone. Отвечай по-русски, коротко, без выдумок.<|im_end|>\n"
     f"<|im_start|>user\n{ask}<|im_end|>\n<|im_start|>assistant\n" + ("<think>\n\n</think>\n\n" if MODEL == "qwen35" else ""))
out, secs, _ = complete(p)
log.append(f"\n## Обновление навыка — что поняла ({secs:.0f} с)\n\n{strip_think(out).strip()}")

log.append(f"\nИтог: ответила на {total_ok} из {len(QUESTIONS)}.")
open(OUT, "w", encoding="utf-8").write("\n".join(log) + "\n")
print("\n".join(log))
