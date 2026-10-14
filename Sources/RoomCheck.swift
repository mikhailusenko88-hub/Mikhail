import Foundation
import ARKit
import RoomPlan
import simd

/// Проверка помещения по скану: углы между стенами, завал и бугры стен, перепад пола,
/// и привязка меток коммуникаций (высота от пола, расстояние до ближайшего угла).
/// Считается по стенам RoomPlan + сетке LiDAR. Пишется в room_check.json и показывается после сохранения.
struct RoomCheck: Codable {
    struct Corner: Codable {
        var walls: String          // «С1–С2»
        var angle: Double          // градусы
        var offMmPerM: Double      // отклонение от 90° в мм на 1 м
    }
    struct Wall: Codable {
        var code: String
        var lengthMm: Int
        var heightMm: Int
        var tiltMm: Double?        // завал по высоте: верх относительно низа, мм (+ — верх в комнату)
        var bumpMm: Double?        // бугры/ямы: размах точек сетки относительно плоскости, мм
        var points: Int
    }
    struct Mark: Codable {
        var category: String
        var heightMm: Int          // от пола
        var wall: String?          // ближайшая стена
        var fromCornerMm: Int?     // от ближайшего угла этой стены
        var toWallMm: Int?         // отступ от стены
    }
    var corners: [Corner] = []
    var walls: [Wall] = []
    var floorDropMm: Double?       // перепад пола (по сетке «пол»), мм
    var marks: [Mark] = []

    static func make(room: CapturedRoom, meshAnchors: [ARMeshAnchor], labels: [ScanLabel]) -> RoomCheck {
        var out = RoomCheck()
        let ws = room.walls
        guard !ws.isEmpty else { return out }

        // концы стен в плане (XZ)
        struct W { let code: String; let m: simd_float4x4; let w: Float; let h: Float
                   var c: SIMD3<Float> { SIMD3(m.columns.3.x, m.columns.3.y, m.columns.3.z) }
                   var ax: SIMD3<Float> { simd_normalize(SIMD3(m.columns.0.x, m.columns.0.y, m.columns.0.z)) }
                   var nz: SIMD3<Float> { simd_normalize(SIMD3(m.columns.2.x, m.columns.2.y, m.columns.2.z)) }
                   var a: SIMD3<Float> { c - ax * (w / 2) }
                   var b: SIMD3<Float> { c + ax * (w / 2) } }
        let walls = ws.enumerated().map { i, s in W(code: "С\(i + 1)", m: s.transform, w: s.dimensions.x, h: s.dimensions.y) }
        let floorY = walls.map { $0.c.y - $0.h / 2 }.min() ?? 0
        let flat = { (p: SIMD3<Float>) in SIMD2<Float>(p.x, p.z) }

        // углы: пары стен, чьи концы сходятся ближе 20 см
        for i in 0..<walls.count {
            for j in (i + 1)..<walls.count {
                let A = walls[i], B = walls[j]
                let ends = [(A.a, B.a), (A.a, B.b), (A.b, B.a), (A.b, B.b)]
                guard ends.contains(where: { simd_distance(flat($0.0), flat($0.1)) < 0.2 }) else { continue }
                let d1 = simd_normalize(flat(A.ax)), d2 = simd_normalize(flat(B.ax))
                let ang = Double(acos(max(-1, min(1, abs(simd_dot(d1, d2)))))) * 180 / .pi   // 90 — прямой угол
                let off = abs(90 - ang)
                out.corners.append(Corner(walls: "\(A.code)–\(B.code)", angle: (ang * 10).rounded() / 10,
                                          offMmPerM: (tan(off * .pi / 180) * 1000 * 10).rounded() / 10))
            }
        }

        // точки сетки в мировых координатах (с классом)
        var pts: [SIMD3<Float>] = []
        pts.reserveCapacity(200_000)
        for anchor in meshAnchors {
            let g = anchor.geometry, m = anchor.transform, vb = g.vertices
            let vptr = vb.buffer.contents()
            for i in 0..<vb.count {
                let p = vptr.advanced(by: vb.offset + vb.stride * i).assumingMemoryBound(to: (Float, Float, Float).self).pointee
                let w = m * SIMD4<Float>(p.0, p.1, p.2, 1)
                pts.append(SIMD3(w.x, w.y, w.z))
            }
        }

        // стены: точки в прямоугольнике стены (с отступом 7 см от краёв) и в слое ±6 см от плоскости
        for W in walls {
            var dz: [Float] = [], top: [Float] = [], bot: [Float] = []
            let inv = W.m.inverse
            for p in pts {
                let l = inv * SIMD4<Float>(p.x, p.y, p.z, 1)
                guard abs(l.x) < W.w / 2 - 0.07, abs(l.y) < W.h / 2 - 0.07, abs(l.z) < 0.06 else { continue }
                dz.append(l.z)
                if l.y > W.h / 2 - 0.35 { top.append(l.z) } else if l.y < -W.h / 2 + 0.35 { bot.append(l.z) }
            }
            var tilt: Double? = nil, bump: Double? = nil
            if top.count > 30 && bot.count > 30 {
                let mt = top.reduce(0, +) / Float(top.count), mb = bot.reduce(0, +) / Float(bot.count)
                tilt = Double(((mt - mb) * 1000 * 10).rounded() / 10)
            }
            if dz.count > 100 {
                let s = dz.sorted(), lo = s[s.count * 3 / 100], hi = s[s.count * 97 / 100]   // без выбросов
                bump = Double(((hi - lo) * 1000 * 10).rounded() / 10)
            }
            out.walls.append(Wall(code: W.code, lengthMm: Int((W.w * 1000).rounded()), heightMm: Int((W.h * 1000).rounded()),
                                  tiltMm: tilt, bumpMm: bump, points: dz.count))
        }

        // пол: точки у пола внутри комнаты (±8 см от уровня пола)
        let fl = pts.filter { abs($0.y - floorY) < 0.08 }.map { $0.y }.sorted()
        if fl.count > 200 {
            out.floorDropMm = Double(((fl[fl.count * 97 / 100] - fl[fl.count * 3 / 100]) * 1000 * 10).rounded() / 10)
        }

        // метки: высота от пола, ближайшая стена, расстояние от её ближайшего конца (угла)
        for lab in labels where lab.point.count >= 3 {
            let p = SIMD3<Float>(lab.point[0], lab.point[1], lab.point[2])
            var best: (W, Float, Float)? = nil   // стена, расстояние до плоскости, положение вдоль
            for W in walls {
                let l = W.m.inverse * SIMD4<Float>(p.x, p.y, p.z, 1)
                guard abs(l.x) < W.w / 2 + 0.1 else { continue }
                if best == nil || abs(l.z) < best!.1 { best = (W, abs(l.z), l.x) }
            }
            var m = Mark(category: lab.category, heightMm: Int(((p.y - floorY) * 1000).rounded()))
            if let (W, d, x) = best, d < 0.6 {
                m.wall = W.code
                m.toWallMm = Int((d * 1000).rounded())
                m.fromCornerMm = Int(((W.w / 2 - abs(x)) * 1000).rounded())
            }
            out.marks.append(m)
        }
        return out
    }

