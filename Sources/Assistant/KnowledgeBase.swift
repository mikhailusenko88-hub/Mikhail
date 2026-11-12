import Foundation

/// Своя база знаний помощника: «запомни», найденное в интернете, пакет знаний о работе.
/// Лежит в телефоне: «Файлы» → «На iPhone» → «Замер 3D» → Assistant → knowledge.json.
struct KnowledgeItem: Codable, Identifiable, Equatable {
    var id: String = UUID().uuidString
    var title: String
    var text: String
    var source: String = "вы"          // вы / интернет / пакет / CRM
    var date: Date = Date()
    var pinned: Bool = false           // «основа» — всегда в голове
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

    @discardableResult
    func add(title: String, text: String, source: String, pinned: Bool = false) -> KnowledgeItem {
        let t = title.trimmingCharacters(in: .whitespacesAndNewlines)
        // та же тема от того же источника — обновляем, а не плодим копии
        if let i = items.firstIndex(where: { $0.title.lowercased() == t.lowercased() && $0.source == source }) {
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
            return sc > 0 ? (it, sc) : nil
        }
        return scored.sorted { $0.1 > $1.1 }.prefix(limit).map { $0.0 }
    }

    private static let stop: Set<String> = ["как", "что", "это", "для", "так", "все", "там", "или", "если", "мне", "мой", "моя", "мои",
                                            "надо", "нужн", "можн", "есть", "был", "быть", "тебе", "твой", "сделай", "сдела", "скажи",
                                            "пожал", "пожа", "какой", "какая", "какие", "котор", "сейча", "тепер", "очень", "только"]

    var pinnedText: String {
        items.filter(\.pinned).map { "## \($0.title)\n\($0.text)" }.joined(separator: "\n\n")
    }

    // MARK: пакет знаний (файл .json или .md)

    /// .json — список {title, text, source?, pinned?}; .md — разделы «## Заголовок», «# ОСНОВА» делает разделы постоянными.
    func importPack(_ url: URL) -> String {
        let ok = url.startAccessingSecurityScopedResource()
        defer { if ok { url.stopAccessingSecurityScopedResource() } }
        guard let data = try? Data(contentsOf: url) else { return "Не открылся файл." }
        var n = 0
        if url.pathExtension.lowercased() == "json" {
            struct P: Decodable { var title: String; var text: String; var source: String?; var pinned: Bool? }
            guard let list = try? JSONDecoder().decode([P].self, from: data) else { return "Файл не похож на пакет знаний." }
            for p in list { add(title: p.title, text: p.text, source: p.source ?? "пакет", pinned: p.pinned ?? false); n += 1 }
        } else {
            let text = String(decoding: data, as: UTF8.self)
            n = importMarkdown(text, source: "пакет")
        }
        return "Добавлено разделов: \(n)"
    }

    @discardableResult
    func importMarkdown(_ text: String, source: String) -> Int {
        var n = 0
        var pinned = false
        var title: String?
        var body: [String] = []
        func flush() {
            if let t = title, !body.joined().trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                add(title: t, text: body.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines), source: source, pinned: pinned)
                n += 1
            }
            body = []
        }
        for line in text.components(separatedBy: "\n") {
            if line.hasPrefix("# ") {
                flush(); title = nil
                pinned = line.uppercased().contains("ОСНОВА")
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

    func exportURL() -> URL {
        save()
        return file
    }
}
