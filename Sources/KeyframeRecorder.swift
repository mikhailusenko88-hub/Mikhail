import Foundation
import ARKit
import CoreImage
import ImageIO
import AVFoundation

/// Сам делает фото во время скана: когда телефон сдвинулся на 25 см или повернулся на 20°.
/// К каждому фото пишется положение камеры и её параметры — по ним фото точно
/// накладываются на 3D-сетку (видно трубы, розетки, швы) и по ним можно мерить.
final class KeyframeRecorder {
    struct Frame: Codable {
        var file: String
        var time: Double
        var transform: [Float]    // камера → мир, 4x4 по столбцам
        var intrinsics: [Float]   // 3x3 по столбцам, в пикселях этого фото
        var width: Int
        var height: Int
    }

    let maxFrames = 250
    private(set) var count = 0
    private var frames: [Frame] = []
    private var lastPos: SIMD3<Float>?
    private var lastFwd: SIMD3<Float>?
    private var lastTime: TimeInterval = 0
    private let queue = DispatchQueue(label: "keyframes", qos: .utility)
    private let ctx = CIContext()
    private let lock = NSLock()
    private(set) var dir: URL

    init() {
        dir = FileManager.default.temporaryDirectory.appendingPathComponent("frames-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    }

    func reset() {
        lock.lock(); defer { lock.unlock() }
        try? FileManager.default.removeItem(at: dir)
        dir = FileManager.default.temporaryDirectory.appendingPathComponent("frames-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        frames.removeAll(); count = 0; lastPos = nil; lastFwd = nil
        hiCount = 0; hiPos = nil; hiFwd = nil; hiTime = 0
    }

    /// Возвращает true, если кадр взят.
    func consider(_ frame: ARFrame) -> Bool {
        guard count < maxFrames, frame.timestamp - lastTime > 0.7 else { return false }
        if case .normal = frame.camera.trackingState {} else { return false }
        let t = frame.camera.transform
        let pos = SIMD3<Float>(t.columns.3.x, t.columns.3.y, t.columns.3.z)
        let fwd = -SIMD3<Float>(t.columns.2.x, t.columns.2.y, t.columns.2.z)
        if let lp = lastPos, let lf = lastFwd {
            let moved = simd_distance(lp, pos)
            let turned = acos(max(-1, min(1, simd_dot(lf, fwd)))) * 180 / .pi
            guard moved > 0.25 || turned > 20 else { return false }
        }
        lastPos = pos; lastFwd = fwd; lastTime = frame.timestamp

        let idx = count
        count += 1
        save(frame, name: String(format: "frame_%04d.jpg", idx), quality: 0.75)
        return true
    }

    // MARK: чёткие фото 12 Мп (ARKit снимает их с той же точки, что и скан)
    let maxHiRes = 80
    private(set) var hiCount = 0
    private var hiPos: SIMD3<Float>?
    private var hiFwd: SIMD3<Float>?
    private var hiTime: TimeInterval = 0
    private var hiBusy = false

    /// Раз в 0,4 м или 25° просит у ARKit полноразмерный кадр (провода, саморезы, швы видно лучше).
    func considerHiRes(_ frame: ARFrame, session: ARSession) {
        guard hiCount < maxHiRes, !hiBusy, frame.timestamp - hiTime > 1.0 else { return }
        if case .normal = frame.camera.trackingState {} else { return }
        let t = frame.camera.transform
        let pos = SIMD3<Float>(t.columns.3.x, t.columns.3.y, t.columns.3.z)
        let fwd = -SIMD3<Float>(t.columns.2.x, t.columns.2.y, t.columns.2.z)
        if let lp = hiPos, let lf = hiFwd {
            let moved = simd_distance(lp, pos)
            let turned = acos(max(-1, min(1, simd_dot(lf, fwd)))) * 180 / .pi
            guard moved > 0.4 || turned > 25 else { return }
        }
        hiBusy = true
        hiTime = frame.timestamp
        session.captureHighResolutionFrame { [weak self] hf, _ in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.hiBusy = false
                guard let hf = hf else { return }
                let ht = hf.camera.transform
                self.hiPos = SIMD3<Float>(ht.columns.3.x, ht.columns.3.y, ht.columns.3.z)
                self.hiFwd = -SIMD3<Float>(ht.columns.2.x, ht.columns.2.y, ht.columns.2.z)
                let n = self.hiCount
                self.hiCount += 1
                self.save(hf, name: String(format: "hires_%03d.jpg", n), quality: 0.7)
            }
        }
    }

    private func save(_ frame: ARFrame, name: String, quality: CGFloat) {
        let t = frame.camera.transform
        let img = CIImage(cvPixelBuffer: frame.capturedImage)
        let w = CVPixelBufferGetWidth(frame.capturedImage)
        let h = CVPixelBufferGetHeight(frame.capturedImage)
        let k = frame.camera.intrinsics
        let rec = Frame(file: name, time: frame.timestamp,
                        transform: [t.columns.0, t.columns.1, t.columns.2, t.columns.3].flatMap { [$0.x, $0.y, $0.z, $0.w] },
                        intrinsics: [k.columns.0, k.columns.1, k.columns.2].flatMap { [$0.x, $0.y, $0.z] },
                        width: w, height: h)
        let url = dir.appendingPathComponent(name)
        queue.async { [ctx, lock] in
            if let cs = CGColorSpace(name: CGColorSpace.sRGB),
               let data = ctx.jpegRepresentation(of: img, colorSpace: cs,
                                                 options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: quality]) {
                try? data.write(to: url)
            }
            lock.lock(); self.frames.append(rec); lock.unlock()
        }
    }

    /// Папка с фото и список кадров (дожидается записи последних).
    func snapshot() -> (dir: URL, frames: [Frame]) {
        queue.sync {}
        lock.lock(); defer { lock.unlock() }
        return (dir, frames.sorted { $0.file < $1.file })
    }
}


/// Видео скана: каждый кадр камеры (≈15 в секунду) пишется в video.mov (HEVC),
/// к каждому кадру — где стоял телефон и параметры камеры (frames.jsonl),
/// к каждому 3-му — карта глубины LiDAR (depth/*.bin: Float16 256×192 + уверенность).
/// По этому потом строится модель комнаты с фото-текстурой, стекло, профили, провода.
final class VideoRecorder {
    private(set) var dir: URL
    private var writer: AVAssetWriter?
    private var input: AVAssetWriterInput?
    private var adaptor: AVAssetWriterInputPixelBufferAdaptor?
    private var jsonl: FileHandle?
    private var t0: TimeInterval = -1
    private var lastT: TimeInterval = -1
    private var index = 0
    private var depthIndex = 0
    private var size = (0, 0)
    private let queue = DispatchQueue(label: "video-rec", qos: .userInitiated)
    private(set) var seconds: Double = 0
    private(set) var running = false

