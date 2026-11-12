import Foundation
import AVFoundation
final class MultikTTS: NSObject {
    private let synth = AVSpeechSynthesizer()
    private var busy = false
    private var jobs: [(String, [String: Any], URL, (Bool) -> Void)] = []

    static func qualityName(_ q: AVSpeechSynthesisVoiceQuality) -> String {
        switch q { case .premium: return "премиум"; case .enhanced: return "улучшенный"; default: return "обычный" }
    }

    /// Голос по описанию персонажа: сохранённый id → иначе лучший русский нужного пола.
    static func pickVoice(_ v: [String: Any]) -> AVSpeechSynthesisVoice? {
        if let id = v["id"] as? String, !id.isEmpty, let x = AVSpeechSynthesisVoice(identifier: id) { return x }
        let ru = AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix("ru") }
            .sorted { $0.quality.rawValue > $1.quality.rawValue }
        let male = (v["base"] as? String ?? "female") == "male"
        func isMale(_ x: AVSpeechSynthesisVoice) -> Bool {
            if x.gender == .male { return true }
            if x.gender == .female { return false }
            let n = x.name.lowercased()
            return n.contains("yuri") || n.contains("юрий") || n.contains("dmitr") || n.contains("дмитр")
        }
        return ru.first { isMale($0) == male } ?? ru.first ?? AVSpeechSynthesisVoice(language: "ru-RU")
    }

    static func utterance(_ text: String, _ v: [String: Any]) -> AVSpeechUtterance {
        // ударения: для слов с известным ударением передаём произношение (IPA) — iPhone читает именно так
        let u: AVSpeechUtterance
        if let spans = v["ipa"] as? [[Any]], !spans.isEmpty {
            let a = NSMutableAttributedString(string: text)
            let len = (text as NSString).length
            for s in spans where s.count == 3 {
                guard let st = (s[0] as? NSNumber)?.intValue, let ln = (s[1] as? NSNumber)?.intValue, let ipa = s[2] as? String,
                      st >= 0, ln > 0, st + ln <= len else { continue }
                a.addAttribute(NSAttributedString.Key(rawValue: AVSpeechSynthesisIPANotationAttribute), value: ipa, range: NSRange(location: st, length: ln))
            }
            u = AVSpeechUtterance(attributedString: a)
        } else {
            u = AVSpeechUtterance(string: text)
        }
        u.voice = pickVoice(v)
        let pitch = (v["pitch"] as? NSNumber)?.floatValue ?? 1
        let rate = (v["rate"] as? NSNumber)?.floatValue ?? AVSpeechUtteranceDefaultSpeechRate
        u.pitchMultiplier = min(2, max(0.5, pitch))
        u.rate = min(AVSpeechUtteranceMaximumSpeechRate, max(AVSpeechUtteranceMinimumSpeechRate, rate))
        u.preUtteranceDelay = 0
        u.postUtteranceDelay = 0
        return u
    }

    func synthesize(text: String, voice: [String: Any], to url: URL, done: @escaping (Bool) -> Void) {
        DispatchQueue.main.async {
            self.jobs.append((text, voice, url, done))
            self.next()
        }
    }

    /// Состояние одной озвучки (класс, чтобы безопасно менять из колбэка синтезатора).
    private final class Job {
        var file: AVAudioFile?
        var finished = false
        var frames: AVAudioFrameCount = 0
        let lock = NSLock()
    }

    private func next() {
        guard !busy, !jobs.isEmpty else { return }
        busy = true
        let (text, voice, url, done) = jobs.removeFirst()
        try? FileManager.default.removeItem(at: url)
        let job = Job()
        let finish: () -> Void = { [weak self] in
            job.lock.lock()
            if job.finished { job.lock.unlock(); return }
            job.finished = true
            job.file = nil   // закрывает файл
            let ok = job.frames > 0
            job.lock.unlock()
            done(ok)
            self?.busy = false
            self?.next()
        }
        synth.write(Self.utterance(text, voice)) { buf in
            guard let pcm = buf as? AVAudioPCMBuffer else { return }
            if pcm.frameLength == 0 { DispatchQueue.main.async { finish() }; return }
            job.lock.lock()
            defer { job.lock.unlock() }
            if job.finished { return }
            if job.file == nil {
                job.file = try? AVAudioFile(forWriting: url, settings: pcm.format.settings,
                                            commonFormat: pcm.format.commonFormat, interleaved: pcm.format.isInterleaved)
            }
            do { try job.file?.write(from: pcm); job.frames += pcm.frameLength } catch {}
        }
        // запасной выход, если система не прислала последний пустой буфер
        let limit = 6.0 + Double(text.count) * 0.25
        DispatchQueue.main.asyncAfter(deadline: .now() + limit) { finish() }
    }
}
// Проверка класса из приложения: те же реплики через MultikTTS.synthesize (как в «Мультиках»)
setvbuf(stdout, nil, _IOLBF, 0)
let jobs = try! JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))) as! [[String: Any]]
let out = URL(fileURLWithPath: CommandLine.arguments[2]); try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
let tts = MultikTTS()
var left = jobs.count
for j in jobs {
    let name = j["name"] as! String
    tts.synthesize(text: j["text"] as! String, voice: j["voice"] as! [String: Any], to: out.appendingPathComponent(name + ".caf")) { ok in
        print(name, ok ? "ок" : "НЕТ ЗВУКА"); left -= 1
    }
}
let t0 = Date()
while left > 0 && Date().timeIntervalSince(t0) < 300 { RunLoop.main.run(until: Date().addingTimeInterval(0.05)) }
print("готово, осталось", left)
