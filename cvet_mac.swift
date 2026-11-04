// Замер сборки «Мультиков» как на iPhone: кадр → JPEG (как toDataURL в WebKit) → CGImage → BGRA → AVAssetWriter H.264.
// swift cvet_mac.swift <папка_кадров> <папка_вывода>
import AVFoundation
import CoreGraphics
import CoreVideo
import Foundation
import ImageIO
import UniformTypeIdentifiers

let W = 1920, H = 1080, FPS: Int32 = 25
let args = CommandLine.arguments
let src = URL(fileURLWithPath: args[1]), out = URL(fileURLWithPath: args[2])
try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
let sRGB = CGColorSpace(name: CGColorSpace.sRGB)!  // на iOS DeviceRGB = sRGB; на Mac берём sRGB, чтобы не мешал профиль экрана

func load(_ u: URL) -> CGImage {
    let s = CGImageSourceCreateWithURL(u as CFURL, nil)!
    return CGImageSourceCreateImageAtIndex(s, 0, nil)!
}
func jpeg(_ img: CGImage, _ q: Double) -> Data {
    let d = NSMutableData()
    let dst = CGImageDestinationCreateWithData(d, UTType.jpeg.identifier as CFString, 1, nil)!
    CGImageDestinationAddImage(dst, img, [kCGImageDestinationLossyCompressionQuality: q] as CFDictionary)
    CGImageDestinationFinalize(dst)
    return d as Data
}
func decode(_ d: Data) -> CGImage {
    let s = CGImageSourceCreateWithData(d as CFData, nil)!
    return CGImageSourceCreateImageAtIndex(s, 0, nil)!
}

// кадры: таблица 25 раз; герои — панорама 2 px/кадр (как в облачном замере)
var frames: [CGImage] = []
let files = try FileManager.default.contentsOfDirectory(at: src, includingPropertiesForKeys: nil)
    .filter { $0.pathExtension == "png" }.sorted { $0.lastPathComponent < $1.lastPathComponent }
for f in files {
    let im = load(f)
    for i in 0..<Int(FPS) {
        if im.width == W { frames.append(im); continue }
        frames.append(im.cropping(to: CGRect(x: 2 * i, y: 10, width: W, height: H))!)
    }
}
print("кадров:", frames.count)

struct V { let name: String; let q: Double?; let props: Bool; let attach: Bool; let rate: Int }
let variants = [
    V(name: "app_seichas", q: 0.9, props: false, attach: false, rate: 10_000_000),   // как в приложении сейчас
    V(name: "app_709props", q: 0.9, props: true, attach: false, rate: 10_000_000),   // только метки в настройках
    V(name: "app_709", q: 0.9, props: true, attach: true, rate: 10_000_000),         // метки + на каждом кадре
    V(name: "app_709_q1", q: 1.0, props: true, attach: true, rate: 10_000_000),      // + JPEG 1.0
    V(name: "app_709_bezjpeg", q: nil, props: true, attach: true, rate: 10_000_000), // без JPEG (вклад JPEG)
    V(name: "app_709_q1_16m", q: 1.0, props: true, attach: true, rate: 16_000_000),  // + 16 Мбит/с
]

// образцы JPEG (для проверки 4:2:0)
for q in [0.9, 0.95, 1.0] {
    try jpeg(frames[Int(FPS) + 12], q).write(to: out.appendingPathComponent("jpeg_q\(Int(q * 100)).jpg"))
}

for v in variants {
    let url = out.appendingPathComponent(v.name + ".mp4")
    try? FileManager.default.removeItem(at: url)
    let wr = try AVAssetWriter(outputURL: url, fileType: .mp4)
    var vs: [String: Any] = [
        AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: W, AVVideoHeightKey: H,
        AVVideoCompressionPropertiesKey: [
            AVVideoAverageBitRateKey: v.rate,
            AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
            AVVideoMaxKeyFrameIntervalKey: Int(FPS) * 2,
        ],
    ]
    if v.props {
        vs[AVVideoColorPropertiesKey] = [
            AVVideoColorPrimariesKey: AVVideoColorPrimaries_ITU_R_709_2,
            AVVideoTransferFunctionKey: AVVideoTransferFunction_ITU_R_709_2,
            AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_709_2,
        ]
    }
    let vin = AVAssetWriterInput(mediaType: .video, outputSettings: vs)
    vin.expectsMediaDataInRealTime = false
    let ad = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: vin, sourcePixelBufferAttributes: [
        kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
        kCVPixelBufferWidthKey as String: W, kCVPixelBufferHeightKey as String: H,
    ])
    wr.add(vin)
    guard wr.startWriting() else { print(v.name, "ошибка", wr.error as Any); continue }
    wr.startSession(atSourceTime: .zero)
    let t0 = Date()
    var n: Int64 = 0
    var jpegBytes = 0
    for f in frames {
        var img = f
        if let q = v.q { let d = jpeg(f, q); jpegBytes += d.count; img = decode(d) }
        while !vin.isReadyForMoreMediaData { usleep(1000) }
        var pbo: CVPixelBuffer?
        CVPixelBufferPoolCreatePixelBuffer(nil, ad.pixelBufferPool!, &pbo)
        let pb = pbo!
        CVPixelBufferLockBaseAddress(pb, [])
        let ctx = CGContext(data: CVPixelBufferGetBaseAddress(pb), width: W, height: H, bitsPerComponent: 8,
                            bytesPerRow: CVPixelBufferGetBytesPerRow(pb), space: sRGB,
                            bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue)!
        ctx.draw(img, in: CGRect(x: 0, y: 0, width: W, height: H))
        CVPixelBufferUnlockBaseAddress(pb, [])
        if v.attach {
            CVBufferSetAttachment(pb, kCVImageBufferColorPrimariesKey, kCVImageBufferColorPrimaries_ITU_R_709_2, .shouldPropagate)
            CVBufferSetAttachment(pb, kCVImageBufferTransferFunctionKey, kCVImageBufferTransferFunction_ITU_R_709_2, .shouldPropagate)
            CVBufferSetAttachment(pb, kCVImageBufferYCbCrMatrixKey, kCVImageBufferYCbCrMatrix_ITU_R_709_2, .shouldPropagate)
        }
        if !ad.append(pb, withPresentationTime: CMTime(value: n, timescale: FPS)) { print(v.name, "append", wr.error as Any); break }
        n += 1
    }
    vin.markAsFinished()
    let sem = DispatchSemaphore(value: 0)
    wr.finishWriting { sem.signal() }
    sem.wait()
    let sz = (try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? Int) ?? 0
    print(v.name, "статус", wr.status.rawValue, "кадров", n, "сек", String(format: "%.1f", Date().timeIntervalSince(t0)),
          "МБ", String(format: "%.1f", Double(sz) / 1e6), "JPEG КБ/кадр", jpegBytes / max(1, Int(n)) / 1024)
}
