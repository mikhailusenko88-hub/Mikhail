import Foundation
import llama

/// Нейросеть внутри телефона: llama.cpp (Metal) + файл модели GGUF.
/// Всё считается на iPhone, в интернет ничего не уходит.
final class LlamaEngine {
    static let shared = LlamaEngine()

    enum Failure: LocalizedError {
        case noModel, loadFailed(String), contextFailed, decodeFailed(Int32), tooLong(Int)
        var errorDescription: String? {
            switch self {
            case .noModel: return "Нейросеть ещё не скачана."
            case .loadFailed(let p): return "Не удалось открыть файл нейросети: \((p as NSString).lastPathComponent)"
            case .contextFailed: return "Не хватило памяти телефона для нейросети. Закройте другие приложения и попробуйте снова."
            case .decodeFailed(let c): return "Сбой при расчёте (код \(c))."
            case .tooLong(let n): return "Слишком длинный разговор (\(n) частей текста) — начните новый."
            }
        }
    }

    /// Флажок «остановить» — меняется с главного потока, читается в расчёте.
    final class Stop {
        private let lock = NSLock()
        private var v = false
        var value: Bool {
            get { lock.lock(); defer { lock.unlock() }; return v }
            set { lock.lock(); v = newValue; lock.unlock() }
        }
    }

    private let queue = DispatchQueue(label: "ru.usenko.zamer3d.llm", qos: .userInitiated)
    private var model: OpaquePointer?
    private var ctx: OpaquePointer?
    private var vocab: OpaquePointer?
    private var cached: [llama_token] = []
    /// Qwen3.5 — «гибридная» нейросеть: её память нельзя откатить на кусок назад. Поэтому держим снимок
    /// прочитанного начала разговора и при следующем вопросе возвращаемся к нему, а не перечитываем всё заново.
    private(set) var rollbackOK = true
    private var snap: (toks: [llama_token], data: [UInt8])?
    private(set) var loadedPath: String?
    private(set) var nCtx: Int = 0
    private static var backendReady = false

    var isLoaded: Bool { queue.sync { ctx != nil } }

    /// Выполнить работу на отдельном потоке нейросети.
    private func run<T>(_ body: @escaping () throws -> T) async throws -> T {
        try await withCheckedThrowingContinuation { (c: CheckedContinuation<T, Error>) in
            queue.async {
                do { c.resume(returning: try body()) } catch { c.resume(throwing: error) }
            }
        }
    }

    // MARK: загрузка

    func load(path: String) async throws {
        try await run { try self.loadSync(path: path) }
    }

    private func loadSync(path: String) throws {
        if loadedPath == path, ctx != nil { return }
        unloadSync()
        guard FileManager.default.fileExists(atPath: path) else { throw Failure.noModel }
        if !Self.backendReady { llama_backend_init(); Self.backendReady = true }
        var mp = llama_model_default_params()
        mp.n_gpu_layers = 999
        guard let m = llama_model_load_from_file(path, mp) else { throw Failure.loadFailed(path) }
        // сначала пробуем длинную память разговора в сжатом виде, не вышло — обычную короче
        let threads = Int32(max(2, min(6, ProcessInfo.processInfo.activeProcessorCount - 2)))
        var made: OpaquePointer?
        var size = 0
        for (n, q8) in [(8192, true), (6144, true), (4096, false), (3072, false)] {
            var cp = llama_context_default_params()
            cp.n_ctx = UInt32(n)
            cp.n_batch = 512
            cp.n_ubatch = 512
            cp.n_threads = threads
            cp.n_threads_batch = threads
            cp.flash_attn_type = q8 ? LLAMA_FLASH_ATTN_TYPE_ENABLED : LLAMA_FLASH_ATTN_TYPE_AUTO   // быстрее на видеокарте iPhone
            if q8 {
                cp.type_k = GGML_TYPE_Q8_0
                cp.type_v = GGML_TYPE_Q8_0
            }
            if let c = llama_init_from_model(m, cp) { made = c; size = n; break }
        }
        guard let c = made else { llama_model_free(m); throw Failure.contextFailed }
        model = m
        ctx = c
        vocab = llama_model_get_vocab(m)
        cached = []
        snap = nil
        nCtx = size
        loadedPath = path
        rollbackOK = probeRollback()
    }

    /// Умеет ли память откатываться кусками (обычные нейросети — да, гибридные — нет).
    private func probeRollback() -> Bool {
        guard let ctx else { return true }
        let mem = llama_get_memory(ctx)
        defer { llama_memory_clear(mem, true); cached = [] }
        let t = tokenize("Проверка памяти нейросети")
        guard t.count >= 3, decode(t) == 0 else { return true }
        return llama_memory_seq_rm(mem, 0, 1, -1)
    }

