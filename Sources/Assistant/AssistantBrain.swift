import Foundation
import SwiftUI
import UIKit

struct ChatMsg: Identifiable, Codable, Equatable {
    enum Role: String, Codable { case user, assistant, tool, note }
    var id = UUID().uuidString
    var role: Role
    var text: String
    var call: String? = nil      // вызов действия (как его написала нейросеть)
    var tool: String? = nil      // имя действия — у результата
    var date = Date()
}

struct PendingConfirm: Identifiable {
    let id = UUID()
    let title: String
    let detail: String
    let answer: (Bool) -> Void
}

/// «Голова» помощника: собирает основу, знания, разговор и действия, гоняет нейросеть по шагам.
@MainActor
final class AssistantBrain: ObservableObject {
    static let shared = AssistantBrain()

    @Published var messages: [ChatMsg] = []
    @Published var busy = false
    @Published var live = ""
    @Published var stage = ""
    @Published var pending: PendingConfirm?
    @Published var crmTools: [ToolSpec] = CRMClient.cachedTools
    @Published var speak = UserDefaults.standard.bool(forKey: "assistant.speak") {
        didSet { UserDefaults.standard.set(speak, forKey: "assistant.speak") }
    }

    private let engine = LlamaEngine.shared
    private var stopFlag = LlamaEngine.Stop()
    private var work: Task<Void, Never>?
    private let maxSteps = 8

    private var chatFile: URL { KnowledgeBase.folder.appendingPathComponent("chat.json") }

