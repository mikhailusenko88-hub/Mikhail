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
        case "js", "mjs": mime = "text/javascript"
        case "json": mime = "application/json"
        case "wasm": mime = "application/wasm"   // нейроголос: onnxruntime-web
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

    func makeUIView(context: Context) -> UIView {
        let box = UIView()
        box.backgroundColor = .black
        let web = MultikHost.shared.webView(onClose: onClose)
        web.removeFromSuperview()
        web.alpha = 1
        web.isUserInteractionEnabled = true
        web.translatesAutoresizingMaskIntoConstraints = false
        box.addSubview(web)
        NSLayoutConstraint.activate([
            web.leadingAnchor.constraint(equalTo: box.leadingAnchor), web.trailingAnchor.constraint(equalTo: box.trailingAnchor),
            web.topAnchor.constraint(equalTo: box.topAnchor), web.bottomAnchor.constraint(equalTo: box.bottomAnchor),
        ])
        MultikHost.shared.bridge?.parked = false
        web.evaluateJavaScript("window.MK_PARKED = false", completionHandler: nil)
        return box
    }

    func updateUIView(_ uiView: UIView, context: Context) {}

    static func dismantleUIView(_ uiView: UIView, coordinator: ()) {
        MultikHost.shared.closed()
    }
}

/// Одна страница «Мультиков» на всё приложение. Если закрыть раздел во время сборки серии, страница не выключается:
/// она остаётся крошечной и почти прозрачной в углу окна, и серия собирается дальше, пока вы в других разделах.
final class MultikHost {
    static let shared = MultikHost()
    private(set) var web: WKWebView?
    private(set) var bridge: MultikBridge?

    func webView(onClose: @escaping () -> Void) -> WKWebView {
        if let w = web, let b = bridge { b.onClose = onClose; return w }
        UIApplication.shared.applicationSupportsShakeToEdit = false   // без окна «Undo вставку», если телефон тряхнуло
        let b = MultikBridge(onClose: onClose)
        let cfg = WKWebViewConfiguration()
        cfg.setURLSchemeHandler(BundleScheme(), forURLScheme: "mebel")
        cfg.userContentController.addScriptMessageHandler(b, contentWorld: .page, name: "multik")
        cfg.allowsInlineMediaPlayback = true
        cfg.mediaTypesRequiringUserActionForPlayback = []
        let w = WKWebView(frame: .zero, configuration: cfg)
        w.isOpaque = false
        w.backgroundColor = .black
        w.uiDelegate = b   // alert / confirm со страницы
        w.navigationDelegate = b
        b.web = w
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)
        w.load(URLRequest(url: URL(string: "mebel://app/multik.html")!))
        web = w; bridge = b
        return w
    }

    /// Раздел «Мультики» закрыт: идёт сборка — страницу держим живой, иначе выключаем.
    func closed() {
        guard let w = web, let b = bridge else { return }
        if b.isBuilding {
            let win = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.flatMap { $0.windows }.first { $0.isKeyWindow }
            if let win = win {
                w.removeFromSuperview()
                w.translatesAutoresizingMaskIntoConstraints = true
                w.frame = win.bounds
                w.autoresizingMask = [.flexibleWidth, .flexibleHeight]
                w.alpha = 0.02   // совсем невидимую (0) iPhone мог бы усыпить
                w.isUserInteractionEnabled = false
                win.insertSubview(w, at: 0)   // под всеми экранами приложения — её не видно и она не мешает нажатиям
                b.parked = true
                w.evaluateJavaScript("window.MK_PARKED = true", completionHandler: nil)
                return
            }
        }
        w.configuration.userContentController.removeScriptMessageHandler(forName: "multik", contentWorld: .page)
        b.cleanup()
        MultikVoiceHost.shared.close()
        w.removeFromSuperview()
        web = nil; bridge = nil
    }
}

