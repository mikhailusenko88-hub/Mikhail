import Foundation
import AVFoundation
import Speech

/// Уши помощника: распознавание русской речи. По умолчанию — только в телефоне (без отправки звука в Apple).
@MainActor
final class AssistantEars: ObservableObject {
    static let shared = AssistantEars()
    @Published var listening = false
    @Published var text = ""
    @Published var problem = ""
    @Published var allowServer = UserDefaults.standard.bool(forKey: "assistant.asr.server") {
        didSet { UserDefaults.standard.set(allowServer, forKey: "assistant.asr.server") }
    }

    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "ru-RU"))
    private let engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?

    var onDevice: Bool { recognizer?.supportsOnDeviceRecognition ?? false }

    func start() {
        problem = ""
        Speaker.shared.stop()
        SFSpeechRecognizer.requestAuthorization { st in
            AVAudioApplication.requestRecordPermission { mic in
                Task { @MainActor in
                    guard st == .authorized, mic else {
                        self.problem = "Нет доступа к микрофону или распознаванию: Настройки → Замер 3D."
                        return
                    }
                    self.begin()
                }
            }
        }
    }

    private func begin() {
        guard let r = recognizer, r.isAvailable else { problem = "Распознавание речи сейчас недоступно."; return }
        if !r.supportsOnDeviceRecognition && !allowServer {
            problem = "Русская речь в этом телефоне распознаётся только через Apple. Разрешите это в ⚙︎ («Распознавание через Apple») или пишите текстом."
            return
        }
        _ = finish()
        text = ""
        do {
            let s = AVAudioSession.sharedInstance()
            try s.setCategory(.playAndRecord, mode: .measurement, options: [.defaultToSpeaker, .duckOthers])
            try s.setActive(true, options: .notifyOthersOnDeactivation)
            let req = SFSpeechAudioBufferRecognitionRequest()
            req.shouldReportPartialResults = true
            req.requiresOnDeviceRecognition = r.supportsOnDeviceRecognition   // есть в телефоне — только в телефоне
            req.addsPunctuation = true
            request = req
            let input = engine.inputNode
            let fmt = input.outputFormat(forBus: 0)
            input.removeTap(onBus: 0)
            input.installTap(onBus: 0, bufferSize: 1024, format: fmt) { buf, _ in req.append(buf) }
            engine.prepare()
            try engine.start()
            listening = true
            task = r.recognitionTask(with: req) { [weak self] res, err in
                let t = res?.bestTranscription.formattedString
                let failed = err != nil
                Task { @MainActor in
                    guard let self else { return }
                    if let t { self.text = t }
                    if failed && self.text.isEmpty && self.listening { self.problem = "Не расслышала. Попробуйте ещё раз." }
                }
            }
        } catch {
            problem = "Микрофон не включился: \(error.localizedDescription)"
            _ = finish()
        }
    }

    /// Остановить и вернуть услышанное.
    func finish() -> String {
        if engine.isRunning { engine.stop() }
        engine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        task?.finish()
        request = nil
        task = nil
        listening = false
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio)
        try? AVAudioSession.sharedInstance().setActive(true)
        return text
    }
}

/// Голос помощника (встроенный в iPhone, работает без интернета).
final class Speaker: NSObject {
    static let shared = Speaker()
    private let synth = AVSpeechSynthesizer()

    static func clean(_ s: String) -> String {
        var t = s.replacingOccurrences(of: "https?://\\S+", with: "ссылка", options: .regularExpression)
        t = t.replacingOccurrences(of: "[*#_`>|]", with: "", options: .regularExpression)
        t = t.replacingOccurrences(of: "₽", with: " рублей")
        return t
    }

    var voice: AVSpeechSynthesisVoice? {
        let ru = AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix("ru") }
        if let id = UserDefaults.standard.string(forKey: "assistant.voice"), let v = ru.first(where: { $0.identifier == id }) { return v }
        return ru.sorted { $0.quality.rawValue > $1.quality.rawValue }.first ?? AVSpeechSynthesisVoice(language: "ru-RU")
    }

    func say(_ text: String) {
        stop()
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio)
        try? AVAudioSession.sharedInstance().setActive(true)
        let u = AVSpeechUtterance(string: Self.clean(text))
        u.voice = voice
        u.rate = AVSpeechUtteranceDefaultSpeechRate * 1.05
        synth.speak(u)
    }

    func stop() {
        if synth.isSpeaking { synth.stopSpeaking(at: .immediate) }
    }
}
