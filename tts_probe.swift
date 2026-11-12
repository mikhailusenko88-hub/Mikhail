// Отчего одна и та же реплика звучит по-разному в tts_mac.swift (каждая в своём процессе) и в классе приложения?
// Режимы: plain | delays0 (pre/postUtteranceDelay = 0) | sleep (2 с до синтеза) | warm (сначала другая реплика) | warm2 (та же реплика дважды, пишем вторую)
//   tts_probe jobs.json outdir index
import Foundation
import AVFoundation
let args = CommandLine.arguments
let all = try! JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: args[1]))) as! [[String: Any]]
let j = all[Int(args[3])!]
setvbuf(stdout, nil, _IOLBF, 0)
let out = URL(fileURLWithPath: args[2]); try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
let ru = AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix("ru") }.sorted { $0.quality.rawValue > $1.quality.rawValue }
let voice = ru.first ?? AVSpeechSynthesisVoice(language: "ru-RU")
let synth = AVSpeechSynthesizer()
let mode = j["mode"] as? String ?? "plain"
func make(_ text: String) -> AVSpeechUtterance {
    let u = AVSpeechUtterance(string: text); u.voice = voice
    u.pitchMultiplier = (j["pitch"] as? NSNumber)?.floatValue ?? 1
    u.rate = (j["rate"] as? NSNumber)?.floatValue ?? AVSpeechUtteranceDefaultSpeechRate
    if mode.contains("delays0") { u.preUtteranceDelay = 0; u.postUtteranceDelay = 0 }
    return u
}
func speak(_ text: String, to url: URL?) -> Int {
    var file: AVAudioFile? = nil; var done = false; var frames = 0
    synth.write(make(text)) { buf in
        guard let pcm = buf as? AVAudioPCMBuffer else { return }
        if pcm.frameLength == 0 { done = true; return }
        if let url = url { if file == nil { file = try? AVAudioFile(forWriting: url, settings: pcm.format.settings, commonFormat: pcm.format.commonFormat, interleaved: pcm.format.isInterleaved) }; try? file?.write(from: pcm) }
        frames += Int(pcm.frameLength)
    }
    let t0 = Date(); while !done && Date().timeIntervalSince(t0) < 30 { RunLoop.main.run(until: Date().addingTimeInterval(0.02)) }
    file = nil; return frames
}
if mode.contains("sleep") { RunLoop.main.run(until: Date().addingTimeInterval(2.0)) }
if mode.contains("warm2") { _ = speak(j["text"] as! String, to: nil) } else if mode.contains("warm") { _ = speak("Привет, друзья! Пойдём к реке.", to: nil) }
let n = speak(j["text"] as! String, to: out.appendingPathComponent((j["name"] as! String) + ".caf"))
print(j["name"] as! String, mode, n)
