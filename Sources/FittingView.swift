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

    private var root: AnchorEntity?
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

    /// Положить kitchen.json (от Claude) в папку скана.
    func importKitchen(from url: URL, into s: String) {
        let ok = url.startAccessingSecurityScopedResource()
        defer { if ok { url.stopAccessingSecurityScopedResource() } }
        do {
            let data = try Data(contentsOf: url)
            _ = try JSONDecoder().decode(Kitchen.self, from: data)
            try data.write(to: Self.docs.appendingPathComponent(s).appendingPathComponent(Self.kitchenFile))
            objectWillChange.send()
        } catch {
            errorText = "Файл кухни не читается: \(error.localizedDescription)"
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
        root = nil; boxes = [:]; placed = false; scan = nil
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
            box.transform = Transform(matrix: m.transform)
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
        status = "Кухня на месте. Зелёный — свободно, красный — что-то мешает"
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
    func turn(_ deg: Float) { turnDeg += deg; applyOffset() }
    func resetOffset() { offsetMm = .zero; turnDeg = 0; applyOffset() }

    private func applyOffset() {
        root?.transform = Transform(matrix: offsetMatrix)
    }

    // MARK: проверка: заходит ли стена / труба / выступ внутрь модуля

    private func check() {
        guard placed, !busy, let k = kitchen,
              let frame = arView.session.currentFrame else { return }
        let meshes = frame.anchors.compactMap { $0 as? ARMeshAnchor }
        let tol = toleranceMm / 1000
        let off = offsetMatrix
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
                let inv = (off * m.transform).inverse
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
    @State private var importFor: String?

    var body: some View {
        ZStack {
            if model.scan == nil {
                chooser
            } else {
                FittingARContainer(model: model).ignoresSafeArea()
                overlay
            }
        }
        .fileImporter(isPresented: Binding(get: { importFor != nil }, set: { if !$0 { importFor = nil } }),
                      allowedContentTypes: [.json]) { res in
            if case .success(let url) = res, let s = importFor { model.importKitchen(from: url, into: s) }
            importFor = nil
        }
        .alert(model.errorText ?? "", isPresented: Binding(
            get: { model.errorText != nil }, set: { if !$0 { model.errorText = nil } })) {
            Button("Понятно", role: .cancel) {}
        }
    }

    private var chooser: some View {
        NavigationStack {
            List {
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
                            Button(model.hasKitchen(s) ? "Заменить" : "Загрузить кухню") { importFor = s }
                                .buttonStyle(.bordered)
                            if model.hasKitchen(s) {
                                Button("Примерить") { model.start(s) }
                                    .buttonStyle(.borderedProminent)
                            }
                        }
                    }
                } footer: {
                    Text("Кухню (kitchen.json) готовит Claude по этому скану. Сохрани файл в «Файлы» и загрузи сюда. Потом в той же комнате нажми «Примерить» и наведи телефон на стену, которую сканировал.")
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
                // Итог по модулям
                let bad = model.conflicts
                Text(bad.isEmpty ? "Всё свободно ✓"
                     : "Мешает: " + bad.map { "\($0.code) (\(model.hits[$0.code] ?? 0))" }.joined(separator: ", "))
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 14).padding(.vertical, 8)
                    .background((bad.isEmpty ? Color.green : Color.red).opacity(0.9),
                                in: RoundedRectangle(cornerRadius: 12))

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
    func makeUIView(context: Context) -> ARView { model.arView }
    func updateUIView(_ uiView: ARView, context: Context) {}
}