/// Нейроголос рассказчика в отдельной скрытой странице voice.html. У каждой WKWebView свой процесс iPhone:
/// модели и onnxruntime (~0.5 ГБ) не считаются в памяти «Мультиков», а после озвучки страницу закрываем —
/// процесс завершается, и память возвращается сразу (в той же странице она оставалась занятой до уборки мусора).
final class MultikVoiceHost: NSObject, WKNavigationDelegate {
    static let shared = MultikVoiceHost()
    private var web: WKWebView?
    private var ready = false
    private var waiters: [(Bool) -> Void] = []

    private func open(_ done: @escaping (Bool) -> Void) {
        if web != nil && ready { done(true); return }
        waiters.append(done)
        if web != nil { return }
        let cfg = WKWebViewConfiguration()
        cfg.setURLSchemeHandler(BundleScheme(), forURLScheme: "mebel")
        let w = WKWebView(frame: CGRect(x: 0, y: 0, width: 4, height: 4), configuration: cfg)
        w.navigationDelegate = self
        w.alpha = 0.02                      // совсем невидимую (0) iPhone мог бы усыпить
        w.isUserInteractionEnabled = false
        let win = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.flatMap { $0.windows }.first { $0.isKeyWindow }
        win?.insertSubview(w, at: 0)        // под всеми экранами — не видна и не мешает нажатиям
        web = w
        w.load(URLRequest(url: URL(string: "mebel://app/voice.html")!))
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard webView === web else { return }
        ready = true
        let ws = waiters; waiters = []; ws.forEach { $0(true) }
    }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { failed(webView) }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { failed(webView) }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { failed(webView) }
    private func failed(_ webView: WKWebView) {
        guard webView === web else { return }
        let ws = waiters; waiters = []
        close()
        ws.forEach { $0(false) }
    }

    /// body: {text, opts} → {pcm: base64 16 бит 48 кГц, n, last: текст с ударениями} или {error}
    func speak(_ body: [String: Any], reply: @escaping (Any?, String?) -> Void) {
        open { ok in
            guard ok, let w = self.web else { reply(["error": "страница голоса не загрузилась"], nil); return }
            let js = """
            const y = await MKVoice.speak(text, opts);
            const n = y.length, b = new Uint8Array(n * 2);
            for (let i = 0; i < n; i++) { let v = Math.max(-1, Math.min(1, y[i])); v = Math.round(v < 0 ? v * 32768 : v * 32767); b[2 * i] = v & 255; b[2 * i + 1] = (v >> 8) & 255; }
            let s = ''; for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode.apply(null, b.subarray(i, i + 32768));
            return { pcm: btoa(s), n: n, last: MKVoice.lastText || '' };
            """
            let args: [String: Any] = ["text": body["text"] as? String ?? "", "opts": body["opts"] as? [String: Any] ?? [:]]
            w.callAsyncJavaScript(js, arguments: args, in: nil, in: .page) { r in
                switch r {
                case .success(let v): reply(v, nil)
                case .failure(let e): reply(["error": e.localizedDescription], nil)
                }
            }
        }
    }

    func close() {
        ready = false
        if let w = web { w.stopLoading(); w.navigationDelegate = nil; w.removeFromSuperview() }
        web = nil
    }
}

/// Мост страница ↔ iPhone. Каждый вызов из JS возвращает Promise (ответ через replyHandler).
final class MultikBridge: NSObject, WKScriptMessageHandlerWithReply, UIDocumentPickerDelegate, WKUIDelegate, WKNavigationDelegate {
    var onClose: () -> Void
    var parked = false
    var busy = false   // страница собирает серии (очередь), в том числе озвучку перед кадрами
    var stage = ""     // что страница сейчас делает («Просмотр серии 10: готовлю сцены…») — пишем в crash.json, если она оборвётся
    var isBuilding: Bool { busy || writer != nil }
    weak var web: WKWebView?
    private let tts = MultikTTS()
    private let speaker = AVSpeechSynthesizer()
    private let listener = MultikListener()
    private let recorder = MultikRecorder()
    private var writer: MultikWriter?
    private let queue = DispatchQueue(label: "multik.writer", qos: .userInitiated)
    private var pickReply: ((Any?, String?) -> Void)?

