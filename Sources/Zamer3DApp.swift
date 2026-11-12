import SwiftUI

@main
struct Zamer3DApp: App {
    @State private var bazis: BazisFile?
    @State private var skills = false

    var body: some Scene {
        WindowGroup {
            HomeView()
                // .b3d / .fr3d / .zip из Telegram, «Файлов», почты → «Поделиться» → «Замер 3D»
                // .navyk — обновление навыков Помощника: спросит «Обновить?», прочитает и скажет, что понял
                .onOpenURL { url in
                    if url.pathExtension.lowercased() == "navyk" {
                        AssistantBrain.shared.offerSkillFile(url)
                        skills = true
                    } else {
                        bazis = BazisFile.load(url)
                    }
                }
                .fullScreenCover(item: $bazis) { BazisScreen(file: $0) }
                .fullScreenCover(isPresented: $skills) { AssistantScreen() }
        }
    }
}
