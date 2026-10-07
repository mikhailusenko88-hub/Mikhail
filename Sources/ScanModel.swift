import Foundation
import SwiftUI
import ARKit
import RealityKit

enum MeasureKind: String, Codable { case distance, angle }

enum MeasureMode: String, CaseIterable, Identifiable {
    case distance = "Расстояние"
    case angle = "Угол"
    case label = "Метка"
    var id: String { rawValue }
}

/// Отметка на скане: что это и где. Позже по ним строятся препятствия для мебели.
struct ScanLabel: Codable {
    static let categories = ["Труба", "Вентиляция", "Канализация", "Вода", "Розетка",
                             "Выключатель", "Газ", "Короб", "Радиатор", "Другое"]
    var category: String
    var point: [Float]
    var pose: CapturePose
}

struct ScanMeasure: Codable {
    var kind: MeasureKind
    var points: [[Float]]      // сырые точки, метры: 2 для расстояния, 3 для угла (вершина — вторая)
    var dir: MeasureDir?       // направление (для расстояния)
    var raw: Double            // по датчику: мм или градусы
    var value: Double          // с учётом калибровки
    var reference: Double?     // эталон: лазер / рулетка / угломер
    var pose: CapturePose      // как держали телефон

    var text: String {
        kind == .distance ? "\(Int(value.rounded())) мм" : String(format: "%.1f°", value)
    }
}

final class ScanModel: NSObject, ObservableObject, ARSessionDelegate {
    let arView = ARView(frame: .zero, cameraMode: .ar, automaticallyConfigureSession: false)

    @Published var status = "Запуск…"
    @Published var measuring = false
    @Published var distanceText: String?
    @Published var measurements: [ScanMeasure] = []
    @Published var shareItem: ShareItem?
    @Published var confirmReset = false
    @Published var errorText: String?
    @Published var calibration = Calibration.load()
    @Published var showCalibration = false
    @Published var askReference = false
    @Published var referenceText = ""
    @Published var mode: MeasureMode = .distance
    @Published var labels: [ScanLabel] = []
    @Published var labelCategory = ScanLabel.categories[0]
    @Published var photoCount = 0
    @Published var rollDeg: Double = 0
    @Published var pitchDeg: Double = 0

    private var picks: [SIMD3<Float>] = []
    private var lastLevelUpdate: TimeInterval = 0
    private var markerAnchors: [AnchorEntity] = []      // текущий незаконченный замер
    private var history: [(kind: String, anchors: [AnchorEntity])] = []   // для «Отменить»
    let photos = KeyframeRecorder()
    private var statusTimer: Timer?
    private var tracking = "—"

    override init() {
        super.init()
        arView.session.delegate = self
        arView.renderOptions.insert(.disableMotionBlur)
    }

    // MARK: скан

    func startScan() {
        guard ARWorldTrackingConfiguration.supportsSceneReconstruction(.meshWithClassification) else {
            status = "Нет LiDAR на этом устройстве"
            errorText = "Для 3D-скана нужен iPhone/iPad Pro с LiDAR."
            return
        }
        let cfg = ARWorldTrackingConfiguration()
        cfg.sceneReconstruction = .meshWithClassification
        cfg.planeDetection = [.horizontal, .vertical]
        cfg.environmentTexturing = .none
        if ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) {
            cfg.frameSemantics.insert(.sceneDepth)
        }
        arView.debugOptions = [.showSceneUnderstanding]
        arView.session.run(cfg, options: [.resetTracking, .removeExistingAnchors])

