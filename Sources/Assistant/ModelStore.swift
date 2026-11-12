import Foundation
import SwiftUI
import UIKit

/// Какие нейросети можно поставить в телефон и где лежат их файлы.
struct BrainModel: Identifiable, Equatable {
    enum Kind { case qwen3, qwen35 }
    let id: String
    let title: String
    let note: String
    let file: String
    let path: String          // путь на Hugging Face: <репозиторий>/resolve/main/<файл>
    let sizeMB: Int
    let kind: Kind

    var urls: [URL] {
        ["https://huggingface.co/", "https://hf-mirror.com/"].compactMap { URL(string: $0 + path) }
    }

    static let all: [BrainModel] = [
        BrainModel(id: "qwen3-4b", title: "Qwen3 4B — основная",
                   note: "Лучше всех держит команды и правила. 2,4 ГБ.",
                   file: "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
                   path: "unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
                   sizeMB: 2381, kind: .qwen3),
        BrainModel(id: "qwen35-4b", title: "Qwen3.5 4B — новее",
                   note: "Свежее поколение, умнее в рассуждениях. 2,6 ГБ.",
                   file: "Qwen3.5-4B-Q4_K_M.gguf",
                   path: "unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf",
                   sizeMB: 2613, kind: .qwen35),
        BrainModel(id: "qwen35-2b", title: "Qwen3.5 2B — быстрая",
                   note: "Вдвое быстрее и легче, но проще. 1,2 ГБ.",
                   file: "Qwen3.5-2B-Q4_K_M.gguf",
                   path: "unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf",
                   sizeMB: 1221, kind: .qwen35),
    ]
}

@MainActor
final class ModelStore: NSObject, ObservableObject, URLSessionDownloadDelegate {
    static let shared = ModelStore()

    @Published var selectedID: String = UserDefaults.standard.string(forKey: "brain.model") ?? "qwen3-4b" {
        didSet { UserDefaults.standard.set(selectedID, forKey: "brain.model") }
    }
    @Published var downloading: String?
    @Published var progress: Double = 0
    @Published var status = ""

    private var session: URLSession!
    private var task: URLSessionDownloadTask?
    private var resume: Data?
    private var tryIndex = 0
    private var attempts = 0

    override init() {
        super.init()
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 60
        cfg.timeoutIntervalForResource = 6 * 3600
        session = URLSession(configuration: cfg, delegate: self, delegateQueue: .main)
    }

