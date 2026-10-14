import SwiftUI
import ARKit
import RealityKit
import UniformTypeIdentifiers

// MARK: - Кухня из файла kitchen.json

/// Модуль мебели — коробка. Координаты в системе скана (та же, что в room.obj), миллиметры.
/// x, y, z — центр коробки; w — ширина (вдоль X), h — высота (вдоль Y), d — глубина (вдоль Z);
/// rotY — поворот вокруг вертикали, градусы.
struct KitchenModule: Codable, Identifiable {
    var code: String
    var name: String?
    var x: Float, y: Float, z: Float
    var w: Float, h: Float, d: Float
    var rotY: Float?
    var id: String { code }

    /// Мир ← модуль (метры).
    var transform: simd_float4x4 {
        var m = simd_float4x4(simd_quatf(angle: (rotY ?? 0) * .pi / 180, axis: [0, 1, 0]))
        m.columns.3 = SIMD4<Float>(x / 1000, y / 1000, z / 1000, 1)
        return m
    }
    var half: SIMD3<Float> { SIMD3<Float>(w, h, d) / 2000 }
}

struct Kitchen: Codable {
    var name: String?
    var modules: [KitchenModule]
}

// MARK: - Модель примерки

final class FittingModel: NSObject, ObservableObject, ARSessionDelegate {
    static let mapFile = "worldmap.armap"
    static let kitchenFile = "kitchen.json"

    let arView = ARView(frame: .zero, cameraMode: .ar, automaticallyConfigureSession: false)

    @Published var scans: [String] = []
    @Published var scan: String?
    @Published var kitchen: Kitchen?
    @Published var status = "Выбери скан"
    @Published var placed = false
    @Published var hits: [String: Int] = [:]        // код модуля → сколько точек стены/трубы внутри
    @Published var toleranceMm: Float = 15          // допуск: точки ближе к краю не считаем
    @Published var offsetMm = SIMD3<Float>(0, 0, 0) // ручная подвижка всей кухни
    @Published var turnDeg: Float = 0
    @Published var errorText: String?
    /// Свободная примерка: без карты комнаты, кухня «летает» за прицелом, потом ставится и двигается пальцем.
    @Published var free = false
    @Published var locked = false
    @Published var title = ""

    private var root: AnchorEntity?
    private var center = SIMD3<Float>(0, 0, 0)       // центр низа кухни в её координатах (метры)
    private var rootWorld = matrix_identity_float4x4  // где стоит кухня в свободном режиме
    private var boxes: [String: ModelEntity] = [:]
    private var timer: Timer?
    private var busy = false
    private let work = DispatchQueue(label: "fitting", qos: .userInitiated)

    override init() {
        super.init()
        arView.session.delegate = self
        refreshScans()
    }

