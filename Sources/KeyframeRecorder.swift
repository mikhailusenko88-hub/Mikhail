import Foundation
import ARKit
import CoreImage
import ImageIO

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
        let name = String(format: "frame_%04d.jpg", idx)
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
                                                 options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: 0.75]) {
                try? data.write(to: url)
            }
            lock.lock(); self.frames.append(rec); lock.unlock()
        }
        return true
    }

    /// Папка с фото и список кадров (дожидается записи последних).
    func snapshot() -> (dir: URL, frames: [Frame]) {
        queue.sync {}
        lock.lock(); defer { lock.unlock() }
        return (dir, frames.sorted { $0.file < $1.file })
    }
}
