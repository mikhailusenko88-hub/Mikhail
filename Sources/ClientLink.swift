import Foundation
import Security

/// Ключ GitHub для «Ссылки клиенту» — хранится в Связке ключей телефона.
enum GitHubKey {
    private static let service = "ru.usenko.zamer3d.github"

    static var value: String? {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                kSecAttrService as String: service,
                                kSecReturnData as String: true]
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess,
              let d = out as? Data, let s = String(data: d, encoding: .utf8), !s.isEmpty else { return nil }
        return s
    }

    static func set(_ v: String?) {
        let base: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                   kSecAttrService as String: service]
        SecItemDelete(base as CFDictionary)
        guard let v = v?.trimmingCharacters(in: .whitespacesAndNewlines), !v.isEmpty else { return }
        var add = base
        add[kSecValueData as String] = Data(v.utf8)
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(add as CFDictionary, nil)
    }
}

/// Выкладывает клиентскую страницу в ветку mebel; сервер в Казахстане забирает её раз в минуту.
/// Ссылка: http://89.207.252.121:8080/mebel/<код>/  — код случайный, номер проекта 100/N из реестра README.
enum ClientLink {
    static let repo = "mikhailusenko88-hub/Mikhail"
    static let branch = "mebel"
    static let server = "http://89.207.252.121:8080/mebel/"

    struct Link: Codable { var code: String; var number: String }

    enum Failure: LocalizedError {
        case noKey, http(Int, String), forbidden(String)
        var errorDescription: String? {
            switch self {
            case .noKey: return "Нет ключа GitHub. Введи его в разделе «Мебель» → «Ссылки клиентам»."
            case .http(let c, let m): return c == 401 ? "Ключ GitHub не подходит (401)." : "GitHub ответил \(c): \(m)"
            case .forbidden(let w): return "На странице есть служебное слово «\(w)» — не выкладываю."
            }
        }
    }

    /// Номер и код: существующие (обновление, ссылка не меняется) или новые.
    static func prepare(existing: Link?) async throws -> (link: Link, isNew: Bool) {
        if let e = existing { return (e, false) }
        let (readme, _) = try await getFile("README.md")
        var maxN = 0
        let re = try NSRegularExpression(pattern: "100/(\\d+)")
        let s = readme ?? ""
        for m in re.matches(in: s, range: NSRange(s.startIndex..., in: s)) {
            if let r = Range(m.range(at: 1), in: s), let n = Int(s[r]) { maxN = max(maxN, n) }
        }
        let chars = Array("abcdefghijkmnpqrstuvwxyz23456789")
        let code = String((0..<7).map { _ in chars.randomElement()! })
        return (Link(code: code, number: "100/\(maxN + 1)"), true)
    }

    /// Загрузить страницу; для нового проекта дописать строку в реестр.
    static func publish(html: String, link: Link, isNew: Bool, what: String) async throws -> URL {
        let low = html.lowercased()
        for w in ["claude", "anthropic", "₽", "деталь", "распил", "наценк", "себестоим"] where low.contains(w) {
            throw Failure.forbidden(w)
        }
        let path = "\(link.code)/index.html"
        let (_, sha) = try await getFile(path)
        try await putFile(path, content: Data(html.utf8), sha: sha, message: "Проект \(link.number)")
        if isNew {
            let (readme, rsha) = try await getFile("README.md")
            var r = readme ?? ""
            if !r.hasSuffix("\n") { r += "\n" }
            let clean = what.replacingOccurrences(of: "|", with: "/")
            r += "| \(link.number) | \(link.code) | \(clean) | \(server)\(link.code)/ |\n"
            try await putFile("README.md", content: Data(r.utf8), sha: rsha, message: "Реестр: \(link.number)")
        }
        return URL(string: "\(server)\(link.code)/")!
    }

    // MARK: GitHub API

    private static func request(_ path: String, method: String = "GET", body: Data? = nil) throws -> URLRequest {
        guard let key = GitHubKey.value else { throw Failure.noKey }
        let enc = path.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? path
        var url = URLComponents(string: "https://api.github.com/repos/\(repo)/contents/\(enc)")!
        if method == "GET" { url.queryItems = [URLQueryItem(name: "ref", value: branch)] }
        var r = URLRequest(url: url.url!)
        r.httpMethod = method
        r.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
        r.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        r.setValue("Zamer3D", forHTTPHeaderField: "User-Agent")
        r.httpBody = body
        r.timeoutInterval = 30
        return r
    }

    /// Текст файла и его sha (nil, nil — файла нет).
    private static func getFile(_ path: String) async throws -> (String?, String?) {
        let (data, resp) = try await URLSession.shared.data(for: try request(path))
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code == 404 { return (nil, nil) }
        guard code == 200 else { throw Failure.http(code, String(data: data, encoding: .utf8) ?? "") }
        let j = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let b64 = (j?["content"] as? String)?.replacingOccurrences(of: "\n", with: "") ?? ""
        let text = Data(base64Encoded: b64).flatMap { String(data: $0, encoding: .utf8) }
        return (text, j?["sha"] as? String)
    }

    private static func putFile(_ path: String, content: Data, sha: String?, message: String) async throws {
        var body: [String: Any] = ["message": message, "content": content.base64EncodedString(), "branch": branch,
                                   "committer": ["name": "Zamer3D", "email": "zamer3d@users.noreply.github.com"]]
        if let sha = sha { body["sha"] = sha }
        let data = try JSONSerialization.data(withJSONObject: body)
        let (out, resp) = try await URLSession.shared.data(for: try request(path, method: "PUT", body: data))
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard code == 200 || code == 201 else { throw Failure.http(code, String(data: out, encoding: .utf8) ?? "") }
    }

    /// Проверка ключа: читается ли реестр.
    static func check() async -> String {
        do {
            let (r, _) = try await getFile("README.md")
            return r == nil ? "Ключ работает, но реестра в ветке mebel нет" : "Ключ работает ✓"
        } catch { return error.localizedDescription }
    }
}
