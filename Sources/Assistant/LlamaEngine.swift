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
            if q8 {
                cp.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_ENABLED
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
        nCtx = size
        loadedPath = path
    }

    func unload() { queue.sync { unloadSync() } }

    private func unloadSync() {
        if let c = ctx { llama_free(c) }
        if let m = model { llama_model_free(m) }
        ctx = nil; model = nil; vocab = nil
        cached = []
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
    func generate(prompt: String, maxTokens: Int, temperature: Float, stops: [String], stop: Stop,
                  onText: @escaping @MainActor (String) -> Void) async throws -> String {
        try await run {
            try self.generateSync(prompt: prompt, maxTokens: maxTokens, temperature: temperature, stops: stops, stop: stop, onText: onText)
        }
    }

    private func decode(_ toks: [llama_token]) -> Int32 {
        guard let ctx else { return -99 }
        var arr = toks
        return arr.withUnsafeMutableBufferPointer { p in
            llama_decode(ctx, llama_batch_get_one(p.baseAddress, Int32(p.count)))
        }
    }

    private func generateSync(prompt: String, maxTokens: Int, temperature: Float, stops: [String], stop: Stop,
                              onText: @escaping @MainActor (String) -> Void) throws -> String {
        guard let ctx, let vocab else { throw Failure.noModel }
        let toks = tokenize(prompt)
        if toks.isEmpty { return "" }
        if toks.count + min(maxTokens, 256) >= nCtx { throw Failure.tooLong(toks.count) }

        // общее начало с прошлым расчётом
        var common = 0
        let lim = min(cached.count, toks.count)
        while common < lim && cached[common] == toks[common] { common += 1 }
        if common == toks.count { common -= 1 }   // последний кусок всегда считаем заново — нужен прогноз
        let mem = llama_get_memory(ctx)
        if common < cached.count {
            if !llama_memory_seq_rm(mem, 0, Int32(common), -1) {
                llama_memory_clear(mem, true)
                common = 0
            }
        }
        cached = Array(cached.prefix(common))
        var i = common
        while i < toks.count {
            if stop.value { return "" }
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
            if Date().timeIntervalSince(lastShown) > 0.08 {
                lastShown = Date()
                let snap = out
                DispatchQueue.main.async { MainActor.assumeIsolated { onText(snap) } }
            }
        }
        let fin = out
        DispatchQueue.main.async { MainActor.assumeIsolated { onText(fin) } }
        return out
    }
}
