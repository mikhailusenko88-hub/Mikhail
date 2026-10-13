import Foundation
import ARKit
import RealityKit

/// Своя копия LiDAR-сетки и её отрисовка с покрытием.
///
/// Раньше сетку рисовал отладочный режим ARKit: если ARKit выкидывал кусок сетки
/// (отвернулся, потерял отслеживание, пересобрал карту) — он пропадал и с экрана,
/// и из сохранения. Теперь каждый кусок хранится у нас, пока скан не начат заново.
///
/// Цвет: красный — снято плохо, зелёный — хорошо.
/// Стена / пол / потолок зелёные, только когда треугольник ровный (стена вертикальна,
/// пол горизонтален) и кусок обновлялся несколько раз; мятая сетка на ровной стене — красная.
/// Остальное (трубы, мебель, короба) зелёное, когда кусок увидели с нескольких ракурсов.
final class MeshCoverage {
    private struct Entry {
        var anchor: ARMeshAnchor
        var bufferID: ObjectIdentifier
        var faces: Int
        var version: Int
        var dirty: Bool
        var holder: AnchorEntity?
        var green: Int = 0
        var total: Int = 0
    }

    private struct Built {
        var positions: [SIMD3<Float>]
        var indices: [UInt32]
        var perFace: [UInt32]
        var green: Int
        var total: Int
    }

    private weak var view: ARView?
    private var entries: [UUID: Entry] = [:]
    private var lastBuild: TimeInterval = 0
    private var inFlight = 0
    private var generation = 0
    private let queue = DispatchQueue(label: "mesh-coverage", qos: .userInitiated)
    private let materials: [RealityKit.Material]

    init(view: ARView) {
        self.view = view
        var red = UnlitMaterial(color: UIColor(red: 1, green: 0.15, blue: 0.1, alpha: 1))
        red.blending = .transparent(opacity: .init(floatLiteral: 0.38))
        var green = UnlitMaterial(color: UIColor(red: 0.1, green: 0.9, blue: 0.3, alpha: 1))
        green.blending = .transparent(opacity: .init(floatLiteral: 0.30))
        materials = [red, green]
    }

    var isEmpty: Bool { entries.isEmpty }

    /// Все куски сетки, что видели за скан (для сохранения).
    var anchors: [ARMeshAnchor] { entries.values.map { $0.anchor } }

    var faceCount: Int { entries.values.reduce(0) { $0 + $1.anchor.geometry.faces.count } }

    /// Процент хорошо снятой поверхности (по треугольникам).
    var coveragePercent: Int {
        let t = entries.values.reduce(0) { $0 + $1.total }
        guard t > 0 else { return 0 }
        let g = entries.values.reduce(0) { $0 + $1.green }
        return Int((Double(g) / Double(t) * 100).rounded())
    }

    func reset() {
        generation += 1
        inFlight = 0
        for e in entries.values { if let h = e.holder { view?.scene.removeAnchor(h) } }
        entries.removeAll()
    }

    /// Принять текущие куски сетки из кадра ARKit. Пропавшие куски НЕ удаляются.
    func ingest(_ anchors: [ARMeshAnchor], now: TimeInterval) {
        for a in anchors {
            let bid = ObjectIdentifier(a.geometry.vertices.buffer as AnyObject)
            let fc = a.geometry.faces.count
            if var e = entries[a.identifier] {
                if e.bufferID != bid || e.faces != fc {
                    e.version += 1
                    e.dirty = true
                    e.bufferID = bid
                    e.faces = fc
                }
                e.anchor = a
                e.holder?.transform = Transform(matrix: a.transform)
                entries[a.identifier] = e
            } else {
                entries[a.identifier] = Entry(anchor: a, bufferID: bid, faces: fc, version: 1, dirty: true)
            }
        }
        guard inFlight == 0, now - lastBuild > 0.5 else { return }
        lastBuild = now
        let dirty = entries.filter { $0.value.dirty }.prefix(12)
        guard !dirty.isEmpty else { return }
        let gen = generation
        for (id, e) in dirty {
            entries[id]?.dirty = false
            inFlight += 1
            let anchor = e.anchor
            let version = e.version
            queue.async { [weak self] in
                let built = Self.build(anchor, version: version)
                DispatchQueue.main.async { self?.apply(built, id: id, anchor: anchor, gen: gen) }
            }
        }
    }