    init() {
        dir = FileManager.default.temporaryDirectory.appendingPathComponent("video-\(UUID().uuidString)")
    }

    func reset() {
        queue.sync {
            writer?.cancelWriting()
            writer = nil; input = nil; adaptor = nil
            try? jsonl?.close(); jsonl = nil
            try? FileManager.default.removeItem(at: dir)
            dir = FileManager.default.temporaryDirectory.appendingPathComponent("video-\(UUID().uuidString)")
            t0 = -1; lastT = -1; index = 0; depthIndex = 0; seconds = 0; running = false
        }
    }

    /// Начать новую запись (старая стирается).
    func start() {
        reset()
        running = true
    }

    private func open(width: Int, height: Int) -> Bool {
        do {
            try FileManager.default.createDirectory(at: dir.appendingPathComponent("depth"), withIntermediateDirectories: true)
            let url = dir.appendingPathComponent("video.mov")
            let w = try AVAssetWriter(outputURL: url, fileType: .mov)
            let settings: [String: Any] = [
                AVVideoCodecKey: AVVideoCodecType.hevc,
                AVVideoWidthKey: width,
                AVVideoHeightKey: height,
                AVVideoCompressionPropertiesKey: [
                    AVVideoAverageBitRateKey: 10_000_000,
                    AVVideoExpectedSourceFrameRateKey: 15,
                    AVVideoMaxKeyFrameIntervalKey: 15
                ]
            ]
            let inp = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
            inp.expectsMediaDataInRealTime = true
            // кадр с камеры лежит «на боку» — для просмотра поворачиваем, сами данные не трогаем
            inp.transform = CGAffineTransform(rotationAngle: .pi / 2)
            let ad = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: inp, sourcePixelBufferAttributes: [
                kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarFullRange,
                kCVPixelBufferWidthKey as String: width,
                kCVPixelBufferHeightKey as String: height
            ])
            guard w.canAdd(inp) else { return false }
            w.add(inp)
            guard w.startWriting() else { return false }
            w.startSession(atSourceTime: .zero)
            let jurl = dir.appendingPathComponent("frames.jsonl")
            FileManager.default.createFile(atPath: jurl.path, contents: nil)
            jsonl = try FileHandle(forWritingTo: jurl)
            writer = w; input = inp; adaptor = ad
            return true
        } catch {
            return false
        }
    }