    func unload() { queue.sync { unloadSync() } }

    /// Освободить память, не дожидаясь на главном потоке (экран не подвисает).
    func unloadLater() { queue.async { self.unloadSync() } }

    private func unloadSync() {
        if let c = ctx { llama_free(c) }
        if let m = model { llama_model_free(m) }
        ctx = nil; model = nil; vocab = nil
        cached = []
        snap = nil
        loadedPath = nil
        nCtx = 0
    }

    // MARK: текст ↔ части (токены)

    private func tokenize(_ text: String) -> [llama_token] {
        guard let vocab else { return [] }
        let n = Int32(text.utf8.count)
        var cap = n + 16
        var toks = [llama_token](repeating: 0, count: Int(cap))
        var got = llama_tokenize(vocab, text, n, &toks, cap, false, true)
        if got < 0 {
            cap = -got
            toks = [llama_token](repeating: 0, count: Int(cap))
            got = llama_tokenize(vocab, text, n, &toks, cap, false, true)
        }
        return got > 0 ? Array(toks.prefix(Int(got))) : []
    }

    private func piece(_ t: llama_token) -> [UInt8] {
        guard let vocab else { return [] }
        var buf = [CChar](repeating: 0, count: 64)
        var n = llama_token_to_piece(vocab, t, &buf, 64, 0, true)
        if n < 0 {
            buf = [CChar](repeating: 0, count: Int(-n))
            n = llama_token_to_piece(vocab, t, &buf, -n, 0, true)
        }
        return n > 0 ? buf.prefix(Int(n)).map { UInt8(bitPattern: $0) } : []
    }

    /// Сколько частей (токенов) в тексте — чтобы обрезать старый разговор.
    func count(_ text: String) async -> Int {
        (try? await run { self.tokenize(text).count }) ?? text.count / 3
    }

    // MARK: ответ

    /// Считает продолжение текста. onText получает весь ответ на текущий момент (на главном потоке).
    /// Повтор начала разговора не пересчитывается — берётся из памяти (быстро).
    /// keepSnap = false — для побочных задач (итоги разговора, разбор навыков): не затирать снимок разговора.
    func generate(prompt: String, maxTokens: Int, temperature: Float, stops: [String], stop: Stop, keepSnap: Bool = true,
                  onText: @escaping @MainActor (String) -> Void) async throws -> String {
        try await run {
            try self.generateSync(prompt: prompt, maxTokens: maxTokens, temperature: temperature, stops: stops, stop: stop, keepSnap: keepSnap, onText: onText)
        }
    }

    /// Заранее прочитать начало (пока хозяин печатает или говорит), чтобы ответ начался сразу.
    /// base — постоянная часть (правила, основа, действия): её прочитанное состояние лежит на диске и при следующем
    /// открытии не пересчитывается. full — base + разговор.
    func warmUp(base: String, full: String, file: URL, stop: Stop) async {
        _ = try? await run { () -> Bool in
            guard self.ctx != nil else { return false }
            let b = self.tokenize(base)
            guard !b.isEmpty, b.count + 512 < self.nCtx else { return false }
            let f = self.tokenize(full)
            let useFull = f.count > b.count && f.count + 1024 < self.nCtx && Array(f.prefix(b.count)) == b
            // можно ли дочитать разговор поверх того, что уже в памяти (или в снимке), не начиная сначала
            let target = useFull ? f : b
            var common = 0
            let lim = min(self.cached.count, target.count)
            while common < lim && self.cached[common] == target[common] { common += 1 }
            let snapOK = self.snap.map { $0.toks.count > b.count && $0.toks.count < target.count && Array(target.prefix($0.toks.count)) == $0.toks } ?? false
            let extendOK = common >= b.count && (common == self.cached.count || self.rollbackOK || snapOK)
            if !extendOK && !snapOK {
                if !self.loadState(file, expect: b) {
                    guard try self.feed(b, stop: stop, keepSnap: true) else { return false }
                    self.saveState(file, b)
                }
            }
            if useFull { _ = try self.feed(f, stop: stop, keepSnap: true) }
            return true
        }
    }

    private func saveState(_ file: URL, _ toks: [llama_token]) {
        guard let ctx else { return }
        var t = toks
        let tmp = file.path + ".tmp"
        if llama_state_seq_save_file(ctx, tmp, 0, &t, t.count) > 0 {
            try? FileManager.default.removeItem(at: file)
            try? FileManager.default.moveItem(atPath: tmp, toPath: file.path)
        } else {
            try? FileManager.default.removeItem(atPath: tmp)
        }
    }

