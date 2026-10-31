import SwiftUI
import QuickLook
import ModelIO
import ARKit
import RealityKit

struct ContentView: View {
    @StateObject private var model = ScanModel()
    @Environment(\.dismiss) private var dismiss
    @State private var showFitting = false
    @State private var showMebel = false
    @State private var confirmExit = false

    private func leave() {
        model.shutdown()
        dismiss()
    }

    var body: some View {
        ZStack {
            ARViewContainer(model: model)
                .ignoresSafeArea()

            // Прицел в центре экрана
            Image(systemName: "plus")
                .font(.system(size: 22, weight: .light))
                .foregroundColor(.white.opacity(0.8))
                .allowsHitTesting(false)

            VStack(spacing: 8) {
                // Верх: статус, фото, калибровка
                HStack(spacing: 8) {
                    Button { if model.unsaved { confirmExit = true } else { leave() } } label: {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 17, weight: .semibold))
                            .frame(width: 38, height: 38)
                            .background(.ultraThinMaterial, in: Circle())
                    }
                    .accessibilityLabel("Меню")
                    Text(model.status)
                        .font(.system(size: 13, weight: .medium))
                        .lineLimit(1)
                        .padding(.horizontal, 12).padding(.vertical, 8)
                        .background(.ultraThinMaterial, in: Capsule())
                    Spacer(minLength: 4)
                    Label("\(model.photoCount)", systemImage: "camera")
                        .font(.system(size: 13, weight: .medium))
                        .padding(.horizontal, 10).padding(.vertical, 8)
                        .background(.ultraThinMaterial, in: Capsule())
                    Button { model.showCalibration = true } label: {
                        Image(systemName: "ruler")
                            .font(.system(size: 17, weight: .semibold))
                            .frame(width: 38, height: 38)
                            .background(.ultraThinMaterial, in: Circle())
                    }
                    .accessibilityLabel("Калибровка")
                    Button { model.pause(); showFitting = true } label: {
                        Image(systemName: "cube.transparent")
                            .font(.system(size: 17, weight: .semibold))
                            .frame(width: 38, height: 38)
                            .background(.ultraThinMaterial, in: Circle())
                    }
                    .accessibilityLabel("Примерка мебели")
                    Button { model.pause(); showMebel = true } label: {
                        Image(systemName: "square.stack.3d.up")
                            .font(.system(size: 17, weight: .semibold))
                            .frame(width: 38, height: 38)
                            .background(.ultraThinMaterial, in: Circle())
                    }
                    .accessibilityLabel("Мебель")
                    if model.phase != .preview {
                        Button { model.confirmReset = true } label: {
                            Image(systemName: "arrow.counterclockwise")
                                .font(.system(size: 17, weight: .semibold))
                                .frame(width: 38, height: 38)
                                .background(.ultraThinMaterial, in: Circle())
                        }
                        .accessibilityLabel("Заново")
                    }
                }
                .padding(.horizontal, 12)

                LevelView(roll: model.rollDeg, pitch: model.pitchDeg)

                if model.phase != .preview {
                    VStack(spacing: 4) {
                        if model.wallsStep {
                            Text("Шаг 1 из 2 — коробка: медленно обведи камерой все стены, окна и двери. Потом «Стены готовы».")
                                .font(.system(size: 13, weight: .semibold))
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 12).padding(.vertical, 6)
                                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
                                .padding(.horizontal, 12)
                        } else {
                            CoverageBar(percent: model.coverage)
                            Text("Детали: \(model.detailCount / 1000) тыс. точек · подноси телефон на 30–80 см к выступам, нишам, трапу")
                                .font(.system(size: 12, weight: .semibold))
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 10).padding(.vertical, 4)
                                .background(.ultraThinMaterial, in: Capsule())
                        }
                        if let w = model.wallsText {
                            Text(w)
                                .font(.system(size: 13, weight: .semibold))
                                .padding(.horizontal, 10).padding(.vertical, 4)
                                .background(.ultraThinMaterial, in: Capsule())
                        }
                        if let h = model.roomHint {
                            Text(h)
                                .font(.system(size: 14, weight: .bold))
                                .foregroundColor(.white)
                                .padding(.horizontal, 12).padding(.vertical, 5)
                                .background(Color.orange.opacity(0.9), in: Capsule())
                        }
                    }
                }

                Spacer()

                if let d = model.distanceText {
                    VStack(spacing: 6) {
                        Text(d)
                            .font(.system(size: 38, weight: .bold, design: .monospaced))
                            .foregroundColor(.white)
                            .padding(.horizontal, 18).padding(.vertical, 8)
                            .background(Color.orange.opacity(0.92), in: RoundedRectangle(cornerRadius: 12))
                        if model.mode != .label, let last = model.measurements.last {
                            if let ref = last.reference {
                                Text(last.kind == .distance
                                     ? "Эталон \(Int(ref)) мм · датчик \(Int(last.raw.rounded())) мм"
                                     : String(format: "Эталон %.1f° · датчик %.1f°", ref, last.raw))
                                    .font(.system(size: 13))
                                    .padding(.horizontal, 10).padding(.vertical, 5)
                                    .background(.ultraThinMaterial, in: Capsule())
                            } else {
                                Button(last.kind == .distance ? "Это эталон — ввести лазер" : "Это эталон — ввести угол") {
                                    model.askReference = true
                                }
                                .font(.system(size: 14, weight: .semibold))
                                .padding(.horizontal, 12).padding(.vertical, 7)
                                .background(.ultraThinMaterial, in: Capsule())
                            }
                        }
                    }
                }

                if model.measuring {
                    VStack(spacing: 8) {
                        Picker("Режим", selection: Binding(get: { model.mode }, set: { model.setMode($0) })) {
                            ForEach(MeasureMode.allCases) { Text($0.rawValue).tag($0) }
                        }
                        .pickerStyle(.segmented)

                        if model.mode == .label {
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 6) {
                                    ForEach(ScanLabel.categories, id: \.self) { c in
                                        Button(c) { model.labelCategory = c }
                                            .font(.system(size: 14, weight: .medium))
                                            .padding(.horizontal, 12).padding(.vertical, 7)
                                            .foregroundColor(model.labelCategory == c ? .white : .primary)
                                            .background(model.labelCategory == c ? Color.pink : Color.clear,
                                                        in: Capsule())
                                            .overlay(Capsule().stroke(Color.primary.opacity(0.25)))
                                    }
                                }
                            }
                        }
                        Text(model.hint)
                            .font(.system(size: 13, weight: .semibold))
                    }
                    .padding(10)
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
                    .padding(.horizontal, 12)
                }

                if model.phase == .preview {
                    VStack(spacing: 10) {
                        if RoomWalls.isSupported {
                            Toggle("Авто-стены, окна, двери (RoomPlan)", isOn: $model.useRoomPlan)
                                .font(.system(size: 14, weight: .medium))
                                .padding(.horizontal, 14).padding(.vertical, 8)
                                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
                        }
                        Button { model.startScanning() } label: {
                            Label("Начать замер", systemImage: "record.circle")
                                .font(.system(size: 20, weight: .bold))
                                .frame(maxWidth: .infinity, minHeight: 64)
                                .foregroundColor(.white)
                                .background(Color.green.opacity(0.92), in: RoundedRectangle(cornerRadius: 16))
                        }
                    }
                    .padding(.horizontal, 12)
                    .padding(.bottom, 10)
                } else {
                    if model.wallsStep {
                        Button { model.finishWalls() } label: {
                            Label("Коробка готова → шаг 2: детали", systemImage: "checkmark.circle.fill")
                                .font(.system(size: 17, weight: .bold))
                                .frame(maxWidth: .infinity, minHeight: 52)
                                .foregroundColor(.white)
                                .background(Color.green.opacity(0.92), in: RoundedRectangle(cornerRadius: 14))
                        }
                        .padding(.horizontal, 12)
                    }
                    Text("Замеров: \(model.measurements.count) · меток: \(model.labels.count) · фото: \(model.photoCount)")
                        .font(.system(size: 12))
                        .padding(.horizontal, 10).padding(.vertical, 4)
                        .background(.ultraThinMaterial, in: Capsule())

                    HStack(spacing: 8) {
                        BigButton(title: model.phase == .paused ? "Продолжить" : "Пауза",
                                  color: model.phase == .paused ? .green : .gray) { model.togglePause() }
                        BigButton(title: model.measuring ? "Готово" : "Измерить",
                                  color: model.measuring ? .orange : .gray) { model.toggleMeasure() }
                        BigButton(title: "Отменить", color: .gray) { model.undo() }
                            .disabled(!model.canUndo)
                            .opacity(model.canUndo ? 1 : 0.5)
                        BigButton(title: "Сохранить", color: .blue) { model.export() }
                    }
                    .padding(.horizontal, 12)
                    .padding(.bottom, 10)
                }
            }
        }
        .fullScreenCover(isPresented: $showFitting, onDismiss: { model.resume() }) {
            FittingView()
        }
        .fullScreenCover(isPresented: $showMebel, onDismiss: { model.resume() }) {
            MebelView()
        }
        .sheet(item: $model.shareItem) { item in
            ShareSheet(items: item.urls)
        }
        .background(
            Color.clear.sheet(isPresented: Binding(
                get: { model.checkText != nil && model.shareItem == nil },
                set: { if !$0 { model.checkText = nil } })) {
                NavigationView {
                    ScrollView {
                        Text(model.checkText ?? "")
                            .font(.system(size: 15, design: .monospaced))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding()
                    }
                    .navigationTitle("Проверка помещения")
                    .toolbar { Button("Готово") { model.checkText = nil } }
                }
            }
        )
        .background(
            Color.clear.sheet(isPresented: $model.showCalibration) {
                CalibrationView(model: model)
            }
        )
        .alert("Сколько показал эталон?", isPresented: $model.askReference) {
            TextField("мм или градусы", text: $model.referenceText)
                .keyboardType(.decimalPad)
            Button("Сохранить") { model.saveReference() }
            Button("Отмена", role: .cancel) { model.referenceText = "" }
        } message: {
            Text("Измерь то же самое лазером, рулеткой или угломером. По эталонам приложение подстраивает датчик отдельно для вертикали, горизонтали, наискосок и углов.")
        }
        .alert("Выйти в меню?", isPresented: $confirmExit) {
            Button("Выйти без сохранения", role: .destructive) { leave() }
            Button("Остаться", role: .cancel) {}
        } message: {
            Text("Скан не сохранён — сетка, фото, замеры и метки пропадут.")
        }
        .alert("Начать скан заново?", isPresented: $model.confirmReset) {
            Button("Заново", role: .destructive) { model.resetScan() }
            Button("Отмена", role: .cancel) {}
        } message: {
            Text("Сетка, фото, замеры и метки удалятся, если не сохранены. Калибровка останется.")
        }
        .alert(model.errorText ?? "", isPresented: Binding(
            get: { model.errorText != nil },
            set: { if !$0 { model.errorText = nil } })) {
            Button("Понятно", role: .cancel) {}
        }
    }
}

