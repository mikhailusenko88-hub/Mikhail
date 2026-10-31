import SwiftUI
import WebKit
import UniformTypeIdentifiers
import AVFoundation
import Speech

/// Раздел «Мебель»: 3D-конструктор на three.js внутри приложения.
/// Стены берутся из скана (RoomPlan), модули сохраняются в папку скана:
/// kitchen.json — для примерки, и копия с понятным именем (Кухня.json, Шкаф.json…).
struct MebelView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var scans: [String] = []
    @State private var scan: String?
    @State private var kind = "Кухня"
    @State private var key = ""
    @State private var keyStatus = GitHubKey.value == nil ? "Ключ не введён" : "Ключ сохранён ✓"
    @State private var pickBazis = false
    @State private var bazis: BazisFile?
    @State private var bazisError: String?
    static let kinds = ["Кухня", "Шкаф", "Гардеробная", "Тумба", "Консоль", "Прачечная", "Другое"]

    var body: some View {
        if let s = scan {
            MebelWeb(scan: s, name: kind) { scan = nil }
                .ignoresSafeArea()
        } else {
            NavigationView {
                List {
                    Section("Что проектируем") {
                        Picker("Тип", selection: $kind) {
                            ForEach(Self.kinds, id: \.self) { Text($0) }
                        }
                    }
                    Section(header: Text("Ссылки клиентам"),
                            footer: Text("Один раз: GitHub → Settings → Developer settings → Fine-grained tokens → доступ только к репозиторию Mikhail, Contents: Read and write. Ключ хранится в Связке ключей телефона.")) {
                        SecureField("Ключ GitHub (github_pat_…)", text: $key)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                        Button("Сохранить и проверить ключ") {
                            GitHubKey.set(key); key = ""
                            keyStatus = "Проверяю…"
                            Task { keyStatus = await ClientLink.check() }
                        }
                        Text(keyStatus).foregroundColor(.secondary)
                    }
                    Section(header: Text("Файлы Базис-Мебельщика"),
                            footer: Text("Открывает .b3d и .fr3d, в том числе внутри .zip. Можно и из Telegram / «Файлов»: «Поделиться» → «Замер 3D».")) {
                        Button("Открыть .b3d / .fr3d") { pickBazis = true }
                        if let e = bazisError { Text(e).foregroundColor(.red) }
                    }
                    Section(header: Text("Проекты и сканы"),
                            footer: Text("Новый проект — пустая комната, без скана. Скан — стены из замера.")) {
                        Button {
                            let df = DateFormatter(); df.dateFormat = "yyyy-MM-dd_HH-mm"
                            let name = "Проект_\(df.string(from: Date()))"
                            try? FileManager.default.createDirectory(at: FittingModel.docs.appendingPathComponent(name),
                                                                     withIntermediateDirectories: true)
                            scan = name
                        } label: {
                            Label("Новый проект без скана", systemImage: "plus.circle.fill")
                        }
                        ForEach(scans, id: \.self) { s in
                            Button(s) { scan = s }
                        }
                    }
                }
                .navigationTitle("Мебель")
                .toolbar { Button("Закрыть") { dismiss() } }
            }
            .onAppear(perform: refresh)
            .fileImporter(isPresented: $pickBazis, allowedContentTypes: BazisFile.types) { r in
                if case .success(let url) = r {
                    bazis = BazisFile.load(url)
                    bazisError = bazis == nil ? "Не удалось прочитать файл" : nil
                }
            }
            .fullScreenCover(item: $bazis) { BazisScreen(file: $0) }
        }
    }

    private func refresh() {
        let docs = FittingModel.docs
        let fm = FileManager.default
        scans = ((try? fm.contentsOfDirectory(atPath: docs.path)) ?? []).filter {
            var dir: ObjCBool = false
            return fm.fileExists(atPath: docs.appendingPathComponent($0).path, isDirectory: &dir) && dir.boolValue
        }.sorted(by: >)
    }
}

