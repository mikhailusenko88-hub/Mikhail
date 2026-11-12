import SwiftUI

@main
struct Zamer3DApp: App {
    @State private var bazis: BazisFile?
    @State private var assistant = false

    var body: some Scene {
        WindowGroup {
            HomeView()
                // .b3d / .fr3d / .zip с Базисом из Telegram, «Файлов», почты → «Поделиться» → «Замер 3D» — раздел «Мебель»
                // .navyk — обновление навыков Помощника: спросит «Обновить?», прочитает и скажет, что понял
                // любой другой файл — Помощнику: откроет и ответит, что в нём
                .onOpenURL { url in
                    let ext = url.pathExtension.lowercased()
                    if ext == "navyk" {
                        AssistantBrain.shared.offerSkillFile(url)
                        assistant = true
                    } else if ["b3d", "fr3d"].contains(ext) || (ext == "zip" && Files.isBazisZip(url)) {
                        bazis = BazisFile.load(url)
                    } else if let ref = Files.importCopy(url) {
                        AssistantBrain.shared.incoming = ref
                        assistant = true
                    }
                }
                .fullScreenCover(item: $bazis) { BazisScreen(file: $0) }
                .fullScreenCover(isPresented: $assistant) { AssistantScreen() }
        }
    }
}