    nonisolated static var folder: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Brain", isDirectory: true)
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        var v = base
        var rv = URLResourceValues(); rv.isExcludedFromBackup = true   // 2 ГБ не тащим в iCloud
        try? v.setResourceValues(rv)
        return base
    }

    var selected: BrainModel { BrainModel.all.first { $0.id == selectedID } ?? BrainModel.all[0] }

    func fileURL(_ m: BrainModel) -> URL { Self.folder.appendingPathComponent(m.file) }

    func isReady(_ m: BrainModel) -> Bool {
        guard let a = try? FileManager.default.attributesOfItem(atPath: fileURL(m).path),
              let n = a[.size] as? NSNumber else { return false }
        return n.int64Value > Int64(m.sizeMB) * 900_000   // файл целый (с запасом на округление)
    }

    /// Готовая модель: выбранная, а если её нет — любая скачанная.
    var readyModel: BrainModel? {
        if isReady(selected) { return selected }
        return BrainModel.all.first { isReady($0) }
    }

    func download(_ m: BrainModel) {
        guard downloading == nil else { return }
        downloading = m.id
        progress = 0
        tryIndex = 0
        attempts = 0
        status = "Скачиваю \(m.title)…"
        UIApplication.shared.isIdleTimerDisabled = true
        start(m)
    }

    private func start(_ m: BrainModel) {
        if let r = resume {
            task = session.downloadTask(withResumeData: r)
            resume = nil
        } else {
            task = session.downloadTask(with: m.urls[min(tryIndex, m.urls.count - 1)])
        }
        task?.taskDescription = m.id
        task?.resume()
    }

    func cancel() {
        task?.cancel(byProducingResumeData: { [weak self] d in
            Task { @MainActor in self?.resume = d }
        })
        task = nil
        downloading = nil
        status = "Остановлено. Нажмите «Скачать» — продолжит с того же места."
        UIApplication.shared.isIdleTimerDisabled = false
    }

    func delete(_ m: BrainModel) {
        if LlamaEngine.shared.loadedPath == fileURL(m).path { LlamaEngine.shared.unload() }
        try? FileManager.default.removeItem(at: fileURL(m))
        objectWillChange.send()
    }

    /// Файл нейросети, принесённый вручную (через «Файлы»).
    func importFile(_ url: URL) -> String {
        let name = url.lastPathComponent
        guard let m = BrainModel.all.first(where: { $0.file == name }) else {
            return "Не знаю такой файл: \(name). Нужен один из: " + BrainModel.all.map(\.file).joined(separator: ", ")
        }
        let ok = url.startAccessingSecurityScopedResource()
        defer { if ok { url.stopAccessingSecurityScopedResource() } }
        do {
            try? FileManager.default.removeItem(at: fileURL(m))
            try FileManager.default.copyItem(at: url, to: fileURL(m))
            selectedID = m.id
            objectWillChange.send()
            return "Готово: \(m.title)"
        } catch {
            return "Не удалось скопировать: \(error.localizedDescription)"
        }
    }

    // MARK: URLSessionDownloadDelegate (очередь — главная)

    nonisolated func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didWriteData bytesWritten: Int64,
                                totalBytesWritten: Int64, totalBytesExpectedToWrite: Int64) {
        MainActor.assumeIsolated {
            let id = downloadTask.taskDescription ?? ""
            let total = totalBytesExpectedToWrite > 0 ? Double(totalBytesExpectedToWrite)
                : Double((BrainModel.all.first { $0.id == id }?.sizeMB ?? 2400) * 1_048_576)
            progress = min(1, Double(totalBytesWritten) / total)
            status = String(format: "Скачано %.0f из %.0f МБ", Double(totalBytesWritten) / 1_048_576, total / 1_048_576)
        }
    }

    nonisolated func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didFinishDownloadingTo location: URL) {
        // файл нужно забрать сразу, до выхода из функции
        let id = downloadTask.taskDescription ?? ""
        guard let m = BrainModel.all.first(where: { $0.id == id }) else { return }
        let code = (downloadTask.response as? HTTPURLResponse)?.statusCode ?? 0
        let dest = ModelStore.folder.appendingPathComponent(m.file)
        var err: String?
        if code == 200 || code == 206 {
            try? FileManager.default.removeItem(at: dest)
            do { try FileManager.default.moveItem(at: location, to: dest) } catch { err = error.localizedDescription }
        } else {
            err = "сервер ответил \(code)"
        }
        MainActor.assumeIsolated {
            if err != nil && code != 0 && tryIndex + 1 < m.urls.count {   // основной адрес не отдал — пробуем зеркало
                tryIndex += 1
                resume = nil
                status = "Пробую другой адрес…"
                start(m)
                return
            }
            UIApplication.shared.isIdleTimerDisabled = false
            downloading = nil
            if let err {
                status = "Не скачалось: \(err)"
            } else if isReady(m) {
                status = "Нейросеть в телефоне: \(m.title)"
                selectedID = m.id
                progress = 1
            } else {
                status = "Файл пришёл не целиком — нажмите «Скачать» ещё раз."
            }
            objectWillChange.send()
        }
    }

    nonisolated func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard let error else { return }
        let ns = error as NSError
        let data = ns.userInfo[NSURLSessionDownloadTaskResumeData] as? Data
        let id = task.taskDescription ?? ""
        MainActor.assumeIsolated {
            if ns.code == NSURLErrorCancelled { return }
            guard let m = BrainModel.all.first(where: { $0.id == id }) else { return }
            if let data {
                resume = data
            } else {
                tryIndex += 1   // не открылся основной адрес — пробуем зеркало
            }
            attempts += 1
            if attempts < 30 && tryIndex < m.urls.count && downloading != nil {
                status = "Связь прервалась, продолжаю…"
                DispatchQueue.main.asyncAfter(deadline: .now() + 3) { [weak self] in
                    guard let self, self.downloading == m.id else { return }
                    self.start(m)
                }
            } else {
                downloading = nil
                UIApplication.shared.isIdleTimerDisabled = false
                status = "Не скачалось: \(error.localizedDescription). Можно скачать файл на компьютере и положить через «Файлы»."
            }
        }
    }
}