struct MebelWeb: UIViewRepresentable {
    let scan: String
    let name: String
    let onClose: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.setURLSchemeHandler(BundleScheme(), forURLScheme: "mebel")
        cfg.userContentController.add(context.coordinator, name: "mebel")
        let web = WKWebView(frame: .zero, configuration: cfg)
        web.isOpaque = false
        web.backgroundColor = .black
        web.scrollView.isScrollEnabled = false
        context.coordinator.web = web
        web.load(URLRequest(url: URL(string: "mebel://app/index.html")!))
        return web
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) {
        uiView.configuration.userContentController.removeScriptMessageHandler(forName: "mebel")
    }

    final class Coordinator: NSObject, WKScriptMessageHandler {
        let parent: MebelWeb
        weak var web: WKWebView?
        init(_ p: MebelWeb) { parent = p }

        var dir: URL { FittingModel.docs.appendingPathComponent(parent.scan) }

        func userContentController(_ c: WKUserContentController, didReceive message: WKScriptMessage) {
            guard let body = message.body as? [String: Any], let type = body["type"] as? String else { return }
            switch type {
            case "ready": sendLoad()
            case "save": save(body["project"], quiet: body["quiet"] as? Bool ?? false)
            case "publish": publish(body)
            case "close": parent.onClose()
            default: break
            }
        }

        /// Отдать странице стены из скана и уже сохранённые модули.
        private func sendLoad() {
            var payload: [String: Any] = ["name": parent.name]
            if let data = try? Data(contentsOf: dir.appendingPathComponent("info.json")),
               let info = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let walls = info["roomPlan"] { payload["walls"] = walls }
            if let data = try? Data(contentsOf: dir.appendingPathComponent("obstacles.json")),
               let obs = try? JSONSerialization.jsonObject(with: data) { payload["obstacles"] = obs }   // выступы, ступеньки, предметы, метки
            let named = dir.appendingPathComponent("\(parent.name).json")
            let file = FileManager.default.fileExists(atPath: named.path) ? named
                     : dir.appendingPathComponent(FittingModel.kitchenFile)
            if let data = try? Data(contentsOf: file),
               let proj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let mods = proj["modules"] {
                payload["modules"] = mods
                if let link = proj["link"] { payload["link"] = link }
                if let plan = proj["plan"] { payload["plan"] = plan }   // стены, заданные вручную
            }
            guard let json = try? JSONSerialization.data(withJSONObject: payload),
                  let s = String(data: json, encoding: .utf8) else { return }
            web?.evaluateJavaScript("Mebel.load(\(s))")
        }

        private func js(_ s: String) -> String {
            (try? JSONEncoder().encode(s)).flatMap { String(data: $0, encoding: .utf8) } ?? "\"\""
        }

        private func say(_ t: String) { web?.evaluateJavaScript("Mebel.saved(\(js(t)))") }

        /// «Ссылка клиенту»: номер 100/N и код → страница от редактора → GitHub (ветка mebel) → ссылка.
        private func publish(_ body: [String: Any]) {
            guard let web = web else { return }
            let proj = body["project"] as? [String: Any]
            let what = (body["what"] as? String) ?? parent.name
            var existing: ClientLink.Link?
            if let d = proj?["link"] as? [String: Any], let c = d["code"] as? String, let n = d["number"] as? String {
                existing = ClientLink.Link(code: c, number: n)
            }
            Task { @MainActor in
                do {
                    let (link, isNew) = try await ClientLink.prepare(existing: existing)
                    guard let html = try await web.evaluateJavaScript("Mebel.clientHTML(\(js(link.number)))") as? String else {
                        say("Страница не собралась"); return
                    }
                    let url = try await ClientLink.publish(html: html, link: link, isNew: isNew, what: what)
                    if let d = try? JSONEncoder().encode(link), let lj = String(data: d, encoding: .utf8) {
                        _ = try? await web.evaluateJavaScript("Mebel.published(\(lj))")
                    }
                    UIPasteboard.general.string = url.absoluteString
                    say("Проект \(link.number): ссылка скопирована, откроется через минуту")
                    share(url, from: web)
                } catch {
                    say(error.localizedDescription)
                }
            }
        }

        private func share(_ url: URL, from v: UIView) {
            guard var top = v.window?.rootViewController else { return }
            while let p = top.presentedViewController { top = p }
            let vc = UIActivityViewController(activityItems: [url], applicationActivities: nil)
            vc.popoverPresentationController?.sourceView = v
            top.present(vc, animated: true)
        }

        private func save(_ project: Any?, quiet: Bool = false) {
            guard let project = project,
                  let data = try? JSONSerialization.data(withJSONObject: project, options: [.prettyPrinted, .sortedKeys]),
                  (try? JSONDecoder().decode(Kitchen.self, from: data)) != nil else {
                web?.evaluateJavaScript("Mebel.saved('Не удалось сохранить')")
                return
            }
            do {
                try data.write(to: dir.appendingPathComponent("\(parent.name).json"))
                try data.write(to: dir.appendingPathComponent(FittingModel.kitchenFile))   // для примерки
                if !quiet { say("Сохранено: \(parent.name).json") }
            } catch {
                web?.evaluateJavaScript("Mebel.saved('Ошибка сохранения')")
            }
        }
    }
}

