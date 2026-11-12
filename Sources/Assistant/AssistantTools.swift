import Foundation
import UIKit
import UserNotifications
import Security

/// Действие, которое нейросеть может вызвать: описание для неё + исполнение в телефоне.
struct ToolParam: Codable, Equatable {
    var name: String
    var type: String = "string"
    var desc: String
    var required: Bool = true
}

struct ToolSpec: Codable, Equatable {
    var name: String
    var desc: String
    var params: [ToolParam]
    var danger: Bool = false          // спросить «да/нет» перед выполнением
    var remote: Bool = false          // выполняет ваша CRM

    /// Описание в формате, которому обучена Qwen.
    var json: String {
        var props: [String: Any] = [:]
        for p in params { props[p.name] = ["type": p.type, "description": p.desc] }
        let fn: [String: Any] = ["name": name, "description": desc,
                                 "parameters": ["type": "object", "properties": props,
                                                "required": params.filter(\.required).map(\.name)]]
        let obj: [String: Any] = ["type": "function", "function": fn]
        let d = (try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys, .withoutEscapingSlashes])) ?? Data()
        return String(decoding: d, as: UTF8.self)
    }
}

// MARK: - ключ CRM в связке ключей iPhone

enum Keychain {
    static func get(_ k: String) -> String? {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrAccount as String: k,
                                kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }
    static func set(_ k: String, _ v: String?) {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrAccount as String: k]
        SecItemDelete(q as CFDictionary)
        guard let v, !v.isEmpty else { return }
        var a = q
        a[kSecValueData as String] = Data(v.utf8)
        a[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(a as CFDictionary, nil)
    }
}

// MARK: - CRM: список команд и их выполнение приходят с вашего сервера

enum CRMClient {
    static var base: String {
        get { UserDefaults.standard.string(forKey: "crm.base") ?? "https://crm.nashdekor.ru" }
        set { UserDefaults.standard.set(newValue, forKey: "crm.base") }
    }
    static var key: String? {
        get { Keychain.get("crm.ai.key") }
        set { Keychain.set("crm.ai.key", newValue) }
    }
    static var connected: Bool { (key ?? "").count > 10 }

    static func request(_ path: String, body: [String: Any]? = nil, timeout: TimeInterval = 30) async throws -> [String: Any] {
        guard let key, let url = URL(string: base.trimmingCharacters(in: CharacterSet(charactersIn: "/ ")) + path) else {
            throw NSError(domain: "crm", code: 1, userInfo: [NSLocalizedDescriptionKey: "CRM не подключена: впишите ключ в настройках помощника."])
        }
        var r = URLRequest(url: url, timeoutInterval: timeout)
        r.setValue("Bearer " + key, forHTTPHeaderField: "Authorization")
        r.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            r.httpMethod = "POST"
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
            r.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (d, resp) = try await URLSession.shared.data(for: r)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        let obj = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any] ?? [:]
        if code == 401 || code == 403 {
            throw NSError(domain: "crm", code: code, userInfo: [NSLocalizedDescriptionKey: "CRM не принимает ключ — создайте новый: CRM → Ещё → Помощник."])
        }
        if code >= 400 {
            let msg = obj["error"] as? String ?? "CRM ответила \(code)"
            throw NSError(domain: "crm", code: code, userInfo: [NSLocalizedDescriptionKey: msg])
        }
        return obj
    }

    /// Команды CRM (обновляются после «Обновить CRM» без переустановки приложения).
    static func fetchTools() async -> [ToolSpec]? {
        guard let o = try? await request("/api/ai/tools"), let list = o["tools"] as? [[String: Any]] else { return nil }
        let tools: [ToolSpec] = list.compactMap { t in
            guard let n = t["name"] as? String, let d = t["desc"] as? String else { return nil }
            let ps = (t["params"] as? [[String: Any]] ?? []).compactMap { p -> ToolParam? in
                guard let pn = p["name"] as? String else { return nil }
                return ToolParam(name: pn, type: p["type"] as? String ?? "string", desc: p["desc"] as? String ?? "", required: p["required"] as? Bool ?? false)
            }
            return ToolSpec(name: n, desc: d, params: ps, danger: t["danger"] as? Bool ?? false, remote: true)
        }
        if let d = try? JSONEncoder().encode(tools) { UserDefaults.standard.set(d, forKey: "crm.tools") }
        return tools
    }

    static var cachedTools: [ToolSpec] {
        guard let d = UserDefaults.standard.data(forKey: "crm.tools") else { return [] }
        return (try? JSONDecoder().decode([ToolSpec].self, from: d)) ?? []
    }

    /// Знания о магазине из базы CRM (в GitHub их нет).
    static func fetchKnowledge() async -> [[String: Any]]? {
        guard let o = try? await request("/api/ai/knowledge") else { return nil }
        return o["items"] as? [[String: Any]]
    }

    /// Копия своей базы знаний на ваш сервер (на случай потери телефона).
    static func backupKnowledge(_ items: [[String: Any]]) async -> String {
        do {
            let o = try await request("/api/ai/knowledge", body: ["items": items], timeout: 60)
            return "Копия на сервере: записей \(o["saved"] as? Int ?? 0)."
        } catch {
            return "Не сохранилось: \(error.localizedDescription)"
        }
    }

    static func restoreKnowledge() async -> [[String: Any]]? {
        guard let o = try? await request("/api/ai/knowledge?backup=1") else { return nil }
        return o["backup"] as? [[String: Any]]
    }

    static func call(_ name: String, _ args: [String: Any], confirmed: Bool) async -> String {
        do {
            let o = try await request("/api/ai/call", body: ["name": name, "args": args, "confirmed": confirmed], timeout: 60)
            return (o["text"] as? String) ?? (o["error"] as? String) ?? "Готово."
        } catch {
            return "Ошибка CRM: \(error.localizedDescription)"
        }
    }
}

