// Голос iPhone (AVSpeechSynthesizer) на Mac — так же, как MultikTTS в приложении «Замер 3D»: текст + IPA-ударения на словах.
//   swift tts_mac.swift jobs.json outdir
import Foundation
import AVFoundation

let args = CommandLine.arguments
let jobs = try! JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: args[1]))) as! [[String: Any]]
let out = URL(fileURLWithPath: args[2]); try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
let ru = AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix("ru") }.sorted { $0.quality.rawValue > $1.quality.rawValue }
print("русские голоса:", ru.map { "\($0.name) [\($0.identifier)] q=\($0.quality.rawValue) g=\($0.gender.rawValue)" })
func pick(_ base: String) -> AVSpeechSynthesisVoice? {
    let male = base == "male"
    func isMale(_ x: AVSpeechSynthesisVoice) -> Bool { if x.gender == .male { return true }; if x.gender == .female { return false }
        let n = x.name.lowercased(); return n.contains("yuri") || n.contains("юрий") || n.contains("dmitr") || n.contains("дмитр") }
    return ru.first { isMale($0) == male } ?? ru.first ?? AVSpeechSynthesisVoice(language: "ru-RU")
}
let synth = AVSpeechSynthesizer()
var log: [[String: Any]] = []
for j in jobs {
    let name = j["name"] as! String, text = j["text"] as! String
    var u: AVSpeechUtterance
    if let ssml = j["ssml"] as? String, let x = AVSpeechUtterance(ssmlRepresentation: ssml) { u = x }
    else if let spans = j["ipa"] as? [[Any]], !spans.isEmpty {
        let a = NSMutableAttributedString(string: text); let len = (text as NSString).length
        for s in spans where s.count == 3 {
            guard let st = (s[0] as? NSNumber)?.intValue, let ln = (s[1] as? NSNumber)?.intValue, let ipa = s[2] as? String, st >= 0, ln > 0, st + ln <= len else { continue }
            a.addAttribute(NSAttributedString.Key(rawValue: AVSpeechSynthesisIPANotationAttribute), value: ipa, range: NSRange(location: st, length: ln))
        }
        u = AVSpeechUtterance(attributedString: a)
    } else { u = AVSpeechUtterance(string: text) }
    let v = pick(j["base"] as? String ?? "female"); u.voice = v
    u.pitchMultiplier = min(2, max(0.5, (j["pitch"] as? NSNumber)?.floatValue ?? 1))
    u.rate = min(AVSpeechUtteranceMaximumSpeechRate, max(AVSpeechUtteranceMinimumSpeechRate, (j["rate"] as? NSNumber)?.floatValue ?? AVSpeechUtteranceDefaultSpeechRate))
    let url = out.appendingPathComponent(name + ".caf")
    var file: AVAudioFile? = nil; var done = false; var frames: AVAudioFrameCount = 0
    synth.write(u) { buf in
        guard let pcm = buf as? AVAudioPCMBuffer else { return }
        if pcm.frameLength == 0 { done = true; return }
        if file == nil { file = try? AVAudioFile(forWriting: url, settings: pcm.format.settings, commonFormat: pcm.format.commonFormat, interleaved: pcm.format.isInterleaved) }
        try? file?.write(from: pcm); frames += pcm.frameLength
    }
    let t0 = Date()
    while !done && Date().timeIntervalSince(t0) < 30 { RunLoop.main.run(until: Date().addingTimeInterval(0.02)) }
    file = nil
    log.append(["name": name, "frames": Int(frames), "voice": v?.name ?? "-"])
    print(name, frames, v?.name ?? "-")
}
try! JSONSerialization.data(withJSONObject: log).write(to: out.appendingPathComponent("_log.json"))