    /// Добавить кадр (вызывать с главного потока, ~15 раз в секунду).
    func add(_ frame: ARFrame) {
        guard running else { return }
        if case .normal = frame.camera.trackingState {} else { return }
        guard frame.timestamp - lastT > 0.06 else { return }
        lastT = frame.timestamp
        let src = frame.capturedImage
        let w = CVPixelBufferGetWidth(src), h = CVPixelBufferGetHeight(src)
        if writer == nil {
            guard open(width: w, height: h) else { running = false; return }
            size = (w, h)
            t0 = frame.timestamp
        }
        guard size == (w, h) else { return }          // формат камеры сменился — кадр не того размера
        guard let ad = adaptor, let inp = input, inp.isReadyForMoreMediaData,
              let pool = ad.pixelBufferPool else { return }
        // копия кадра в свой буфер — ARKit не ждёт, пока кодируется видео
        var dst: CVPixelBuffer?
        CVPixelBufferPoolCreatePixelBuffer(nil, pool, &dst)
        guard let out = dst, Self.copy(src, to: out) else { return }

        let t = frame.camera.transform, k = frame.camera.intrinsics
        let rel = frame.timestamp - t0
        let i = index
        index += 1
        seconds = rel
        var depthName: String? = nil
        var depthData: Data? = nil
        if i % 3 == 0, let sd = frame.sceneDepth ?? frame.smoothedSceneDepth {   // «сырая» глубина: края чётче, шум усредню сам по кадрам
            depthName = String(format: "depth/%05d.bin", depthIndex)
            depthIndex += 1
            depthData = Self.pack(sd)
        }
        var rec: [String: Any] = [
            "i": i, "t": (rel * 1000).rounded() / 1000,
            "transform": [t.columns.0, t.columns.1, t.columns.2, t.columns.3].flatMap { [$0.x, $0.y, $0.z, $0.w] },
            "intrinsics": [k.columns.0, k.columns.1, k.columns.2].flatMap { [$0.x, $0.y, $0.z] },
            "w": w, "h": h
        ]
        if let d = depthName, let sd = frame.sceneDepth ?? frame.smoothedSceneDepth {
            rec["depth"] = d
            rec["dw"] = CVPixelBufferGetWidth(sd.depthMap)
            rec["dh"] = CVPixelBufferGetHeight(sd.depthMap)
        }
        let line = (try? JSONSerialization.data(withJSONObject: rec)) ?? Data()
        let dirURL = dir
        queue.async { [weak self] in
            guard let self = self, let ad = self.adaptor else { return }
            let pts = CMTime(seconds: rel, preferredTimescale: 600)
            if ad.assetWriterInput.isReadyForMoreMediaData { ad.append(out, withPresentationTime: pts) }
            self.jsonl?.write(line + Data([0x0A]))
            if let n = depthName, let d = depthData { try? d.write(to: dirURL.appendingPathComponent(n)) }
        }
    }