/// Покрытие скана: сколько поверхности снято хорошо (зелёное).
struct CoverageBar: View {
    let percent: Int
    var body: some View {
        let c: Color = percent >= 85 ? .green : (percent >= 60 ? .yellow : .red)
        HStack(spacing: 8) {
            ZStack(alignment: .leading) {
                Capsule().fill(Color.white.opacity(0.25)).frame(width: 120, height: 8)
                Capsule().fill(c).frame(width: CGFloat(max(0, min(100, percent))) * 1.2, height: 8)
            }
            Text("Покрытие \(percent)%")
                .font(.system(size: 13, weight: .semibold, design: .monospaced))
                .foregroundColor(c)
        }
        .padding(.horizontal, 12).padding(.vertical, 6)
        .background(.ultraThinMaterial, in: Capsule())
    }
}

/// Уровень: наклон телефона влево/вправо и вверх/вниз.
struct LevelView: View {
    let roll: Double
    let pitch: Double
    var body: some View {
        let ok = abs(roll) < 1
        HStack(spacing: 10) {
            ZStack {
                Capsule().stroke(Color.white.opacity(0.7), lineWidth: 1.5)
                    .frame(width: 120, height: 18)
                Rectangle().fill(Color.white.opacity(0.7)).frame(width: 1, height: 18)
                Circle().fill(ok ? Color.green : Color.orange)
                    .frame(width: 14, height: 14)
                    .offset(x: CGFloat(max(-10, min(10, roll))) * 5.3)
            }
            Text(String(format: "%@%.1f°  ↕%.0f°", roll >= 0 ? "▶" : "◀", abs(roll), pitch))
                .font(.system(size: 13, weight: .semibold, design: .monospaced))
                .foregroundColor(ok ? .green : .orange)
        }
        .padding(.horizontal, 12).padding(.vertical, 6)
        .background(.ultraThinMaterial, in: Capsule())
    }
}