    /// Текст для экрана после сохранения.
    var summary: String {
        var s: [String] = []
        if !corners.isEmpty {
            s.append("Углы между стенами:")
            for c in corners {
                let flag = c.offMmPerM > 10 ? "  ⚠︎" : ""
                s.append("  \(c.walls): \(String(format: "%.1f", c.angle))° · \(String(format: "%.0f", c.offMmPerM)) мм на 1 м\(flag)")
            }
        }
        if !walls.isEmpty {
            s.append("Стены:")
            for w in walls {
                var line = "  \(w.code): \(w.lengthMm)×\(w.heightMm)"
                if let t = w.tiltMm { line += " · завал \(String(format: "%+.0f", t)) мм" }
                if let b = w.bumpMm { line += " · неровность \(String(format: "%.0f", b)) мм" }
                if w.tiltMm == nil && w.bumpMm == nil { line += " · мало точек сетки" }
                s.append(line)
            }
        }
        if let f = floorDropMm { s.append("Пол: перепад \(String(format: "%.0f", f)) мм") }
        if !marks.isEmpty {
            s.append("Метки:")
            for m in marks {
                var line = "  \(m.category): \(m.heightMm) мм от пола"
                if let w = m.wall, let c = m.fromCornerMm { line += " · \(w), \(c) мм от угла" }
                s.append(line)
            }
        }
        s.append("Точность — примерно ±5–10 мм, критичное перемерьте рулеткой или лазером.")
        return s.joined(separator: "\n")
    }

    func write(to dir: URL) {
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        if let d = try? enc.encode(self) { try? d.write(to: dir.appendingPathComponent("room_check.json")) }
    }
}