// MARK: - инструменты в самом телефоне

enum LocalTools {
    static let specs: [ToolSpec] = [
        ToolSpec(name: "web_search", desc: "Поиск в интернете. Возвращает список ссылок с кратким текстом. Для проверки фактов ищи 2–3 разными запросами.",
                 params: [ToolParam(name: "query", desc: "короткий запрос, 2–6 слов")]),
        ToolSpec(name: "open_page", desc: "Открыть страницу и прочитать её текст (после web_search, чтобы проверить подробности).",
                 params: [ToolParam(name: "url", desc: "адрес страницы"),
                          ToolParam(name: "find", desc: "слова, которые нужно найти на странице", required: false)]),
        ToolSpec(name: "remember", desc: "Запомнить надолго в свою базу знаний (то, что сказал хозяин, или проверенный факт с источником).",
                 params: [ToolParam(name: "title", desc: "короткая тема"), ToolParam(name: "text", desc: "что запомнить")]),
        ToolSpec(name: "recall", desc: "Найти в своей базе знаний.", params: [ToolParam(name: "query", desc: "о чём")]),
        ToolSpec(name: "forget", desc: "Удалить из базы знаний запись по теме.", params: [ToolParam(name: "title", desc: "тема записи")], danger: true),
        ToolSpec(name: "skill_improve", desc: "Улучшить навык: дописать урок «в следующий раз делать так» (после поправки хозяина или удачного нового способа).",
                 params: [ToolParam(name: "skill", desc: "название навыка"), ToolParam(name: "lesson", desc: "урок одной строкой")]),
        ToolSpec(name: "skill_rollback", desc: "Вернуть прошлую версию навыка.", params: [ToolParam(name: "skill", desc: "название навыка")], danger: true),
        ToolSpec(name: "reminder", desc: "Напоминание на телефоне в нужное время.",
                 params: [ToolParam(name: "text", desc: "о чём напомнить"),
                          ToolParam(name: "when", desc: "ГГГГ-ММ-ДД ЧЧ:ММ или «через 30 минут», «через 2 часа»")]),
        ToolSpec(name: "calc", desc: "Точный расчёт по формуле: + - * / ^ ( ) %. Все расчёты денег и площадей делай только им.",
                 params: [ToolParam(name: "expr", desc: "например (2.8*3.1-1.2)*1.1")]),
        ToolSpec(name: "open_link", desc: "Открыть на телефоне ссылку: сайт, карта, звонок tel:+7…, письмо mailto:…",
                 params: [ToolParam(name: "url", desc: "ссылка")], danger: true),
    ]