/// Отдаёт файлы движка из приложения по адресу mebel://app/… (так модули JS грузятся без интернета).
final class BundleScheme: NSObject, WKURLSchemeHandler {
    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        guard let url = task.request.url,
              let root = Bundle.main.url(forResource: "Mebel", withExtension: nil) else {
            task.didFailWithError(URLError(.fileDoesNotExist)); return
        }
        let path = url.path.isEmpty || url.path == "/" ? "index.html" : String(url.path.dropFirst())
        let file = root.appendingPathComponent(path)
        guard let data = try? Data(contentsOf: file) else {
            task.didFailWithError(URLError(.fileDoesNotExist)); return
        }
        let mime: String
        switch file.pathExtension {
        case "html": mime = "text/html"
        case "js": mime = "text/javascript"
        case "json": mime = "application/json"
        default: mime = UTType(filenameExtension: file.pathExtension)?.preferredMIMEType ?? "application/octet-stream"
        }
        let resp = HTTPURLResponse(url: url, statusCode: 200, httpVersion: "HTTP/1.1",
                                   headerFields: ["Content-Type": mime, "Content-Length": "\(data.count)"])!
        task.didReceive(resp)
        task.didReceive(data)
        task.didFinish()
    }

    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) {}
}


// MARK: - Мультики: сериалы по сценариям из чата, персонажи с замороженным кодом, озвучка голосами iPhone, сборка mp4

struct MultikScreen: View {
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        MultikWeb { dismiss() }
            .ignoresSafeArea()
            .background(Color.black)
    }
}

struct MultikWeb: UIViewRepresentable {
    let onClose: () -> Void

    func makeCoordinator() -> MultikBridge { MultikBridge(onClose: onClose) }

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.setURLSchemeHandler(BundleScheme(), forURLScheme: "mebel")
        cfg.userContentController.addScriptMessageHandler(context.coordinator, contentWorld: .page, name: "multik")
        cfg.allowsInlineMediaPlayback = true
        cfg.mediaTypesRequiringUserActionForPlayback = []
        let web = WKWebView(frame: .zero, configuration: cfg)
        web.isOpaque = false
        web.backgroundColor = .black
        context.coordinator.web = web
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)
        web.load(URLRequest(url: URL(string: "mebel://app/multik.html")!))
        return web
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    static func dismantleUIView(_ uiView: WKWebView, coordinator: MultikBridge) {
        uiView.configuration.userContentController.removeScriptMessageHandler(forName: "multik", contentWorld: .page)
        coordinator.cleanup()
    }
}

/// Мост страница ↔ iPhone. Каждый вызов из JS возвращает Promise (ответ через replyHandler).
final class MultikBridge: NSObject, WKScriptMessageHandlerWithReply, UIDocumentPickerDelegate {
    let onClose: () -> Void
    weak var web: WKWebView?
    private let tts = MultikTTS()
    private let speaker = AVSpeechSynthesizer()
    private let listener = MultikListener()
    private var writer: MultikWriter?
    private let queue = DispatchQueue(label: "multik.writer", qos: .userInitiated)
    private var pickReply: ((Any?, String?) -> Void)?

