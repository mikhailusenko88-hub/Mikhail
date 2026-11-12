import Foundation
import UIKit
import UserNotifications
import Security
import Vision
import PDFKit
import Speech
import AVFoundation
import Compression
import UniformTypeIdentifiers

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
        ToolSpec(name: "calc", desc: "Точный расчёт: + - * / ^ ( ) %. Несколько формул — через «;». Все расчёты денег и площадей делай только им.",
                 params: [ToolParam(name: "expr", desc: "например 2.8*3.1-1.2; (2.8*3.1-1.2)*1290")]),
        ToolSpec(name: "open_link", desc: "Открыть на телефоне ссылку: сайт, карта, звонок tel:+7…, письмо mailto:…",
                 params: [ToolParam(name: "url", desc: "ссылка")], danger: true),
        ToolSpec(name: "file_read", desc: "Читать присланный хозяином файл дальше: с нужного знака (from) или найти в нём слова (find).",
                 params: [ToolParam(name: "from", type: "integer", desc: "с какого знака читать", required: false),
                          ToolParam(name: "find", desc: "слова, которые нужно найти в файле", required: false)]),
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
            let parts = s("expr").split(separator: ";").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
            return parts.map { e in Calc.eval(e).map { "\(e) = \(Calc.format($0))" } ?? "Не поняла формулу: \(e)" }.joined(separator: "\n")
        case "open_link":
            guard let u = URL(string: s("url")) else { return "Плохая ссылка." }
            let ok = await MainActor.run { () -> Bool in UIApplication.shared.open(u); return true }
            return ok ? "Открыла." : "Не открылась."
        case "file_read":
            let from = Int(s("from")) ?? Int(Double(s("from")) ?? 0)
            return Files.part(from: from, find: s("find"))
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

    /// Куски текста вокруг нужных слов (для страниц и присланных файлов).
    static func around(_ text: String, find: String, limit: Int = 2400) -> String? {
        let keys = KnowledgeBase.stems(find)
        guard !keys.isEmpty else { return nil }
        let lines = text.components(separatedBy: "\n").filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
        var picked: [String] = []
        var last = -10
        for (i, l) in lines.enumerated() {
            let st = Set(KnowledgeBase.stems(l))
            if keys.contains(where: st.contains) {
                let a = max(last + 2, i - 1), b = min(lines.count - 1, i + 1)
                if a <= b { picked.append(lines[a...b].joined(separator: " ")) }
                last = b - 1
            }
            if picked.joined().count > limit { break }
        }
        return picked.isEmpty ? nil : String(picked.joined(separator: "\n…\n").prefix(limit + 400))
    }

    static func open(_ s: String, find: String) async -> String {
        guard let u = URL(string: s.trimmingCharacters(in: .whitespaces)), u.scheme?.hasPrefix("http") == true else { return "Плохой адрес страницы." }
        do {
            let (html, http) = try await get(u, timeout: 25)
            if let c = http?.statusCode, c >= 400 { return "Страница не открылась (код \(c))." }
            let title = clean(matches(#"<title[^>]*>(.*?)</title>"#, html).first?[1] ?? "")
            let date = matches(#"(?:article:published_time|article:modified_time|datePublished|dateModified)["']?\s*(?:content=|:)\s*["']([0-9]{4}-[0-9]{2}-[0-9]{2})"#, html).first?[1]
            let text = pageText(html)
            let body = around(text, find: find) ?? String(text.prefix(2600))
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

// MARK: - фото: сохранить, прочитать текст (распознавание Apple — прямо в iPhone, без интернета)

enum Eyes {
    static var folder: URL {
        let d = KnowledgeBase.folder.appendingPathComponent("img", isDirectory: true)
        try? FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
        return d
    }

    /// Уменьшить до maxSide по длинной стороне и сохранить JPEG. Возвращает имя файла.
    static func save(_ img: UIImage, maxSide: CGFloat = 1600) -> String? {
        let im = scaled(img, maxSide: maxSide)
        guard let d = im.jpegData(compressionQuality: 0.85) else { return nil }
        let name = UUID().uuidString + ".jpg"
        do { try d.write(to: folder.appendingPathComponent(name), options: .atomic) } catch { return nil }
        return name
    }

    static func url(_ name: String) -> URL { folder.appendingPathComponent(name) }

    static func load(_ name: String) -> UIImage? { UIImage(contentsOfFile: url(name).path) }

    static func scaled(_ img: UIImage, maxSide: CGFloat) -> UIImage {
        let s = img.size
        let k = min(1, maxSide / max(s.width, s.height, 1))
        let size = CGSize(width: max(1, (s.width * k).rounded()), height: max(1, (s.height * k).rounded()))
        let f = UIGraphicsImageRendererFormat.default()
        f.scale = 1
        return UIGraphicsImageRenderer(size: size, format: f).image { _ in img.draw(in: CGRect(origin: .zero, size: size)) }
    }

    /// JPEG поменьше — для «глаза» нейросети (быстрее и меньше памяти).
    static func jpegForEye(_ name: String) -> Data? {
        guard let im = load(name) else { return nil }
        return scaled(im, maxSide: 896).jpegData(compressionQuality: 0.9)
    }

    /// Текст на фото (русский и английский), строками сверху вниз.
    static func readText(_ name: String) async -> String {
        guard let cg = load(name)?.cgImage else { return "" }
        return await readText(cg: cg)
    }

    static func readText(cg: CGImage) async -> String {
        await Task.detached(priority: .userInitiated) { () -> String in
            let req = VNRecognizeTextRequest()
            req.recognitionLevel = .accurate
            req.usesLanguageCorrection = true
            req.recognitionLanguages = ["ru-RU", "en-US"]
            let h = VNImageRequestHandler(cgImage: cg, options: [:])
            do { try h.perform([req]) } catch { return "" }
            let obs = req.results ?? []
            let lines = obs.sorted { $0.boundingBox.minY > $1.boundingBox.minY }
                .compactMap { $0.topCandidates(1).first?.string }
            return lines.joined(separator: "\n")
        }.value
    }

    /// Несколько кадров в одну картинку 2×2 (для видео).
    static func collage(_ imgs: [UIImage]) -> UIImage? {
        guard let first = imgs.first else { return nil }
        if imgs.count == 1 { return first }
        let cell = CGSize(width: 800, height: 800 * first.size.height / max(first.size.width, 1))
        let cols = 2, rows = (imgs.count + 1) / 2
        let f = UIGraphicsImageRendererFormat.default()
        f.scale = 1
        return UIGraphicsImageRenderer(size: CGSize(width: cell.width * CGFloat(cols), height: cell.height * CGFloat(rows)), format: f).image { c in
            UIColor.black.setFill(); c.fill(CGRect(x: 0, y: 0, width: cell.width * CGFloat(cols), height: cell.height * CGFloat(rows)))
            for (i, im) in imgs.enumerated() {
                im.draw(in: CGRect(x: CGFloat(i % cols) * cell.width, y: CGFloat(i / cols) * cell.height, width: cell.width, height: cell.height))
            }
        }
    }
}

// MARK: - ZIP: свой маленький распаковщик (Word, Excel, PowerPoint, OpenOffice, EPUB, архивы)

struct ZipBox {
    struct Entry { let name: String; let method: Int; let csize: Int; let usize: Int; let local: Int }
    private let b: [UInt8]
    private(set) var entries: [Entry] = []

    init?(_ data: Data) {
        b = [UInt8](data)
        let n = b.count
        guard n >= 22 else { return nil }
        var eocd = -1
        var i = n - 22
        let stop = max(0, n - 22 - 65_535)
        while i >= stop {
            if b[i] == 0x50 && b[i + 1] == 0x4b && b[i + 2] == 5 && b[i + 3] == 6 { eocd = i; break }
            i -= 1
        }
        guard eocd >= 0 else { return nil }
        let count = u16(eocd + 10)
        var p = u32(eocd + 16)
        let ru866 = String.Encoding(rawValue: CFStringConvertEncodingToNSStringEncoding(CFStringEncoding(CFStringEncodings.dosRussian.rawValue)))
        for _ in 0..<count {
            guard p >= 0, p + 46 <= n, u32(p) == 0x02014b50 else { break }
            let flags = u16(p + 8), method = u16(p + 10), cs = u32(p + 20), us = u32(p + 24)
            let nl = u16(p + 28), el = u16(p + 30), cl = u16(p + 32), off = u32(p + 42)
            guard p + 46 + nl <= n else { break }
            let nb = Array(b[(p + 46)..<(p + 46 + nl)])
            let name = String(bytes: nb, encoding: .utf8) ?? (flags & 0x800 == 0 ? String(bytes: nb, encoding: ru866) : nil) ?? "?"
            entries.append(Entry(name: name, method: method, csize: cs, usize: us, local: off))
            p += 46 + nl + el + cl
        }
        if entries.isEmpty && count > 0 { return nil }
    }

    private func u16(_ o: Int) -> Int { Int(b[o]) | Int(b[o + 1]) << 8 }
    private func u32(_ o: Int) -> Int { u16(o) | u16(o + 2) << 16 }

    var names: [String] { entries.map(\.name) }

    func entry(_ name: String) -> Entry? {
        entries.first { $0.name == name } ?? entries.first { $0.name.lowercased() == name.lowercased() }
    }

    func data(_ e: Entry, limit: Int = 80_000_000) -> Data? {
        guard e.local >= 0, e.local + 30 <= b.count, u32(e.local) == 0x04034b50, e.usize <= limit else { return nil }
        let start = e.local + 30 + u16(e.local + 26) + u16(e.local + 28)
        guard start + e.csize <= b.count else { return nil }
        if e.method == 0 { return Data(b[start..<(start + e.csize)]) }
        guard e.method == 8 else { return nil }
        if e.usize == 0 { return Data() }
        let out = UnsafeMutablePointer<UInt8>.allocate(capacity: e.usize)
        defer { out.deallocate() }
        let got = b.withUnsafeBufferPointer { src in
            compression_decode_buffer(out, e.usize, src.baseAddress! + start, e.csize, nil, COMPRESSION_ZLIB)
        }
        return got > 0 ? Data(bytes: out, count: got) : nil
    }

    func text(_ name: String) -> String? {
        guard let e = entry(name), let d = data(e) else { return nil }
        return String(data: d, encoding: .utf8) ?? String(decoding: d, as: UTF8.self)
    }
}

// MARK: - файлы: Помощник открывает любой присланный файл (всё читается в телефоне, никуда не отправляется)

struct FileRead {
    var kind: String
    var text = ""
    var image: UIImage? = nil      // картинка для «зрения»: фото, первая страница скана, кадры видео
    var imageHint = ""             // что это за картинка
    var note: [String] = []
}

final class Once {
    private var done = false
    private let lock = NSLock()
    func run(_ f: () -> Void) {
        lock.lock(); let was = done; done = true; lock.unlock()
        if !was { f() }
    }
}

enum Files {
    static var folder: URL {
        let d = KnowledgeBase.folder.appendingPathComponent("files", isDirectory: true)
        try? FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
        return d
    }

    /// Копия присланного файла у себя: files/<номер>/<имя>. Возвращает «<номер>/<имя>».
    static func importCopy(_ src: URL) -> String? {
        let ok = src.startAccessingSecurityScopedResource()
        defer { if ok { src.stopAccessingSecurityScopedResource() } }
        let id = String(UUID().uuidString.prefix(8))
        let dir = folder.appendingPathComponent(id, isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        var name = src.lastPathComponent.replacingOccurrences(of: "/", with: "_")
        if name.isEmpty || name == "." { name = "файл" }
        let dest = dir.appendingPathComponent(name)
        var copied = false
        var err: NSError?
        NSFileCoordinator().coordinate(readingItemAt: src, options: [.withoutChanges], error: &err) { u in
            copied = (try? FileManager.default.copyItem(at: u, to: dest)) != nil
        }
        if !copied { copied = (try? FileManager.default.copyItem(at: src, to: dest)) != nil }
        if src.path.contains("/Inbox/") { try? FileManager.default.removeItem(at: src) }   // копия из Telegram/почты больше не нужна
        if !copied { try? FileManager.default.removeItem(at: dir) }
        return copied ? "\(id)/\(name)" : nil
    }

    static func url(_ ref: String) -> URL { folder.appendingPathComponent(ref) }
    static func name(_ ref: String) -> String { (ref as NSString).lastPathComponent }
    static func textURL(_ ref: String) -> URL { url(ref).deletingLastPathComponent().appendingPathComponent(".text.txt") }

    /// Последний присланный файл — его читает действие file_read.
    static var last: String? {
        get { UserDefaults.standard.string(forKey: "assistant.lastFile") }
        set { UserDefaults.standard.set(newValue, forKey: "assistant.lastFile") }
    }

    static func isImage(_ ref: String) -> Bool {
        UTType(filenameExtension: url(ref).pathExtension.lowercased())?.conforms(to: .image) ?? false
    }

    /// ZIP с чертежами Базиса — его открывает раздел «Мебель», а не Помощник.
    static func isBazisZip(_ u: URL) -> Bool {
        let ok = u.startAccessingSecurityScopedResource()
        defer { if ok { u.stopAccessingSecurityScopedResource() } }
        guard let d = try? Data(contentsOf: u, options: .mappedIfSafe), let z = ZipBox(d) else { return false }
        return z.names.contains { ["b3d", "fr3d"].contains(($0 as NSString).pathExtension.lowercased()) }
    }

    static func sizeText(_ n: Int) -> String {
        n >= 1_048_576 ? String(format: "%.1f МБ", Double(n) / 1_048_576) : n >= 1024 ? "\(n / 1024) КБ" : "\(n) байт"
    }

    static func timeText(_ sec: Double) -> String {
        guard sec.isFinite, sec > 0 else { return "?" }
        let s = Int(sec.rounded())
        return s >= 3600 ? String(format: "%d:%02d:%02d", s / 3600, s / 60 % 60, s % 60) : String(format: "%d:%02d", s / 60, s % 60)
    }

    static let textExt: Set<String> = ["txt", "text", "md", "markdown", "csv", "tsv", "json", "xml", "yaml", "yml", "log", "ini", "cfg", "conf",
                                       "sql", "svg", "plist", "gpx", "kml", "ics", "vcf", "eml", "srt", "vtt", "swift", "py", "js", "ts", "css",
                                       "java", "kt", "c", "h", "cpp", "m", "sh", "bat", "php", "rb", "go", "rs", "tex", "navyk", "toml", "env", "rtx"]

    // MARK: чтение

    static func read(_ ref: String) async -> FileRead { await read(url(ref), depth: 0) }

    static func read(_ u: URL, depth: Int) async -> FileRead {
        let fm = FileManager.default
        let ext = u.pathExtension.lowercased()
        let type = UTType(filenameExtension: ext)
        var isDir: ObjCBool = false
        _ = fm.fileExists(atPath: u.path, isDirectory: &isDir)
        let size = isDir.boolValue ? folderSize(u) : ((try? fm.attributesOfItem(atPath: u.path)[.size] as? Int) ?? 0)
        var r = FileRead(kind: type?.localizedDescription ?? (ext.isEmpty ? "файл" : ext.uppercased()))
        r.note.append("размер \(sizeText(size))")
        func isA(_ t: UTType) -> Bool { type?.conforms(to: t) ?? false }

        if ext == "pdf" {
            await readPDF(u, into: &r)
        } else if ["docx", "docm", "dotx", "dotm"].contains(ext) {
            r.kind = "документ Word"
            if let z = zip(u) { r.text = docx(z) } else { r.note.append("файл повреждён") }
        } else if ["xlsx", "xlsm", "xltx"].contains(ext) {
            r.kind = "таблица Excel"
            if let z = zip(u) { r.text = xlsx(z) } else { r.note.append("файл повреждён") }
        } else if ["pptx", "ppsx", "potx"].contains(ext) {
            r.kind = "презентация PowerPoint"
            if let z = zip(u) { r.text = pptx(z) } else { r.note.append("файл повреждён") }
        } else if ["odt", "ods", "odp", "ott"].contains(ext) {
            r.kind = ext == "ods" ? "таблица OpenOffice" : ext == "odp" ? "презентация OpenOffice" : "документ OpenOffice"
            if let z = zip(u), let x = z.text("content.xml") { r.text = odf(x) }
        } else if ext == "epub" {
            r.kind = "электронная книга"
            if let z = zip(u) { r.text = epub(z) }
        } else if ["pages", "numbers", "key"].contains(ext) {
            r.kind = ext == "pages" ? "документ Pages" : ext == "numbers" ? "таблица Numbers" : "презентация Keynote"
            await readIWork(u, isDir: isDir.boolValue, into: &r)
        } else if ["rtf", "rtfd"].contains(ext) {
            r.kind = "документ RTF"
            let dt: NSAttributedString.DocumentType = ext == "rtf" ? .rtf : .rtfd
            r.text = (try? NSAttributedString(url: u, options: [.documentType: dt], documentAttributes: nil))?.string ?? ""
        } else if ["doc", "xls", "ppt", "dot", "xlt", "pps"].contains(ext) {
            r.kind = ext == "xls" ? "старая таблица Excel" : ext.hasPrefix("p") ? "старая презентация PowerPoint" : "старый документ Word"
            if let d = try? Data(contentsOf: u, options: .mappedIfSafe) { r.text = binaryStrings(d) }
            r.note.append("старый формат — текст достала приблизительно, без таблиц и порядка ячеек")
        } else if ["b3d", "fr3d"].contains(ext) {
            r.kind = "чертёж Базис-Мебельщика"
            if let d = try? Data(contentsOf: u, options: .mappedIfSafe) { r.text = binaryStrings(d, limit: 20_000) }
            r.note.append("полностью открывается в разделе «Мебель» → Базис (Поделиться → «Замер 3D»); здесь — только надписи из файла")
        } else if ext == "zip" || isA(.zip) {
            r.kind = "архив ZIP"
            await readArchive(u, depth: depth, into: &r)
        } else if ["rar", "7z", "tar", "gz", "tgz", "bz2", "xz"].contains(ext) {
            r.kind = "архив \(ext.uppercased())"
            r.note.append("такие архивы телефон не распаковывает — пришлите ZIP или сами файлы")
        } else if isA(.image) && ext != "svg" {
            r.kind = "картинка"
            if let im = UIImage(contentsOfFile: u.path) {
                r.image = im
                r.note.append("\(Int(im.size.width * im.scale))×\(Int(im.size.height * im.scale)) пикс.")
            } else { r.note.append("картинка не открылась (формат)") }
        } else if isA(.movie) || isA(.video) {
            r.kind = "видео"
            await readVideo(u, into: &r)
        } else if isA(.audio) || ["ogg", "opus", "oga", "amr"].contains(ext) {
            r.kind = "аудио"
            await readAudio(u, into: &r)
        } else if isA(.html) || ["htm", "html", "xhtml", "mht"].contains(ext) {
            r.kind = "веб-страница"
            if let d = try? Data(contentsOf: u) { r.text = Web.pageText(decodeText(d)) }
        } else if isA(.text) || isA(.sourceCode) || textExt.contains(ext) {
            if let d = try? Data(contentsOf: u) { r.text = decodeText(d) }
        } else if isDir.boolValue {
            r.kind = "папка"
            let list = (try? fm.subpathsOfDirectory(atPath: u.path)) ?? []
            r.text = "Внутри (\(list.count)):\n" + list.prefix(200).joined(separator: "\n")
        } else if let d = try? Data(contentsOf: u, options: .mappedIfSafe) {
            // неизвестный тип: похоже на текст — читаем как текст, иначе достаём надписи
            if !d.prefix(8000).contains(0) {
                r.text = decodeText(d)
            } else {
                if d.starts(with: [0x50, 0x4b, 0x03, 0x04]), let z = ZipBox(d) {
                    r.kind = "архив (ZIP внутри)"
                    r.text = "Файлы внутри (\(z.entries.count)):\n" + z.names.prefix(200).joined(separator: "\n")
                } else {
                    r.text = binaryStrings(d, limit: 30_000)
                    r.note.append("двоичный файл: показаны только надписи, которые в нём нашлись")
                }
            }
        }
        r.text = r.text.replacingOccurrences(of: "\r\n", with: "\n").replacingOccurrences(of: "\u{0}", with: "")
        return r
    }

    private static func folderSize(_ u: URL) -> Int {
        let fm = FileManager.default
        return ((try? fm.subpathsOfDirectory(atPath: u.path)) ?? []).reduce(0) {
            $0 + ((try? fm.attributesOfItem(atPath: u.appendingPathComponent($1).path)[.size] as? Int) ?? 0)
        }
    }

    private static func zip(_ u: URL) -> ZipBox? {
        guard let d = try? Data(contentsOf: u, options: .mappedIfSafe), d.count < 400_000_000 else { return nil }
        return ZipBox(d)
    }

    static func decodeText(_ d: Data) -> String {
        if d.starts(with: [0xEF, 0xBB, 0xBF]) { return String(decoding: d.dropFirst(3), as: UTF8.self) }
        if d.starts(with: [0xFF, 0xFE]) { return String(data: d.dropFirst(2), encoding: .utf16LittleEndian) ?? "" }
        if d.starts(with: [0xFE, 0xFF]) { return String(data: d.dropFirst(2), encoding: .utf16BigEndian) ?? "" }
        if let s = String(data: d, encoding: .utf8) { return s }
        if let s = String(data: d, encoding: .windowsCP1251) { return s }
        return String(decoding: d, as: UTF8.self)
    }

    /// XML офисных файлов → текст: rules — замены (регулярные выражения) до удаления тегов.
    static func xmlText(_ x: String, _ rules: [(String, String)]) -> String {
        var t = x
        for (a, b) in rules { t = t.replacingOccurrences(of: a, with: b, options: .regularExpression) }
        t = t.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        t = Web.decodeEntities(t)
        t = t.replacingOccurrences(of: "[ \\u00a0]{2,}", with: " ", options: .regularExpression)
        t = t.replacingOccurrences(of: " *\\n *", with: "\n", options: .regularExpression)
        t = t.replacingOccurrences(of: "\\n{3,}", with: "\n\n", options: .regularExpression)
        return t.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func attr(_ a: String, _ k: String) -> String? {
        Web.matches("(?:^|\\s)" + NSRegularExpression.escapedPattern(for: k) + "\\s*=\\s*\"([^\"]*)\"", a).first?[1]
    }

    private static func num(_ s: String) -> Int { Int(Web.matches("(\\d+)\\.xml$", s).first?[1] ?? "") ?? 0 }

    static func docx(_ z: ZipBox) -> String {
        let rules = [("<w:tab/>", "\t"), ("<w:br[^>]*/>", "\n"), ("<w:cr/>", "\n"), ("</w:tc>", " | "), ("</w:tr>", "\n"), ("</w:p>", "\n")]
        var parts: [String] = []
        if let x = z.text("word/document.xml") { parts.append(xmlText(x, rules)) }
        for n in z.names where n.hasPrefix("word/footnotes") || n.hasPrefix("word/endnotes") {
            if let x = z.text(n) { let t = xmlText(x, rules); if !t.isEmpty { parts.append("Сноски:\n" + t) } }
        }
        return parts.joined(separator: "\n\n")
    }

    static func xlsx(_ z: ZipBox) -> String {
        var shared: [String] = []
        if let s = z.text("xl/sharedStrings.xml") {
            for m in Web.matches("<si>(.*?)</si>", s) {
                shared.append(Web.decodeEntities(Web.matches("<t(?:\\s[^>]*)?>(.*?)</t>", m[1]).map { $0[1] }.joined()))
            }
        }
        let wb = z.text("xl/workbook.xml") ?? ""
        let rels = z.text("xl/_rels/workbook.xml.rels") ?? ""
        var target: [String: String] = [:]
        for m in Web.matches("<Relationship\\b([^>]*?)/?>", rels) {
            if let id = attr(m[1], "Id"), let t = attr(m[1], "Target") {
                target[id] = t.hasPrefix("/") ? String(t.dropFirst()) : "xl/" + t
            }
        }
        var sheets: [(String, String)] = []
        for m in Web.matches("<sheet\\b([^>]*?)/?>", wb) {
            if let n = attr(m[1], "name"), let id = attr(m[1], "r:id"), let t = target[id] { sheets.append((Web.decodeEntities(n), t)) }
        }
        if sheets.isEmpty {
            sheets = z.names.filter { $0.hasPrefix("xl/worksheets/sheet") && $0.hasSuffix(".xml") }.sorted { num($0) < num($1) }.map { ($0, $0) }
        }
        var out: [String] = []
        for (name, path) in sheets {
            guard let x = z.text(path) else { continue }
            out.append("=== Лист «\(name)» ===")
            var count = 0
            for rm in Web.matches("<row\\b([^>]*?)(?:/>|>(.*?)</row>)", x) {
                var cells: [String] = []
                for cm in Web.matches("<c\\b([^>]*?)(?:/>|>(.*?)</c>)", rm.count > 2 ? rm[2] : "") {
                    let a = cm[1], body = cm.count > 2 ? cm[2] : ""
                    if body.isEmpty { continue }
                    let t = attr(a, "t") ?? ""
                    var v = Web.matches("<v>(.*?)</v>", body).first?[1] ?? ""
                    if t == "s", let i = Int(v), i < shared.count { v = shared[i] }
                    else if t == "inlineStr" { v = Web.decodeEntities(Web.matches("<t(?:\\s[^>]*)?>(.*?)</t>", body).map { $0[1] }.joined()) }
                    else if t == "b" { v = v == "1" ? "ИСТИНА" : "ЛОЖЬ" }
                    else {
                        v = Web.decodeEntities(v)
                        if v.count > 12, v.contains("."), let d = Double(v) { v = String(format: "%.10g", d) }
                    }
                    v = v.replacingOccurrences(of: "\n", with: " ").trimmingCharacters(in: .whitespaces)
                    if v.isEmpty { continue }
                    let col = (attr(a, "r") ?? "").prefix { $0.isLetter }
                    cells.append(col.isEmpty ? v : "\(col): \(v)")
                }
                if cells.isEmpty { continue }
                let rn = attr(rm[1], "r") ?? "\(count + 1)"
                out.append("\(rn) | " + cells.joined(separator: " | "))
                count += 1
                if count >= 5000 { out.append("… (дальше строки не читала)"); break }
            }
        }
        return out.joined(separator: "\n")
    }

    static func pptx(_ z: ZipBox) -> String {
        let slides = z.names.filter { $0.range(of: "^ppt/slides/slide\\d+\\.xml$", options: .regularExpression) != nil }.sorted { num($0) < num($1) }
        return slides.enumerated().map { i, n in
            "— Слайд \(i + 1) —\n" + xmlText(z.text(n) ?? "", [("</a:p>", "\n"), ("<a:br[^>]*/>", "\n"), ("<a:tab/>", "\t")])
        }.joined(separator: "\n\n")
    }

    static func odf(_ x: String) -> String {
        xmlText(x, [("<text:tab/>", "\t"), ("<text:line-break/>", "\n"), ("<text:s(?: [^>]*)?/>", " "),
                    ("</text:p>", "\n"), ("</text:h>", "\n"), ("</table:table-cell>", " | "), ("</table:table-row>", "\n"),
                    ("<table:table [^>]*table:name=\"([^\"]*)\"[^>]*>", "\n=== $1 ===\n"), ("</draw:page>", "\n\n")])
    }

    static func epub(_ z: ZipBox) -> String {
        var order: [String] = []
        if let c = z.text("META-INF/container.xml"), let opfPath = Web.matches("full-path=\"([^\"]+)\"", c).first?[1], let opf = z.text(opfPath) {
            let base = (opfPath as NSString).deletingLastPathComponent
            var href: [String: String] = [:]
            for m in Web.matches("<item\\b([^>]*?)/?>", opf) {
                if let id = attr(m[1], "id"), let h = attr(m[1], "href") { href[id] = base.isEmpty ? h : base + "/" + h }
            }
            for m in Web.matches("<itemref\\b([^>]*?)/?>", opf) {
                if let id = attr(m[1], "idref"), let h = href[id] { order.append(h.removingPercentEncoding ?? h) }
            }
        }
        if order.isEmpty {
            order = z.names.filter { n in [".xhtml", ".html", ".htm"].contains { n.lowercased().hasSuffix($0) } }.sorted()
        }
        return order.compactMap { z.text($0) }.map { Web.pageText($0) }.filter { !$0.isEmpty }.joined(separator: "\n\n")
    }

    /// Надписи из двоичного файла: русский текст в UTF-16 (старые Word/Excel) и в 1251.
    static func binaryStrings(_ d: Data, limit: Int = 150_000) -> String {
        let b = [UInt8](d.prefix(40_000_000))
        var out: [String] = []
        var total = 0
        var seen = Set<String>()
        func add(_ s: String) {
            let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
            let letters = t.filter { $0.isLetter }.count
            guard t.count >= 4, letters * 2 >= t.count, !seen.contains(t), total < limit else { return }
            seen.insert(t); out.append(t); total += t.count
        }
        func ok16(_ c: UInt16) -> Bool {
            (c >= 0x20 && c < 0x7F) || (c >= 0x0400 && c <= 0x04FF) || c == 9 || c == 10 || c == 13 || (c >= 0xA0 && c <= 0xFF)
                || (c >= 0x2010 && c <= 0x2026) || c == 0x2116 || c == 0x20BD
        }
        for start in 0...1 {
            var run: [UInt16] = []
            var i = start
            while i + 1 < b.count {
                let c = UInt16(b[i]) | UInt16(b[i + 1]) << 8
                if ok16(c) { run.append(c) } else { if run.count >= 4 { add(String(decoding: run, as: UTF16.self)) }; run.removeAll(keepingCapacity: true) }
                i += 2
            }
            if run.count >= 4 { add(String(decoding: run, as: UTF16.self)) }
        }
        var run: [UInt8] = []
        for x in b {
            if x == 9 || x == 10 || x == 13 || (x >= 0x20 && x < 0x7F) || x >= 0xC0 || x == 0xA8 || x == 0xB8 || x == 0xB9 { run.append(x) }
            else {
                if run.count >= 6 { add(String(data: Data(run), encoding: .windowsCP1251) ?? "") }
                run.removeAll(keepingCapacity: true)
            }
        }
        if run.count >= 6 { add(String(data: Data(run), encoding: .windowsCP1251) ?? "") }
        return out.joined(separator: "\n")
    }

    private static func readPDF(_ u: URL, into r: inout FileRead) async {
        r.kind = "PDF"
        guard let doc = PDFDocument(url: u) else { r.note.append("PDF не открылся"); return }
        if doc.isLocked { r.note.append("PDF защищён паролем — текст не прочитать"); return }
        let n = doc.pageCount
        r.note.append("страниц \(n)")
        var pages: [String] = []
        var empty: [Int] = []
        for i in 0..<n {
            let t = (doc.page(at: i)?.string ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            if t.count < 20 { empty.append(i) }
            pages.append(t)
        }
        // страницы-сканы читаем по картинке (до 15 страниц)
        var ocr = 0
        for i in empty.prefix(15) {
            guard let p = doc.page(at: i), let cg = p.thumbnail(of: CGSize(width: 2200, height: 2200), for: .mediaBox).cgImage else { continue }
            pages[i] = await Eyes.readText(cg: cg)
            ocr += 1
        }
        if ocr > 0 { r.note.append("страниц-сканов прочитано по картинке: \(ocr)" + (empty.count > 15 ? " из \(empty.count)" : "")) }
        r.text = pages.enumerated().map { "— стр. \($0.offset + 1) —\n\($0.element)" }.joined(separator: "\n\n")
        // почти без текста (чертёж, фото, скан) — первую страницу покажем «зрению»
        if pages.joined().count < 300 || empty.contains(0), let p = doc.page(at: 0) {
            r.image = p.thumbnail(of: CGSize(width: 1600, height: 1600), for: .mediaBox)
            r.imageHint = "Это первая страница PDF."
        }
    }

    private static func readIWork(_ u: URL, isDir: Bool, into r: inout FileRead) async {
        var pdfData: Data?, jpg: Data?
        if isDir {
            for p in ["QuickLook/Preview.pdf", "preview.jpg", "QuickLook/Thumbnail.jpg", "preview-web.jpg"] {
                if let d = try? Data(contentsOf: u.appendingPathComponent(p)) { if p.hasSuffix("pdf") { pdfData = d } else if jpg == nil { jpg = d } }
            }
        } else if let z = zip(u) {
            for p in ["QuickLook/Preview.pdf", "preview.jpg", "QuickLook/Thumbnail.jpg", "preview-web.jpg"] {
                if let e = z.entry(p), let d = z.data(e) { if p.hasSuffix("pdf") { pdfData = d } else if jpg == nil { jpg = d } }
            }
        }
        if let pdfData, let doc = PDFDocument(data: pdfData) {
            r.text = (0..<doc.pageCount).compactMap { doc.page(at: $0)?.string }.joined(separator: "\n\n")
        }
        if r.text.isEmpty, let jpg, let im = UIImage(data: jpg) {
            r.image = im
            r.imageHint = "Это картинка первой страницы файла \(u.pathExtension)."
            if let cg = im.cgImage { r.text = await Eyes.readText(cg: cg) }
        }
        r.note.append("Pages/Numbers/Keynote хранят текст в своём формате — прочитала только то, что есть в превью. Для полного текста экспортируйте в Word, Excel или PDF")
    }

    private static func readArchive(_ u: URL, depth: Int, into r: inout FileRead) async {
        guard let z = zip(u) else { r.note.append("архив не открылся"); return }
        let files = z.entries.filter { !$0.name.hasSuffix("/") && !$0.name.hasPrefix("__MACOSX") && !($0.name as NSString).lastPathComponent.hasPrefix(".") }
        r.note.append("файлов внутри \(files.count)")
        var parts = ["Файлы в архиве:\n" + files.prefix(150).map { "• \($0.name) (\(sizeText($0.usize)))" }.joined(separator: "\n")]
        guard depth == 0 else { r.text = parts[0]; return }
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("arch-" + UUID().uuidString, isDirectory: true)
        try? FileManager.default.createDirectory(at: tmp, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tmp) }
        var opened = 0, chars = 0
        for e in files where opened < 12 && chars < 60_000 && e.usize < 60_000_000 {
            guard let d = z.data(e) else { continue }
            let f = tmp.appendingPathComponent(String(opened) + "-" + (e.name as NSString).lastPathComponent)
            guard (try? d.write(to: f)) != nil else { continue }
            let inner = await read(f, depth: depth + 1)
            opened += 1
            if r.image == nil, let im = inner.image { r.image = im; r.imageHint = "Это картинка из архива: \(e.name)." }
            let t = inner.text.trimmingCharacters(in: .whitespacesAndNewlines)
            if !t.isEmpty {
                let piece = String(t.prefix(20_000))
                parts.append("=== \(e.name) (\(inner.kind)) ===\n" + piece)
                chars += piece.count
            }
        }
        r.text = parts.joined(separator: "\n\n")
    }

    private static func readVideo(_ u: URL, into r: inout FileRead) async {
        let asset = AVURLAsset(url: u)
        let dur = (try? await asset.load(.duration)).map { CMTimeGetSeconds($0) } ?? 0
        r.note.append("длительность \(timeText(dur))")
        let gen = AVAssetImageGenerator(asset: asset)
        gen.appliesPreferredTrackTransform = true
        gen.maximumSize = CGSize(width: 1000, height: 1000)
        var frames: [UIImage] = []
        for k in [0.1, 0.37, 0.63, 0.9] where dur > 0 {
            if let cg = try? await gen.image(at: CMTime(seconds: dur * k, preferredTimescale: 600)).image { frames.append(UIImage(cgImage: cg)) }
        }
        if let c = Eyes.collage(frames) {
            r.image = c
            r.imageHint = frames.count > 1 ? "Это \(frames.count) кадра из видео по порядку: слева направо, сверху вниз." : "Это кадр из видео."
        }
        let hasAudio = !((try? await asset.loadTracks(withMediaType: .audio)) ?? []).isEmpty
        if hasAudio {
            if let m4a = await exportAudio(asset) {
                let t = await transcribe(m4a)
                try? FileManager.default.removeItem(at: m4a)
                if let t, !t.isEmpty { r.text = "Речь в видео (распознал телефон):\n" + t }
                else { r.note.append(t == nil ? speechProblem : "речи в видео не слышно") }
            }
        } else { r.note.append("без звука") }
    }

    private static func readAudio(_ u: URL, into r: inout FileRead) async {
        let asset = AVURLAsset(url: u)
        if let d = try? await asset.load(.duration), CMTimeGetSeconds(d) > 0 { r.note.append("длительность \(timeText(CMTimeGetSeconds(d)))") }
        let playable = (try? await asset.load(.isPlayable)) ?? false
        guard playable else { r.note.append("этот формат звука iPhone не читает (например .ogg из Telegram) — пришлите .m4a, .mp3 или .wav"); return }
        if let t = await transcribe(u), !t.isEmpty { r.text = "Речь (распознал телефон):\n" + t }
        else { r.note.append(speechProblem) }
    }

    static var speechProblem: String {
        "речь не распознана: нет речи, плохой звук или русское распознавание в этом телефоне идёт только через Apple (переключатель в ⚙︎ → Голос)"
    }

    private static func exportAudio(_ asset: AVAsset) async -> URL? {
        guard let ex = AVAssetExportSession(asset: asset, presetName: AVAssetExportPresetAppleM4A) else { return nil }
        let out = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".m4a")
        ex.outputURL = out
        ex.outputFileType = .m4a
        await ex.export()
        return ex.status == .completed ? out : nil
    }

    /// Речь из файла → текст. В телефоне, если он умеет русский без сервера; иначе — только если хозяин разрешил «Распознавание через Apple».
    static func transcribe(_ u: URL) async -> String? {
        let st: SFSpeechRecognizerAuthorizationStatus = await withCheckedContinuation { c in
            SFSpeechRecognizer.requestAuthorization { c.resume(returning: $0) }
        }
        guard st == .authorized, let rec = SFSpeechRecognizer(locale: Locale(identifier: "ru-RU")) else { return nil }
        let server = UserDefaults.standard.bool(forKey: "assistant.asr.server")
        guard rec.supportsOnDeviceRecognition || server else { return nil }
        let req = SFSpeechURLRecognitionRequest(url: u)
        req.requiresOnDeviceRecognition = rec.supportsOnDeviceRecognition
        req.shouldReportPartialResults = false
        req.addsPunctuation = true
        let once = Once()
        var task: SFSpeechRecognitionTask?
        let text: String? = await withCheckedContinuation { c in
            task = rec.recognitionTask(with: req) { res, err in
                if let res, res.isFinal { once.run { c.resume(returning: res.bestTranscription.formattedString) } }
                else if err != nil { once.run { c.resume(returning: nil) } }
            }
        }
        withExtendedLifetime((rec, task)) {}
        return text
    }

    // MARK: для нейросети

    /// Что увидит нейросеть: вид файла + начало текста. Весь текст — в .text.txt для file_read.
    static func summary(_ ref: String, _ r: FileRead, head: Int = 3500) -> String {
        var s = "[Хозяин прислал файл «\(name(ref))» — \(r.kind)" + (r.note.isEmpty ? "" : "; " + r.note.joined(separator: "; ")) + "]"
        let t = r.text.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty {
            if r.image == nil { s += "\nТекста в файле не нашлось." }
        } else if t.count <= head {
            s += "\nСодержимое файла:\n" + t
        } else {
            s += "\nСодержимое файла (начало: \(head) из \(t.count) знаков):\n" + t.prefix(head)
            s += "\n…\nФайл длинный. Читай дальше действием file_read: from — с какого знака (следующий кусок с \(head)), или find — найти нужные слова."
        }
        return s
    }

    static func part(from: Int, find: String) -> String {
        guard let ref = last, let t = try? String(contentsOf: textURL(ref), encoding: .utf8), !t.isEmpty else {
            return "Нет присланного файла с текстом."
        }
        if !find.trimmingCharacters(in: .whitespaces).isEmpty {
            return "Файл «\(name(ref))», найдено по «\(find)»:\n" + (Web.around(t, find: find, limit: 3000) ?? "ничего не нашлось — попробуй другие слова или читай по порядку (from).")
        }
        let a = max(0, min(from, t.count))
        let chunk = t.dropFirst(a).prefix(3000)
        let end = a + chunk.count
        return "Файл «\(name(ref))», знаки \(a)–\(end) из \(t.count):\n" + chunk + (end < t.count ? "\n…дальше: file_read from \(end)" : "\n(конец файла)")
    }
}