    static var docs: URL { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0] }

    func refreshScans() {
        let fm = FileManager.default
        let items = (try? fm.contentsOfDirectory(atPath: Self.docs.path)) ?? []
        scans = items.filter {
            fm.fileExists(atPath: Self.docs.appendingPathComponent($0).appendingPathComponent(Self.mapFile).path)
        }.sorted(by: >)
    }

    func hasKitchen(_ s: String) -> Bool {
        FileManager.default.fileExists(atPath: Self.docs.appendingPathComponent(s)
            .appendingPathComponent(Self.kitchenFile).path)
    }

    /// Все папки, где есть кухня (сканы и проекты без скана) — для свободной примерки.
    var kitchenFolders: [String] {
        let fm = FileManager.default
        return ((try? fm.contentsOfDirectory(atPath: Self.docs.path)) ?? []).filter { hasKitchen($0) }.sorted(by: >)
    }

    static func readKitchen(_ url: URL) throws -> Kitchen {
        let ok = url.startAccessingSecurityScopedResource()
        defer { if ok { url.stopAccessingSecurityScopedResource() } }
        var data: Data?
        var err: NSError?
        NSFileCoordinator().coordinate(readingItemAt: url, options: [], error: &err) { u in data = try? Data(contentsOf: u) }
        guard let d = data ?? (try? Data(contentsOf: url)) else { throw err ?? CocoaError(.fileReadNoPermission) }
        let k = try JSONDecoder().decode(Kitchen.self, from: d)
        guard !k.modules.isEmpty else { throw CocoaError(.fileReadCorruptFile) }
        return k
    }

    /// Положить kitchen.json (от Claude или из конструктора) в папку скана.
    func importKitchen(from url: URL, into s: String) {
        let ok = url.startAccessingSecurityScopedResource()
        defer { if ok { url.stopAccessingSecurityScopedResource() } }
        do {
            let k = try Self.readKitchen(url)
            let data = try JSONEncoder().encode(k)
            try data.write(to: Self.docs.appendingPathComponent(s).appendingPathComponent(Self.kitchenFile))
            objectWillChange.send()
            status = "Кухня загружена: модулей \(k.modules.count)"
        } catch {
            errorText = "Файл кухни не читается (нужен .json с модулями из конструктора): \(error.localizedDescription)"
        }
    }

    func start(_ s: String) {
        let dir = Self.docs.appendingPathComponent(s)
        do {
            let mapData = try Data(contentsOf: dir.appendingPathComponent(Self.mapFile))
            guard let map = try NSKeyedUnarchiver.unarchivedObject(ofClass: ARWorldMap.self, from: mapData) else {
                errorText = "Карта комнаты повреждена"; return
            }
            kitchen = try JSONDecoder().decode(Kitchen.self,
                                               from: Data(contentsOf: dir.appendingPathComponent(Self.kitchenFile)))
            scan = s
            free = false
            title = s
            placed = false
            hits = [:]
            let cfg = ARWorldTrackingConfiguration()
            cfg.initialWorldMap = map
            cfg.sceneReconstruction = .mesh
            cfg.environmentTexturing = .none
            arView.session.run(cfg, options: [.resetTracking, .removeExistingAnchors])
            status = "Ищу комнату: наведи на ту же стену, что сканировал"
            timer?.invalidate()
            timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in self?.check() }
        } catch {
            errorText = "Не открыть скан или кухню: \(error.localizedDescription)"
        }
    }

    func stop() {
        timer?.invalidate()
        arView.session.pause()
        root.map { arView.scene.removeAnchor($0) }
        root = nil; boxes = [:]; placed = false; scan = nil; free = false; locked = false
        offsetMm = .zero; turnDeg = 0; hits = [:]
    }

    // MARK: свободная примерка (без карты комнаты)

    func startFree(_ k: Kitchen, name: String) {
        guard ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh) else { errorText = "Нужен iPhone с LiDAR"; return }
        kitchen = k
        title = name
        // центр низа кухни: модули ставим относительно него
        let lo = k.modules.map { SIMD3<Float>($0.x - $0.w / 2, $0.y - $0.h / 2, $0.z - $0.d / 2) }
        let hi = k.modules.map { SIMD3<Float>($0.x + $0.w / 2, $0.y + $0.h / 2, $0.z + $0.d / 2) }
        let mn = lo.reduce(SIMD3<Float>(repeating: .greatestFiniteMagnitude)) { simd_min($0, $1) }
        let mx = hi.reduce(SIMD3<Float>(repeating: -.greatestFiniteMagnitude)) { simd_max($0, $1) }
        center = SIMD3<Float>((mn.x + mx.x) / 2, mn.y, (mn.z + mx.z) / 2) / 1000
        free = true; locked = false; placed = false; hits = [:]; offsetMm = .zero; turnDeg = 0
        scan = "free"
        let cfg = ARWorldTrackingConfiguration()
        cfg.sceneReconstruction = .mesh
        cfg.planeDetection = [.horizontal, .vertical]
        cfg.environmentTexturing = .none
        arView.session.run(cfg, options: [.resetTracking, .removeExistingAnchors])
        place()
        status = "Наведи прицел на пол — кухня летит за ним. Нажми «Поставить»"
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 0.08, repeats: true) { [weak self] _ in self?.tick() }
    }

    private var tickN = 0
    private func tick() {
        tickN += 1
        if free && !locked { follow() }
        if tickN % 6 == 0 { check() }
    }

    /// Кухня за прицелом: точка пола в центре экрана.
    private func follow() {
        let c = CGPoint(x: arView.bounds.midX, y: arView.bounds.midY)
        guard let hit = arView.raycast(from: c, allowing: .estimatedPlane, alignment: .horizontal).first else { return }
        let p = hit.worldTransform.columns.3
        rootWorld = Self.yaw(turnDeg, at: SIMD3<Float>(p.x, p.y, p.z))
        applyOffset()
    }

    static func yaw(_ deg: Float, at p: SIMD3<Float>) -> simd_float4x4 {
        var m = simd_float4x4(simd_quatf(angle: deg * .pi / 180, axis: [0, 1, 0]))
        m.columns.3 = SIMD4<Float>(p, 1)
        return m
    }

    func lock(_ on: Bool) {
        locked = on
        status = on ? "Стоит. Тяни пальцем — двигать по полу, два пальца — повернуть" : "Наведи прицел на пол и нажми «Поставить»"
    }

    /// Перетаскивание пальцем по полу (свободный режим, кухня поставлена).
    func drag(to pt: CGPoint) {
        guard free, locked else { return }
        let y = rootWorld.columns.3.y
        guard let r = arView.ray(through: pt), abs(r.direction.y) > 1e-4 else { return }
        let t = (y - r.origin.y) / r.direction.y
        guard t > 0 else { return }
        let p = r.origin + r.direction * t
        rootWorld = Self.yaw(turnDeg, at: SIMD3<Float>(p.x, y, p.z))
        applyOffset()
    }

    func rotate(by deg: Float) {
        turnDeg += deg
        if free { let p = rootWorld.columns.3; rootWorld = Self.yaw(turnDeg, at: SIMD3<Float>(p.x, p.y, p.z)) }
        applyOffset()
    }

    func session(_ session: ARSession, cameraDidChangeTrackingState camera: ARCamera) {
        DispatchQueue.main.async {
            switch camera.trackingState {
            case .normal:
                if !self.placed, self.scan != nil { self.place() }
            case .limited(.relocalizing):
                self.status = "Узнаю комнату… медленно поводи телефоном"
            case .limited:
                self.status = "Отслеживание ограничено"
            case .notAvailable:
                self.status = "Нет отслеживания"
            }
        }
    }

    // Кухня в координатах скана. Комната узнана → система совпадает со сканом.
    private func place() {
        guard let k = kitchen else { return }
        let anchor = AnchorEntity(world: matrix_identity_float4x4)
        for m in k.modules {
            let box = ModelEntity(mesh: .generateBox(size: m.half * 2),
                                  materials: [Self.material(.systemGreen)])
            box.transform = Transform(matrix: local(m))
            // Подпись кода модуля сверху
            let text = ModelEntity(mesh: .generateText(m.code, extrusionDepth: 0.002,
                                                       font: .systemFont(ofSize: 0.06),
                                                       containerFrame: .zero, alignment: .center,
                                                       lineBreakMode: .byWordWrapping),
                                   materials: [UnlitMaterial(color: .white)])
            let tb = text.visualBounds(relativeTo: nil)
            text.position = [-tb.extents.x / 2, m.half.y + 0.01, 0]
            box.addChild(text)
            anchor.addChild(box)
            boxes[m.code] = box
        }
        arView.scene.addAnchor(anchor)
        root = anchor
        placed = true
        applyOffset()
        if !free { status = "Кухня на месте. Зелёный — свободно, красный — что-то мешает" }
    }

    /// Модуль в координатах кухни: по скану — как есть, в свободном режиме — от центра низа кухни.
    private func local(_ m: KitchenModule) -> simd_float4x4 {
        var t = m.transform
        if free { t.columns.3 -= SIMD4<Float>(center, 0) }
        return t
    }

    /// Где стоит вся кухня в мире.
    private var placement: simd_float4x4 {
        if free {
            var o = rootWorld
            o.columns.3 += SIMD4<Float>(simd_make_float3(rootWorld * SIMD4<Float>(offsetMm / 1000, 0)), 0)
            return o
        }
        return offsetMatrix
    }

    static func material(_ c: UIColor) -> SimpleMaterial {
        SimpleMaterial(color: c.withAlphaComponent(0.45), isMetallic: false)
    }

    // MARK: ручная подгонка

    var offsetMatrix: simd_float4x4 {
        var m = simd_float4x4(simd_quatf(angle: turnDeg * .pi / 180, axis: [0, 1, 0]))
        m.columns.3 = SIMD4<Float>(offsetMm / 1000, 1)
        return m
    }

    func nudge(_ d: SIMD3<Float>) { offsetMm += d; applyOffset() }
    func turn(_ deg: Float) { rotate(by: deg) }
    func resetOffset() { offsetMm = .zero; rotate(by: -turnDeg) }

    private func applyOffset() {
        root?.transform = Transform(matrix: placement)
    }

    // MARK: проверка: заходит ли стена / труба / выступ внутрь модуля

    private func check() {
        guard placed, !busy, let k = kitchen,
              let frame = arView.session.currentFrame else { return }
        let meshes = frame.anchors.compactMap { $0 as? ARMeshAnchor }
        let tol = toleranceMm / 1000
        let off = placement
        let locals = Dictionary(uniqueKeysWithValues: k.modules.map { ($0.code, local($0)) })
        busy = true
        work.async {
            // Все точки живой LiDAR-сетки в мировых координатах
            var pts: [SIMD3<Float>] = []
            for a in meshes {
                let vb = a.geometry.vertices
                let base = vb.buffer.contents()
                pts.reserveCapacity(pts.count + vb.count)
                for i in 0..<vb.count {
                    let p = base.advanced(by: vb.offset + vb.stride * i)
                        .assumingMemoryBound(to: (Float, Float, Float).self).pointee
                    let w = a.transform * SIMD4<Float>(p.0, p.1, p.2, 1)
                    pts.append(SIMD3<Float>(w.x, w.y, w.z))
                }
            }
            var result: [String: Int] = [:]
            for m in k.modules {
                let inv = (off * (locals[m.code] ?? m.transform)).inverse
                let lim = m.half - SIMD3<Float>(repeating: tol)
                guard lim.x > 0, lim.y > 0, lim.z > 0 else { result[m.code] = 0; continue }
                var n = 0
                for p in pts {
                    let q = inv * SIMD4<Float>(p, 1)
                    if abs(q.x) < lim.x, abs(q.y) < lim.y, abs(q.z) < lim.z { n += 1 }
                }
                result[m.code] = n
            }
            DispatchQueue.main.async {
                self.busy = false
                self.hits = result
                for (code, n) in result {
                    self.boxes[code]?.model?.materials = [Self.material(n >= Self.hitLimit ? .systemRed : .systemGreen)]
                }
            }
        }
    }

    /// Сколько точек внутри модуля уже считаем помехой (одиночные — шум датчика).
    static let hitLimit = 4

    var conflicts: [KitchenModule] {
        (kitchen?.modules ?? []).filter { (hits[$0.code] ?? 0) >= Self.hitLimit }
    }
}