    init(onClose: @escaping () -> Void) { self.onClose = onClose }

    static var root: URL {
        let u = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("multik")
        for d in ["", "voice", "video", "tmp"] {
            try? FileManager.default.createDirectory(at: u.appendingPathComponent(d), withIntermediateDirectories: true)
        }
        return u
    }

    func cleanup() {
        _ = listener.stop()
        if let w = writer { queue.async { w.cancel() } }
        writer = nil
        UIApplication.shared.isIdleTimerDisabled = false
    }

    func userContentController(_ c: WKUserContentController, didReceive message: WKScriptMessage,
                               replyHandler: @escaping (Any?, String?) -> Void) {
        guard let body = message.body as? [String: Any], let cmd = body["cmd"] as? String else {
            replyHandler(nil, "bad message"); return
        }
        let root = Self.root
        switch cmd {
        case "load":
            replyHandler((try? String(contentsOf: root.appendingPathComponent("library.json"), encoding: .utf8)) ?? NSNull(), nil)
        case "save":
            let json = body["json"] as? String ?? ""
            let url = root.appendingPathComponent("library.json")
            // резервная копия прошлой версии библиотеки
            if FileManager.default.fileExists(atPath: url.path) {
                let bak = root.appendingPathComponent("library.bak.json")
                try? FileManager.default.removeItem(at: bak)
                try? FileManager.default.copyItem(at: url, to: bak)
            }
            replyHandler((try? json.write(to: url, atomically: true, encoding: .utf8)) != nil, nil)
        case "resolveVoice":
            let v = MultikTTS.pickVoice(body["voice"] as? [String: Any] ?? [:])
            replyHandler(["id": v?.identifier ?? "", "name": v.map { "\($0.name) (\(MultikTTS.qualityName($0.quality)))" } ?? "нет"], nil)
        case "voices":
            let list = AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix("ru") }
                .map { ["name": $0.name, "id": $0.identifier, "quality": MultikTTS.qualityName($0.quality)] }
            replyHandler(list, nil)
        case "tts":
            let text = body["text"] as? String ?? ""
            let key = (body["key"] as? String ?? UUID().uuidString).replacingOccurrences(of: "/", with: "_")
            let voice = body["voice"] as? [String: Any] ?? [:]
            let url = root.appendingPathComponent("voice/\(key).caf")
            if let d = try? Data(contentsOf: url), d.count > 1000 {
                replyHandler(["wav": d.base64EncodedString(), "cached": true], nil); return
            }
            tts.synthesize(text: text, voice: voice, to: url) { ok in
                DispatchQueue.main.async {
                    if ok, let d = try? Data(contentsOf: url) { replyHandler(["wav": d.base64EncodedString()], nil) }
                    else { replyHandler(NSNull(), nil) }
                }
            }
        case "speak":
            speaker.stopSpeaking(at: .immediate)
            speaker.speak(MultikTTS.utterance(body["text"] as? String ?? "", body["voice"] as? [String: Any] ?? [:]))
            replyHandler(true, nil)
        case "listenStart":
            listener.start(onText: { [weak self] t in
                guard let d = try? JSONEncoder().encode(t), let js = String(data: d, encoding: .utf8) else { return }
                self?.web?.evaluateJavaScript("Ed.onSpeech(\(js))")
            }) { ok in replyHandler(ok, nil) }
        case "listenStop":
            replyHandler(listener.stop(), nil)
        case "paste":
            replyHandler(UIPasteboard.general.string ?? "", nil)
        case "copy":
            UIPasteboard.general.string = body["text"] as? String ?? ""
            replyHandler(true, nil)
        case "pickFile":
            pickReply = replyHandler
            let picker = UIDocumentPickerViewController(forOpeningContentTypes: [.json, .plainText, .text, .data])
            picker.delegate = self
            Self.top()?.present(picker, animated: true)
        case "fetch":
            guard let s = body["url"] as? String, let url = URL(string: s) else { replyHandler(NSNull(), nil); return }
            var req = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
            if body["api"] as? Bool == true { req.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept") }
            URLSession.shared.dataTask(with: req) { data, resp, _ in
                let ok = ((resp as? HTTPURLResponse)?.statusCode ?? 0) == 200
                let text = ok ? data.flatMap { String(data: $0, encoding: .utf8) } : nil
                DispatchQueue.main.async { replyHandler(text ?? NSNull(), nil) }
            }.resume()
        case "share":
            guard let p = body["path"] as? String else { replyHandler(false, nil); return }
            let url = p.hasPrefix("/") ? URL(fileURLWithPath: p) : root.appendingPathComponent(p)
            guard FileManager.default.fileExists(atPath: url.path) else { replyHandler(false, "Файл не найден"); return }
            let vc = UIActivityViewController(activityItems: [url], applicationActivities: nil)
            if let top = Self.top() {
                vc.popoverPresentationController?.sourceView = top.view
                vc.popoverPresentationController?.sourceRect = CGRect(x: top.view.bounds.midX, y: top.view.bounds.midY, width: 1, height: 1)
                top.present(vc, animated: true)
            }
            replyHandler(true, nil)
        case "audioChunk":
            let url = root.appendingPathComponent("tmp/audio.wav")
            let d = Data(base64Encoded: body["d"] as? String ?? "") ?? Data()
            queue.async {
                if body["first"] as? Bool == true { try? FileManager.default.removeItem(at: url); FileManager.default.createFile(atPath: url.path, contents: nil) }
                if let h = try? FileHandle(forWritingTo: url) { h.seekToEndOfFile(); h.write(d); try? h.close() }
                DispatchQueue.main.async { replyHandler(true, nil) }
            }
        case "videoBegin":
            let w = body["w"] as? Int ?? 1920, h = body["h"] as? Int ?? 1080, fps = body["fps"] as? Int ?? 25
            let name = (body["name"] as? String ?? "Серия").replacingOccurrences(of: "/", with: "-")
            let out = root.appendingPathComponent("video/\(name).mp4")
            let audio = root.appendingPathComponent("tmp/audio.wav")
            UIApplication.shared.isIdleTimerDisabled = true
            queue.async {
                let wr = MultikWriter(out: out, tmp: root.appendingPathComponent("tmp/render.mp4"), w: w, h: h, fps: Int32(fps), audio: audio)
                let ok = wr.start()
                DispatchQueue.main.async { self.writer = ok ? wr : nil; replyHandler(ok, ok ? nil : wr.error) }
            }
        case "videoFrame":
            guard let wr = writer, let s = body["d"] as? String else { replyHandler(false, "нет записи"); return }
            queue.async {
                let ok = Data(base64Encoded: s).map { wr.append(jpeg: $0) } ?? false
                DispatchQueue.main.async { replyHandler(ok, nil) }
            }
        case "videoEnd":
            guard let wr = writer else { replyHandler(["error": "нет записи"], nil); return }
            writer = nil
            queue.async {
                let path = wr.finish()
                DispatchQueue.main.async {
                    UIApplication.shared.isIdleTimerDisabled = false
                    if let p = path { replyHandler(["path": "video/" + p.lastPathComponent], nil) }
                    else { replyHandler(["error": wr.error ?? "ошибка записи"], nil) }
                }
            }
        case "videoCancel":
            cleanup(); replyHandler(true, nil)
        case "close":
            cleanup(); replyHandler(true, nil)
            speaker.stopSpeaking(at: .immediate)
            onClose()
        default:
            replyHandler(NSNull(), nil)
        }
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        var text = ""
        if let u = urls.first {
            let ok = u.startAccessingSecurityScopedResource()
            text = (try? String(contentsOf: u, encoding: .utf8)) ?? ""
            if ok { u.stopAccessingSecurityScopedResource() }
        }
        pickReply?(text, nil); pickReply = nil
    }
    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) { pickReply?("", nil); pickReply = nil }

    static func top() -> UIViewController? {
        let scene = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first
        var vc = scene?.windows.first(where: { $0.isKeyWindow })?.rootViewController ?? scene?.windows.first?.rootViewController
        while let p = vc?.presentedViewController { vc = p }
        return vc
    }
}

