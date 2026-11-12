import Foundation

/// Своя база знаний помощника: «запомни», найденное в интернете, пакет знаний о работе.
/// Лежит в телефоне: «Файлы» → «На iPhone» → «Замер 3D» → Assistant → knowledge.json.
struct SkillVersion: Codable, Equatable {
    var version: Int
    var text: String
    var date: Date
}

struct KnowledgeItem: Codable, Identifiable, Equatable {
    var id: String = UUID().uuidString
    var title: String
    var text: String
    var source: String = "вы"          // вы / интернет / пакет / CRM / сама
    var date: Date = Date()
    var pinned: Bool = false           // «основа» — всегда в голове
    var kind: String = "знание"        // знание / навык (как делать — с версиями)
    var version: Int = 1
    var history: [SkillVersion] = []   // прошлые версии навыка (до 10)

    var isSkill: Bool { kind == "навык" }

    init(title: String, text: String, source: String = "вы", pinned: Bool = false, kind: String = "знание") {
        self.title = title; self.text = text; self.source = source; self.pinned = pinned; self.kind = kind
    }

    // старые записи без новых полей тоже читаются
    init(from d: Decoder) throws {
        let c = try d.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? UUID().uuidString
        title = try c.decode(String.self, forKey: .title)
        text = try c.decode(String.self, forKey: .text)
        source = try c.decodeIfPresent(String.self, forKey: .source) ?? "вы"
        date = try c.decodeIfPresent(Date.self, forKey: .date) ?? Date()
        pinned = try c.decodeIfPresent(Bool.self, forKey: .pinned) ?? false
        kind = try c.decodeIfPresent(String.self, forKey: .kind) ?? "знание"
        version = try c.decodeIfPresent(Int.self, forKey: .version) ?? 1
        history = try c.decodeIfPresent([SkillVersion].self, forKey: .history) ?? []
    }
}

/// Что изменилось в навыке — помощник прочитает и скажет, что понял.
struct SkillUpdate {
    var title: String
    var version: Int
    var old: String?
    var new: String
}

@MainActor
final class KnowledgeBase: ObservableObject {
    static let shared = KnowledgeBase()
    @Published private(set) var items: [KnowledgeItem] = []

    nonisolated static var folder: URL {
        let d = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Assistant", isDirectory: true)
        try? FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
        return d
    }
    private var file: URL { Self.folder.appendingPathComponent("knowledge.json") }

    init() { load() }

    func load() {
        guard let d = try? Data(contentsOf: file) else { items = []; return }
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        items = (try? dec.decode([KnowledgeItem].self, from: d)) ?? []
    }

    func save() {
        let enc = JSONEncoder(); enc.dateEncodingStrategy = .iso8601; enc.outputFormatting = [.prettyPrinted, .withoutEscapingSlashes]
        if let d = try? enc.encode(items) { try? d.write(to: file, options: .atomic) }
    }

    // MARK: навыки — как делать задачи; у каждого версия и история

    var skills: [KnowledgeItem] { items.filter(\.isSkill) }

    func skill(named n: String) -> KnowledgeItem? {
        let q = n.lowercased().trimmingCharacters(in: .whitespaces)
        if let it = skills.first(where: { $0.title.lowercased() == q }) { return it }
        if let it = skills.first(where: { $0.title.lowercased().contains(q) || q.contains($0.title.lowercased()) }) { return it }
        return search(n, limit: 1, excludePinned: false).first(where: \.isSkill)
    }

    /// Новый или обновлённый навык. Возвращает обновление, если текст изменился.
    @discardableResult
    func saveSkill(title: String, text: String, source: String) -> SkillUpdate? {
        let t = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let body = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty, !body.isEmpty else { return nil }
        if let i = items.firstIndex(where: { $0.isSkill && $0.title.lowercased() == t.lowercased() }) {
            if items[i].text == body { return nil }
            let old = items[i].text
            items[i].history.append(SkillVersion(version: items[i].version, text: old, date: items[i].date))
            if items[i].history.count > 10 { items[i].history.removeFirst(items[i].history.count - 10) }
            items[i].version += 1
            items[i].text = body
            items[i].date = Date()
            items[i].source = source
            save()
            return SkillUpdate(title: items[i].title, version: items[i].version, old: old, new: body)
        }
        items.append(KnowledgeItem(title: t, text: body, source: source, kind: "навык"))
        save()
        return SkillUpdate(title: t, version: 1, old: nil, new: body)
    }

    /// Урок «в следующий раз делать так» — в конец навыка (новая версия).
    func addLesson(skill name: String, lesson: String) -> SkillUpdate? {
        let l = lesson.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !l.isEmpty else { return nil }
        let f = DateFormatter(); f.locale = Locale(identifier: "ru_RU"); f.dateFormat = "dd.MM"
        let line = "- \(f.string(from: Date())): \(l)"
        if let it = skill(named: name) {
            let text = it.text.contains("\nУроки:") ? it.text + "\n" + line : it.text + "\n\nУроки:\n" + line
            return saveSkill(title: it.title, text: text, source: it.source == "CRM" ? "CRM + сама" : it.source)
        }
        return saveSkill(title: name, text: "Уроки:\n" + line, source: "сама")
    }

