import SwiftUI

struct CalibrationView: View {
    @ObservedObject var model: ScanModel
    @Environment(\.dismiss) private var dismiss
    @State private var confirmReset = false

    var body: some View {
        let cal = model.calibration
        NavigationStack {
            List {
                Section {
                    row("Общая", cal.describe(cal.global))
                    ForEach(MeasureDir.allCases, id: \.self) { d in
                        row(d.title, cal.byDir[d.rawValue].map { cal.describe($0) } ?? "нет эталонов → общая")
                    }
                    row("Углы", cal.angleSamples.isEmpty ? "нет эталонов"
                        : String(format: "%+.2f° · %d шт.", cal.angleOffsetDeg, cal.angleSamples.count))
                } header: {
                    Text("Текущие поправки")
                } footer: {
                    Text("«Измерить» → точки → «Это эталон» → ввести лазер/рулетку/угломер. Бери разные длины (0,5 / 1,5 / 3 м) и разные направления: вертикаль, горизонталь, наискосок. С 3+ эталонами разной длины учитывается и масштаб, и постоянный сдвиг. Наклон телефона и расстояние записываются в каждый эталон.")
                }

                Section("Эталоны длины") {
                    if cal.samples.isEmpty { Text("Пока нет").foregroundColor(.secondary) }
                    ForEach(cal.samples) { s in
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("\(s.dir.title): эталон \(Int(s.trueMm)) мм")
                                Text("датчик \(Int(s.rawMm.rounded())) мм" + poseText(s.pose))
                                    .font(.footnote).foregroundColor(.secondary)
                            }
                            Spacer()
                            let res = cal.residual(s)
                            Text(String(format: "%+.1f", res))
                                .font(.system(.body, design: .monospaced))
                                .foregroundColor(abs(res) <= 2 ? .green : (abs(res) <= 5 ? .orange : .red))
                        }
                        .swipeActions {
                            Button("Удалить", role: .destructive) { model.removeSample(s.id) }
                        }
                    }
                }

                Section("Эталоны углов") {
                    if cal.angleSamples.isEmpty { Text("Пока нет").foregroundColor(.secondary) }
                    ForEach(cal.angleSamples) { a in
                        HStack {
                            Text(String(format: "эталон %.1f°", a.trueDeg))
                            Spacer()
                            Text(String(format: "датчик %.1f°", a.rawDeg)).foregroundColor(.secondary)
                        }
                        .swipeActions {
                            Button("Удалить", role: .destructive) { model.removeSample(a.id) }
                        }
                    }
                }

                Section {
                    Button("Сбросить калибровку", role: .destructive) { confirmReset = true }
                }
            }
            .navigationTitle("Калибровка")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Готово") { dismiss() } }
            }
            .confirmationDialog("Удалить все эталоны?", isPresented: $confirmReset, titleVisibility: .visible) {
                Button("Сбросить", role: .destructive) { model.resetCalibration() }
            }
        }
    }

    private func row(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.subheadline.weight(.semibold))
            Text(value).font(.system(.footnote, design: .monospaced)).foregroundColor(.secondary)
        }
    }

    private func poseText(_ p: CapturePose?) -> String {
        guard let p else { return "" }
        return String(format: " · наклон %+.1f° · %.1f м", p.rollDeg, max(p.distAmm, p.distBmm) / 1000)
    }
}
