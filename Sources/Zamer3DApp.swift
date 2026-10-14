import SwiftUI

@main
struct Zamer3DApp: App {
    @State private var bazis: BazisFile?

    var body: some Scene {
        WindowGroup {
            HomeView()
                // .b3d / .fr3d / .zip из Telegram, «Файлов», почты → «Поделиться» → «Замер 3D»
                .onOpenURL { url in bazis = BazisFile.load(url) }
                .fullScreenCover(item: $bazis) { BazisScreen(file: $0) }
        }
    }
}