    init(onClose: @escaping () -> Void) {
        self.onClose = onClose
        super.init()
        // приложение уходит с экрана (свернули, заблокировали, звонок): дописываем текущий кусок видео,
        // иначе iPhone оборвёт кодирование. Вернётесь — сборка продолжится с того же кадра.
        NotificationCenter.default.addObserver(forName: UIApplication.willResignActiveNotification, object: nil, queue: .main) { [weak self] _ in
            self?.pauseWriter()
        }
    }

    private func pauseWriter() {
        guard let w = writer else { return }
        var bg = UIBackgroundTaskIdentifier.invalid
        bg = UIApplication.shared.beginBackgroundTask(withName: "multik-pause") {
            if bg != .invalid { UIApplication.shared.endBackgroundTask(bg); bg = .invalid }
        }
        queue.async {
            w.pause()
            DispatchQueue.main.async { if bg != .invalid { UIApplication.shared.endBackgroundTask(bg); bg = .invalid } }
        }
    }

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
        case "recStart":
            let key = (body["key"] as? String ?? "rec").replacingOccurrences(of: "/", with: "_")
            recorder.start(url: root.appendingPathComponent("voice/\(key).wav")) { ok in replyHandler(ok, nil) }
        case "recStop":
            recorder.stop()
            replyHandler(true, nil)
        case "recLoad":
            let key = (body["key"] as? String ?? "rec").replacingOccurrences(of: "/", with: "_")
            if let d = try? Data(contentsOf: root.appendingPathComponent("voice/\(key).wav")), d.count > 2000 {
                replyHandler(["wav": d.base64EncodedString()], nil)
            } else { replyHandler(NSNull(), nil) }
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
        case "ttsServer":   // голос рассказчика со своего сервера (нейроголос «Альбина»); нет связи — пустой ответ, страница возьмёт голос iPhone
            let key = (body["key"] as? String ?? UUID().uuidString).replacingOccurrences(of: "/", with: "_")
            let file = root.appendingPathComponent("voice/\(key).wav")
            if let d = try? Data(contentsOf: file), d.count > 2000 {
                replyHandler(["wav": d.base64EncodedString(), "cached": true], nil); return
            }
            guard let s = body["url"] as? String, let url = URL(string: s) else { replyHandler(NSNull(), nil); return }
            var req = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: (body["timeout"] as? Double) ?? 45)
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try? JSONSerialization.data(withJSONObject: body["payload"] as? [String: Any] ?? [:])
            URLSession.shared.dataTask(with: req) { data, resp, _ in
                let ok = ((resp as? HTTPURLResponse)?.statusCode ?? 0) == 200
                DispatchQueue.main.async {
                    if ok, let d = data, d.count > 2000 {
                        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
                        try? d.write(to: file)
                        replyHandler(["wav": d.base64EncodedString()], nil)
                    } else { replyHandler(NSNull(), nil) }
                }
            }.resume()
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
            let resume = body["resume"] as? Bool ?? false
            UIApplication.shared.isIdleTimerDisabled = true
            if let old = writer { writer = nil; queue.async { old.pause() } }
            queue.async {
                let wr = MultikWriter(out: out, dir: root.appendingPathComponent("tmp/build"), w: w, h: h, fps: Int32(fps), audio: audio)
                let ok = wr.start(resume: resume)
                let done = Int(wr.frames)
                DispatchQueue.main.async {
                    self.writer = ok ? wr : nil
                    if ok { replyHandler(["ok": true, "frames": done], nil) } else { replyHandler(false, wr.error) }
                }
            }
        case "videoFrame":
            guard let wr = writer, let s = body["d"] as? String else { replyHandler(false, "нет записи"); return }
            let index = Int64((body["i"] as? NSNumber)?.intValue ?? -1)
            queue.async {
                // ответ: 1…4 — кадр записан, число — нагрев телефона (1 норма … 4 критично); 0 — не записан;
                // −(N+1) — «продолжайте с кадра N» (после паузы кусок мог оборваться)
                var reply = 0
                if let d = Data(base64Encoded: s) {
                    let r = wr.append(jpeg: d, index: index)
                    if r == -1 { reply = ProcessInfo.processInfo.thermalState.rawValue + 1 } else if r >= 0 { reply = -Int(r) - 1 }
                }
                DispatchQueue.main.async { replyHandler(reply, nil) }
            }
        case "remuxAudio":   // готовая серия: заменить звук (картинка копируется как есть, за секунды)
            let rel = body["path"] as? String ?? ""
            let src = root.appendingPathComponent(rel), audio = root.appendingPathComponent("tmp/audio.wav"), tmp = root.appendingPathComponent("tmp/remux.mp4")
            queue.async {
                var err: String? = FileManager.default.fileExists(atPath: src.path) ? nil : "нет файла серии"
                if err == nil { err = MultikWriter.mux(parts: [src], total: AVURLAsset(url: src).duration, audio: audio, out: tmp) }
                if err == nil { try? FileManager.default.removeItem(at: src); do { try FileManager.default.moveItem(at: tmp, to: src) } catch { err = error.localizedDescription } }
                DispatchQueue.main.async { if let e = err { replyHandler(["error": e], nil) } else { replyHandler(["path": rel], nil) } }
            }
        case "thermal":
            replyHandler(ProcessInfo.processInfo.thermalState.rawValue, nil)
        case "videoEnd":
            guard let wr = writer else { replyHandler(["error": "нет записи"], nil); return }
            writer = nil
            queue.async {
                let path = wr.finish()
                DispatchQueue.main.async {
                    if let p = path { var r: [String: Any] = ["path": "video/" + p.lastPathComponent]; if let w = wr.warn { r["warn"] = w }; replyHandler(r, nil) }
                    else { replyHandler(["error": wr.error ?? "ошибка записи"], nil) }
                }
            }
        case "videoCancel":
            if body["keep"] as? Bool == true, let w = writer {   // ошибка: готовые куски оставляем, чтобы продолжить потом
                writer = nil
                queue.async { w.pause() }
            } else if writer != nil { cleanup() } else {
                let dir = root.appendingPathComponent("tmp/build")
                queue.async { try? FileManager.default.removeItem(at: dir) }
            }
            replyHandler(true, nil)
        case "removeFile":   // удалённая серия: стереть её видео (только внутри папки мультиков)
            if let p = body["path"] as? String {
                let url = p.hasPrefix("/") ? URL(fileURLWithPath: p) : root.appendingPathComponent(p)
                if url.standardizedFileURL.path.hasPrefix(root.standardizedFileURL.path) { try? FileManager.default.removeItem(at: url) }
            }
            replyHandler(true, nil)
        case "keepAwake":   // очередь серий: экран не гаснет и между сериями, страница не выключается при закрытии раздела
            busy = body["on"] as? Bool ?? false
            UIApplication.shared.isIdleTimerDisabled = busy
            replyHandler(true, nil)
        case "voiceSpeak":   // нейроголос рассказчика — в отдельной скрытой странице (свой процесс iPhone)
            MultikVoiceHost.shared.speak(body, reply: replyHandler)
        case "voiceUnload":  // озвучка закончена — закрываем страницу голоса, iPhone сразу забирает её память
            MultikVoiceHost.shared.close()
            replyHandler(true, nil)
        case "stage":   // этап работы страницы (для сообщения после обрыва)
            stage = body["text"] as? String ?? ""
            replyHandler(true, nil)
        case "crashInfo":   // страница перезапускалась посреди сборки? (один раз, потом стираем)
            let u = root.appendingPathComponent("tmp/crash.json")
            if let d = try? Data(contentsOf: u), let j = try? JSONSerialization.jsonObject(with: d) { try? FileManager.default.removeItem(at: u); replyHandler(j, nil) }
            else { replyHandler(NSNull(), nil) }
        case "parked":   // страница спрятана (раздел закрыт, сборка идёт)
            replyHandler(parked, nil)
        case "buildDone":   // очередь серий закончилась: если раздел закрыт — выключаем спрятанную страницу
            replyHandler(true, nil)
            if parked { DispatchQueue.main.async { MultikHost.shared.closed() } }
        case "close":
            if !isBuilding { cleanup() }   // во время сборки страница остаётся работать
            replyHandler(true, nil)
            speaker.stopSpeaking(at: .immediate)
            onClose()
        default:
            replyHandler(NSNull(), nil)
        }
    }

    // iPhone выгрузил страницу из памяти: готовые куски видео сохраняем; раздел открыт — перезагружаем
    // (страница сама предложит продолжить сборку), закрыт — выключаем, продолжится при следующем открытии
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        // запомнить, где и как оборвалось: страница после перезапуска продолжит сама, а при повторах — сообщит
        let info: [String: Any] = ["frame": Int(writer?.frames ?? -1), "bg": UIApplication.shared.applicationState != .active,
                                   "building": isBuilding, "stage": stage, "at": Date().timeIntervalSince1970]
        stage = ""
        if let d = try? JSONSerialization.data(withJSONObject: info) { try? d.write(to: Self.root.appendingPathComponent("tmp/crash.json")) }
        if let w = writer { writer = nil; queue.async { w.pause() } }
        busy = false
        UIApplication.shared.isIdleTimerDisabled = false
        if parked { MultikHost.shared.closed() } else { webView.reload() }
    }

    // окна alert / confirm / prompt со страницы (без этого WKWebView их молча пропускает)
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
        guard let top = Self.top() else { completionHandler(); return }
        top.present(a, animated: true)
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        a.addAction(UIAlertAction(title: "Отмена", style: .cancel) { _ in completionHandler(false) })
        a.addAction(UIAlertAction(title: "Да", style: .default) { _ in completionHandler(true) })
        guard let top = Self.top() else { completionHandler(false); return }
        top.present(a, animated: true)
    }

    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let a = UIAlertController(title: nil, message: prompt, preferredStyle: .alert)
        a.addTextField { $0.text = defaultText }
        a.addAction(UIAlertAction(title: "Отмена", style: .cancel) { _ in completionHandler(nil) })
        a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(a.textFields?.first?.text) })
        guard let top = Self.top() else { completionHandler(nil); return }
        top.present(a, animated: true)
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
/// Запись своего смеха (или любого возгласа) для героя — через микрофон iPhone.
final class MultikRecorder: NSObject {
    private var rec: AVAudioRecorder?

