import Foundation
import ARKit

/// Пишет LiDAR-сетку в OBJ (группы по типу поверхности) и сводку в JSON.
enum Exporter {
    static let classNames = ["other", "wall", "floor", "ceiling", "table", "seat", "window", "door"]

    struct PlaneInfo: Codable {
        var kind: String
        var transform: [Float]   // 4x4 по столбцам
        var width: Float
        var height: Float
    }
    struct Info: Codable {
        var app = "Zamer3D"
        var version = 3
        var created: String
        var units = "m"
        var upAxis = "Y"
        var vertices: Int
        var triangles: Int
        var measurements: [ScanMeasure]
        var planes: [PlaneInfo]
        var labels: [ScanLabel]
        var calibration: Calibration   // сетка в OBJ — сырая; поправку применяет обработка
        var device: String
        var photos: [KeyframeRecorder.Frame]
    }

    /// Пишет папку скана и возвращает её ZIP (один файл — удобно отправить).
    static func write(meshAnchors: [ARMeshAnchor], planes: [ARPlaneAnchor],
                      measurements: [ScanMeasure], labels: [ScanLabel], calibration: Calibration,
                      photos: (dir: URL, frames: [KeyframeRecorder.Frame])) throws -> URL {
        let df = DateFormatter()
        df.dateFormat = "yyyy-MM-dd_HH-mm"
        let stamp = df.string(from: Date())
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let dir = docs.appendingPathComponent("Скан_\(stamp)", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)

        var verts = ""
        verts.reserveCapacity(4_000_000)
        var groups = Array(repeating: "", count: classNames.count)
        var base = 0
        var vCount = 0
        var tCount = 0

        for anchor in meshAnchors {
            let g = anchor.geometry
            let m = anchor.transform
            let vb = g.vertices
            let vptr = vb.buffer.contents()
            for i in 0..<vb.count {
                let p = vptr.advanced(by: vb.offset + vb.stride * i)
                    .assumingMemoryBound(to: (Float, Float, Float).self).pointee
                let w = m * SIMD4<Float>(p.0, p.1, p.2, 1)
                verts += "v \(r(w.x)) \(r(w.y)) \(r(w.z))\n"
            }
            let f = g.faces
            let fptr = f.buffer.contents()
            let bpi = f.bytesPerIndex
            let cls = g.classification
            for j in 0..<f.count {
                var idx = [Int](repeating: 0, count: 3)
                for k in 0..<3 {
                    let at = fptr.advanced(by: (j * 3 + k) * bpi)
                    idx[k] = bpi == 4 ? Int(at.assumingMemoryBound(to: UInt32.self).pointee)
                                      : Int(at.assumingMemoryBound(to: UInt16.self).pointee)
                }
                var c = 0
                if let cls = cls {
                    let v = cls.buffer.contents().advanced(by: cls.offset + cls.stride * j)
                        .assumingMemoryBound(to: UInt8.self).pointee
                    c = Int(v) < classNames.count ? Int(v) : 0
                }
                groups[c] += "f \(base + idx[0] + 1) \(base + idx[1] + 1) \(base + idx[2] + 1)\n"
            }
            base += vb.count
            vCount += vb.count
            tCount += f.count
        }

        var obj = "# Zamer3D LiDAR scan, metres, Y up\n"
        obj += "# vertices \(vCount) triangles \(tCount)\n"
        obj += verts
        for (i, body) in groups.enumerated() where !body.isEmpty {
            obj += "g \(classNames[i])\n" + body
        }
        let objURL = dir.appendingPathComponent("room.obj")
        try obj.write(to: objURL, atomically: true, encoding: .utf8)

        let planeInfos: [PlaneInfo] = planes.map { p in
            let kind: String
            switch p.classification {
            case .wall: kind = "wall"
            case .floor: kind = "floor"
            case .ceiling: kind = "ceiling"
            case .table: kind = "table"
            case .seat: kind = "seat"
            case .window: kind = "window"
            case .door: kind = "door"
            default: kind = p.alignment == .vertical ? "vertical" : "horizontal"
            }
            let t = p.transform * p.center4
            let cols = [t.columns.0, t.columns.1, t.columns.2, t.columns.3]
            return PlaneInfo(kind: kind,
                             transform: cols.flatMap { [$0.x, $0.y, $0.z, $0.w] },
                             width: p.planeExtent.width,
                             height: p.planeExtent.height)
        }
        let iso = ISO8601DateFormatter().string(from: Date())
        // фото кадров
        let photoDir = dir.appendingPathComponent("photos", isDirectory: true)
        try FileManager.default.createDirectory(at: photoDir, withIntermediateDirectories: true)
        var saved: [KeyframeRecorder.Frame] = []
        for f in photos.frames {
            let src = photos.dir.appendingPathComponent(f.file)
            guard FileManager.default.fileExists(atPath: src.path) else { continue }
            try? FileManager.default.copyItem(at: src, to: photoDir.appendingPathComponent(f.file))
            saved.append(f)
        }
        let info = Info(created: iso, vertices: vCount, triangles: tCount,
                        measurements: measurements, planes: planeInfos, labels: labels,
                        calibration: calibration, device: deviceModel(), photos: saved)
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        let jsonURL = dir.appendingPathComponent("info.json")
        try enc.encode(info).write(to: jsonURL)
        return try zip(dir)
    }

    /// Системный способ упаковать папку в ZIP без сторонних библиотек.
    private static func zip(_ dir: URL) throws -> URL {
        let out = dir.deletingLastPathComponent().appendingPathComponent(dir.lastPathComponent + ".zip")
        try? FileManager.default.removeItem(at: out)
        var coordErr: NSError?
        var copyErr: Error?
        NSFileCoordinator().coordinate(readingItemAt: dir, options: .forUploading, error: &coordErr) { tmp in
            do { try FileManager.default.copyItem(at: tmp, to: out) } catch { copyErr = error }
        }
        if let e = coordErr { throw e }
        if let e = copyErr { throw e }
        return out
    }

    /// Модель телефона (например iPhone17,1) — калибровка привязана к конкретному датчику.
    private static func deviceModel() -> String {
        var s = utsname()
        uname(&s)
        return withUnsafeBytes(of: &s.machine) { raw in
            String(decoding: raw.prefix(while: { $0 != 0 }), as: UTF8.self)
        }
    }

    private static func r(_ v: Float) -> String {
        String(Double((v * 10000).rounded()) / 10000)
    }
}

extension ARPlaneAnchor {
    /// Сдвиг к центру плоскости с учётом поворота её экстента.
    var center4: simd_float4x4 {
        var m = matrix_identity_float4x4
        m.columns.3 = SIMD4<Float>(center.x, center.y, center.z, 1)
        return m * simd_float4x4(simd_quatf(angle: planeExtent.rotationOnYAxis, axis: [0, 1, 0]))
    }
}