    /// Закончить запись. completion — папка с video.mov, frames.jsonl, depth/ (или nil, если записи не было).
    func finish(_ completion: @escaping (URL?) -> Void) {
        running = false
        queue.async {
            guard let w = self.writer, let inp = self.input else { completion(nil); return }
            inp.markAsFinished()
            try? self.jsonl?.close(); self.jsonl = nil
            let d = self.dir
            w.finishWriting {
                completion(w.status == .completed ? d : nil)
            }
            self.writer = nil; self.input = nil; self.adaptor = nil
        }
    }

    // MARK: служебное

    private static func copy(_ src: CVPixelBuffer, to dst: CVPixelBuffer) -> Bool {
        CVPixelBufferLockBaseAddress(src, .readOnly); CVPixelBufferLockBaseAddress(dst, [])
        defer { CVPixelBufferUnlockBaseAddress(src, .readOnly); CVPixelBufferUnlockBaseAddress(dst, []) }
        let planes = CVPixelBufferGetPlaneCount(src)
        guard planes == CVPixelBufferGetPlaneCount(dst), planes > 0 else { return false }
        for p in 0..<planes {
            guard let s = CVPixelBufferGetBaseAddressOfPlane(src, p),
                  let d = CVPixelBufferGetBaseAddressOfPlane(dst, p) else { return false }
            let sRow = CVPixelBufferGetBytesPerRowOfPlane(src, p), dRow = CVPixelBufferGetBytesPerRowOfPlane(dst, p)
            let rows = min(CVPixelBufferGetHeightOfPlane(src, p), CVPixelBufferGetHeightOfPlane(dst, p))
            let n = min(sRow, dRow)
            for r in 0..<rows { memcpy(d.advanced(by: r * dRow), s.advanced(by: r * sRow), n) }
        }
        return true
    }

    /// Глубина Float32 → Float16 (метры) + байт уверенности на точку.
    private static func pack(_ sd: ARDepthData) -> Data {
        let dm = sd.depthMap
        CVPixelBufferLockBaseAddress(dm, .readOnly); defer { CVPixelBufferUnlockBaseAddress(dm, .readOnly) }
        let w = CVPixelBufferGetWidth(dm), h = CVPixelBufferGetHeight(dm), row = CVPixelBufferGetBytesPerRow(dm)
        guard let base = CVPixelBufferGetBaseAddress(dm) else { return Data() }
        var out = Data(count: w * h * 3)
        out.withUnsafeMutableBytes { (o: UnsafeMutableRawBufferPointer) in
            let f16 = o.baseAddress!.assumingMemoryBound(to: Float16.self)
            for y in 0..<h {
                let r = base.advanced(by: y * row).assumingMemoryBound(to: Float32.self)
                for x in 0..<w { f16[y * w + x] = Float16(r[x]) }
            }
            if let cm = sd.confidenceMap {
                CVPixelBufferLockBaseAddress(cm, .readOnly)
                if let cb = CVPixelBufferGetBaseAddress(cm) {
                    let crow = CVPixelBufferGetBytesPerRow(cm)
                    let c8 = o.baseAddress!.advanced(by: w * h * 2).assumingMemoryBound(to: UInt8.self)
                    for y in 0..<h {
                        let r = cb.advanced(by: y * crow).assumingMemoryBound(to: UInt8.self)
                        for x in 0..<w { c8[y * w + x] = r[x] }
                    }
                }
                CVPixelBufferUnlockBaseAddress(cm, .readOnly)
            }
        }
        return out
    }
}
