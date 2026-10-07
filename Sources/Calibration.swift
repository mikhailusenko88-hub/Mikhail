import Foundation

/// Направление замера относительно гравитации (ось Y скана — вверх).
enum MeasureDir: String, Codable, CaseIterable {
    case vertical, horizontal, diagonal

    var title: String {
        switch self {
        case .vertical: return "Вертикаль"
        case .horizontal: return "Горизонталь"
        case .diagonal: return "Наискосок"
        }
    }

    /// По вектору А→Б: круче 80° — вертикаль, положе 10° — горизонталь, иначе наискосок.
    static func of(_ dx: Float, _ dy: Float, _ dz: Float) -> MeasureDir {
        let len = (dx * dx + dy * dy + dz * dz).squareRoot()
        guard len > 0 else { return .horizontal }
        let s = abs(dy) / len           // синус угла к горизонту
        if s > 0.985 { return .vertical }
        if s < 0.174 { return .horizontal }
        return .diagonal
    }
}

/// Положение телефона в момент замера: наклон влево/вправо, вверх/вниз,
/// расстояние до точек и угол, под которым луч падал на поверхность.
struct CapturePose: Codable {
    var rollDeg: Double      // + вправо, − влево (портретная ориентация)
    var pitchDeg: Double     // + камера смотрит вверх, − вниз
    var distAmm: Double      // от телефона до точки А
    var distBmm: Double
}

/// Калибровка датчика по эталонам (лазер/рулетка/угломер).
/// Длины: истина ≈ scale × сырое + offsetMm, отдельно для каждого направления
/// (если по направлению эталонов нет — общая поправка). Углы: постоянный сдвиг в градусах.
/// Всё хранится на телефоне и выгружается в info.json вместе с сырыми точками,
/// поэтому при обработке можно пересчитать и более сложной моделью.
struct Calibration: Codable {
    struct Sample: Codable, Identifiable {
        var id = UUID()
        var rawMm: Double
        var trueMm: Double
        var dir: MeasureDir
        var a: [Float]          // точки замера (сырые, метры) — для будущих моделей
        var b: [Float]
        var pose: CapturePose?  // как держали телефон
        var date = Date()
    }
    struct AngleSample: Codable, Identifiable {
        var id = UUID()
        var rawDeg: Double
        var trueDeg: Double
        var date = Date()
    }
    struct Fit: Codable {
        var scale: Double = 1
        var offsetMm: Double = 0
        var count = 0
    }

    var samples: [Sample] = []
    var angleSamples: [AngleSample] = []
    var global = Fit()
    var byDir: [String: Fit] = [:]
    var angleOffsetDeg: Double = 0

    // MARK: применение

    func fit(for dir: MeasureDir) -> Fit {
        if let f = byDir[dir.rawValue], f.count > 0 { return f }
        return global
    }

    func apply(_ rawMm: Double, dir: MeasureDir) -> Int {
        let f = fit(for: dir)
        return Int((rawMm * f.scale + f.offsetMm).rounded())
    }

    func applyAngle(_ rawDeg: Double) -> Double { rawDeg + angleOffsetDeg }

    func residual(_ s: Sample) -> Double {
        let f = fit(for: s.dir)
        return s.rawMm * f.scale + f.offsetMm - s.trueMm
    }

    func describe(_ f: Fit) -> String {
        if f.count == 0 { return "нет эталонов" }
        let sign = f.offsetMm >= 0 ? "+" : "−"
        return String(format: "×%.4f (%+.2f%%) %@ %.1f мм · %d шт.",
                      f.scale, (f.scale - 1) * 100, sign, abs(f.offsetMm), f.count)
    }

    // MARK: изменение

    mutating func add(_ s: Sample) { samples.append(s); refit() }
    mutating func addAngle(raw: Double, truth: Double) {
        angleSamples.append(AngleSample(rawDeg: raw, trueDeg: truth)); refit()
    }
    mutating func remove(id: UUID) {
        samples.removeAll { $0.id == id }
        angleSamples.removeAll { $0.id == id }
        refit()
    }

    mutating func refit() {
        global = Self.fitLine(samples)
        byDir = [:]
        for d in MeasureDir.allCases {
            let sub = samples.filter { $0.dir == d }
            if !sub.isEmpty { byDir[d.rawValue] = Self.fitLine(sub) }
        }
        angleOffsetDeg = angleSamples.isEmpty ? 0
            : angleSamples.map { $0.trueDeg - $0.rawDeg }.reduce(0, +) / Double(angleSamples.count)
    }

    static func fitLine(_ s: [Sample]) -> Fit {
        let n = Double(s.count)
        guard n > 0 else { return Fit() }
        let r = s.map(\.rawMm), t = s.map(\.trueMm)
        let spread = (r.max() ?? 0) - (r.min() ?? 0)
        var f = Fit(count: s.count)
        if s.count >= 3 && spread >= 300 {
            // прямая методом наименьших квадратов: масштаб + постоянный сдвиг
            let mr = r.reduce(0, +) / n, mt = t.reduce(0, +) / n
            var sxy = 0.0, sxx = 0.0
            for i in 0..<s.count { sxy += (r[i] - mr) * (t[i] - mt); sxx += (r[i] - mr) * (r[i] - mr) }
            f.scale = sxx > 0 ? sxy / sxx : 1
            f.offsetMm = mt - f.scale * mr
        } else {
            // мало эталонов или похожие длины — только масштаб
            var stt = 0.0, srr = 0.0
            for i in 0..<s.count { stt += t[i] * r[i]; srr += r[i] * r[i] }
            f.scale = srr > 0 ? stt / srr : 1
        }
        return f
    }

    // MARK: хранение на телефоне
    private static let key = "calibration.v2"

    static func load() -> Calibration {
        guard let d = UserDefaults.standard.data(forKey: key),
              let c = try? JSONDecoder().decode(Calibration.self, from: d) else { return Calibration() }
        return c
    }

    func save() {
        if let d = try? JSONEncoder().encode(self) { UserDefaults.standard.set(d, forKey: Self.key) }
    }
}