struct BigButton: View {
    let title: String
    let color: Color
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 15, weight: .semibold))
                .lineLimit(1)
                .minimumScaleFactor(0.8)
                .frame(maxWidth: .infinity, minHeight: 50)
                .foregroundColor(.white)
                .background(color.opacity(0.92), in: RoundedRectangle(cornerRadius: 14))
        }
    }
}

struct ARViewContainer: UIViewRepresentable {
    @ObservedObject var model: ScanModel

    func makeUIView(context: Context) -> ARView {
        let view = model.arView
        let tap = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.tapped(_:)))
        view.addGestureRecognizer(tap)
        model.startPreview()
        return view
    }

    func updateUIView(_ uiView: ARView, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(model: model) }

    final class Coordinator: NSObject {
        let model: ScanModel
        init(model: ScanModel) { self.model = model }
        @objc func tapped(_ g: UITapGestureRecognizer) {
            model.handleTap(at: g.location(in: g.view))
        }
    }
}

struct ShareItem: Identifiable {
    let id = UUID()
    let urls: [URL]
}

struct ShareSheet: UIViewControllerRepresentable {
    let items: [URL]
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }
    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}


/// Главный экран: разделы «Замер», «Мебель», «Примерка».
struct HomeView: View {
    @State private var showScan = false
    @State private var showMebel = false
    @State private var showFitting = false
    @State private var showObject = false
    @State private var showMultik = false

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 14) {
                    HomeCard(title: "Замер помещения",
                             text: "LiDAR-скан: стены, окна, двери, углы, неровности, метки коммуникаций",
                             icon: "camera.viewfinder", color: .green) { showScan = true }
                    HomeCard(title: "Мебель",
                             text: "Конструктор, файлы Базиса (.b3d / .fr3d), ссылки клиентам",
                             icon: "square.stack.3d.up.fill", color: .blue) { showMebel = true }
                    HomeCard(title: "Примерка",
                             text: "Поставить спроектированную мебель в комнату через камеру",
                             icon: "cube.transparent", color: .orange) { showFitting = true }
                    HomeCard(title: "Скан предмета",
                             text: "Обойти предмет на столе со всех сторон — точная 3D-модель с размерами",
                             icon: "cube.fill", color: .purple) { showObject = true }
                    HomeCard(title: "Мультики",
                             text: "Сериалы по сценариям: персонажи с постоянным кодом, озвучка, сборка видео для YouTube",
                             icon: "film.stack", color: .pink) { showMultik = true }
                }
                .padding(16)
            }
            .navigationTitle("Замер 3D")
        }
        .navigationViewStyle(.stack)
        .fullScreenCover(isPresented: $showScan) { ContentView() }
        .fullScreenCover(isPresented: $showMebel) { MebelView() }
        .fullScreenCover(isPresented: $showFitting) { FittingView() }
        .fullScreenCover(isPresented: $showObject) { ObjectScanScreen() }
        .fullScreenCover(isPresented: $showMultik) { MultikScreen() }
    }
}