    static func run(_ name: String, _ a: [String: Any]) async -> String {
        func s(_ k: String) -> String { (a[k] as? String) ?? (a[k].map { "\($0)" } ?? "") }
        switch name {
        case "web_search": return await Web.search(s("query"))
        case "open_page": return await Web.open(s("url"), find: s("find"))
        case "remember":
            let it = await MainActor.run { KnowledgeBase.shared.add(title: s("title"), text: s("text"), source: "вы") }
            return "Запомнила: «\(it.title)»."
        case "recall":
            let found = await MainActor.run { KnowledgeBase.shared.search(s("query"), limit: 4, excludePinned: false) }
            return found.isEmpty ? "В базе ничего нет по этой теме." : found.map { "• \($0.title): \($0.text.prefix(600))" }.joined(separator: "\n")
        case "forget":
            let t = s("title").lowercased()
            let n: Int = await MainActor.run {
                let kb = KnowledgeBase.shared
                let hit = kb.items.filter { $0.title.lowercased().contains(t) && !$0.pinned }
                hit.forEach { kb.remove($0.id) }
                return hit.count
            }
            return n > 0 ? "Удалено записей: \(n)." : "Не нашла такой записи (основу так не удалить — только вручную)."
        case "skill_improve":
            let u = await MainActor.run { KnowledgeBase.shared.addLesson(skill: s("skill"), lesson: s("lesson")) }
            guard let u else { return "Урок пустой — не записала." }
            return "Навык «\(u.title)» улучшен, теперь версия \(u.version). Записан урок: \(s("lesson"))"
        case "skill_rollback":
            let u = await MainActor.run { KnowledgeBase.shared.rollback(skill: s("skill")) }
            guard let u else { return "У навыка «\(s("skill"))» нет прошлых версий." }
            return "Навык «\(u.title)» возвращён к версии \(u.version)."
        case "reminder": return await Reminders.add(text: s("text"), when: s("when"))
        case "calc":
            if let v = Calc.eval(s("expr")) { return "\(s("expr")) = \(Calc.format(v))" }
            return "Не поняла формулу: \(s("expr"))"
        case "open_link":
            guard let u = URL(string: s("url")) else { return "Плохая ссылка." }
            let ok = await MainActor.run { () -> Bool in UIApplication.shared.open(u); return true }
            return ok ? "Открыла." : "Не открылась."
        default: return "Нет такого действия: \(name)"
        }
    }
}

// MARK: - интернет

enum Web {
    static let ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"

    static func get(_ url: URL, timeout: TimeInterval = 20) async throws -> (String, HTTPURLResponse?) {
        var r = URLRequest(url: url, timeoutInterval: timeout)
        r.setValue(ua, forHTTPHeaderField: "User-Agent")
        r.setValue("ru-RU,ru;q=0.9,en;q=0.6", forHTTPHeaderField: "Accept-Language")
        let (d, resp) = try await URLSession.shared.data(for: r)
        let http = resp as? HTTPURLResponse
        var enc = String.Encoding.utf8
        let ct = (http?.value(forHTTPHeaderField: "Content-Type") ?? "").lowercased()
        let head = String(decoding: d.prefix(3000), as: UTF8.self).lowercased()
        if ct.contains("1251") || head.contains("charset=windows-1251") || head.contains("charset=\"windows-1251") { enc = .windowsCP1251 }
        let text = String(data: d, encoding: enc) ?? String(decoding: d, as: UTF8.self)
        return (text, http)
    }

    struct Hit { var title: String; var url: String; var snippet: String }

