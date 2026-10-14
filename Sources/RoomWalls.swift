import Foundation
import ARKit
import RealityKit
import RoomPlan

/// Стена / окно / дверь / проём от RoomPlan — в миллиметрах, для info.json.
struct RoomSurface: Codable {
    var kind: String          // wall, door, window, opening
    var code: String          // С1, С2… / О1… / Д1… / П1…
    var widthMm: Int
    var heightMm: Int
    var transform: [Float]    // 4x4 по столбцам, в системе скана (та же, что room.obj)
    var confidence: String
}

/// Движок Apple RoomPlan поверх того же AR-сеанса, что и LiDAR-скан:
/// сам находит стены, окна, двери, проёмы и даёт их размеры.
final class RoomWalls: NSObject, RoomCaptureSessionDelegate {
    static var isSupported: Bool { RoomCaptureSession.isSupported }

    private weak var view: ARView?
    private var session: RoomCaptureSession?
    private var holder: AnchorEntity?
    private var lastRedraw: TimeInterval = 0
    private(set) var room: CapturedRoom?
    private(set) var running = false

    var onUpdate: ((String) -> Void)?        // сводка: «Стен 4 · окон 1 · дверей 1»
    var onInstruction: ((String?) -> Void)?  // подсказка RoomPlan по-русски
    var onFail: ((String) -> Void)?          // RoomPlan остановился с ошибкой

    init(view: ARView) { self.view = view }

    func start(on arSession: ARSession) {
        let s = RoomCaptureSession(arSession: arSession)
        s.delegate = self
        session = s
        running = true
        s.run(configuration: RoomCaptureSession.Configuration())
    }

    /// Остановить поиск стен. Найденное остаётся (и на экране, и для сохранения).
    func stop(pauseARSession: Bool) {
        guard running else { return }
        running = false
        session?.stop(pauseARSession: pauseARSession)
    }

    func clear() {
        stop(pauseARSession: false)
        if let h = holder { view?.scene.removeAnchor(h) }
        holder = nil
        room = nil
        session = nil
    }

    // MARK: RoomCaptureSessionDelegate

    func captureSession(_ session: RoomCaptureSession, didUpdate room: CapturedRoom) {
        DispatchQueue.main.async { self.take(room) }
    }

    func captureSession(_ session: RoomCaptureSession, didProvide instruction: RoomCaptureSession.Instruction) {
        let t: String?
        switch instruction {
        case .moveCloseToWall: t = "Подойди ближе к стене"
        case .moveAwayFromWall: t = "Отойди от стены"
        case .slowDown: t = "Медленнее"
        case .turnOnLight: t = "Нужно больше света"
        case .lowTexture: t = "Мало деталей — больше света"
        case .normal: t = nil
        @unknown default: t = nil
        }
        DispatchQueue.main.async { self.onInstruction?(t) }
    }

    func captureSession(_ session: RoomCaptureSession, didEndWith data: CapturedRoomData, error: Error?) {
        guard let e = error else { return }
        DispatchQueue.main.async {
            guard self.running else { return }
            self.running = false
            self.onFail?(e.localizedDescription)
        }
    }

    private func take(_ room: CapturedRoom) {
        guard running else { return }
        self.room = room
        onUpdate?("Стен \(room.walls.count) · окон \(room.windows.count) · дверей \(room.doors.count)"
                  + (room.openings.isEmpty ? "" : " · проёмов \(room.openings.count)"))
        let now = CACurrentMediaTime()
        guard now - lastRedraw > 0.4 else { return }
        lastRedraw = now
        redraw(room)
    }

    // MARK: Отрисовка: стены синие, окна голубые, двери/проёмы жёлтые, с кодом и размером

    private func redraw(_ room: CapturedRoom) {
        guard let view = view else { return }
        if let h = holder { view.scene.removeAnchor(h) }
        let root = AnchorEntity(world: matrix_identity_float4x4)
        for s in Self.surfaces(room) {
            let color: UIColor
            let depth: Float
            switch s.kind {
            case "wall": color = .systemBlue; depth = 0.01
            case "window": color = .cyan; depth = 0.03
            default: color = .systemYellow; depth = 0.03
            }
            var mat = UnlitMaterial(color: color)
            mat.blending = .transparent(opacity: .init(floatLiteral: s.kind == "wall" ? 0.18 : 0.35))
            let w = Float(s.widthMm) / 1000, h = Float(s.heightMm) / 1000
            let box = ModelEntity(mesh: .generateBox(size: [w, h, depth]), materials: [mat])
            box.transform = Transform(matrix: Self.matrix(s.transform))
            root.addChild(box)

            // подпись с двух сторон стены
            let text = "\(s.code)  \(s.widthMm)×\(s.heightMm)"
            let mesh = MeshResource.generateText(text, extrusionDepth: 0.002,
                                                 font: .systemFont(ofSize: 0.07, weight: .bold),
                                                 containerFrame: .zero, alignment: .center,
                                                 lineBreakMode: .byWordWrapping)
            let tw = mesh.bounds.extents.x
            let yUp: Float = s.kind == "wall" ? 0.15 : 0
            for side in [Float(1), -1] {
                let label = ModelEntity(mesh: mesh, materials: [UnlitMaterial(color: .white)])
                label.position = [side * -tw / 2, yUp, side * (depth / 2 + 0.01)]
                if side < 0 { label.orientation = simd_quatf(angle: .pi, axis: [0, 1, 0]) }
                box.addChild(label)
            }
        }
        view.scene.addAnchor(root)
        holder = root
    }

    // MARK: Для сохранения

    static func surfaces(_ room: CapturedRoom) -> [RoomSurface] {
        func pack(_ list: [CapturedRoom.Surface], kind: String, prefix: String) -> [RoomSurface] {
            list.enumerated().map { i, s in
                let t = s.transform
                let cols = [t.columns.0, t.columns.1, t.columns.2, t.columns.3]
                let conf: String
                switch s.confidence {
                case .high: conf = "high"
                case .medium: conf = "medium"
                case .low: conf = "low"
                @unknown default: conf = "unknown"
                }
                return RoomSurface(kind: kind, code: "\(prefix)\(i + 1)",
                                   widthMm: Int((s.dimensions.x * 1000).rounded()),
                                   heightMm: Int((s.dimensions.y * 1000).rounded()),
                                   transform: cols.flatMap { [$0.x, $0.y, $0.z, $0.w] },
                                   confidence: conf)
            }
        }
        return pack(room.walls, kind: "wall", prefix: "С")
            + pack(room.windows, kind: "window", prefix: "О")
            + pack(room.doors, kind: "door", prefix: "Д")
            + pack(room.openings, kind: "opening", prefix: "П")
    }

    private static func matrix(_ a: [Float]) -> simd_float4x4 {
        simd_float4x4(SIMD4<Float>(a[0], a[1], a[2], a[3]), SIMD4<Float>(a[4], a[5], a[6], a[7]),
                      SIMD4<Float>(a[8], a[9], a[10], a[11]), SIMD4<Float>(a[12], a[13], a[14], a[15]))
    }

    /// Пишет room_plan.json (полные данные RoomPlan) и room_plan.usdz (модель стен) в папку скана.
    static func write(_ room: CapturedRoom, to dir: URL) {
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        if let data = try? enc.encode(room) {
            try? data.write(to: dir.appendingPathComponent("room_plan.json"))
        }
        try? room.export(to: dir.appendingPathComponent("room_plan.usdz"))
    }
}