struct HomeCard: View {
    let title: String
    let text: String
    let icon: String
    let color: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 16) {
                Image(systemName: icon)
                    .font(.system(size: 30, weight: .semibold))
                    .foregroundColor(.white)
                    .frame(width: 64, height: 64)
                    .background(color, in: RoundedRectangle(cornerRadius: 16))
                VStack(alignment: .leading, spacing: 4) {
                    Text(title).font(.system(size: 20, weight: .bold)).foregroundColor(.primary)
                    Text(text).font(.system(size: 14)).foregroundColor(.secondary)
                        .multilineTextAlignment(.leading)
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").foregroundColor(.secondary)
            }
            .padding(14)
            .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 20))
        }
        .buttonStyle(.plain)
    }
}


// MARK: - Скан предмета (Apple Object Capture): обойти со всех сторон → модель USDZ + OBJ с размерами

@MainActor
final class ObjectScanModel: ObservableObject {
    enum Step: Equatable { case capture, building(Double), done, failed(String) }
    @Published var session: ObjectCaptureSession?
    @Published var state: ObjectCaptureSession.CaptureState = .initializing
    @Published var step: Step = .capture
    @Published var passDone = false
    @Published var shots = 0
    @Published var sizeText = ""
    @Published var modelURL: URL?
    @Published var shareURLs: [URL] = []
    private var dir: URL?
    private var tasks: [Task<Void, Never>] = []