/// Озвучка реплик голосами iPhone в файл (.caf).
final class MultikTTS: NSObject {
    private let synth = AVSpeechSynthesizer()
    private var busy = false
    private var jobs: [(String, [String: Any], URL, (Bool) -> Void)] = []

    static func qualityName(_ q: AVSpeechSynthesisVoiceQuality) -> String {
        switch q { case .premium: return "премиум"; case .enhanced: return "улучшенный"; default: return "обычный" }
    }

    /// Голос по описанию персонажа: сохранённый id → иначе лучший русский нужного пола.
    static func pickVoice(_ v: [String: Any]) -> AVSpeechSynthesisVoice? {
        if let id = v["id"] as? String, !id.isEmpty, let x = AVSpeechSynthesisVoice(identifier: id) { return x }
        let ru = AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix("ru") }
            .sorted { $0.quality.rawValue > $1.quality.rawValue }
        let male = (v["base"] as? String ?? "female") == "male"
        func isMale(_ x: AVSpeechSynthesisVoice) -> Bool {
            if x.gender == .male { return true }
            if x.gender == .female { return false }
            let n = x.name.lowercased()
            return n.contains("yuri") || n.contains("юрий") || n.contains("dmitr") || n.contains("дмитр")
        }
        return ru.first { isMale($0) == male } ?? ru.first ?? AVSpeechSynthesisVoice(language: "ru-RU")
    }

    static func utterance(_ text: String, _ v: [String: Any]) -> AVSpeechUtterance {
        let u = AVSpeechUtterance(string: text)
        u.voice = pickVoice(v)
        let pitch = (v["pitch"] as? NSNumber)?.floatValue ?? 1
        let rate = (v["rate"] as? NSNumber)?.floatValue ?? AVSpeechUtteranceDefaultSpeechRate
        u.pitchMultiplier = min(2, max(0.5, pitch))
        u.rate = min(AVSpeechUtteranceMaximumSpeechRate, max(AVSpeechUtteranceMinimumSpeechRate, rate))
        u.preUtteranceDelay = 0
        u.postUtteranceDelay = 0
        return u
    }

    func synthesize(text: String, voice: [String: Any], to url: URL, done: @escaping (Bool) -> Void) {
        DispatchQueue.main.async {
            self.jobs.append((text, voice, url, done))
            self.next()
        }
    }

    /// Состояние одной озвучки (класс, чтобы безопасно менять из колбэка синтезатора).
    private final class Job {
        var file: AVAudioFile?
        var finished = false
        var frames: AVAudioFrameCount = 0
        let lock = NSLock()
    }

    private func next() {
        guard !busy, !jobs.isEmpty else { return }
        busy = true
        let (text, voice, url, done) = jobs.removeFirst()
        try? FileManager.default.removeItem(at: url)
        let job = Job()
        let finish: () -> Void = { [weak self] in
            job.lock.lock()
            if job.finished { job.lock.unlock(); return }
            job.finished = true
            job.file = nil   // закрывает файл
            let ok = job.frames > 0
            job.lock.unlock()
            done(ok)
            self?.busy = false
            self?.next()
        }
        synth.write(Self.utterance(text, voice)) { buf in
            guard let pcm = buf as? AVAudioPCMBuffer else { return }
            if pcm.frameLength == 0 { DispatchQueue.main.async { finish() }; return }
            job.lock.lock()
            defer { job.lock.unlock() }
            if job.finished { return }
            if job.file == nil {
                job.file = try? AVAudioFile(forWriting: url, settings: pcm.format.settings,
                                            commonFormat: pcm.format.commonFormat, interleaved: pcm.format.isInterleaved)
            }
            do { try job.file?.write(from: pcm); job.frames += pcm.frameLength } catch {}
        }
        // запасной выход, если система не прислала последний пустой буфер
        let limit = 6.0 + Double(text.count) * 0.25
        DispatchQueue.main.asyncAfter(deadline: .now() + limit) { finish() }
    }
}

