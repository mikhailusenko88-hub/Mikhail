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
                    Section("Скан комнаты") {
                        if scans.isEmpty {
                            Text("Пока нет сохранённых сканов. Сначала сделай замер и нажми «Сохранить».")
                                .foregroundColor(.secondary)
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
            case "save": save(body["project"])
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
            let named = dir.appendingPathComponent("\(parent.name).json")
            let file = FileManager.default.fileExists(atPath: named.path) ? named
                     : dir.appendingPathComponent(FittingModel.kitchenFile)
            if let data = try? Data(contentsOf: file),
               let proj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let mods = proj["modules"] { payload["modules"] = mods }
            guard let json = try? JSONSerialization.data(withJSONObject: payload),
                  let s = String(data: json, encoding: .utf8) else { return }
            web?.evaluateJavaScript("Mebel.load(\(s))")
        }

        private func save(_ project: Any?) {
            guard let project = project,
                  let data = try? JSONSerialization.data(withJSONObject: project, options: [.prettyPrinted, .sortedKeys]),
                  (try? JSONDecoder().decode(Kitchen.self, from: data)) != nil else {
                web?.evaluateJavaScript("Mebel.saved('Не удалось сохранить')")
                return
            }
            do {
                try data.write(to: dir.appendingPathComponent("\(parent.name).json"))
                try data.write(to: dir.appendingPathComponent(FittingModel.kitchenFile))   // для примерки
                web?.evaluateJavaScript("Mebel.saved('Сохранено: \(parent.name).json')")
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
