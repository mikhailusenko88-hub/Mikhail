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
    var body: some View {
        BazisView(file: file) { dismiss() }
            .ignoresSafeArea()
    }
}