    /// Вернуть прошлую версию навыка.
    func rollback(skill name: String) -> SkillUpdate? {
        guard let it = skill(named: name), let i = items.firstIndex(where: { $0.id == it.id }),
              let prev = items[i].history.popLast() else { return nil }
        let cur = items[i].text
        items[i].text = prev.text
        items[i].version = prev.version
        items[i].date = Date()
        save()
        return SkillUpdate(title: items[i].title, version: prev.version, old: cur, new: prev.text)
    }

    /// Блоки «#НАВЫК Название» из сообщения хозяина: всё до следующего «#НАВЫК» — текст навыка.
    nonisolated static func skillBlocks(_ text: String) -> [(String, String)] {
        var out: [(String, String)] = []
        var title: String?
        var body: [String] = []
        for line in text.components(separatedBy: "\n") {
            let l = line.trimmingCharacters(in: .whitespaces)
            let up = l.uppercased()
            if up.hasPrefix("#НАВЫК") || up.hasPrefix("# НАВЫК") {
                if let t = title { out.append((t, body.joined(separator: "\n"))) }
                var rest = l.drop(while: { $0 == "#" || $0 == " " })
                rest = rest.dropFirst(5)                       // «НАВЫК»
                title = rest.trimmingCharacters(in: CharacterSet(charactersIn: " :—-«»\""))
                body = []
            } else if title != nil {
                body.append(line)
            }
        }
        if let t = title { out.append((t, body.joined(separator: "\n"))) }
        return out.filter { !$0.0.isEmpty && !$0.1.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    }

    @discardableResult
    func add(title: String, text: String, source: String, pinned: Bool = false) -> KnowledgeItem {
        let t = title.trimmingCharacters(in: .whitespacesAndNewlines)
        // та же тема от того же источника — обновляем, а не плодим копии
        if let i = items.firstIndex(where: { $0.isSkill && $0.title.lowercased() == t.lowercased() && $0.source == source }) {
            items[i].kind = "знание"; items[i].history = []; items[i].version = 1
        }
        if let i = items.firstIndex(where: { !$0.isSkill && $0.title.lowercased() == t.lowercased() && $0.source == source }) {
            items[i].text = text
            items[i].date = Date()
            items[i].pinned = items[i].pinned || pinned
            save()
            return items[i]
        }
        let it = KnowledgeItem(title: t.isEmpty ? String(text.prefix(40)) : t, text: text, source: source, pinned: pinned)
        items.append(it)
        save()
        return it
    }

    func remove(_ id: String) { items.removeAll { $0.id == id }; save() }

    func update(_ it: KnowledgeItem) {
        if let i = items.firstIndex(where: { $0.id == it.id }) { items[i] = it; save() }
    }

    // MARK: поиск по смыслу слов (основа слова — первые 5 букв)

    nonisolated static func stems(_ s: String) -> [String] {
        let low = s.lowercased().replacingOccurrences(of: "ё", with: "е")
        var out: [String] = []
        var cur = ""
        for ch in low {
            if ch.isLetter || ch.isNumber { cur.append(ch) } else { if cur.count >= 3 { out.append(String(cur.prefix(5))) }; cur = "" }
        }
        if cur.count >= 3 { out.append(String(cur.prefix(5))) }
        return out
    }

    func search(_ query: String, limit: Int = 3, excludePinned: Bool = true) -> [KnowledgeItem] {
        let q = Set(Self.stems(query)).subtracting(Self.stop)
        guard !q.isEmpty else { return [] }
        let pool = items.filter { !(excludePinned && $0.pinned) }
        var df: [String: Int] = [:]
        let docs = pool.map { it -> (KnowledgeItem, Set<String>, Set<String>) in
            let t = Set(Self.stems(it.title)), b = Set(Self.stems(it.text))
            for w in t.union(b) where q.contains(w) { df[w, default: 0] += 1 }
            return (it, t, b)
        }
        let n = Double(max(pool.count, 1))
        let scored = docs.compactMap { (it, t, b) -> (KnowledgeItem, Double)? in
            var sc = 0.0
            for w in q {
                let idf = log(1 + n / Double(df[w] ?? 1))
                if t.contains(w) { sc += 3 * idf } else if b.contains(w) { sc += idf }
            }
            if it.isSkill { sc *= 1.3 }
            return sc > 0 ? (it, sc) : nil
        }
        return scored.sorted { $0.1 > $1.1 }.prefix(limit).map { $0.0 }
    }

    private static let stop: Set<String> = ["как", "что", "это", "для", "так", "все", "там", "или", "если", "мне", "мой", "моя", "мои",
                                            "надо", "нужн", "можн", "есть", "был", "быть", "тебе", "твой", "сделай", "сдела", "скажи",
                                            "пожал", "пожа", "какой", "какая", "какие", "котор", "сейча", "тепер", "очень", "только"]

    var pinnedText: String {
        items.filter { $0.pinned && !$0.isSkill }.map { "## \($0.title)\n\($0.text)" }.joined(separator: "\n\n")
    }

    // MARK: пакет знаний (файл .json или .md)

    /// .json — список {title, text, source?, pinned?}; .md — разделы «## Заголовок», «# ОСНОВА» делает разделы постоянными.
    func importPack(_ url: URL) -> String {
        let ok = url.startAccessingSecurityScopedResource()
        defer { if ok { url.stopAccessingSecurityScopedResource() } }
        guard let data = try? Data(contentsOf: url) else { return "Не открылся файл." }
        var n = 0
        if url.pathExtension.lowercased() == "json" {
            struct P: Decodable { var title: String; var text: String; var source: String?; var pinned: Bool?; var kind: String? }
            guard let list = try? JSONDecoder().decode([P].self, from: data) else { return "Файл не похож на пакет знаний." }
            for p in list {
                if p.kind == "навык" {
                    if let u = saveSkill(title: p.title, text: p.text, source: p.source ?? "пакет"), u.old != nil || list.count <= 3 { pendingUpdates.append(u) }
                } else {
                    add(title: p.title, text: p.text, source: p.source ?? "пакет", pinned: p.pinned ?? false)
                }
                n += 1
            }
        } else {
            let text = String(decoding: data, as: UTF8.self)
            n = importMarkdown(text, source: "пакет")
        }
        return "Добавлено разделов: \(n)"
    }

    /// Обновления навыков, которые помощник ещё не прочитал (покажет «что понял»).
    var pendingUpdates: [SkillUpdate] = []

    @discardableResult
    func importMarkdown(_ text: String, source: String) -> Int {
        let blocks = Self.skillBlocks(text)
        if !blocks.isEmpty {
            for (t, b) in blocks { if let u = saveSkill(title: t, text: b, source: source) { pendingUpdates.append(u) } }
            return blocks.count
        }
        var n = 0
        var pinned = false
        var skillSection = false
        var title: String?
        var body: [String] = []
        func flush() {
            if let t = title, !body.joined().trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                let b = body.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines)
                if skillSection {
                    if let u = saveSkill(title: t, text: b, source: source) { pendingUpdates.append(u) }
                } else {
                    add(title: t, text: b, source: source, pinned: pinned)
                }
                n += 1
            }
            body = []
        }
        for line in text.components(separatedBy: "\n") {
            if line.hasPrefix("# ") {
                flush(); title = nil
                pinned = line.uppercased().contains("ОСНОВА")
                skillSection = line.uppercased().contains("НАВЫК")
            } else if line.hasPrefix("## ") {
                flush()
                title = String(line.dropFirst(3)).trimmingCharacters(in: .whitespaces)
            } else if title != nil {
                body.append(line)
            }
        }
        flush()
        return n
    }

    private var firstSync = !UserDefaults.standard.bool(forKey: "kb.synced")   // первый раз сотни навыков не «читаем» вслух

    /// Знания из CRM: добавить/обновить, а удалённые в CRM — убрать из телефона.
    func syncFromCRM(_ list: [[String: Any]]) -> Int {
        var titles = Set<String>()
        for it in list {
            guard let t = it["title"] as? String, let x = it["text"] as? String else { continue }
            titles.insert(t.lowercased())
            if (it["kind"] as? String) == "навык" {
                let isNew = !items.contains { $0.isSkill && $0.title.lowercased() == t.lowercased() }
                if let u = saveSkill(title: t, text: x, source: "CRM"), !(isNew && firstSync) { pendingUpdates.append(u) }
            } else {
                add(title: t, text: x, source: "CRM", pinned: it["pinned"] as? Bool ?? false)
            }
        }
        firstSync = false
        UserDefaults.standard.set(true, forKey: "kb.synced")
        let before = items.count
        items.removeAll { $0.source == "CRM" && !$0.isSkill && !titles.contains($0.title.lowercased()) }
        if items.count != before { save() }
        return titles.count
    }

    /// Своё (не из CRM) — для копии на сервер.
    var ownForBackup: [[String: Any]] {
        let f = ISO8601DateFormatter()
        return items.filter { $0.source != "CRM" && $0.source != "пакет" }.map {
            ["title": $0.title, "text": $0.text, "source": $0.source, "pinned": $0.pinned, "date": f.string(from: $0.date),
             "kind": $0.kind, "version": $0.version] as [String: Any]
        }
    }

    func restore(_ list: [[String: Any]]) -> Int {
        var n = 0
        for it in list {
            guard let t = it["title"] as? String, let x = it["text"] as? String else { continue }
            if items.contains(where: { $0.title.lowercased() == t.lowercased() && $0.text == x }) { continue }
            if (it["kind"] as? String) == "навык" {
                saveSkill(title: t, text: x, source: it["source"] as? String ?? "сама")
            } else {
                add(title: t, text: x, source: it["source"] as? String ?? "вы", pinned: it["pinned"] as? Bool ?? false)
            }
            n += 1
        }
        return n
    }

    func exportURL() -> URL {
        save()
        return file
    }
}
