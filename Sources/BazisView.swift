import SwiftUI
import WebKit
import UniformTypeIdentifiers

/// Файл Базис-Мебельщика (.b3d / .fr3d, можно в .zip) для просмотра.
struct BazisFile: Identifiable {
    let id = UUID()
    let name: String
    let data: Data

    static let types: [UTType] = [UTType("ru.usenko.zamer3d.bazis"), .zip, .data].compactMap { $0 }

    static func load(_ url: URL) -> BazisFile? {
        let ok = url.startAccessingSecurityScopedResource()
        defer { if ok { url.stopAccessingSecurityScopedResource() } }
        var data: Data?
        var err: NSError?
        NSFileCoordinator().coordinate(readingItemAt: url, options: [], error: &err) { u in
            data = try? Data(contentsOf: u)
        }
        guard let d = data ?? (try? Data(contentsOf: url)) else { return nil }
        return BazisFile(name: url.lastPathComponent, data: d)
    }
}

/// Просмотр: 3D, список деталей (позиция, название, материал, размеры, толщина, кромка), фурнитура.
struct BazisView: UIViewRepresentable {
    let file: BazisFile
    let onClose: () -> Void
    var onMebel: (([String: Any]) -> Void)? = nil

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.setURLSchemeHandler(BundleScheme(), forURLScheme: "mebel")
        cfg.userContentController.add(context.coordinator, name: "bazis")
        let web = WKWebView(frame: .zero, configuration: cfg)
        web.isOpaque = false
        web.backgroundColor = .black
        web.scrollView.isScrollEnabled = false
        context.coordinator.web = web
        web.load(URLRequest(url: URL(string: "mebel://app/bazis.html")!))
        return web
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) {
        uiView.configuration.userContentController.removeScriptMessageHandler(forName: "bazis")
    }

    final class Coordinator: NSObject, WKScriptMessageHandler {
        let parent: BazisView
        weak var web: WKWebView?
        init(_ p: BazisView) { parent = p }

        func userContentController(_ c: WKUserContentController, didReceive message: WKScriptMessage) {
            guard let body = message.body as? [String: Any], let type = body["type"] as? String else { return }
            if type == "close" { parent.onClose(); return }
            if type == "toMebel", let p = body["project"] as? [String: Any] { parent.onMebel?(p); return }
            guard type == "ready",
                  let nameJSON = try? JSONEncoder().encode(parent.file.name),
                  let name = String(data: nameJSON, encoding: .utf8) else { return }
            web?.evaluateJavaScript("Bazis.open(\(name), '\(parent.file.data.base64EncodedString())')")
        }
    }
}

struct BazisScreen: View {
    let file: BazisFile
    @Environment(\.dismiss) private var dismiss
    @State private var target: MebelTarget?
    var body: some View {
        BazisView(file: file, onClose: { dismiss() }, onMebel: { target = MebelTarget.make(from: $0) })
            .ignoresSafeArea()
            .fullScreenCover(item: $target) { t in
                MebelWeb(scan: t.folder, name: t.kind) { target = nil }
                    .ignoresSafeArea()
            }
    }
}

/// Проект из Базиса для конструктора: своя папка «Базис · <название>» в документах,
/// стены из файла → info.json (как у скана RoomPlan), модули → <Тип>.json и kitchen.json.
struct MebelTarget: Identifiable {
    let id = UUID()
    let folder: String
    let kind: String

    static func kindFor(_ title: String) -> String {
        let t = title.lowercased()
        for k in MebelView.kinds where t.contains(k.lowercased()) { return k }
        return "Другое"
    }

    static func make(from project: [String: Any]) -> MebelTarget? {
        let title = (project["name"] as? String) ?? "Мебель"
        let safe = title.replacingOccurrences(of: "/", with: "-").replacingOccurrences(of: ":", with: " ")
        let folder = "Базис · \(safe)"
        let k = Self.kindFor(title)
        let dir = FittingModel.docs.appendingPathComponent(folder)
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            let info: [String: Any] = ["roomPlan": project["walls"] ?? []]
            try JSONSerialization.data(withJSONObject: info, options: [.prettyPrinted]).write(to: dir.appendingPathComponent("info.json"))
            let proj: [String: Any] = ["name": k, "modules": project["modules"] ?? []]
            let data = try JSONSerialization.data(withJSONObject: proj, options: [.prettyPrinted, .sortedKeys])
            try data.write(to: dir.appendingPathComponent("\(k).json"))
            try data.write(to: dir.appendingPathComponent(FittingModel.kitchenFile))
        } catch { return nil }
        return MebelTarget(folder: folder, kind: k)
    }
}
