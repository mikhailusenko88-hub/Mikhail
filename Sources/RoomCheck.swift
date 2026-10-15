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

// MARK: - Препятствия: выступы у стен, ступеньки на полу, предметы RoomPlan, метки

/// Что мешает ставить мебель «ровно к стене»: короба, тумбы, шкафы, трапы, ступеньки, провода.
/// Координаты как у скана (мм), коробка: центр x,y,z, размеры w (вдоль стены), h, d (от стены), поворот rotY.
struct Obstacle: Codable {
    var kind: String      // bump — выступ у стены, step — ступенька/подиум, object — предмет RoomPlan, mark — метка
    var code: String
    var name: String
    var wall: String?
    var x: Int, y: Int, z: Int
    var w: Int, h: Int, d: Int
    var rotY: Double
    var fromFloorMm: Int
}

enum RoomObstacles {
    static func make(room: CapturedRoom, meshAnchors: [ARMeshAnchor], labels: [ScanLabel]) -> [Obstacle] {
        // точки сетки (центры треугольников): «прочее» и «пол» отдельно, потолок и двери не берём
        var pts: [SIMD3<Float>] = [], floorPts: [SIMD3<Float>] = []
        for a in meshAnchors {
            let g = a.geometry, m = a.transform, vb = g.vertices, fb = g.faces
            let vp = vb.buffer.contents(), fp = fb.buffer.contents(), bpi = fb.bytesPerIndex
            func v(_ i: Int) -> SIMD3<Float> {
                let p = vp.advanced(by: vb.offset + vb.stride * i).assumingMemoryBound(to: (Float, Float, Float).self).pointee
                let w = m * SIMD4<Float>(p.0, p.1, p.2, 1); return SIMD3(w.x, w.y, w.z)
            }
            for j in 0..<fb.count {
                var idx = [0, 0, 0]
                for k in 0..<3 {
                    let at = fp.advanced(by: (j * 3 + k) * bpi)
                    idx[k] = bpi == 4 ? Int(at.assumingMemoryBound(to: UInt32.self).pointee) : Int(at.assumingMemoryBound(to: UInt16.self).pointee)
                }
                var c = 0
                if let cl = g.classification {
                    c = Int(cl.buffer.contents().advanced(by: cl.offset + cl.stride * j).assumingMemoryBound(to: UInt8.self).pointee)
                }
                let p = (v(idx[0]) + v(idx[1]) + v(idx[2])) / 3
                if c == 2 { floorPts.append(p) } else if c != 3 && c != 7 { pts.append(p) }
            }
        }
        // стены комнаты: оба конца сходятся с другими стенами (отсекает короб, принятый за стену, и коридор за дверью)
        let all = room.walls
        func ends(_ s: CapturedRoom.Surface) -> [SIMD2<Float>] {
            let t = s.transform, c = SIMD2(t.columns.3.x, t.columns.3.z), u = simd_normalize(SIMD2(t.columns.0.x, t.columns.0.z))
            return [c - u * s.dimensions.x / 2, c + u * s.dimensions.x / 2]
        }
        let walls = all.enumerated().filter { i, s in
            ends(s).filter { e in all.enumerated().contains { j, o in j != i && ends(o).contains { simd_distance($0, e) < 0.25 } } }.count == 2
        }
        guard !walls.isEmpty else { return [] }
        let floorY = walls.map { $0.1.transform.columns.3.y - $0.1.dimensions.y / 2 }.min() ?? 0
        let cent = walls.reduce(SIMD3<Float>(0, 0, 0)) { $0 + SIMD3($1.1.transform.columns.3.x, $1.1.transform.columns.3.y, $1.1.transform.columns.3.z) } / Float(walls.count)
        let G: Float = 0.05
        var out: [Obstacle] = []
        var n = 1

        /// Области сетки: соседние клетки с похожей глубиной (±tol).
        func regions(_ P: [[Float]], tol: Float, minCells: Int) -> [[(Int, Int)]] {
            let H = P.count, W = P.first?.count ?? 0
            var seen = Array(repeating: Array(repeating: false, count: W), count: H), res: [[(Int, Int)]] = []
            for i in 0..<H { for j in 0..<W where P[i][j] > 0 && !seen[i][j] {
                var q = [(i, j)], cells: [(Int, Int)] = []; seen[i][j] = true
                while let (a, b) = q.popLast() {
                    cells.append((a, b))
                    for (x, y) in [(a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)] where x >= 0 && x < H && y >= 0 && y < W {
                        if !seen[x][y] && P[x][y] > 0 && abs(P[x][y] - P[a][b]) < tol { seen[x][y] = true; q.append((x, y)) }
                    }
                }
                if cells.count >= minCells { res.append(cells) }
            } }
            return res
        }
        func median(_ a: [Float]) -> Float { let s = a.sorted(); return s.isEmpty ? 0 : s[s.count / 2] }

        // выступы у каждой стены: ближайшая к стене поверхность в клетке 5×5 см
        for (wi, s) in walls {
            let T = s.transform, inv = T.inverse, w = s.dimensions.x, h = s.dimensions.y
            let sgn: Float = (inv * SIMD4<Float>(cent, 1)).z >= 0 ? 1 : -1
            let nu = Int(w / G) + 1, ny = Int(h / G) + 1
            var cell = Array(repeating: Array(repeating: [Float](), count: nu), count: ny)
            for p in pts {
                let l = inv * SIMD4<Float>(p, 1), z = l.z * sgn
                guard abs(l.x) < w / 2 - 0.05, z > -0.03, z < 0.6, l.y > -h / 2 + 0.06, l.y < h / 2 - 0.06 else { continue }
                cell[Int((l.y + h / 2) / G)][Int((l.x + w / 2) / G)].append(z)
            }
            var P = Array(repeating: Array(repeating: Float(0), count: nu), count: ny)
            for i in 0..<ny { for j in 0..<nu where cell[i][j].count >= 2 {
                let v = cell[i][j].sorted(), near = v[min(1, v.count - 1)]
                P[i][j] = near < 0.02 ? 0 : (near > 0.03 ? near : 0)
            } }
            for cells in regions(P, tol: 0.04, minCells: 4) {
                let ys = cells.map { $0.0 }, us = cells.map { $0.1 }
                let u0 = Float(us.min()!) * G, u1 = Float(us.max()! + 1) * G, y0 = Float(ys.min()!) * G, y1 = Float(ys.max()! + 1) * G
                guard (u1 - u0) * (y1 - y0) >= 0.02 else { continue }
                let dep = median(cells.map { P[$0.0][$0.1] })
                let c = T * SIMD4<Float>((u0 + u1) / 2 - w / 2, (y0 + y1) / 2 - h / 2, sgn * dep / 2, 1)
                let rot = Double(atan2(-T.columns.0.z, T.columns.0.x)) * 180 / .pi
                out.append(Obstacle(kind: "bump", code: "В\(n)", name: "выступ", wall: "С\(wi + 1)",
                                    x: Int(c.x * 1000), y: Int(c.y * 1000), z: Int(c.z * 1000),
                                    w: Int((u1 - u0) * 1000), h: Int((y1 - y0) * 1000), d: Int(dep * 1000), rotY: rot,
                                    fromFloorMm: Int((c.y - (y1 - y0) / 2 - floorY) * 1000)))
                n += 1
            }
        }

        // пол: подиумы, трапы, ступеньки (высота над основным полом 15–250 мм), только внутри комнаты
        let fl = floorPts + pts.filter { $0.y > floorY - 0.03 && $0.y < floorY + 0.3 }
        if fl.count > 100 {
            let x0 = fl.map { $0.x }.min()!, z0 = fl.map { $0.z }.min()!
            let nx = Int((fl.map { $0.x }.max()! - x0) / G) + 1, nz = Int((fl.map { $0.z }.max()! - z0) / G) + 1
            var cell = Array(repeating: Array(repeating: [Float](), count: nx), count: nz)
            for p in fl { cell[Int((p.z - z0) / G)][Int((p.x - x0) / G)].append(p.y) }
            var F = Array(repeating: Array(repeating: Float(0), count: nx), count: nz), all: [Float] = []
            for i in 0..<nz { for j in 0..<nx where cell[i][j].count >= 2 { let v = cell[i][j].sorted(); F[i][j] = v[v.count / 10]; all.append(F[i][j]) } }
            let base = all.sorted()[all.count / 5]
            var H = F
            for i in 0..<nz { for j in 0..<nx { H[i][j] = cell[i][j].count >= 2 && F[i][j] - base > 0.015 ? F[i][j] - base : 0 } }
            var k = 1
            for cells in regions(H, tol: 0.03, minCells: 6) {
                let hs = median(cells.map { H[$0.0][$0.1] }); guard hs <= 0.25 else { continue }
                let zs = cells.map { $0.0 }, xs = cells.map { $0.1 }
                let cx = x0 + Float(xs.min()! + xs.max()! + 1) * G / 2, cz = z0 + Float(zs.min()! + zs.max()! + 1) * G / 2
                let inside = walls.allSatisfy { _, s in
                    let inv = s.transform.inverse, sg: Float = (inv * SIMD4<Float>(cent, 1)).z >= 0 ? 1 : -1
                    return (inv * SIMD4<Float>(cx, floorY, cz, 1)).z * sg > -0.05
                }
                guard inside else { continue }
                out.append(Obstacle(kind: "step", code: "Ст\(k)", name: "ступенька / подиум", wall: nil,
                                    x: Int(cx * 1000), y: Int((base + hs / 2) * 1000), z: Int(cz * 1000),
                                    w: Int(Float(xs.max()! - xs.min()! + 1) * G * 1000), h: Int(hs * 1000),
                                    d: Int(Float(zs.max()! - zs.min()! + 1) * G * 1000), rotY: 0, fromFloorMm: 0))
                k += 1
            }
        }

        // предметы, которые узнал RoomPlan
        for (i, o) in room.objects.enumerated() {
            let t = o.transform, dm = o.dimensions
            let name: String
            switch o.category {
            case .storage: name = "шкаф / тумба"
            case .toilet: name = "унитаз"
            case .sink: name = "раковина"
            case .bathtub: name = "ванна"
            case .washerDryer: name = "стиральная машина"
            case .stove: name = "плита"
            case .oven: name = "духовка"
            case .refrigerator: name = "холодильник"
            case .dishwasher: name = "посудомойка"
            case .table: name = "стол"
            case .chair: name = "стул"
            case .sofa: name = "диван"
            case .bed: name = "кровать"
            case .fireplace: name = "камин"
            case .stairs: name = "лестница"
            case .television: name = "телевизор"
            @unknown default: name = "предмет"
            }
            out.append(Obstacle(kind: "object", code: "П\(i + 1)", name: name, wall: nil,
                                x: Int(t.columns.3.x * 1000), y: Int(t.columns.3.y * 1000), z: Int(t.columns.3.z * 1000),
                                w: Int(dm.x * 1000), h: Int(dm.y * 1000), d: Int(dm.z * 1000),
                                rotY: Double(atan2(-t.columns.0.z, t.columns.0.x)) * 180 / .pi,
                                fromFloorMm: Int((t.columns.3.y - dm.y / 2 - floorY) * 1000)))
        }

        // метки (провода, трубы, розетки): маленькие кубики 60 мм
        for (i, l) in labels.enumerated() where l.point.count >= 3 {
            out.append(Obstacle(kind: "mark", code: "М\(i + 1)", name: l.category.lowercased(), wall: nil,
                                x: Int(l.point[0] * 1000), y: Int(l.point[1] * 1000), z: Int(l.point[2] * 1000),
                                w: 60, h: 60, d: 60, rotY: 0, fromFloorMm: Int((l.point[1] - floorY) * 1000)))
        }
        return out
    }