    static func search(_ q: String) async -> String {
        let query = q.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty, let enc = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) else { return "Пустой запрос." }
        var hits: [Hit] = []
        if let u = URL(string: "https://html.duckduckgo.com/html/?q=\(enc)&kl=ru-ru"), let r = try? await get(u) {
            hits = parseDDG(r.0)
        }
        if hits.isEmpty, let u = URL(string: "https://www.bing.com/search?q=\(enc)&setlang=ru&cc=RU"), let r = try? await get(u) {
            hits = parseBing(r.0)
        }
        if hits.isEmpty { return "Поиск ничего не дал (или нет интернета). Попробуй другие слова." }
        return hits.prefix(6).enumerated().map { i, h in
            let host = URL(string: h.url)?.host ?? ""
            return "\(i + 1). \(h.title) — \(host)\n   \(h.snippet)\n   \(h.url)"
        }.joined(separator: "\n")
    }

    static func matches(_ re: String, _ s: String) -> [[String]] {
        guard let r = try? NSRegularExpression(pattern: re, options: [.dotMatchesLineSeparators, .caseInsensitive]) else { return [] }
        let ns = s as NSString
        return r.matches(in: s, range: NSRange(location: 0, length: ns.length)).map { m in
            (0..<m.numberOfRanges).map { m.range(at: $0).location == NSNotFound ? "" : ns.substring(with: m.range(at: $0)) }
        }
    }

    static func parseDDG(_ html: String) -> [Hit] {
        let links = matches(#"<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>"#, html)
        let snips = matches(#"class="result__snippet"[^>]*>(.*?)</a>"#, html)
        return links.enumerated().compactMap { i, m in
            var url = decodeEntities(m[1])
            if let r = url.range(of: "uddg=") {
                let rest = url[r.upperBound...]
                let raw = rest.split(separator: "&").first.map(String.init) ?? ""
                url = raw.removingPercentEncoding ?? raw
            }
            if url.hasPrefix("//") { url = "https:" + url }
            if url.contains("duckduckgo.com/y.js") { return nil }   // реклама
            let sn = i < snips.count ? clean(snips[i][1]) : ""
            return Hit(title: clean(m[2]), url: url, snippet: String(sn.prefix(300)))
        }
    }

    static func parseBing(_ html: String) -> [Hit] {
        let blocks = matches(#"<li class="b_algo"(.*?)</li>"#, html)
        return blocks.compactMap { b in
            guard let a = matches(#"<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>"#, b[1]).first else { return nil }
            let p = matches(#"<p[^>]*>(.*?)</p>"#, b[1]).first?[1] ?? ""
            return Hit(title: clean(a[2]), url: decodeEntities(a[1]), snippet: String(clean(p).prefix(300)))
        }
    }

    static func decodeEntities(_ s: String) -> String {
        var t = s
        for (k, v) in [("&amp;", "&"), ("&quot;", "\""), ("&#39;", "'"), ("&#x27;", "'"), ("&apos;", "'"), ("&lt;", "<"), ("&gt;", ">"),
                       ("&nbsp;", " "), ("&laquo;", "«"), ("&raquo;", "»"), ("&mdash;", "—"), ("&ndash;", "–"), ("&hellip;", "…"), ("&#8381;", "₽")] {
            t = t.replacingOccurrences(of: k, with: v)
        }
        for m in matches(#"&#(\d{2,6});"#, t) {
            if let n = UInt32(m[1]), let u = Unicode.Scalar(n) { t = t.replacingOccurrences(of: m[0], with: String(Character(u))) }
        }
        return t
    }

    static func clean(_ html: String) -> String {
        var t = html.replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
        t = decodeEntities(t)
        t = t.replacingOccurrences(of: "[ \\t\\u00a0]+", with: " ", options: .regularExpression)
        t = t.replacingOccurrences(of: "\\s*\\n\\s*", with: "\n", options: .regularExpression)
        t = t.replacingOccurrences(of: "\\n{3,}", with: "\n\n", options: .regularExpression)
        return t.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    static func pageText(_ html: String) -> String {
        var t = html
        for tag in ["script", "style", "noscript", "svg", "nav", "footer", "header", "form"] {
            t = t.replacingOccurrences(of: "(?is)<\(tag)[^>]*>.*?</\(tag)>", with: " ", options: [.regularExpression])
        }
        t = t.replacingOccurrences(of: "<(br|/p|/div|/li|/h[1-6]|/tr)[^>]*>", with: "\n", options: [.regularExpression, .caseInsensitive])
        return clean(t)
    }

    static func open(_ s: String, find: String) async -> String {
        guard let u = URL(string: s.trimmingCharacters(in: .whitespaces)), u.scheme?.hasPrefix("http") == true else { return "Плохой адрес страницы." }
        do {
            let (html, http) = try await get(u, timeout: 25)
            if let c = http?.statusCode, c >= 400 { return "Страница не открылась (код \(c))." }
            let title = clean(matches(#"<title[^>]*>(.*?)</title>"#, html).first?[1] ?? "")
            let date = matches(#"(?:article:published_time|article:modified_time|datePublished|dateModified)["']?\s*(?:content=|:)\s*["']([0-9]{4}-[0-9]{2}-[0-9]{2})"#, html).first?[1]
            let text = pageText(html)
            var body: String
            let keys = KnowledgeBase.stems(find)
            if !keys.isEmpty {
                // куски вокруг нужных слов
                let lines = text.components(separatedBy: "\n").filter { !$0.isEmpty }
                var picked: [String] = []
                for (i, l) in lines.enumerated() {
                    let st = Set(KnowledgeBase.stems(l))
                    if keys.contains(where: st.contains) {
                        picked.append(lines[max(0, i - 1)...min(lines.count - 1, i + 1)].joined(separator: " "))
                    }
                    if picked.joined().count > 2400 { break }
                }
                body = picked.isEmpty ? String(text.prefix(2400)) : picked.joined(separator: "\n…\n")
            } else {
                body = String(text.prefix(2600))
            }
            return "Страница: \(title)\nАдрес: \(u.absoluteString)\(date.map { "\nДата на странице: \($0)" } ?? "")\n\n\(body)"
        } catch {
            return "Страница не открылась: \(error.localizedDescription)"
        }
    }
}

// MARK: - напоминания

enum Reminders {
    static func parse(_ w: String) -> Date? {
        let s = w.lowercased().trimmingCharacters(in: .whitespaces)
        let f = DateFormatter(); f.locale = Locale(identifier: "ru_RU"); f.timeZone = .current
        for fmt in ["yyyy-MM-dd HH:mm", "yyyy-MM-dd'T'HH:mm", "dd.MM.yyyy HH:mm", "yyyy-MM-dd"] {
            f.dateFormat = fmt
            if let d = f.date(from: s) { return d }
        }
        if let m = Web.matches(#"через\s+(\d+)\s*(мин|час|д)"#, s).first, let n = Double(m[1]) {
            let k: Double = m[2].hasPrefix("мин") ? 60 : m[2].hasPrefix("час") ? 3600 : 86400
            return Date().addingTimeInterval(n * k)
        }
        if s.contains("через час") { return Date().addingTimeInterval(3600) }
        return nil
    }

    static func add(text: String, when: String) async -> String {
        guard let d = parse(when), d > Date() else { return "Не поняла время «\(when)». Нужно ГГГГ-ММ-ДД ЧЧ:ММ или «через 30 минут»." }
        let c = UNUserNotificationCenter.current()
        let ok = (try? await c.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
        guard ok else { return "Телефон не разрешил уведомления: Настройки → Замер 3D → Уведомления." }
        let content = UNMutableNotificationContent()
        content.title = "Напоминание"
        content.body = text
        content.sound = .default
        let comps = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: d)
        let req = UNNotificationRequest(identifier: UUID().uuidString, content: content,
                                        trigger: UNCalendarNotificationTrigger(dateMatching: comps, repeats: false))
        do { try await c.add(req) } catch { return "Не получилось: \(error.localizedDescription)" }
        let f = DateFormatter(); f.locale = Locale(identifier: "ru_RU"); f.dateFormat = "d MMMM в HH:mm"
        return "Напомню \(f.string(from: d)): \(text)"
    }
}

// MARK: - калькулятор (свой, без NSExpression — тот падает на кривой формуле)

enum Calc {
    static func eval(_ s: String) -> Double? {
        let src = s.replacingOccurrences(of: ",", with: ".").replacingOccurrences(of: "×", with: "*")
            .replacingOccurrences(of: "÷", with: "/").replacingOccurrences(of: " ", with: "")
        var p = Parser(chars: Array(src))
        guard let v = p.expr(), p.i == p.chars.count, v.isFinite else { return nil }
        return v
    }
    static func format(_ v: Double) -> String {
        if abs(v - v.rounded()) < 1e-9 { return String(format: "%.0f", v) }
        var t = String(format: "%.4f", v)
        while t.hasSuffix("0") { t.removeLast() }
        if t.hasSuffix(".") { t.removeLast() }
        return t
    }
    struct Parser {
        var chars: [Character]
        var i = 0
        mutating func peek() -> Character? { i < chars.count ? chars[i] : nil }
        mutating func expr() -> Double? {
            guard var v = term() else { return nil }
            while let c = peek(), c == "+" || c == "-" {
                i += 1
                guard let r = term() else { return nil }
                v = c == "+" ? v + r : v - r
            }
            return v
        }
        mutating func term() -> Double? {
            guard var v = power() else { return nil }
            while let c = peek(), c == "*" || c == "/" {
                i += 1
                guard let r = power() else { return nil }
                if c == "/" { if r == 0 { return nil }; v /= r } else { v *= r }
            }
            return v
        }
        mutating func power() -> Double? {
            guard let b = unary() else { return nil }
            if peek() == "^" { i += 1; guard let e = power() else { return nil }; return pow(b, e) }
            return b
        }
        mutating func unary() -> Double? {
            if peek() == "-" { i += 1; return unary().map { -$0 } }
            if peek() == "+" { i += 1; return unary() }
            guard var v = atom() else { return nil }
            if peek() == "%" { i += 1; v /= 100 }
            return v
        }
        mutating func atom() -> Double? {
            if peek() == "(" {
                i += 1
                let v = expr()
                guard peek() == ")" else { return nil }
                i += 1
                return v
            }
            let start = i
            while let c = peek(), c.isNumber || c == "." { i += 1 }
            return i > start ? Double(String(chars[start..<i])) : nil
        }
    }
}