    init() {
        if let d = try? Data(contentsOf: chatFile) {
            let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
            messages = (try? dec.decode([ChatMsg].self, from: d)) ?? []
        }
        NotificationCenter.default.addObserver(forName: UIApplication.didReceiveMemoryWarningNotification, object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in if self?.busy == false { LlamaEngine.shared.unload() } }
        }
    }

    func saveChat() {
        let enc = JSONEncoder(); enc.dateEncodingStrategy = .iso8601
        if let d = try? enc.encode(Array(messages.suffix(300))) { try? d.write(to: chatFile, options: .atomic) }
    }

    func newChat() {
        stop()
        messages = []
        saveChat()
    }

    func stop() {
        stopFlag.value = true
        work?.cancel()
        if let p = pending { pending = nil; p.answer(false) }
    }

    @Published var knowledgeNote = ""

    func refreshCRM() async {
        guard CRMClient.connected else { crmTools = []; return }
        if let t = await CRMClient.fetchTools() { crmTools = t }
        if let k = await CRMClient.fetchKnowledge() {
            let n = KnowledgeBase.shared.syncFromCRM(k)
            let up = KnowledgeBase.shared.pendingUpdates.count
            knowledgeNote = "Знаний и навыков из CRM: \(n)" + (up > 0 ? ", обновлено навыков: \(up)." : ".")
            if up > 0 { reviewPending() }
        }
    }

    var allTools: [ToolSpec] { LocalTools.specs + crmTools }

    // MARK: основа (общая часть — без сведений о магазине; их даёт пакет знаний)

    static let core = """
    Ты — «Помощник», личный помощник хозяина. Ты работаешь внутри его iPhone, твоя память и база знаний хранятся только здесь.
    Отвечай по-русски, коротко и по делу: обычно 1–5 предложений; шаги — коротким списком. Без таблиц и без украшений.

    Честность:
    - Не выдумывай цифры, цены, имена, телефоны, ссылки, даты и сроки. Не знаешь — так и скажи и предложи найти.
    - Отделяй проверенное («на сайте X написано…») от догадок («думаю…», «скорее всего…»).
    - Ошиблась — признай и исправь.

    Как искать и проверять (делай сама, не спрашивая):
    - Всё, что меняется (цены, наличие, законы, правила, контакты, новости, курсы, расписания), ищи через web_search, а не по памяти.
    - Запрос короткий, 2–6 слов, по-русски; для местных дел добавляй город. Не нашлось — другие слова, а не тот же запрос.
    - Открой 1–2 лучших ссылки через open_page. Сначала официальные источники: сайт производителя, магазина, госоргана, банка; форумы — в последнюю очередь.
    - Важную цифру подтверждай вторым источником. Смотри дату: старше года — предупреди. Источники расходятся — назови оба значения.
    - В ответе называй источник (сайт).
    - Любые расчёты денег, площадей, количества — только через calc, в уме не считай. Каждое число в ответе бери из результата calc (несколько формул — через «;»).
    - Никогда не пиши, что искала, открывала или считала, если не вызывала для этого действие.

    Как выполнять задания:
    - Сначала пойми цель. Неясно и от ответа зависит результат — задай один короткий вопрос.
    - Разбей на шаги, делай по одному действию, после каждого проверь результат. Ошибка — попробуй иначе один раз, потом честно скажи, что не вышло.
    - Опасные действия (отправка клиенту, изменения на сервере, удаление) телефон сам покажет хозяину на подтверждение — не переспрашивай текстом.
    - В конце коротко: что сделано и что осталось.

    Память:
    - «Запомни», новое правило, решение или предпочтение хозяина — сохрани через remember.
    - Проверенный полезный факт из интернета — сохрани через remember с источником и датой. Мелочи не сохраняй.
    - Раздел «Из базы знаний» ниже — твои знания по теме вопроса. Правила хозяина из основы выполняй всегда.
    - «Навык» ниже — как делать такую задачу: следуй ему. Хозяин поправил тебя или нашёлся способ лучше — допиши урок через skill_improve (одна строка: что делать в следующий раз).
    - Заявки, клиенты, склад, оплаты, почта — смотри в CRM (действия crm_…), а не по памяти. Если действий crm_… ниже нет — CRM не подключена: так и скажи, ничего не выдумывай.

    Примеры правильного первого шага:
    Хозяин: стена 3,2 на 2,7 минус дверь 0,9 на 2,1, сколько по 1290 за метр?
    Ты: <tool_call>{"name": "calc", "arguments": {"expr": "3.2*2.7-0.9*2.1; (3.2*2.7-0.9*2.1)*1290"}}</tool_call>
    Хозяин: найди, сколько стоит доставка ПЭК 300 кг Москва — Петербург
    Ты: <tool_call>{"name": "web_search", "arguments": {"query": "ПЭК стоимость доставки Москва Санкт-Петербург 300 кг"}}</tool_call>
    """

    private static func dateLine() -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "ru_RU"); f.dateFormat = "EEEE, d MMMM yyyy, HH:mm"
        return "Сейчас: \(f.string(from: Date())) (время телефона)."
    }

    /// level 0 — всё; 1 — меньше знаний по теме; 2 — без знаний по теме (когда разговор длинный).
    private func systemPrompt(for question: String, level: Int) -> String {
        var s = Self.core + "\n" + Self.dateLine()
        if crmTools.isEmpty { s += "\nCRM сейчас не подключена — действий crm_… нет." }
        let kb = KnowledgeBase.shared
        let pin = kb.pinnedText
        if !pin.isEmpty { s += "\n\n# Основа (правила и сведения хозяина)\n" + String(pin.prefix(level >= 2 ? 1500 : 2500)) }
        let found = level >= 2 ? [] : kb.search(question, limit: level == 0 ? 3 : 1)
        if !found.isEmpty {
            s += "\n\n# Из базы знаний (по теме)\n" + found.enumerated().map { i, it in
                let head = it.isSkill ? "## Навык «\(it.title)» (версия \(it.version))" : "## \(it.title) [\(it.source)]"
                let size = it.isSkill && i == 0 ? (level == 0 ? 1400 : 900) : (level == 0 ? 700 : 500)
                return head + "\n" + String(it.text.prefix(size))
            }.joined(separator: "\n\n")
        }
        s += "\n\n# Tools\n\nYou may call one or more functions to assist with the user query.\n\nYou are provided with function signatures within <tools></tools> XML tags:\n<tools>\n"
        s += allTools.map(\.json).joined(separator: "\n")
        s += "\n</tools>\n\nFor each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:\n<tool_call>\n{\"name\": <function-name>, \"arguments\": <args-json-object>}\n</tool_call>"
        return s
    }

    private func render(_ msgs: [ChatMsg]) -> String {
        var out = ""
        for m in msgs {
            switch m.role {
            case .user: out += "<|im_start|>user\n\(m.text)<|im_end|>\n"
            case .assistant:
                var body = m.text
                if let c = m.call { body += (body.isEmpty ? "" : "\n") + "<tool_call>\n\(c)\n</tool_call>" }
                out += "<|im_start|>assistant\n\(body)<|im_end|>\n"
            case .tool: out += "<|im_start|>user\n<tool_response>\n\(m.text)\n</tool_response><|im_end|>\n"
            case .note: break
            }
        }
        return out
    }

    private func prompt(question: String, kind: BrainModel.Kind) async -> String {
        var level = 0
        var sys = "<|im_start|>system\n\(systemPrompt(for: question, level: level))<|im_end|>\n"
        let tail = "<|im_start|>assistant\n" + (kind == .qwen35 ? "<think>\n\n</think>\n\n" : "")
        var hist = messages.filter { $0.role != .note }
        // старые результаты действий укорачиваем — в голову влезает немного
        if let lastUser = hist.lastIndex(where: { $0.role == .user }) {
            for i in hist.indices where i < lastUser && hist[i].role == .tool && hist[i].text.count > 400 {
                hist[i].text = String(hist[i].text.prefix(400)) + " …"
            }
        }
        let budget = max(1500, engine.nCtx - 800)
        var squeezed = false
        while true {
            let p = sys + render(hist) + tail
            if await engine.count(p) <= budget { return p }
            let lastUser = hist.lastIndex(where: { $0.role == .user }) ?? 0
            if lastUser > 0 {
                // убираем самый старый вопрос с ответами; текущий вопрос не трогаем
                hist.removeFirst()
                while let f = hist.first, f.role != .user { hist.removeFirst() }
            } else if !squeezed {
                // остался только текущий вопрос: укорачиваем результаты действий в нём
                squeezed = true
                for i in hist.indices where hist[i].role == .tool && hist[i].text.count > 700 {
                    hist[i].text = String(hist[i].text.prefix(700)) + " …"
                }
            } else if level < 2 {
                level += 1
                sys = "<|im_start|>system\n\(systemPrompt(for: question, level: level))<|im_end|>\n"
            } else {
                return p
            }
        }
    }

    // MARK: разбор ответа нейросети

    private static func stripThink(_ s: String) -> String {
        var t = s
        while let a = t.range(of: "<think>") {
            if let b = t.range(of: "</think>", range: a.upperBound..<t.endIndex) { t.removeSubrange(a.lowerBound..<b.upperBound) } else { t.removeSubrange(a.lowerBound..<t.endIndex) }
        }
        return t
    }

    struct Call { var name: String; var args: [String: Any]; var raw: String }

    private static func parse(_ out: String) -> (text: String, call: Call?) {
        let t = stripThink(out).replacingOccurrences(of: "<|im_end|>", with: "")
        guard let a = t.range(of: "<tool_call>") else { return (t.trimmingCharacters(in: .whitespacesAndNewlines), nil) }
        let before = String(t[..<a.lowerBound]).trimmingCharacters(in: .whitespacesAndNewlines)
        var rest = String(t[a.upperBound...])
        if let b = rest.range(of: "</tool_call>") { rest = String(rest[..<b.lowerBound]) }
        guard let o = rest.firstIndex(of: "{"), let c = rest.lastIndex(of: "}") else { return (before, nil) }
        let raw = String(rest[o...c])
        guard let obj = try? JSONSerialization.jsonObject(with: Data(raw.utf8)) as? [String: Any],
              let name = obj["name"] as? String else { return (before, Call(name: "", args: [:], raw: raw)) }
        var args = obj["arguments"] as? [String: Any] ?? [:]
        if args.isEmpty, let s = obj["arguments"] as? String,
           let o2 = try? JSONSerialization.jsonObject(with: Data(s.utf8)) as? [String: Any] { args = o2 }
        return (before, Call(name: name, args: args, raw: raw))
    }

    static func normURL(_ s: String) -> String {
        var t = s.trimmingCharacters(in: .whitespacesAndNewlines)
        if let h = t.firstIndex(of: "#") { t = String(t[..<h]) }
        while t.hasSuffix("/") { t.removeLast() }
        if t.hasPrefix("http://") { t = "https://" + t.dropFirst(7) }
        return t.lowercased()
    }

    static func urls(in text: String) -> Set<String> {
        Set(Web.matches(#"https?://[^\s<>"'«»]+"#, text).map { normURL($0[0]) })
    }

    static func allowedURL(_ u: String, known: Set<String>) -> Bool {
        known.contains(normURL(u))
    }

    /// Маленькая нейросеть иногда отвечает по памяти там, где нужно поискать или посчитать — один раз подсказываем.
    static func needTool(_ q: String, used: Set<String>) -> String? {
        let t = q.lowercased().replacingOccurrences(of: "ё", with: "е")
        let crm = ["заявк", "клиент", "склад", "остат", "задач", "crm", "срм", "оплат", "почт", "письм"].contains { t.contains($0) }
        let search = ["найди", "поищи", "узнай", "в интернете", "сколько стоит", "какая цена", "цена на", "цены на", "где купить",
                      "курс ", "погод", "новост", "проверь компан", "кто такой", "что такое", "расписани", "адрес "].contains { t.contains($0) }
        if search && !crm && !used.contains("web_search") {
            return "Подсказка: это нужно искать в интернете. Сначала вызови web_search коротким запросом, потом открой лучшую ссылку через open_page. По памяти цифры не называй."
        }
        let nums = Web.matches(#"\d+(?:[.,]\d+)?"#, t).count
        let calcWords = ["посчитай", "сколько будет", "рассчитай", "расчитай", "площад", "умнож", "сумм", "итого", "квадрат", "по ", "×", "*"]
        if nums >= 2 && calcWords.contains(where: { t.contains($0) }) && !used.contains("calc") && !crm {
            return "Подсказка: здесь нужен расчёт. Вызови calc с одной формулой, в уме не считай."
        }
        return nil
    }

    private func describe(_ c: Call, _ spec: ToolSpec?) -> String {
        let a = c.args.map { "\($0.key): \($0.value)" }.sorted().joined(separator: "\n")
        return (spec?.desc ?? c.name) + (a.isEmpty ? "" : "\n\n" + a)
    }

    private func stageText(_ name: String, _ args: [String: Any]) -> String {
        switch name {
        case "web_search": return "Ищу в интернете: \(args["query"] as? String ?? "")"
        case "open_page": return "Читаю страницу: \(URL(string: args["url"] as? String ?? "")?.host ?? "")"
        case "remember": return "Запоминаю…"
        case "recall": return "Вспоминаю…"
        case "calc": return "Считаю…"
        case "reminder": return "Ставлю напоминание…"
        default: return name.hasPrefix("crm") ? "Работаю с CRM…" : "Выполняю: \(name)"
        }
    }

    private func confirm(_ title: String, _ detail: String) async -> Bool {
        await withCheckedContinuation { (c: CheckedContinuation<Bool, Never>) in
            var done = false
            pending = PendingConfirm(title: title, detail: detail) { ok in
                if done { return }
                done = true
                c.resume(returning: ok)
            }
        }
    }

    func answer(_ ok: Bool) {
        guard let p = pending else { return }
        pending = nil
        p.answer(ok)
    }

    // MARK: главный цикл

    /// «#НАВЫК Название …» в сообщении — сохраняем сами, без пересказа нейросетью, и она читает и отвечает, что поняла.
    private func takeSkills(_ q: String) -> Bool {
        let blocks = KnowledgeBase.skillBlocks(q)
        guard !blocks.isEmpty else { return false }
        let kb = KnowledgeBase.shared
        messages.append(ChatMsg(role: .user, text: blocks.count == 1 ? "#НАВЫК \(blocks[0].0)\n" + String(blocks[0].1.prefix(400)) + (blocks[0].1.count > 400 ? " …" : "")
                                                                     : "Навыки: " + blocks.map(\.0).joined(separator: ", ")))
        var n = 0
        for (t, b) in blocks { if let u = kb.saveSkill(title: t, text: b, source: "вы") { kb.pendingUpdates.append(u); n += 1 } }
        if n == 0 { messages.append(ChatMsg(role: .note, text: "Эти навыки у меня уже такие же — ничего не изменилось.")) }
        saveChat()
        return true
    }

    /// Файл навыков (.navyk), открытый из чата, почты или «Файлов»: сначала спросить хозяина, потом сохранить и прочитать.
    func offerSkillFile(_ url: URL) {
        let ok = url.startAccessingSecurityScopedResource()
        defer { if ok { url.stopAccessingSecurityScopedResource() } }
        guard let data = try? Data(contentsOf: url) else {
            messages.append(ChatMsg(role: .note, text: "Не открылся файл навыков \(url.lastPathComponent)."))
            return
        }
        let text = String(decoding: data, as: UTF8.self)
        let blocks = KnowledgeBase.skillBlocks(text)
        guard !blocks.isEmpty else {
            messages.append(ChatMsg(role: .note, text: "В файле \(url.lastPathComponent) нет блоков «#НАВЫК Название»."))
            return
        }
        let kb = KnowledgeBase.shared
        let list = blocks.map { b -> String in
            let cur = kb.skills.first { $0.title.lowercased() == b.0.lowercased() }
            return "• \(b.0) — " + (cur == nil ? "новый" : (cur!.text == b.1.trimmingCharacters(in: .whitespacesAndNewlines) ? "без изменений" : "обновление, сейчас версия \(cur!.version)"))
        }.joined(separator: "\n")
        pending = PendingConfirm(title: "Обновить навыки из файла?", detail: "\(url.lastPathComponent)\n\n\(list)\n\nПринимайте файлы навыков только от себя или от Claude.") { [weak self] yes in
            guard let self else { return }
            self.pending = nil
            guard yes else {
                self.messages.append(ChatMsg(role: .note, text: "Навыки из файла не приняты."))
                return
            }
            var n = 0
            for (t, b) in blocks { if let u = kb.saveSkill(title: t, text: b, source: "файл") { kb.pendingUpdates.append(u); n += 1 } }
            self.messages.append(ChatMsg(role: .note, text: n > 0 ? "Принято навыков: \(n). Читаю…" : "Все навыки из файла уже такие же."))
            self.saveChat()
            self.reviewPending()
        }
    }

    /// Прочитать новые и изменённые навыки и коротко сказать хозяину, что поняла.
    func reviewPending() {
        let kb = KnowledgeBase.shared
        guard !busy, !kb.pendingUpdates.isEmpty, let model = ModelStore.shared.readyModel else { return }
        let list = kb.pendingUpdates
        kb.pendingUpdates = []
        busy = true
        stopFlag = LlamaEngine.Stop()
        let flag = stopFlag
        work = Task { [weak self] in
            guard let self else { return }
            do {
                if self.engine.loadedPath != ModelStore.shared.fileURL(model).path {
                    self.stage = "Загружаю нейросеть в память (10–30 секунд)…"
                    try await self.engine.load(path: ModelStore.shared.fileURL(model).path)
                }
                for u in list.prefix(5) {
                    if flag.value { break }
                    self.stage = "Читаю навык «\(u.title)»…"
                    var ask = "Тебе \(u.old == nil ? "добавили новый навык" : "обновили навык") «\(u.title)», версия \(u.version).\n"
                    if let o = u.old { ask += "Было:\n\(String(o.prefix(700)))\n\n" }
                    ask += "Стало:\n\(String(u.new.prefix(1500)))\n\nПрочитай внимательно и ответь хозяину 2–4 предложениями: что поняла и что теперь будешь делать "
                    ask += u.old == nil ? "(когда будешь пользоваться этим навыком)." : "иначе, чем раньше."
                    let p = "<|im_start|>system\nТы — «Помощник», личный помощник хозяина в его iPhone. Отвечай по-русски, коротко, без выдумок.<|im_end|>\n"
                        + "<|im_start|>user\n\(ask)<|im_end|>\n<|im_start|>assistant\n" + (model.kind == .qwen35 ? "<think>\n\n</think>\n\n" : "")
                    self.live = ""
                    let out = try await self.engine.generate(prompt: p, maxTokens: 260, temperature: 0.3, stops: ["<|im_end|>"], stop: flag) { [weak self] t in
                        self?.live = Self.stripThink(t).trimmingCharacters(in: .whitespacesAndNewlines)
                    }
                    let text = Self.stripThink(out).replacingOccurrences(of: "<|im_end|>", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
                    self.live = ""
                    self.messages.append(ChatMsg(role: .assistant, text: "📘 Навык «\(u.title)», версия \(u.version)\n\(text)"))
                    if self.speak { Speaker.shared.say("Навык \(u.title). \(text)") }
                    self.saveChat()
                }
                if list.count > 5 {
                    self.messages.append(ChatMsg(role: .note, text: "Ещё обновлено навыков: \(list.count - 5). Список — ⚙︎ → «Навыки»."))
                }
            } catch {
                self.messages.append(ChatMsg(role: .note, text: "⚠️ " + error.localizedDescription))
            }
            self.busy = false
            self.stage = ""
            self.saveChat()
        }
    }

    func send(_ text: String) {
        let q = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty, !busy else { return }
        if takeSkills(q) { reviewPending(); return }
        messages.append(ChatMsg(role: .user, text: q))
        saveChat()
        busy = true
        stopFlag = LlamaEngine.Stop()
        let flag = stopFlag
        work = Task { [weak self] in
            await self?.loop(question: q, flag: flag)
            await MainActor.run {
                self?.messages.removeAll { $0.tool == "hint" }
                self?.busy = false
                self?.live = ""
                self?.stage = ""
                self?.saveChat()
            }
        }
    }

    private func loop(question: String, flag: LlamaEngine.Stop) async {
        let store = ModelStore.shared
        guard let model = store.readyModel else {
            messages.append(ChatMsg(role: .note, text: "Нейросеть ещё не в телефоне. Откройте ⚙︎ и нажмите «Скачать»."))
            return
        }
        do {
            if engine.loadedPath != store.fileURL(model).path {
                stage = "Загружаю нейросеть в память (10–30 секунд)…"
                try await engine.load(path: store.fileURL(model).path)
            }
            if crmTools.isEmpty && CRMClient.connected { await refreshCRM() }
            var badFormat = 0
            var used = Set<String>()
            var nudged = false
            var known = Self.urls(in: question)      // адреса, которые можно открывать без вопроса
            for step in 0..<maxSteps {
                if flag.value { break }
                stage = step == 0 ? "Думаю…" : "Думаю дальше…"
                let p = await prompt(question: question, kind: model.kind)
                live = ""
                let out = try await engine.generate(prompt: p, maxTokens: 700, temperature: 0.4, stops: ["</tool_call>", "<|im_end|>"], stop: flag) { [weak self] t in
                    guard let self else { return }
                    let visible = Self.stripThink(t).components(separatedBy: "<tool_call>").first ?? ""
                    self.live = visible.trimmingCharacters(in: .whitespacesAndNewlines)
                    if !visible.isEmpty { self.stage = "" }
                }
                if flag.value { break }
                let (text, call) = Self.parse(out)
                live = ""
                guard let call else {
                    if !nudged, let hint = Self.needTool(question, used: used) {
                        nudged = true
                        messages.append(ChatMsg(role: .tool, text: hint, tool: "hint"))   // на экране не видно, после ответа убирается
                        continue
                    }
                    let final = text.isEmpty ? "…" : text
                    messages.append(ChatMsg(role: .assistant, text: final))
                    if speak { Speaker.shared.say(final) }
                    return
                }
                let spec = allTools.first { $0.name == call.name }
                messages.append(ChatMsg(role: .assistant, text: text, call: call.raw))
                guard let spec else {
                    badFormat += 1
                    messages.append(ChatMsg(role: .tool, text: "Ошибка: нет действия «\(call.name)». Доступны: \(allTools.map(\.name).joined(separator: ", ")).", tool: call.name))
                    if badFormat > 2 { break }
                    continue
                }
                used.insert(call.name)
                var confirmed = false
                // защита от «подсказок» на чужих страницах: сама открывает только ссылки из поиска или из вашего сообщения
                if call.name == "open_page", let u = call.args["url"] as? String, !Self.allowedURL(u, known: known) {
                    stage = "Жду вашего ответа…"
                    let ok = await confirm("Открыть страницу не из поиска?", "Адрес: \(u)\n\nЕго нет ни в результатах поиска, ни в вашем сообщении. Если адрес подозрительный или в нём видны ваши данные — нажмите «Нет».")
                    if !ok {
                        messages.append(ChatMsg(role: .tool, text: "Хозяин не разрешил открывать этот адрес. Открывай только ссылки из результатов поиска.", tool: call.name))
                        continue
                    }
                }
                if spec.danger {
                    stage = "Жду вашего ответа…"
                    confirmed = await confirm(spec.remote ? "CRM: сделать?" : "Сделать?", describe(call, spec))
                    if !confirmed {
                        messages.append(ChatMsg(role: .tool, text: "Хозяин отказался. Не делай этого и спроси, как поступить.", tool: call.name))
                        continue
                    }
                }
                stage = stageText(call.name, call.args)
                let result = spec.remote ? await CRMClient.call(call.name, call.args, confirmed: confirmed)
                                         : await LocalTools.run(call.name, call.args)
                if call.name == "web_search" { known.formUnion(Self.urls(in: result)) }
                messages.append(ChatMsg(role: .tool, text: String(result.prefix(3000)), tool: call.name))
                saveChat()
            }
            if !flag.value {
                messages.append(ChatMsg(role: .note, text: "Остановилась после \(maxSteps) шагов. Напишите «продолжай», если нужно."))
            }
        } catch {
            messages.append(ChatMsg(role: .note, text: "⚠️ " + error.localizedDescription))
            if let f = error as? LlamaEngine.Failure, case .tooLong = f { messages.append(ChatMsg(role: .note, text: "Нажмите «Новый разговор» ↻.")) }
        }
    }
}
