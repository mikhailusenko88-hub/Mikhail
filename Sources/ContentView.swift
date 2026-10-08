import SwiftUI
import ARKit
import RealityKit

struct ContentView: View {
    @StateObject private var model = ScanModel()
    @State private var showFitting = false

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
                }
                .padding(.horizontal, 12)

                LevelView(roll: model.rollDeg, pitch: model.pitchDeg)

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

                Text("Замеров: \(model.measurements.count) · меток: \(model.labels.count)")
                    .font(.system(size: 12))
                    .padding(.horizontal, 10).padding(.vertical, 4)
                    .background(.ultraThinMaterial, in: Capsule())

                HStack(spacing: 8) {
                    BigButton(title: model.measuring ? "Готово" : "Измерить",
                              color: model.measuring ? .orange : .gray) { model.toggleMeasure() }
                    BigButton(title: "Отменить", color: .gray) { model.undo() }
                        .disabled(!model.canUndo)
                        .opacity(model.canUndo ? 1 : 0.5)
                    BigButton(title: "Сохранить", color: .blue) { model.export() }
                    BigButton(title: "Заново", color: .gray) { model.confirmReset = true }
                }
                .padding(.horizontal, 12)
                .padding(.bottom, 10)
            }
        }
        .fullScreenCover(isPresented: $showFitting, onDismiss: { model.resume() }) {
            FittingView()
        }
        .sheet(item: $model.shareItem) { item in
            ShareSheet(items: item.urls)
        }
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
        model.startScan()
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