// MARK: - Экран примерки

struct FittingView: View {
    @StateObject private var model = FittingModel()
    @Environment(\.dismiss) private var dismiss
    /// Куда грузим файл: в папку скана или сразу в свободную примерку. Хранится отдельно от показа окна —
    /// иначе SwiftUI сбрасывает его до того, как файл выбран, и ничего не происходит.
    private enum Target { case scan(String), free }
    @State private var target: Target?
    @State private var showPicker = false

    var body: some View {
        ZStack {
            if model.scan == nil {
                chooser
            } else {
                FittingARContainer(model: model).ignoresSafeArea()
                if model.free && !model.locked {
                    Image(systemName: "plus.circle").font(.system(size: 34, weight: .light)).foregroundColor(.white)
                        .allowsHitTesting(false)
                }
                overlay
            }
        }
        .fileImporter(isPresented: $showPicker, allowedContentTypes: [.json, .data]) { res in
            let t = target
            target = nil
            guard case .success(let url) = res else { return }
            switch t {
            case .scan(let s)?: model.importKitchen(from: url, into: s)
            case .free?:
                do { model.startFree(try FittingModel.readKitchen(url), name: url.deletingPathExtension().lastPathComponent) }
                catch { model.errorText = "Файл не читается (нужен .json кухни из конструктора): \(error.localizedDescription)" }
            case nil: break
            }
        }
        .alert(model.errorText ?? "", isPresented: Binding(
            get: { model.errorText != nil }, set: { if !$0 { model.errorText = nil } })) {
            Button("Понятно", role: .cancel) {}
        }
    }