        statusTimer?.invalidate()
        statusTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.refreshStatus()
        }
    }

    func resetScan() {
        clearMarkers()
        history.forEach { $0.anchors.forEach { arView.scene.removeAnchor($0) } }
        history.removeAll()
        labels.removeAll()
        photos.reset()
        photoCount = 0
        measurements.removeAll()
        distanceText = nil
        picks.removeAll()
        startScan()
    }

    private func meshAnchors() -> [ARMeshAnchor] {
        arView.session.currentFrame?.anchors.compactMap { $0 as? ARMeshAnchor } ?? []
    }

    private func refreshStatus() {
        let faces = meshAnchors().reduce(0) { $0 + $1.geometry.faces.count }
        status = "Сетка: \(faces.formatted()) треуг. · \(tracking)"
    }

    func session(_ session: ARSession, cameraDidChangeTrackingState camera: ARCamera) {
        let t: String
        switch camera.trackingState {
        case .normal: t = "отслеживание ок"
        case .notAvailable: t = "нет отслеживания"
        case .limited(let r):
            switch r {
            case .excessiveMotion: t = "медленнее!"
            case .insufficientFeatures: t = "мало деталей, больше света"
            case .initializing, .relocalizing: t = "настройка…"
            @unknown default: t = "ограничено"
            }
        }
        DispatchQueue.main.async { self.tracking = t }
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        DispatchQueue.main.async { self.errorText = "Ошибка AR: \(error.localizedDescription)" }
    }

    // MARK: уровень телефона

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        if photos.consider(frame) {
            DispatchQueue.main.async { self.photoCount = self.photos.count }
        }
        guard frame.timestamp - lastLevelUpdate > 0.1 else { return }
        lastLevelUpdate = frame.timestamp
        let (r, p) = Self.tilt(frame.camera.transform)
        DispatchQueue.main.async { self.rollDeg = r; self.pitchDeg = p }
    }

    /// Наклон телефона в портретной ориентации: влево/вправо и вверх/вниз, градусы.
    static func tilt(_ t: simd_float4x4) -> (roll: Double, pitch: Double) {
        let side = t.columns.1        // короткая сторона телефона
        let back = t.columns.2        // камера смотрит вдоль −Z
        let roll = asin(Double(max(-1, min(1, side.y)))) * 180 / .pi
        let pitch = asin(Double(max(-1, min(1, -back.y)))) * 180 / .pi
        return (roll, pitch)
    }

    // MARK: замеры

    func toggleMeasure() {
        measuring.toggle()
        picks.removeAll()
    }

    func setMode(_ m: MeasureMode) {
        mode = m
        picks.removeAll()
    }

    var hint: String {
        switch mode {
        case .distance: return picks.isEmpty ? "Коснись первой точки" : "Теперь вторую"
        case .angle: return ["Точка на первой стороне", "Теперь вершину угла", "Точка на второй стороне"][min(picks.count, 2)]
        case .label: return "Коснись: \(labelCategory.lowercased())"
        }
    }

    func handleTap(at point: CGPoint) {
        guard measuring else { return }
        let hit = arView.raycast(from: point, allowing: .existingPlaneGeometry, alignment: .any).first
            ?? arView.raycast(from: point, allowing: .estimatedPlane, alignment: .any).first
        guard let r = hit else { return }
        let c = r.worldTransform.columns.3
        let p = SIMD3<Float>(c.x, c.y, c.z)
        if mode == .label {
            addMarker(at: p, color: .systemPink, radius: 0.015)
            labels.append(ScanLabel(category: labelCategory, point: arr(p), pose: capturePose([p])))
            commitHistory("label")
            distanceText = labelCategory
            return
        }
        addMarker(at: p)
        if let prev = picks.last { addLine(from: prev, to: p) }
        picks.append(p)
        objectWillChange.send()

        let need = mode == .distance ? 2 : 3
        guard picks.count == need else { distanceText = nil; return }

        let pose = capturePose(picks)
        var m: ScanMeasure
        if mode == .distance {
            let a = picks[0], b = picks[1], d = b - a
            let dir = MeasureDir.of(d.x, d.y, d.z)
            let raw = Double(simd_distance(a, b)) * 1000
            m = ScanMeasure(kind: .distance, points: [arr(a), arr(b)], dir: dir, raw: raw,
                            value: Double(calibration.apply(raw, dir: dir)), reference: nil, pose: pose)
        } else {
            let u = simd_normalize(picks[0] - picks[1]), v = simd_normalize(picks[2] - picks[1])
            let raw = acos(Double(max(-1, min(1, simd_dot(u, v))))) * 180 / .pi
            m = ScanMeasure(kind: .angle, points: picks.map(arr), dir: nil, raw: raw,
                            value: calibration.applyAngle(raw), reference: nil, pose: pose)
        }
        measurements.append(m)
        commitHistory("measure")
        distanceText = m.text
        picks.removeAll()
    }

    private func arr(_ p: SIMD3<Float>) -> [Float] { [p.x, p.y, p.z] }

    private func commitHistory(_ kind: String) {
        history.append((kind, markerAnchors))
        markerAnchors.removeAll()
    }

    /// Отменить: сначала незаконченный замер, иначе последний замер или метку.
    func undo() {
        if !picks.isEmpty {
            clearMarkers(); picks.removeAll(); return
        }
        guard let last = history.popLast() else { return }
        last.anchors.forEach { arView.scene.removeAnchor($0) }
        if last.kind == "label" { _ = labels.popLast() } else { _ = measurements.popLast() }
        distanceText = measurements.last?.text
    }

    var canUndo: Bool { !picks.isEmpty || !history.isEmpty }

    private func capturePose(_ pts: [SIMD3<Float>]) -> CapturePose {
        guard let t = arView.session.currentFrame?.camera.transform else {
            return CapturePose(rollDeg: 0, pitchDeg: 0, distAmm: 0, distBmm: 0)
        }
        let cam = SIMD3<Float>(t.columns.3.x, t.columns.3.y, t.columns.3.z)
        let (r, p) = Self.tilt(t)
        return CapturePose(rollDeg: r, pitchDeg: p,
                           distAmm: Double(simd_distance(cam, pts.first!)) * 1000,
                           distBmm: Double(simd_distance(cam, pts.last!)) * 1000)
    }

    // MARK: калибровка

    /// Последний замер отмечается эталоном: вводим, что показал лазер / рулетка / угломер.
    func saveReference() {
        let cleaned = referenceText.replacingOccurrences(of: ",", with: ".")
            .filter { $0.isNumber || $0 == "." }
        guard let truth = Double(cleaned), truth > 0, var last = measurements.last else {
            errorText = "Введи число: миллиметры для расстояния или градусы для угла."
            return
        }
        last.reference = truth
        measurements[measurements.count - 1] = last
        if last.kind == .distance, let dir = last.dir {
            calibration.add(Calibration.Sample(rawMm: last.raw, trueMm: truth, dir: dir,
                                               a: last.points[0], b: last.points[1], pose: last.pose))
        } else {
            calibration.addAngle(raw: last.raw, truth: truth)
        }
        calibration.save()
        recalcMeasurements()
        referenceText = ""
    }

    func removeSample(_ id: UUID) {
        calibration.remove(id: id)
        calibration.save()
        recalcMeasurements()
    }

    func resetCalibration() {
        calibration = Calibration()
        calibration.save()
        recalcMeasurements()
    }

    private func recalcMeasurements() {
        for i in measurements.indices {
            let m = measurements[i]
            measurements[i].value = m.kind == .distance
                ? Double(calibration.apply(m.raw, dir: m.dir ?? .horizontal))
                : calibration.applyAngle(m.raw)
        }
        if let last = measurements.last { distanceText = last.text }
    }

    private func addMarker(at p: SIMD3<Float>, color: UIColor = .orange, radius: Float = 0.008) {
        let anchor = AnchorEntity(world: p)
        let ball = ModelEntity(mesh: .generateSphere(radius: radius),
                               materials: [UnlitMaterial(color: color)])
        anchor.addChild(ball)
        arView.scene.addAnchor(anchor)
        markerAnchors.append(anchor)
    }

    private func addLine(from a: SIMD3<Float>, to b: SIMD3<Float>) {
        let len = simd_distance(a, b)
        let mid = (a + b) / 2
        let anchor = AnchorEntity(world: mid)
        let line = ModelEntity(mesh: .generateBox(size: [0.003, 0.003, len]),
                               materials: [UnlitMaterial(color: .orange)])
        anchor.addChild(line)
        arView.scene.addAnchor(anchor)
        line.look(at: b, from: mid, relativeTo: nil)
        markerAnchors.append(anchor)
    }

    private func clearMarkers() {
        markerAnchors.forEach { arView.scene.removeAnchor($0) }
        markerAnchors.removeAll()
    }

    // MARK: сохранение

    func export() {
        let anchors = meshAnchors()
        guard !anchors.isEmpty else {
            errorText = "Сетка ещё пустая. Поводи телефоном по комнате."
            return
        }
        let planes = arView.session.currentFrame?.anchors.compactMap { $0 as? ARPlaneAnchor } ?? []
        let meas = measurements
        let labs = labels
        let cal = calibration
        let photoSet = photos.snapshot()
        status = "Сохраняю…"
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                let zip = try Exporter.write(meshAnchors: anchors, planes: planes, measurements: meas,
                                             labels: labs, calibration: cal, photos: photoSet)
                DispatchQueue.main.async {
                    self.status = "Сохранено: \(zip.lastPathComponent)"
                    self.shareItem = ShareItem(urls: [zip])
                }
            } catch {
                DispatchQueue.main.async { self.errorText = "Не удалось сохранить: \(error.localizedDescription)" }
            }
        }
    }
}
