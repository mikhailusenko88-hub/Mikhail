import SwiftUI
import WebKit
import UniformTypeIdentifiers

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