/// Пишет кадры (JPEG) + готовую звуковую дорожку (WAV) в mp4 (H.264 + AAC), звук вплетается по ходу.
final class MultikWriter {
    let out: URL, tmp: URL, w: Int, h: Int, fps: Int32, audio: URL
    var error: String?
    private var writer: AVAssetWriter?
    private var vIn: AVAssetWriterInput?
    private var aIn: AVAssetWriterInput?
    private var adaptor: AVAssetWriterInputPixelBufferAdaptor?
    private var reader: AVAssetReader?
    private var aOut: AVAssetReaderTrackOutput?
    private var pending: CMSampleBuffer?
    private var audioDone = true
    private var frames: Int64 = 0

    init(out: URL, tmp: URL, w: Int, h: Int, fps: Int32, audio: URL) {
        self.out = out; self.tmp = tmp; self.w = w; self.h = h; self.fps = fps; self.audio = audio
    }

    func start() -> Bool {
        try? FileManager.default.removeItem(at: tmp)
        do {
            let wr = try AVAssetWriter(outputURL: tmp, fileType: .mp4)
            let vs: [String: Any] = [
                AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: w, AVVideoHeightKey: h,
                AVVideoCompressionPropertiesKey: [
                    AVVideoAverageBitRateKey: w >= 1920 ? 10_000_000 : 5_000_000,
                    AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
                    AVVideoMaxKeyFrameIntervalKey: Int(fps) * 2,
                ],
            ]
            let v = AVAssetWriterInput(mediaType: .video, outputSettings: vs)
            v.expectsMediaDataInRealTime = false
            let ad = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: v, sourcePixelBufferAttributes: [
                kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
                kCVPixelBufferWidthKey as String: w, kCVPixelBufferHeightKey as String: h,
            ])
            wr.add(v)
            // звук
            let asset = AVURLAsset(url: audio)
            if FileManager.default.fileExists(atPath: audio.path), let track = asset.tracks(withMediaType: .audio).first {
                let rd = try AVAssetReader(asset: asset)
                let o = AVAssetReaderTrackOutput(track: track, outputSettings: [AVFormatIDKey: kAudioFormatLinearPCM])
                rd.add(o)
                let a = AVAssetWriterInput(mediaType: .audio, outputSettings: [
                    AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: 44100, AVNumberOfChannelsKey: 1, AVEncoderBitRateKey: 160_000,
                ])
                a.expectsMediaDataInRealTime = false
                wr.add(a)
                if rd.startReading() { reader = rd; aOut = o; aIn = a; audioDone = false }
            }
            guard wr.startWriting() else { error = wr.error?.localizedDescription ?? "не стартовала запись"; return false }
            wr.startSession(atSourceTime: .zero)
            writer = wr; vIn = v; adaptor = ad
            return true
        } catch {
            self.error = error.localizedDescription
            return false
        }
    }

    private func pumpAudio(until t: Double) {
        guard !audioDone, let a = aIn, let o = aOut else { return }
        while a.isReadyForMoreMediaData {
            let sb = pending ?? o.copyNextSampleBuffer()
            pending = nil
            guard let s = sb else { audioDone = true; a.markAsFinished(); return }
            if CMSampleBufferGetPresentationTimeStamp(s).seconds > t { pending = s; return }
            if !a.append(s) { audioDone = true; return }
        }
    }

    func append(jpeg: Data) -> Bool {
        guard let v = vIn, let ad = adaptor, writer?.status == .writing else { return false }
        let t = Double(frames) / Double(fps)
        pumpAudio(until: t + 1)
        var waited = 0
        while !v.isReadyForMoreMediaData && waited < 4000 { pumpAudio(until: t + 2); usleep(1000); waited += 1 }
        guard let img = UIImage(data: jpeg)?.cgImage, let pool = ad.pixelBufferPool else { return false }
        var pbo: CVPixelBuffer?
        CVPixelBufferPoolCreatePixelBuffer(nil, pool, &pbo)
        guard let pb = pbo else { return false }
        CVPixelBufferLockBaseAddress(pb, [])
        if let ctx = CGContext(data: CVPixelBufferGetBaseAddress(pb), width: w, height: h, bitsPerComponent: 8,
                               bytesPerRow: CVPixelBufferGetBytesPerRow(pb), space: CGColorSpaceCreateDeviceRGB(),
                               bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue) {
            ctx.draw(img, in: CGRect(x: 0, y: 0, width: w, height: h))
        }
        CVPixelBufferUnlockBaseAddress(pb, [])
        let ok = ad.append(pb, withPresentationTime: CMTime(value: frames, timescale: fps))
        frames += 1
        if !ok { error = writer?.error?.localizedDescription }
        return ok
    }

    func finish() -> URL? {
        guard let wr = writer else { return nil }
        let end = Double(frames) / Double(fps)
        vIn?.markAsFinished()
        var n = 0
        while !audioDone && n < 20000 {
            pumpAudio(until: end)
            if let s = pending, CMSampleBufferGetPresentationTimeStamp(s).seconds > end {
                pending = nil; audioDone = true; aIn?.markAsFinished(); break
            }
            if !audioDone { usleep(1000) }
            n += 1
        }
        if !audioDone { audioDone = true; aIn?.markAsFinished() }
        reader?.cancelReading()
        let sem = DispatchSemaphore(value: 0)
        wr.finishWriting { sem.signal() }
        sem.wait()
        guard wr.status == .completed else { error = wr.error?.localizedDescription ?? "запись не завершилась"; return nil }
        try? FileManager.default.removeItem(at: out)
        do { try FileManager.default.moveItem(at: tmp, to: out) } catch { self.error = error.localizedDescription; return nil }
        return out
    }

    func cancel() {
        reader?.cancelReading()
        writer?.cancelWriting()
        try? FileManager.default.removeItem(at: tmp)
    }
}