    private func loadState(_ file: URL, expect: [llama_token]) -> Bool {
        guard let ctx, FileManager.default.fileExists(atPath: file.path) else { return false }
        let mem = llama_get_memory(ctx)
        llama_memory_clear(mem, true)
        cached = []
        var out = [llama_token](repeating: 0, count: expect.count + 16)
        var n = 0
        let r = llama_state_seq_load_file(ctx, file.path, 0, &out, out.count, &n)
        guard r > 0, n == expect.count, Array(out.prefix(n)) == expect else {
            llama_memory_clear(mem, true)
            try? FileManager.default.removeItem(at: file)   // устарел (поменялись правила или нейросеть)
            return false
        }
        cached = expect
        if !rollbackOK { takeSnap(expect) }
        return true
    }

    private func takeSnap(_ toks: [llama_token]) {
        guard let ctx else { return }
        let n = llama_state_seq_get_size(ctx, 0)
        var buf: [UInt8]
        if let s = snap, s.data.count == n { buf = s.data; snap = nil } else { snap = nil; buf = [] }
        guard n > 0, n < 450_000_000 else { return }
        if buf.count != n { buf = [UInt8](repeating: 0, count: n) }
        let w = buf.withUnsafeMutableBufferPointer { llama_state_seq_get_data(ctx, $0.baseAddress, n, 0) }
        if w > 0 { snap = (toks, buf) }
    }

    /// Довести память до «прочитан текст toks» с наименьшим пересчётом. false — остановлено.
    private func feed(_ toks: [llama_token], stop: Stop, keepSnap: Bool) throws -> Bool {
        guard let ctx else { throw Failure.noModel }
        let mem = llama_get_memory(ctx)
        // общее начало с тем, что уже в памяти
        var common = 0
        let lim = min(cached.count, toks.count)
        while common < lim && cached[common] == toks[common] { common += 1 }
        if common == toks.count { common -= 1 }   // последний кусок всегда считаем заново — нужен прогноз
        func restoreSnap() -> Bool {
            guard let s = snap, s.toks.count < toks.count, Array(toks.prefix(s.toks.count)) == s.toks else { return false }
            llama_memory_clear(mem, true)
            if s.data.withUnsafeBufferPointer({ llama_state_seq_set_data(ctx, $0.baseAddress, $0.count, 0) }) > 0 {
                common = s.toks.count
                return true
            }
            llama_memory_clear(mem, true)
            snap = nil
            common = 0
            return false
        }
        if common < cached.count {
            // в памяти лишнее (прошлый ответ, другой разговор) — откатываемся
            if !(rollbackOK && llama_memory_seq_rm(mem, 0, Int32(common), -1)) {
                llama_memory_clear(mem, true)
                common = 0
                _ = restoreSnap()   // гибридная нейросеть: возвращаемся к снимку прочитанного начала
            }
        } else if let s = snap, s.toks.count > common {
            _ = restoreSnap()       // память пустая или короче снимка (например, после фото)
        }
        cached = Array(toks.prefix(common))
        var i = common
        while i < toks.count {
            if stop.value { return false }
            let end = min(i + 512, toks.count)
            let chunk = Array(toks[i..<end])
            let rc = decode(chunk)
            if rc != 0 {
                llama_memory_clear(mem, true)
                cached = []
                throw Failure.decodeFailed(rc)
            }
            cached.append(contentsOf: chunk)
            i = end
        }
        if !rollbackOK && keepSnap && i > common { takeSnap(toks) }
        return true
    }

    private func decode(_ toks: [llama_token]) -> Int32 {
        guard let ctx else { return -99 }
        var arr = toks
        return arr.withUnsafeMutableBufferPointer { p in
            llama_decode(ctx, llama_batch_get_one(p.baseAddress, Int32(p.count)))
        }
    }

    private func generateSync(prompt: String, maxTokens: Int, temperature: Float, stops: [String], stop: Stop, keepSnap: Bool,
                              onText: @escaping @MainActor (String) -> Void) throws -> String {
        guard ctx != nil, vocab != nil else { throw Failure.noModel }
        let toks = tokenize(prompt)
        if toks.isEmpty { return "" }
        if toks.count + min(maxTokens, 256) >= nCtx { throw Failure.tooLong(toks.count) }

        guard try feed(toks, stop: stop, keepSnap: keepSnap) else { return "" }

        return sampleLoop(maxTokens: maxTokens, temperature: temperature, stops: stops, stop: stop, onText: onText)
    }