    func start(url: URL, done: @escaping (Bool) -> Void) {
        AVAudioApplication.requestRecordPermission { granted in
            DispatchQueue.main.async {
                guard granted else { done(false); return }
                let s = AVAudioSession.sharedInstance()
                try? s.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker])
                try? s.setActive(true)
                try? FileManager.default.removeItem(at: url)
                let settings: [String: Any] = [AVFormatIDKey: Int(kAudioFormatLinearPCM), AVSampleRateKey: 44100.0,
                                               AVNumberOfChannelsKey: 1, AVLinearPCMBitDepthKey: 16,
                                               AVLinearPCMIsFloatKey: false, AVLinearPCMIsBigEndianKey: false]
                self.rec = try? AVAudioRecorder(url: url, settings: settings)
                done(self.rec?.record(forDuration: 8) ?? false)
            }
        }
    }

    func stop() {
        rec?.stop()
        rec = nil
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default, options: [])
    }
}

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
        // ударения: для слов с известным ударением передаём произношение (IPA) — iPhone читает именно так
        let u: AVSpeechUtterance
        if let spans = v["ipa"] as? [[Any]], !spans.isEmpty {
            let a = NSMutableAttributedString(string: text)
            let len = (text as NSString).length
            for s in spans where s.count == 3 {
                guard let st = (s[0] as? NSNumber)?.intValue, let ln = (s[1] as? NSNumber)?.intValue, let ipa = s[2] as? String,
                      st >= 0, ln > 0, st + ln <= len else { continue }
                a.addAttribute(NSAttributedString.Key(rawValue: AVSpeechSynthesisIPANotationAttribute), value: ipa, range: NSRange(location: st, length: ln))
            }
            u = AVSpeechUtterance(attributedString: a)
        } else {
            u = AVSpeechUtterance(string: text)
        }
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
/// Запись серии кусками. Если iPhone прервёт кодирование (приложение свернули, заблокировали, звонок),
/// готовые куски остаются на диске, а страница продолжает с того же кадра — даже после перезапуска приложения.
/// В конце куски и звук склеиваются в один mp4 без перекодирования видео.
final class MultikWriter {
    let out: URL, dir: URL, w: Int, h: Int, fps: Int32, audio: URL
    var error: String?
    private var seg: MultikSegment?
    private var done: [Int64] = []        // кадров в каждом готовом куске
    private(set) var frames: Int64 = 0    // всего кадров (готовые куски + текущий)

