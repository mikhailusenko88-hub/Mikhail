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
    var eyeFile: String? = nil      // «глаз» — понимание фото (mmproj), отдельный файл
    var eyePath: String? = nil
    var eyeMB: Int = 0

    var urls: [URL] { Self.urls(path) }
    var eyeURLs: [URL] { eyePath.map(Self.urls) ?? [] }

    static func urls(_ path: String) -> [URL] {
        ["https://huggingface.co/", "https://hf-mirror.com/"].compactMap { URL(string: $0 + path) }
    }

    // проверено 12.11.2026 на одинаковых заданиях: Qwen3.5 4B сама ищет, открывает источники и считает через calc
    static let all: [BrainModel] = [
        BrainModel(id: "qwen35-4b", title: "Qwen3.5 4B — основная",
                   note: "Лучше всех ищет, проверяет и выполняет задания. 2,6 ГБ.",
                   file: "Qwen3.5-4B-Q4_K_M.gguf",
                   path: "unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf",
                   sizeMB: 2613, kind: .qwen35,
                   eyeFile: "Qwen3.5-4B-mmproj-F16.gguf", eyePath: "unsloth/Qwen3.5-4B-GGUF/resolve/main/mmproj-F16.gguf", eyeMB: 641),
        BrainModel(id: "qwen3-4b", title: "Qwen3 4B — запасная",
                   note: "Прошлое поколение, чуть меньше. 2,4 ГБ.",
                   file: "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
                   path: "unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
                   sizeMB: 2381, kind: .qwen3),
        BrainModel(id: "qwen35-2b", title: "Qwen3.5 2B — быстрая",
                   note: "Вдвое быстрее и легче, но проще. 1,2 ГБ.",
                   file: "Qwen3.5-2B-Q4_K_M.gguf",
                   path: "unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf",
                   sizeMB: 1221, kind: .qwen35,
                   eyeFile: "Qwen3.5-2B-mmproj-F16.gguf", eyePath: "unsloth/Qwen3.5-2B-GGUF/resolve/main/mmproj-F16.gguf", eyeMB: 637),
    ]
}

@MainActor
final class ModelStore: NSObject, ObservableObject, URLSessionDownloadDelegate {
    static let shared = ModelStore()

    @Published var selectedID: String = UserDefaults.standard.string(forKey: "brain.model") ?? "qwen35-4b" {
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
    func eyeURL(_ m: BrainModel) -> URL? { m.eyeFile.map { Self.folder.appendingPathComponent($0) } }

    func isEyeReady(_ m: BrainModel) -> Bool {
        guard let u = eyeURL(m), let a = try? FileManager.default.attributesOfItem(atPath: u.path),
              let n = a[.size] as? NSNumber else { return false }
        return n.int64Value > Int64(m.eyeMB) * 900_000
    }

    /// Задача скачивания: «id» — нейросеть, «id#eye» — её «глаз».
    private func spec(_ tid: String) -> (m: BrainModel, eye: Bool)? {
        let eye = tid.hasSuffix("#eye")
        let id = eye ? String(tid.dropLast(4)) : tid
        guard let m = BrainModel.all.first(where: { $0.id == id }) else { return nil }
        return (m, eye)
    }

    func downloadEye(_ m: BrainModel) {
        guard downloading == nil, m.eyePath != nil else { return }
        downloading = m.id + "#eye"
        progress = 0
        tryIndex = 0
        attempts = 0
        resume = nil
        status = "Скачиваю «зрение» для \(m.title)…"
        UIApplication.shared.isIdleTimerDisabled = true
        start(m, eye: true)
    }

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
        start(m, eye: false)
    }

    private func start(_ m: BrainModel, eye: Bool) {
        let list = eye ? m.eyeURLs : m.urls
        if let r = resume {
            task = session.downloadTask(withResumeData: r)
            resume = nil
        } else {
            task = session.downloadTask(with: list[min(tryIndex, list.count - 1)])
        }
        task?.taskDescription = eye ? m.id + "#eye" : m.id
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
        if let e = eyeURL(m) { try? FileManager.default.removeItem(at: e) }
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
            let sp = spec(downloadTask.taskDescription ?? "")
            let mb = sp.map { $0.eye ? $0.m.eyeMB : $0.m.sizeMB } ?? 2400
            let total = totalBytesExpectedToWrite > 0 ? Double(totalBytesExpectedToWrite) : Double(mb * 1_048_576)
            progress = min(1, Double(totalBytesWritten) / total)
            status = String(format: "Скачано %.0f из %.0f МБ", Double(totalBytesWritten) / 1_048_576, total / 1_048_576)
        }
    }

    nonisolated func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didFinishDownloadingTo location: URL) {
        // файл нужно забрать сразу, до выхода из функции
        let tid = downloadTask.taskDescription ?? ""
        let eye = tid.hasSuffix("#eye")
        let id = eye ? String(tid.dropLast(4)) : tid
        guard let m = BrainModel.all.first(where: { $0.id == id }) else { return }
        let code = (downloadTask.response as? HTTPURLResponse)?.statusCode ?? 0
        let dest = ModelStore.folder.appendingPathComponent(eye ? (m.eyeFile ?? "eye.gguf") : m.file)
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
                start(m, eye: eye)
                return
            }
            UIApplication.shared.isIdleTimerDisabled = false
            downloading = nil
            if let err {
                status = "Не скачалось: \(err)"
            } else if eye {
                status = isEyeReady(m) ? "«Зрение» в телефоне — можно присылать фото." : "Файл пришёл не целиком — нажмите ещё раз."
                progress = 1
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
        let tid = task.taskDescription ?? ""
        MainActor.assumeIsolated {
            if ns.code == NSURLErrorCancelled { return }
            guard let sp = spec(tid) else { return }
            let m = sp.m
            if let data {
                resume = data
            } else {
                tryIndex += 1   // не открылся основной адрес — пробуем зеркало
            }
            attempts += 1
            if attempts < 30 && tryIndex < m.urls.count && downloading != nil {
                status = "Связь прервалась, продолжаю…"
                DispatchQueue.main.asyncAfter(deadline: .now() + 3) { [weak self] in
                    guard let self, self.downloading == tid else { return }
                    self.start(m, eye: sp.eye)
                }
            } else {
                downloading = nil
                UIApplication.shared.isIdleTimerDisabled = false
                status = "Не скачалось: \(error.localizedDescription). Можно скачать файл на компьютере и положить через «Файлы»."
            }
        }
    }
}