/// Голосовой ввод описаний персонажа (распознавание русской речи на iPhone).
final class MultikListener {
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "ru-RU"))
    private let engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var text = ""
    private var active = false

    func start(onText: @escaping (String) -> Void, done: @escaping (Bool) -> Void) {
        SFSpeechRecognizer.requestAuthorization { st in
            AVAudioApplication.requestRecordPermission { mic in
                DispatchQueue.main.async {
                    guard st == .authorized, mic, let r = self.recognizer, r.isAvailable else { done(false); return }
                    done(self.begin(r, onText: onText))
                }
            }
        }
    }

    private func begin(_ r: SFSpeechRecognizer, onText: @escaping (String) -> Void) -> Bool {
        _ = stop()
        text = ""
        do {
            let s = AVAudioSession.sharedInstance()
            try s.setCategory(.playAndRecord, mode: .measurement, options: [.defaultToSpeaker, .duckOthers])
            try s.setActive(true, options: .notifyOthersOnDeactivation)
            let req = SFSpeechAudioBufferRecognitionRequest()
            req.shouldReportPartialResults = true
            req.requiresOnDeviceRecognition = false   // для русского офлайн-режим может молчать — разрешаем сервер Apple
            request = req
            let input = engine.inputNode
            let fmt = input.outputFormat(forBus: 0)
            input.removeTap(onBus: 0)
            input.installTap(onBus: 0, bufferSize: 1024, format: fmt) { buf, _ in req.append(buf) }
            engine.prepare()
            active = true
            try engine.start()
            task = r.recognitionTask(with: req) { [weak self] res, err in
                guard let self else { return }
                if let res {
                    let t = res.bestTranscription.formattedString
                    DispatchQueue.main.async { self.text = t; onText(t) }
                } else if let err, self.text.isEmpty {
                    DispatchQueue.main.async { onText("⚠️ Не распознал речь: \(err.localizedDescription)") }
                }
            }
            return true
        } catch {
            _ = stop()
            return false
        }
    }

    func stop() -> String {
        guard active else { return text }
        active = false
        if engine.isRunning { engine.stop() }
        engine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        task?.finish()
        request = nil; task = nil
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)
        return text
    }
}