    init(out: URL, dir: URL, w: Int, h: Int, fps: Int32, audio: URL) {
        self.out = out; self.dir = dir; self.w = w; self.h = h; self.fps = fps; self.audio = audio
    }

    private var listURL: URL { dir.appendingPathComponent("segs.json") }
    private func segURL(_ k: Int) -> URL { dir.appendingPathComponent(String(format: "seg_%03d.mp4", k)) }
    private var doneFrames: Int64 { done.reduce(0, +) }

    func start(resume: Bool) -> Bool {
        let fm = FileManager.default
        if !resume { try? fm.removeItem(at: dir) }
        try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
        done = []
        if resume, let d = try? Data(contentsOf: listURL), let a = try? JSONDecoder().decode([Int64].self, from: d) { done = a }
        // оборванные и лишние куски — удалить
        if let files = try? fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil) {
            for f in files where f.lastPathComponent.hasPrefix("seg_") {
                let k = Int(f.deletingPathExtension().lastPathComponent.dropFirst(4)) ?? -1
                if k < 0 || k >= done.count { try? fm.removeItem(at: f) }
            }
        }
        frames = doneFrames
        return true
    }

    private func save() { if let d = try? JSONEncoder().encode(done) { try? d.write(to: listURL) } }

    /// Кадр номер i. Ответ: −1 — записан; −2 — ошибка; N ≥ 0 — «продолжайте с кадра N».
    func append(jpeg: Data, index i: Int64) -> Int64 {
        if i != frames { return frames }
        if seg == nil {
            let s = MultikSegment(url: segURL(done.count), w: w, h: h, fps: fps)
            guard s.start() else { error = s.error; return -2 }
            seg = s
        }
        guard let s = seg else { return -2 }
        if s.append(jpeg: jpeg) {
            frames += 1
            if s.count >= Int64(fps) * 30 { pause() }   // куски по 30 с: при сбое теряется не больше
            return -1
        }
        // кусок оборвался — выбрасываем его, страница перерисует эти кадры
        s.cancel(); seg = nil; frames = doneFrames
        return frames
    }

    /// Дописать текущий кусок (приложение уходит с экрана или конец сборки).
    func pause() {
        guard let s = seg else { return }
        seg = nil
        if s.count == 0 { s.cancel(); return }
        if s.finish() { done.append(s.count); save() } else { s.cancel() }
        frames = doneFrames
    }

    /// Готовое видео: куски подряд (без перекодирования) + звук из wav (AAC). Звук не записался — видео всё равно
    /// отдаём, но с предупреждением (warn), чтобы не потерять сборку; звук потом можно наложить заново.
    var warn: String?
    func finish() -> URL? {
        pause()
        guard !done.isEmpty else { error = error ?? "нет кадров"; return nil }
        let parts = (0..<done.count).map { segURL($0) }, total = CMTime(value: doneFrames, timescale: fps)
        let tmp = dir.appendingPathComponent("final.mp4")
        if let e = MultikWriter.mux(parts: parts, total: total, audio: audio, out: tmp) {
            // со звуком не вышло — пробуем без него
            guard MultikWriter.mux(parts: parts, total: total, audio: nil, out: tmp) == nil else { error = e; return nil }
            warn = e
        }
        try? FileManager.default.removeItem(at: out)
        do { try FileManager.default.moveItem(at: tmp, to: out) } catch { self.error = error.localizedDescription; return nil }
        try? FileManager.default.removeItem(at: dir)
        return out
    }

    /// Склейка mp4: видеокадры копируются как есть (куски один за другим), звук кодируется из wav в AAC 160 кбит/с.
    /// Возвращает текст ошибки или nil.
    static func mux(parts: [URL], total: CMTime, audio: URL?, out: URL) -> String? {
        let fm = FileManager.default
        try? fm.removeItem(at: out)
        guard let first = parts.first, let fv = AVURLAsset(url: first).tracks(withMediaType: .video).first,
              let fd = fv.formatDescriptions.first else { return "нет видео" }
        let wr: AVAssetWriter
        do { wr = try AVAssetWriter(outputURL: out, fileType: .mp4) } catch { return error.localizedDescription }
        let vIn = AVAssetWriterInput(mediaType: .video, outputSettings: nil, sourceFormatHint: (fd as! CMFormatDescription))
        vIn.expectsMediaDataInRealTime = false
        wr.add(vIn)
        var aIn: AVAssetWriterInput?, aOut: AVAssetReaderTrackOutput?, aRd: AVAssetReader?
        if let au = audio {
            guard fm.fileExists(atPath: au.path) else { return "нет файла звука" }
            let asset = AVURLAsset(url: au)
            guard let track = asset.tracks(withMediaType: .audio).first, let rd = try? AVAssetReader(asset: asset) else { return "файл звука не читается" }
            let o = AVAssetReaderTrackOutput(track: track, outputSettings: [AVFormatIDKey: kAudioFormatLinearPCM])
            rd.add(o)
            let a = AVAssetWriterInput(mediaType: .audio, outputSettings: [
                AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: 44100, AVNumberOfChannelsKey: 1, AVEncoderBitRateKey: 160_000,
            ])
            a.expectsMediaDataInRealTime = false
            wr.add(a)
            guard rd.startReading() else { return rd.error?.localizedDescription ?? "звук не читается" }
            aIn = a; aOut = o; aRd = rd
        }
        guard wr.startWriting() else { return wr.error?.localizedDescription ?? "запись не началась" }
        wr.startSession(atSourceTime: .zero)
        var k = 0, offset = CMTime.zero, vRd: AVAssetReader?, vOut: AVAssetReaderTrackOutput?, vDone = false, aDone = aIn == nil, idle = 0
        while !(vDone && aDone) {
            var moved = false
            // видео: следующий кусок, кадры со сдвигом времени
            while !vDone && vIn.isReadyForMoreMediaData {
                if vOut == nil {
                    if k >= parts.count { vDone = true; vIn.markAsFinished(); break }
                    let asset = AVURLAsset(url: parts[k])
                    guard let t = asset.tracks(withMediaType: .video).first, let rd = try? AVAssetReader(asset: asset) else { k += 1; continue }
                    let o = AVAssetReaderTrackOutput(track: t, outputSettings: nil); o.alwaysCopiesSampleData = false; rd.add(o)
                    guard rd.startReading() else { k += 1; continue }
                    vRd = rd; vOut = o
                    if k > 0 { offset = CMTimeAdd(offset, CMTimeMinimum(AVURLAsset(url: parts[k - 1]).duration, total)) }
                    k += 1
                }
                guard let sb = vOut?.copyNextSampleBuffer() else { vRd?.cancelReading(); vRd = nil; vOut = nil; continue }
                guard let rs = retimed(sb, by: offset) else { continue }
                if !vIn.append(rs) { return wr.error?.localizedDescription ?? "видео не склеилось" }
                moved = true
            }
            // звук: до конца видео
            while !aDone, let a = aIn, a.isReadyForMoreMediaData {
                guard let sb = aOut?.copyNextSampleBuffer() else { aDone = true; a.markAsFinished(); break }
                if CMTimeCompare(CMSampleBufferGetPresentationTimeStamp(sb), total) >= 0 { aDone = true; a.markAsFinished(); aRd?.cancelReading(); break }
                if !a.append(sb) { return wr.error?.localizedDescription ?? "звук не записался" }
                moved = true
            }
            if moved { idle = 0 } else { usleep(2000); idle += 1; if idle > 15000 { wr.cancelWriting(); return "склейка зависла" } }
        }
        let sem = DispatchSemaphore(value: 0)
        wr.finishWriting { sem.signal() }
        sem.wait()
        return wr.status == .completed ? nil : (wr.error?.localizedDescription ?? "склейка не удалась")
    }

    private static func retimed(_ sb: CMSampleBuffer, by off: CMTime) -> CMSampleBuffer? {
        if off == .zero { return sb }
        var n: CMItemCount = 0
        CMSampleBufferGetSampleTimingInfoArray(sb, entryCount: 0, arrayToFill: nil, entriesNeededOut: &n)
        var info = [CMSampleTimingInfo](repeating: CMSampleTimingInfo(), count: max(1, n))
        CMSampleBufferGetSampleTimingInfoArray(sb, entryCount: n, arrayToFill: &info, entriesNeededOut: &n)
        for i in 0..<n {
            info[i].presentationTimeStamp = CMTimeAdd(info[i].presentationTimeStamp, off)
            if info[i].decodeTimeStamp.isValid { info[i].decodeTimeStamp = CMTimeAdd(info[i].decodeTimeStamp, off) }
        }
        var outSB: CMSampleBuffer?
        CMSampleBufferCreateCopyWithNewTiming(allocator: nil, sampleBuffer: sb, sampleTimingEntryCount: n, sampleTimingArray: &info, sampleBufferOut: &outSB)
        return outSB
    }

    func cancel() {
        seg?.cancel(); seg = nil
        try? FileManager.default.removeItem(at: dir)
    }
}

