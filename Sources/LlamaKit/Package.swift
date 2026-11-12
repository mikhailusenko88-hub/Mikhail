// swift-tools-version:5.9
// llama.cpp для «Помощника»: готовая сборка под iPhone (Metal), MIT. Версию менять вместе с checksum.
import PackageDescription

let package = Package(
    name: "LlamaKit",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [.library(name: "LlamaKit", targets: ["llama"])],
    targets: [
        .binaryTarget(
            name: "llama",
            url: "https://github.com/ggml-org/llama.cpp/releases/download/b12317/llama-b12317-xcframework.zip",
            checksum: "db87353dcfed41f2bd6474dd146fbd26ef0630d2f48c4e07a4b269f4646f7ec0")
    ]
)