    private func sampleLoop(maxTokens: Int, temperature: Float, stops: [String], stop: Stop,
                            onText: @escaping @MainActor (String) -> Void) -> String {
        guard let ctx, let vocab else { return "" }
        let chain = llama_sampler_chain_init(llama_sampler_chain_default_params())!
        defer { llama_sampler_free(chain) }
        llama_sampler_chain_add(chain, llama_sampler_init_penalties(llama_vocab_n_tokens(vocab), 64, 1.05, 0, 0))
        llama_sampler_chain_add(chain, llama_sampler_init_top_k(20))
        llama_sampler_chain_add(chain, llama_sampler_init_top_p(0.8, 1))
        llama_sampler_chain_add(chain, llama_sampler_init_temp(temperature))
        llama_sampler_chain_add(chain, llama_sampler_init_dist(UInt32.random(in: 1...UInt32.max - 1)))

        var bytes: [UInt8] = []
        var out = ""
        var lastShown = Date.distantPast
        for _ in 0..<maxTokens {
            if stop.value { break }
            let t = llama_sampler_sample(chain, ctx, -1)
            if llama_vocab_is_eog(vocab, t) { break }
            bytes += piece(t)
            if let s = String(bytes: bytes, encoding: .utf8) {   // кусок буквы ждёт следующую часть
                out += s
                bytes = []
            } else if bytes.count > 12 {
                out += String(decoding: bytes, as: UTF8.self)
                bytes = []
            }
            if cached.count + 1 >= nCtx { break }
            let rc = decode([t])
            if rc != 0 { break }
            cached.append(t)
            if let hit = stops.compactMap({ s in out.range(of: s).map { (s, $0) } }).min(by: { $0.1.lowerBound < $1.1.lowerBound }) {
                out = String(out[..<hit.1.upperBound])
                break
            }
            // телефон перегрелся — даём видеокарте передышку между словами
            switch ProcessInfo.processInfo.thermalState {
            case .critical: usleep(40_000)
            case .serious: usleep(15_000)
            default: break
            }
            if Date().timeIntervalSince(lastShown) > 0.2 {   // экран обновляем 5 раз в секунду, не чаще
                lastShown = Date()
                let snap = out
                DispatchQueue.main.async { MainActor.assumeIsolated { onText(snap) } }
            }
        }
        let fin = out
        DispatchQueue.main.async { MainActor.assumeIsolated { onText(fin) } }
        return out
    }

    // MARK: зрение — фото через «глаз» нейросети (mmproj), всё в телефоне

    /// Описать фото: картинка (JPEG/PNG) + вопрос. После ответа память разговора очищается (следующий шаг пересчитает текст).
    func describeImage(_ image: Data, prompt: String, eyePath: String, maxTokens: Int, stop: Stop,
                       onText: @escaping @MainActor (String) -> Void) async throws -> String {
        try await run { try self.describeSync(image, prompt: prompt, eyePath: eyePath, maxTokens: maxTokens, stop: stop, onText: onText) }
    }

    private func describeSync(_ image: Data, prompt: String, eyePath: String, maxTokens: Int, stop: Stop,
                              onText: @escaping @MainActor (String) -> Void) throws -> String {
        guard let ctx, let model else { throw Failure.noModel }
        var mp = mtmd_context_params_default()
        mp.use_gpu = true
        mp.print_timings = false
        mp.warmup = false
        mp.n_threads = Int32(max(2, min(6, ProcessInfo.processInfo.activeProcessorCount - 2)))
        guard let mctx = mtmd_init_from_file(eyePath, model, mp) else { throw Failure.loadFailed(eyePath) }
        defer { mtmd_free(mctx) }
        let mem = llama_get_memory(ctx)
        llama_memory_clear(mem, true)
        cached = []
        defer { llama_memory_clear(mem, true); cached = [] }

        let wrap = image.withUnsafeBytes { raw -> mtmd_helper_bitmap_wrapper in
            let p = raw.bindMemory(to: UInt8.self).baseAddress
            return mtmd_helper_bitmap_init_from_buf(mctx, p, raw.count, false, mtmd_helper_init_opt_default())
        }
        guard let bitmap = wrap.bitmap else { throw Failure.loadFailed("фото") }
        defer { mtmd_bitmap_free(bitmap) }
        let marker = String(cString: mtmd_default_marker())
        let text = prompt.replacingOccurrences(of: "<__media__>", with: marker)
        let chunks = mtmd_input_chunks_init()!
        defer { mtmd_input_chunks_free(chunks) }
        let rc: Int32 = text.withCString { cs in
            var it = mtmd_input_text(text: cs, text_len: strlen(cs), add_special: false, parse_special: true)
            var bm: OpaquePointer? = bitmap
            return withUnsafePointer(to: &bm) { bp in mtmd_tokenize(mctx, chunks, &it, bp, 1) }
        }
        if rc != 0 { throw Failure.decodeFailed(rc) }
        var newPast: llama_pos = 0
        let ev = mtmd_helper_eval_chunks(mctx, ctx, chunks, 0, 0, 512, true, &newPast)
        if ev != 0 { throw Failure.decodeFailed(ev) }
        return sampleLoop(maxTokens: maxTokens, temperature: 0.2, stops: ["<|im_end|>"], stop: stop, onText: onText)
    }
}