    static var supported: Bool { ObjectCaptureSession.isSupported }

    func start() {
        let df = DateFormatter(); df.dateFormat = "yyyy-MM-dd_HH-mm"
        let d = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Предмет_\(df.string(from: Date()))", isDirectory: true)
        let images = d.appendingPathComponent("Images", isDirectory: true)
        let snaps = d.appendingPathComponent("Snapshots", isDirectory: true)
        try? FileManager.default.createDirectory(at: images, withIntermediateDirectories: true)
        try? FileManager.default.createDirectory(at: snaps, withIntermediateDirectories: true)
        dir = d
        var cfg = ObjectCaptureSession.Configuration()
        cfg.checkpointDirectory = snaps
        cfg.isOverCaptureEnabled = false
        let s = ObjectCaptureSession()
        s.start(imagesDirectory: images, configuration: cfg)
        session = s
        step = .capture; passDone = false; shots = 0; modelURL = nil; sizeText = ""
        tasks.forEach { $0.cancel() }
        tasks = [
            Task { [weak self] in
                for await st in s.stateUpdates {
                    guard let self else { return }
                    self.state = st
                    if case .completed = st { self.build() }
                    if case .failed(let e) = st { self.step = .failed(e.localizedDescription) }
                }
            },
            Task { [weak self] in
                while !Task.isCancelled {
                    try? await Task.sleep(nanoseconds: 300_000_000)
                    guard let self, let s = self.session else { return }
                    self.passDone = s.userCompletedScanPass
                    self.shots = s.numberOfShotsTaken
                }
            },
        ]
    }

    func detect() { _ = session?.startDetecting() }
    func capture() { session?.startCapturing() }
    func nextPass() { session?.beginNewScanPass() }
    func finish() { session?.finish() }
    func cancel() { session?.cancel(); tasks.forEach { $0.cancel() }; session = nil }

    /// Сборка модели на телефоне (2–5 минут). Результат: model.usdz, model.obj, размеры.
    private func build() {
        guard let d = dir else { return }
        step = .building(0)
        session = nil
        let out = d.appendingPathComponent("model.usdz")
        Task {
            do {
                var cfg = PhotogrammetrySession.Configuration()
                cfg.checkpointDirectory = d.appendingPathComponent("Snapshots")
                let ps = try PhotogrammetrySession(input: d.appendingPathComponent("Images"), configuration: cfg)
                try ps.process(requests: [.modelFile(url: out)])
                for try await o in ps.outputs {
                    switch o {
                    case .requestProgress(_, let f): self.step = .building(f)
                    case .requestError(_, let e): self.step = .failed(e.localizedDescription)
                    case .processingComplete: self.finishModel(out, dir: d)
                    default: break
                    }
                }
            } catch {
                self.step = .failed(error.localizedDescription)
            }
        }
    }

    private func finishModel(_ usdz: URL, dir d: URL) {
        guard FileManager.default.fileExists(atPath: usdz.path) else { step = .failed("Модель не собралась"); return }
        var urls = [usdz]
        let asset = MDLAsset(url: usdz)
        let obj = d.appendingPathComponent("model.obj")
        if (try? asset.export(to: obj)) != nil { urls.append(obj) }
        let b = asset.boundingBox
        let sz = (b.maxBounds - b.minBounds) * 1000
        if sz.x > 0, sz.y > 0, sz.z > 0 {
            sizeText = String(format: "Габарит: %.0f × %.0f × %.0f мм (Ш × В × Г)", sz.x, sz.y, sz.z)
            let info = ["widthMm": sz.x, "heightMm": sz.y, "depthMm": sz.z]
            if let j = try? JSONSerialization.data(withJSONObject: info, options: .prettyPrinted) {
                let f = d.appendingPathComponent("size.json"); try? j.write(to: f); urls.append(f)
            }
        }
        modelURL = usdz
        shareURLs = urls
        step = .done
    }
}