    static func write(_ list: [Obstacle], to dir: URL) {
        let enc = JSONEncoder(); enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        if let d = try? enc.encode(list) { try? d.write(to: dir.appendingPathComponent("obstacles.json")) }
    }

    /// Строки для экрана «Проверка помещения».
    static func summary(_ list: [Obstacle]) -> String {
        var s: [String] = []
        let bumps = list.filter { $0.kind == "bump" && $0.d >= 30 && $0.w * $0.h >= 40_000 }
        if !bumps.isEmpty {
            s.append("Выступы у стен (Ш × В, выступ, от пола):")
            for b in bumps.sorted(by: { $0.wall ?? "" < $1.wall ?? "" }) { s.append("  \(b.code) на \(b.wall ?? "?"): \(b.w)×\(b.h), выступ \(b.d) мм, от пола \(b.fromFloorMm)") }
        }
        let steps = list.filter { $0.kind == "step" }
        if !steps.isEmpty { s.append("Пол:"); steps.forEach { s.append("  \($0.code): \($0.w)×\($0.d), выше пола на \($0.h) мм") } }
        let objs = list.filter { $0.kind == "object" }
        if !objs.isEmpty { s.append("Предметы:"); objs.forEach { s.append("  \($0.code) \($0.name): \($0.w)×\($0.h)×\($0.d)") } }
        return s.joined(separator: "\n")
    }
}