/// Один кусок видео (без звука): кадры JPEG → H.264.
final class MultikSegment {
    let url: URL, w: Int, h: Int, fps: Int32
    var error: String?
    private(set) var count: Int64 = 0
    private var writer: AVAssetWriter?
    private var vIn: AVAssetWriterInput?
    private var adaptor: AVAssetWriterInputPixelBufferAdaptor?

    init(url: URL, w: Int, h: Int, fps: Int32) { self.url = url; self.w = w; self.h = h; self.fps = fps }

    func start() -> Bool {
        try? FileManager.default.removeItem(at: url)
        do {
            let wr = try AVAssetWriter(outputURL: url, fileType: .mp4)
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
            guard wr.startWriting() else { error = wr.error?.localizedDescription ?? "не стартовала запись"; return false }
            wr.startSession(atSourceTime: .zero)
            writer = wr; vIn = v; adaptor = ad
            return true
        } catch {
            self.error = error.localizedDescription
            return false
        }
    }

    func append(jpeg: Data) -> Bool {
        guard let v = vIn, let ad = adaptor, writer?.status == .writing else { return false }
        var waited = 0
        while !v.isReadyForMoreMediaData && waited < 4000 { usleep(1000); waited += 1 }
        guard v.isReadyForMoreMediaData, let img = UIImage(data: jpeg)?.cgImage, let pool = ad.pixelBufferPool else { return false }
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
        let ok = ad.append(pb, withPresentationTime: CMTime(value: count, timescale: fps))
        if ok { count += 1 } else { error = writer?.error?.localizedDescription }
        return ok
    }

    func finish() -> Bool {
        guard let wr = writer, wr.status == .writing else { return false }
        vIn?.markAsFinished()
        let sem = DispatchSemaphore(value: 0)
        wr.finishWriting { sem.signal() }
        sem.wait()
        writer = nil
        return wr.status == .completed
    }

    func cancel() {
        writer?.cancelWriting(); writer = nil
        try? FileManager.default.removeItem(at: url)
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