struct ObjectScanScreen: View {
    @StateObject private var m = ObjectScanModel()
    @Environment(\.dismiss) private var dismiss
    @State private var share = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            if !ObjectScanModel.supported {
                Text("На этом устройстве скан предметов недоступен (нужен iPhone с LiDAR и iOS 17).")
                    .foregroundColor(.white).padding()
            } else {
                content
            }
            VStack {
                HStack {
                    Button { m.cancel(); dismiss() } label: {
                        Image(systemName: "chevron.left").font(.system(size: 17, weight: .semibold))
                            .frame(width: 38, height: 38).background(.ultraThinMaterial, in: Circle())
                    }
                    Spacer()
                }.padding(.horizontal, 12)
                Spacer()
            }
        }
        .onAppear { if ObjectScanModel.supported && m.session == nil && m.step == .capture { m.start() } }
        .sheet(isPresented: $share) { ShareSheet(items: m.shareURLs) }
    }

    @ViewBuilder private var content: some View {
        switch m.step {
        case .capture:
            if let s = m.session {
                ObjectCaptureView(session: s).ignoresSafeArea()
                VStack(spacing: 10) {
                    Spacer()
                    Text(hint).font(.system(size: 15, weight: .semibold)).foregroundColor(.white)
                        .multilineTextAlignment(.center).padding(10)
                        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
                    controls
                }
                .padding(.horizontal, 16).padding(.bottom, 24)
            }
        case .building(let f):
            VStack(spacing: 14) {
                ProgressView(value: f).tint(.purple).frame(width: 240)
                Text("Собираю 3D-модель… \(Int(f * 100))%").foregroundColor(.white)
                Text("Это 2–5 минут. Телефон не закрывайте.").font(.footnote).foregroundColor(.gray)
            }
        case .done:
            VStack(spacing: 10) {
                if let u = m.modelURL { QuickLookView(url: u).ignoresSafeArea(edges: .horizontal) }
                Text(m.sizeText).font(.system(size: 15, weight: .bold)).foregroundColor(.white)
                HStack(spacing: 8) {
                    BigButton(title: "Отправить", color: .blue) { share = true }
                    BigButton(title: "Новый предмет", color: .purple) { m.start() }
                }.padding(.horizontal, 16).padding(.bottom, 20)
            }.padding(.top, 56)
        case .failed(let e):
            VStack(spacing: 12) {
                Text("Не получилось: \(e)").foregroundColor(.white).multilineTextAlignment(.center)
                BigButton(title: "Заново", color: .purple) { m.start() }.frame(width: 200)
            }.padding()
        }
    }

    private var hint: String {
        switch m.state {
        case .ready: return "Наведи на предмет на столе и нажми «Найти предмет»"
        case .detecting: return "Подгони рамку по предмету и нажми «Начать съёмку»"
        case .capturing:
            return m.passDone ? "Круг пройден (\(m.shots) снимков). Переверни предмет или сними сверху/снизу — «Ещё круг», или «Готово»"
                              : "Медленно обойди предмет по кругу, держи его в кадре · снимков \(m.shots)"
        case .finishing: return "Заканчиваю съёмку…"
        default: return "Готовлю камеру…"
        }
    }

    @ViewBuilder private var controls: some View {
        switch m.state {
        case .ready: BigButton(title: "Найти предмет", color: .purple) { m.detect() }
        case .detecting: BigButton(title: "Начать съёмку", color: .green) { m.capture() }
        case .capturing:
            HStack(spacing: 8) {
                if m.passDone { BigButton(title: "Ещё круг", color: .gray) { m.nextPass() } }
                BigButton(title: "Готово", color: .blue) { m.finish() }
            }
        default: EmptyView()
        }
    }
}

/// Просмотр USDZ: вращать, приближать, AR («поставить на стол»).
struct QuickLookView: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> QLPreviewController {
        let c = QLPreviewController(); c.dataSource = context.coordinator; return c
    }
    func updateUIViewController(_ c: QLPreviewController, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator(url) }
    final class Coordinator: NSObject, QLPreviewControllerDataSource {
        let url: URL
        init(_ u: URL) { url = u }
        func numberOfPreviewItems(in controller: QLPreviewController) -> Int { 1 }
        func previewController(_ controller: QLPreviewController, previewItemAt index: Int) -> QLPreviewItem { url as NSURL }
    }
}