    private func openKitchen(_ folder: String) {
        let url = FittingModel.docs.appendingPathComponent(folder).appendingPathComponent(FittingModel.kitchenFile)
        do { model.startFree(try FittingModel.readKitchen(url), name: folder.replacingOccurrences(of: "_", with: " ")) }
        catch { model.errorText = "Кухня не читается: \(error.localizedDescription)" }
    }

    private var chooser: some View {
        NavigationStack {
            List {
                Section {
                    Button { target = .free; showPicker = true } label: {
                        Label("Открыть файл кухни (.json)…", systemImage: "doc")
                    }
                    ForEach(model.kitchenFolders, id: \.self) { s in
                        Button { openKitchen(s) } label: {
                            Label(s.replacingOccurrences(of: "_", with: " "), systemImage: "cube.transparent")
                        }
                    }
                } header: {
                    Text("Свободно — поставить где угодно")
                } footer: {
                    Text("Кухня летает за прицелом по полу. «Поставить» — и двигай пальцем, поворачивай двумя. Зелёная — встаёт, красная — упирается в стену, трубу или выступ.")
                }
                Section {
                    if model.scans.isEmpty {
                        Text("Нет сканов с картой комнаты. Отсканируй комнату и нажми «Сохранить».")
                            .foregroundColor(.secondary)
                    }
                    ForEach(model.scans, id: \.self) { s in
                        HStack {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(s.replacingOccurrences(of: "_", with: " "))
                                Text(model.hasKitchen(s) ? "кухня загружена" : "нет кухни")
                                    .font(.footnote)
                                    .foregroundColor(model.hasKitchen(s) ? .green : .secondary)
                            }
                            Spacer()
                            Button(model.hasKitchen(s) ? "Заменить" : "Загрузить") { target = .scan(s); showPicker = true }
                                .buttonStyle(.bordered)
                            if model.hasKitchen(s) {
                                Button("Примерить") { model.start(s) }
                                    .buttonStyle(.borderedProminent)
                            }
                        }
                    }
                } header: {
                    Text("Точно по скану")
                } footer: {
                    Text("Кухня встаёт ровно туда, где её поставили в конструкторе по этому скану. Нажми «Примерить» в той же комнате и наведи телефон на стену, которую сканировал.")
                }
            }
            .navigationTitle("Примерка мебели")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Закрыть") { dismiss() } }
            }
            .onAppear { model.refreshScans() }
        }
    }

    private var overlay: some View {
        VStack(spacing: 8) {
            HStack {
                Text(model.status)
                    .font(.system(size: 13, weight: .medium))
                    .lineLimit(2)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(.ultraThinMaterial, in: Capsule())
                Spacer()
                Button("Выход") { model.stop() }
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(.ultraThinMaterial, in: Capsule())
            }
            .padding(.horizontal, 12)

            Spacer()

            if model.placed {
                let bad = model.conflicts
                Text(bad.isEmpty ? "Встаёт — ничего не мешает ✓"
                     : "Мешает: " + bad.map { "\($0.code) (\(model.hits[$0.code] ?? 0))" }.joined(separator: ", "))
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 14).padding(.vertical, 8)
                    .background((bad.isEmpty ? Color.green : Color.red).opacity(0.9),
                                in: RoundedRectangle(cornerRadius: 12))

                if model.free {
                    HStack(spacing: 8) {
                        Button(model.locked ? "Переставить" : "Поставить") { model.lock(!model.locked) }
                            .font(.system(size: 17, weight: .bold))
                            .frame(maxWidth: .infinity, minHeight: 48)
                            .foregroundColor(.white)
                            .background((model.locked ? Color.gray : Color.green).opacity(0.92), in: RoundedRectangle(cornerRadius: 14))
                        small("↺ 90°") { model.turn(90) }
                        small("↻ 90°") { model.turn(-90) }
                    }
                    .padding(.horizontal, 12)
                }

                VStack(spacing: 6) {
                    Text(String(format: "Сдвиг X %+.0f  Y %+.0f  Z %+.0f мм · поворот %+.1f°",
                                model.offsetMm.x, model.offsetMm.y, model.offsetMm.z, model.turnDeg))
                        .font(.system(size: 12, design: .monospaced))
                    HStack(spacing: 6) {
                        nudge("◀ X", [-5, 0, 0]); nudge("X ▶", [5, 0, 0])
                        nudge("▼ Y", [0, -5, 0]); nudge("Y ▲", [0, 5, 0])
                        nudge("Z −", [0, 0, -5]); nudge("Z +", [0, 0, 5])
                    }
                    HStack(spacing: 6) {
                        small("↺ 0,5°") { model.turn(0.5) }
                        small("↻ 0,5°") { model.turn(-0.5) }
                        small("Сброс") { model.resetOffset() }
                        Stepper("Допуск \(Int(model.toleranceMm)) мм",
                                value: $model.toleranceMm, in: 5...40, step: 5)
                            .font(.system(size: 12))
                    }
                }
                .padding(10)
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
                .padding(.horizontal, 12)
                .padding(.bottom, 10)
            }
        }
    }

    private func nudge(_ t: String, _ d: SIMD3<Float>) -> some View {
        small(t) { model.nudge(d) }
    }

    private func small(_ t: String, _ a: @escaping () -> Void) -> some View {
        Button(t, action: a)
            .font(.system(size: 13, weight: .semibold))
            .frame(minWidth: 44, minHeight: 34)
            .padding(.horizontal, 4)
            .background(Color.gray.opacity(0.35), in: RoundedRectangle(cornerRadius: 8))
    }
}

struct FittingARContainer: UIViewRepresentable {
    @ObservedObject var model: FittingModel
    func makeCoordinator() -> Coordinator { Coordinator(model) }
    func makeUIView(context: Context) -> ARView {
        let v = model.arView
        if v.gestureRecognizers?.contains(where: { $0.name == "fit" }) != true {
            let pan = UIPanGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.pan(_:)))
            pan.maximumNumberOfTouches = 1; pan.name = "fit"
            let rot = UIRotationGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.rot(_:)))
            rot.name = "fit"
            v.addGestureRecognizer(pan); v.addGestureRecognizer(rot)
        }
        return v
    }
    func updateUIView(_ uiView: ARView, context: Context) {}

    final class Coordinator: NSObject {
        let model: FittingModel
        init(_ m: FittingModel) { model = m }
        @objc func pan(_ g: UIPanGestureRecognizer) { model.drag(to: g.location(in: g.view)) }
        @objc func rot(_ g: UIRotationGestureRecognizer) {
            guard model.free, model.locked else { return }
            model.rotate(by: -Float(g.rotation) * 180 / .pi)
            g.rotation = 0
        }
    }
}