    private func apply(_ b: Built?, id: UUID, anchor: ARMeshAnchor, gen: Int) {
        guard gen == generation else { return }
        inFlight = max(0, inFlight - 1)
        guard let b = b, var e = entries[id], let view = view else { return }
        var d = MeshDescriptor(name: "scan")
        d.positions = MeshBuffers.Positions(b.positions)
        d.primitives = .triangles(b.indices)
        d.materials = .perFace(b.perFace)
        guard let mesh = try? MeshResource.generate(from: [d]) else { return }
        if let holder = e.holder, let model = holder.children.first as? ModelEntity {
            model.model = ModelComponent(mesh: mesh, materials: materials)
            holder.transform = Transform(matrix: e.anchor.transform)
        } else {
            let holder = AnchorEntity(world: e.anchor.transform)
            holder.addChild(ModelEntity(mesh: mesh, materials: materials))
            view.scene.addAnchor(holder)
            e.holder = holder
        }
        e.green = b.green
        e.total = b.total
        entries[id] = e
    }

    /// Готовит геометрию куска и решает цвет каждого треугольника.
    private static func build(_ a: ARMeshAnchor, version: Int) -> Built? {
        let g = a.geometry
        let vb = g.vertices
        let fb = g.faces
        guard vb.count > 0, fb.count > 0 else { return nil }
        let vptr = vb.buffer.contents()
        var pos = [SIMD3<Float>](repeating: .zero, count: vb.count)
        for i in 0..<vb.count {
            let p = vptr.advanced(by: vb.offset + vb.stride * i)
                .assumingMemoryBound(to: (Float, Float, Float).self).pointee
            pos[i] = SIMD3<Float>(p.0, p.1, p.2)
        }
        let m = a.transform
        let rot = simd_float3x3(SIMD3<Float>(m.columns.0.x, m.columns.0.y, m.columns.0.z),
                                SIMD3<Float>(m.columns.1.x, m.columns.1.y, m.columns.1.z),
                                SIMD3<Float>(m.columns.2.x, m.columns.2.y, m.columns.2.z))
        let fptr = fb.buffer.contents()
        let bpi = fb.bytesPerIndex
        let cls = g.classification
        var idx = [UInt32](repeating: 0, count: fb.count * 3)
        var mat = [UInt32](repeating: 0, count: fb.count)
        var green = 0
        for j in 0..<fb.count {
            for k in 0..<3 {
                let at = fptr.advanced(by: (j * 3 + k) * bpi)
                idx[j * 3 + k] = bpi == 4 ? at.assumingMemoryBound(to: UInt32.self).pointee
                                          : UInt32(at.assumingMemoryBound(to: UInt16.self).pointee)
            }
            var c = 0
            if let cls = cls {
                c = Int(cls.buffer.contents().advanced(by: cls.offset + cls.stride * j)
                    .assumingMemoryBound(to: UInt8.self).pointee)
            }
            let p0 = pos[Int(idx[j * 3])], p1 = pos[Int(idx[j * 3 + 1])], p2 = pos[Int(idx[j * 3 + 2])]
            let cr = simd_cross(p1 - p0, p2 - p0)
            let len = simd_length(cr)
            var good = false
            if len > 1e-9 {
                let n = rot * (cr / len)
                switch c {
                case 1, 6, 7:      // стена, окно, дверь — должна быть вертикальной
                    good = version >= 2 && abs(n.y) < 0.2
                case 2, 3:         // пол, потолок — горизонтальные
                    good = version >= 2 && abs(n.y) > 0.97
                default:           // трубы, мебель, прочее — увидели несколько раз
                    good = version >= 3
                }
            }
            if good { mat[j] = 1; green += 1 }
        }
        return Built(positions: pos, indices: idx, perFace: mat, green: green, total: fb.count)
    }
}
