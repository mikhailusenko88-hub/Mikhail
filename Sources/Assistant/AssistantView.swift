import SwiftUI
import UniformTypeIdentifiers
import AVFoundation
import PhotosUI

/// Раздел «Помощник»: своя нейросеть в телефоне, голос, интернет, CRM, база знаний.
struct AssistantScreen: View {
    @Environment(\.dismiss) private var dismiss
    @StateObject private var brain = AssistantBrain.shared
    @StateObject private var store = ModelStore.shared
    @StateObject private var ears = AssistantEars.shared
    @State private var input = ""
    @State private var showSettings = false
    @State private var openTool: Set<String> = []
    @FocusState private var typing: Bool
    // вложение к следующему сообщению: фото или файл
    enum Attach { case photo(UIImage), file(String) }
    @State private var attach: Attach?
    @State private var showPhotos = false
    @State private var showCamera = false
    @State private var showFiles = false
    @State private var photoItem: PhotosPickerItem?
    @State private var attachError = ""

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                if store.readyModel == nil {
                    ScrollView { FirstRunCard(store: store).padding(16) }
                } else {
                    chat
                }
                inputBar
            }
            .navigationTitle("Помощник")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button { brain.stop(); dismiss() } label: { Image(systemName: "chevron.left") }
                }
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    Button { brain.speak.toggle(); if !brain.speak { Speaker.shared.stop() } } label: {
                        Image(systemName: brain.speak ? "speaker.wave.2.fill" : "speaker.slash")
                    }
                    Button { brain.newChat() } label: { Image(systemName: "arrow.counterclockwise") }
                        .disabled(brain.messages.isEmpty)
                    Button { showSettings = true } label: { Image(systemName: "gearshape") }
                }
            }
            .sheet(isPresented: $showSettings, onDismiss: { brain.reviewPending() }) { AssistantSettings(brain: brain, store: store, ears: ears) }
            .overlay(alignment: .bottom) {
                if let p = brain.pending { ConfirmCard(p: p) { brain.answer($0) }.padding(12).padding(.bottom, 70) }
            }
        }
        .navigationViewStyle(.stack)
        .photosPicker(isPresented: $showPhotos, selection: $photoItem, matching: .images)
        .onChange(of: photoItem) { item in
            guard let item else { return }
            Task {
                if let d = try? await item.loadTransferable(type: Data.self), let im = UIImage(data: d) { attach = .photo(im); attachError = "" }
                else { attachError = "Фото не загрузилось — попробуйте ещё раз." }
                photoItem = nil
            }
        }
        .fileImporter(isPresented: $showFiles, allowedContentTypes: [.item]) { r in
            switch r {
            case .success(let u):
                if let ref = Files.importCopy(u) { attach = .file(ref); attachError = "" } else { attachError = "Файл не открылся." }
            case .failure(let e): attachError = e.localizedDescription
            }
        }
        .fullScreenCover(isPresented: $showCamera) {
            CameraPicker { im in attach = .photo(im) }.ignoresSafeArea()
        }
        .onAppear { takeIncoming() }
        .onChange(of: brain.incoming) { _ in takeIncoming() }
        .task { await brain.refreshCRM(); brain.reviewPending(); brain.warmUp() }
        .onDisappear {
            // нейросеть занимает ~3 ГБ памяти — отдаём её сканеру и мультикам
            brain.stop()
            _ = ears.finish()
            Speaker.shared.stop()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { LlamaEngine.shared.unload() }
        }
    }

    /// Файл пришёл через «Поделиться» → «Замер 3D»: прикрепляем и ждём вопроса.
    private func takeIncoming() {
        guard let ref = brain.incoming else { return }
        brain.incoming = nil
        if Files.isImage(ref), let im = UIImage(contentsOfFile: Files.url(ref).path) { attach = .photo(im) } else { attach = .file(ref) }
        attachError = ""
    }

    private func sendNow(_ text: String) {
        var img: UIImage?, file: String?
        switch attach {
        case .photo(let im): img = im
        case .file(let ref): file = ref
        case nil: break
        }
        brain.send(text, image: img, file: file)
        attach = nil
        input = ""
    }

    private var chat: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 10) {
                    if brain.messages.isEmpty { hello }
                    ForEach(brain.messages.filter { $0.tool != "hint" }) { m in row(m).id(m.id) }
                    if brain.busy {
                        if !brain.live.isEmpty { bubble(brain.live, mine: false) }
                        if !brain.stage.isEmpty {
                            HStack(spacing: 8) { ProgressView(); Text(brain.stage).font(.footnote).foregroundColor(.secondary) }
                                .padding(.horizontal, 4)
                        }
                    }
                    Color.clear.frame(height: 4).id("end")
                }
                .padding(12)
            }
            .onChange(of: brain.messages.count) { _ in withAnimation { proxy.scrollTo("end", anchor: .bottom) } }
            .onChange(of: brain.live) { _ in proxy.scrollTo("end", anchor: .bottom) }
            .onAppear { proxy.scrollTo("end", anchor: .bottom) }
            .onTapGesture { typing = false }
        }
    }

    private var hello: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Чем помочь?").font(.title3.bold())
            Text("Скажите или напишите задание. Например:").foregroundColor(.secondary)
            ForEach([CRMClient.connected ? "Что у нас сегодня по заявкам?" : "Сколько будет 3,2 × 2,7 минус дверь 0,9 × 2,1, по 1290 ₽ за м²?",
                     "Найди, сколько стоит доставка ПЭК из Москвы в Петербург 300 кг",
                     "Запомни: поставщик отгружает по вторникам", "Напомни завтра в 10:00 позвонить клиенту"], id: \.self) { ex in
                Button { input = ex; typing = true } label: {
                    Text(ex).font(.subheadline).padding(10).frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
                }.buttonStyle(.plain)
            }
        }
        .padding(.top, 8)
    }

    @ViewBuilder private func row(_ m: ChatMsg) -> some View {
        switch m.role {
        case .user:
            VStack(alignment: .trailing, spacing: 4) {
                if let f = m.file {
                    HStack {
                        Spacer(minLength: 40)
                        ShareLink(item: Files.url(f)) {
                            Label(Files.name(f), systemImage: "doc.fill").font(.caption).lineLimit(1)
                                .padding(.horizontal, 10).padding(.vertical, 7)
                                .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 12))
                        }
                    }
                }
                if let img = m.image, let ui = Eyes.load(img) {
                    HStack {
                        Spacer(minLength: 40)
                        Image(uiImage: ui).resizable().scaledToFit().frame(maxWidth: 220, maxHeight: 220)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                }
                bubble(m.text, mine: true)
            }
        case .assistant:
            if !m.text.isEmpty { bubble(m.text, mine: false) }
        case .tool:
            let open = openTool.contains(m.id)
            VStack(alignment: .leading, spacing: 4) {
                Button { if open { openTool.remove(m.id) } else { openTool.insert(m.id) } } label: {
                    Label(Self.toolTitle(m.tool ?? ""), systemImage: "wrench.and.screwdriver")
                        .font(.caption).foregroundColor(.secondary)
                }.buttonStyle(.plain)
                Text(open ? m.text : String(m.text.prefix(140)) + (m.text.count > 140 ? " …" : ""))
                    .font(.caption2).foregroundColor(.secondary).textSelection(.enabled)
            }
            .padding(8)
            .background(Color(.tertiarySystemBackground), in: RoundedRectangle(cornerRadius: 10))
        case .note:
            Text(m.text).font(.footnote).foregroundColor(.orange).padding(.horizontal, 4)
        }
    }

    /// **жирный**, `код`, ссылки — как в чате, а не звёздочками.
    static func rich(_ t: String) -> AttributedString {
        (try? AttributedString(markdown: t, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace))) ?? AttributedString(t)
    }

    static func toolTitle(_ n: String) -> String {
        switch n {
        case "web_search": return "Поиск в интернете"
        case "open_page": return "Страница"
        case "remember": return "Запомнила"
        case "recall": return "Из памяти"
        case "forget": return "Удалено из памяти"
        case "calc": return "Расчёт"
        case "skill_improve": return "Улучшила навык"
        case "skill_rollback": return "Вернула версию навыка"
        case "reminder": return "Напоминание"
        case "open_link": return "Ссылка"
        case "file_read": return "Файл"
        default: return n.hasPrefix("crm") ? "CRM" : n
        }
    }

    private func bubble(_ t: String, mine: Bool) -> some View {
        HStack {
            if mine { Spacer(minLength: 40) }
            Text(Self.rich(t))
                .textSelection(.enabled)
                .padding(10)
                .foregroundColor(mine ? .white : .primary)
                .background(mine ? Color.blue : Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 16))
            if !mine { Spacer(minLength: 40) }
        }
    }

    private var inputBar: some View {
        VStack(spacing: 4) {
            if !ears.problem.isEmpty {
                Text(ears.problem).font(.caption).foregroundColor(.orange).frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 12)
            }
            if !attachError.isEmpty {
                Text(attachError).font(.caption).foregroundColor(.orange).frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 12)
            }
            if let a = attach {
                HStack(spacing: 8) {
                    switch a {
                    case .photo(let im):
                        Image(uiImage: im).resizable().scaledToFill().frame(width: 52, height: 52).clipShape(RoundedRectangle(cornerRadius: 8))
                        Text("Фото — спросите, что нужно").font(.caption).foregroundColor(.secondary)
                    case .file(let ref):
                        Image(systemName: "doc.fill").font(.system(size: 26)).foregroundColor(.blue).frame(width: 52, height: 52)
                        Text(Files.name(ref)).font(.caption).lineLimit(2)
                    }
                    Spacer()
                    Button { attach = nil } label: { Image(systemName: "xmark.circle.fill").font(.system(size: 22)).foregroundColor(.secondary) }
                }
                .padding(.horizontal, 12).padding(.top, 6)
            }
            HStack(alignment: .bottom, spacing: 6) {
                Menu {
                    Button { showPhotos = true } label: { Label("Фото из галереи", systemImage: "photo") }
                    if UIImagePickerController.isSourceTypeAvailable(.camera) {
                        Button { showCamera = true } label: { Label("Снять фото", systemImage: "camera") }
                    }
                    Button { showFiles = true } label: { Label("Файл", systemImage: "doc") }
                } label: {
                    Image(systemName: "paperclip").font(.system(size: 21)).foregroundColor(.blue).frame(width: 34, height: 40)
                }
                .disabled(brain.busy || store.readyModel == nil)

                Button {
                    if ears.listening {
                        let t = ears.finish().trimmingCharacters(in: .whitespacesAndNewlines)
                        if !t.isEmpty || attach != nil { sendNow(t) }
                    } else {
                        typing = false
                        ears.start()
                    }
                } label: {
                    Image(systemName: ears.listening ? "stop.circle.fill" : "mic.fill")
                        .font(.system(size: 22)).foregroundColor(ears.listening ? .red : .blue)
                        .frame(width: 34, height: 40)
                }
                .disabled(brain.busy || store.readyModel == nil)

                TextField(ears.listening ? "Слушаю… нажмите ■, когда закончите" : "Задание…", text: ears.listening ? $ears.text : $input, axis: .vertical)
                    .lineLimit(1...6)
                    .focused($typing)
                    .padding(.horizontal, 12).padding(.vertical, 9)
                    .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 18))

                if brain.busy {
                    Button { brain.stop() } label: {
                        Image(systemName: "stop.fill").font(.system(size: 18)).foregroundColor(.white)
                            .frame(width: 40, height: 40).background(Color.red, in: Circle())
                    }
                } else {
                    Button { sendNow(input) } label: {
                        Image(systemName: "arrow.up").font(.system(size: 18, weight: .bold)).foregroundColor(.white)
                            .frame(width: 40, height: 40).background(Color.blue, in: Circle())
                    }
                    .disabled((input.trimmingCharacters(in: .whitespaces).isEmpty && attach == nil) || store.readyModel == nil)
                }
            }
            .padding(.horizontal, 10).padding(.vertical, 8)
        }
        .background(.bar)
    }
}

struct ConfirmCard: View {
    let p: PendingConfirm
    let answer: (Bool) -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(p.title, systemImage: "exclamationmark.shield.fill").font(.headline).foregroundColor(.orange)
            ScrollView { Text(p.detail).font(.subheadline).frame(maxWidth: .infinity, alignment: .leading) }.frame(maxHeight: 180)
            HStack {
                Button("Нет") { answer(false) }.buttonStyle(.bordered)
                Spacer()
                Button("Да, сделать") { answer(true) }.buttonStyle(.borderedProminent)
            }
        }
        .padding(14)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18))
        .shadow(radius: 8)
    }
}

struct FirstRunCard: View {
    @ObservedObject var store: ModelStore
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Своя нейросеть в телефоне").font(.title2.bold())
            Text("Один раз скачайте файл нейросети (около 2,6 ГБ, лучше по Wi-Fi). Дальше она работает прямо в iPhone, без интернета и без оплаты. Разговоры и база знаний остаются в телефоне.")
                .foregroundColor(.secondary)
            ModelList(store: store)
        }
    }
}

struct ModelList: View {
    @ObservedObject var store: ModelStore
    @State private var pick = false
    @State private var msg = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(BrainModel.all) { m in
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Image(systemName: store.selectedID == m.id ? "checkmark.circle.fill" : "circle")
                            .foregroundColor(store.selectedID == m.id ? .green : .secondary)
                        Text(m.title).font(.headline)
                        Spacer()
                        if store.isReady(m) {
                            Text("в телефоне").font(.caption).foregroundColor(.green)
                        }
                    }
                    Text(m.note).font(.caption).foregroundColor(.secondary)
                    if store.downloading == m.id {
                        ProgressView(value: store.progress)
                        HStack { Text(store.status).font(.caption2); Spacer(); Button("Стоп") { store.cancel() }.font(.caption) }
                    } else if store.isReady(m) {
                        HStack {
                            Button("Выбрать") { store.selectedID = m.id }.disabled(store.selectedID == m.id)
                            Spacer()
                            Button("Удалить", role: .destructive) { store.delete(m) }
                        }.font(.callout)
                        if m.eyeFile != nil {
                            if store.downloading == m.id + "#eye" {
                                ProgressView(value: store.progress)
                                HStack { Text(store.status).font(.caption2); Spacer(); Button("Стоп") { store.cancel() }.font(.caption) }
                            } else if store.isEyeReady(m) {
                                Label("«Зрение» для фото — в телефоне", systemImage: "eye").font(.caption).foregroundColor(.green)
                            } else {
                                Button { store.downloadEye(m) } label: { Label("Скачать «зрение» для фото — \(m.eyeMB) МБ", systemImage: "eye") }
                                    .font(.callout).disabled(store.downloading != nil)
                                Text("Без него нейросеть читает только текст на фото и в файлах; с ним — понимает, что изображено.")
                                    .font(.caption2).foregroundColor(.secondary)
                            }
                        }
                    } else {
                        Button { store.download(m) } label: { Label("Скачать", systemImage: "arrow.down.circle") }
                            .disabled(store.downloading != nil)
                    }
                }
                .padding(12)
                .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 14))
                .onTapGesture { if store.isReady(m) { store.selectedID = m.id } }
            }
            if store.downloading == nil && !store.status.isEmpty { Text(store.status).font(.caption).foregroundColor(.secondary) }
            Button { pick = true } label: { Label("Файл нейросети уже есть (.gguf) — выбрать в «Файлах»", systemImage: "folder") }
                .font(.caption)
            if !msg.isEmpty { Text(msg).font(.caption) }
        }
        .fileImporter(isPresented: $pick, allowedContentTypes: [.data]) { r in
            if case .success(let u) = r { msg = store.importFile(u) }
        }
    }
}

struct AssistantSettings: View {
    @ObservedObject var brain: AssistantBrain
    @ObservedObject var store: ModelStore
    @ObservedObject var ears: AssistantEars
    @StateObject private var kb = KnowledgeBase.shared
    @Environment(\.dismiss) private var dismiss
    @State private var crmBase = CRMClient.base
    @State private var crmKey = ""
    @State private var crmStatus = CRMClient.connected ? "Ключ сохранён." : "Не подключена."
    @State private var pickPack = false
    @State private var packMsg = ""
    @State private var voiceID = UserDefaults.standard.string(forKey: "assistant.voice") ?? ""

    var body: some View {
        NavigationView {
            Form {
                Section("Нейросеть") { ModelList(store: store) }

                Section {
                    TextField("Адрес CRM", text: $crmBase).keyboardType(.URL).autocorrectionDisabled().textInputAutocapitalization(.never)
                    SecureField(CRMClient.connected ? "Ключ сохранён — вставьте новый, чтобы заменить" : "Ключ из CRM → Ещё → Помощник", text: $crmKey)
                    Button("Сохранить и проверить") {
                        CRMClient.base = crmBase
                        if !crmKey.isEmpty { CRMClient.key = crmKey.trimmingCharacters(in: .whitespacesAndNewlines); crmKey = "" }
                        crmStatus = "Проверяю…"
                        Task {
                            await brain.refreshCRM()
                            crmStatus = brain.crmTools.isEmpty ? "CRM не ответила или ключ неверный." : "Подключена: команд CRM — \(brain.crmTools.count)."
                        }
                    }
                    if CRMClient.connected {
                        Button("Отключить CRM", role: .destructive) { CRMClient.key = nil; brain.crmTools = []; crmStatus = "Отключена." }
                    }
                    Text(crmStatus).font(.caption).foregroundColor(.secondary)
                } header: { Text("CRM") } footer: {
                    Text("Необязательно: без CRM помощник работает сам по себе. Когда решите подключить — ключ создаётся в CRM → Ещё → Помощник, хранится в связке ключей телефона.")
                }

                Section {
                    Toggle("Отвечать голосом", isOn: $brain.speak)
                    Picker("Голос", selection: $voiceID) {
                        Text("Лучший русский").tag("")
                        ForEach(AVSpeechVoices.russian, id: \.identifier) { v in Text(v.name + " (" + MultikTTS.qualityName(v.quality) + ")").tag(v.identifier) }
                    }
                    .onChange(of: voiceID) { v in UserDefaults.standard.set(v, forKey: "assistant.voice") }
                    Toggle("Распознавание через Apple", isOn: $ears.allowServer)
                } header: { Text("Голос") } footer: {
                    Text(ears.onDevice ? "Русская речь распознаётся прямо в телефоне — звук никуда не уходит."
                                       : "В этом телефоне русская речь распознаётся только на серверах Apple. Пока переключатель выключен — микрофон не работает, пишите текстом.")
                }

                Section {
                    NavigationLink("Навыки (\(kb.skills.count))") { KnowledgeList(kb: kb, onlySkills: true) }
                    NavigationLink("Что я знаю (\(kb.items.count))") { KnowledgeList(kb: kb) }
                    Button("Загрузить пакет знаний (.json или .md)") { pickPack = true }
                    ShareLink(item: kb.exportURL()) { Label("Сохранить копию базы знаний", systemImage: "square.and.arrow.up") }
                    if CRMClient.connected {
                        Button("Обновить знания из CRM") {
                            packMsg = "Обновляю…"
                            Task { await brain.refreshCRM(); packMsg = brain.knowledgeNote.isEmpty ? "CRM не ответила." : brain.knowledgeNote }
                        }
                        Button("Копию своей базы — на сервер") {
                            packMsg = "Сохраняю…"
                            Task { packMsg = await CRMClient.backupKnowledge(kb.ownForBackup) }
                        }
                        Button("Вернуть базу с сервера (новый телефон)") {
                            packMsg = "Забираю…"
                            Task {
                                if let l = await CRMClient.restoreKnowledge() { packMsg = "Вернула записей: \(kb.restore(l))." } else { packMsg = "Сервер не ответил." }
                            }
                        }
                    }
                    if !packMsg.isEmpty { Text(packMsg).font(.caption) }
                } header: { Text("Знания") } footer: {
                    Text("База лежит в «Файлы» → На iPhone → Замер 3D → Assistant. Разделы с пометкой «основа» помощник помнит всегда, остальные — подтягивает по теме вопроса. Знания о магазине приходят из CRM (Ещё → Помощник) — в GitHub их нет.")
                }
            }
            .navigationTitle("Помощник — настройки")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Готово") { dismiss() } } }
            .fileImporter(isPresented: $pickPack, allowedContentTypes: [.json, .plainText, .data]) { r in
                if case .success(let u) = r {
                    packMsg = kb.importPack(u)
                    if !kb.pendingUpdates.isEmpty { packMsg += " Навыков обновлено: \(kb.pendingUpdates.count) — помощник прочитает и ответит в чате."; brain.reviewPending() }
                }
            }
        }
    }
}

enum AVSpeechVoices {
    static var russian: [AVSpeechSynthesisVoice] {
        AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix("ru") }.sorted { $0.quality.rawValue > $1.quality.rawValue }
    }
}

struct KnowledgeList: View {
    @ObservedObject var kb: KnowledgeBase
    var onlySkills = false
    @State private var q = ""
    var list: [KnowledgeItem] {
        let pool = onlySkills ? kb.skills : kb.items
        let all = pool.sorted { ($0.pinned ? 0 : 1, $1.date) < ($1.pinned ? 0 : 1, $0.date) }
        return q.isEmpty ? all : kb.search(q, limit: 50, excludePinned: false).filter { !onlySkills || $0.isSkill }
    }
    var body: some View {
        List {
            ForEach(list) { it in
                NavigationLink { KnowledgeEdit(kb: kb, item: it) } label: {
                    VStack(alignment: .leading, spacing: 3) {
                        HStack {
                            if it.pinned { Image(systemName: "pin.fill").font(.caption).foregroundColor(.orange) }
                            if it.isSkill { Text("🛠 v\(it.version)").font(.caption2).foregroundColor(.teal) }
                            Text(it.title).font(.subheadline.bold())
                        }
                        Text(it.text).font(.caption).foregroundColor(.secondary).lineLimit(2)
                        Text(it.source).font(.caption2).foregroundColor(.secondary)
                    }
                }
            }
            .onDelete { idx in idx.map { list[$0].id }.forEach(kb.remove) }
        }
        .searchable(text: $q, prompt: "Найти в знаниях")
        .navigationTitle(onlySkills ? "Навыки" : "Что я знаю")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                NavigationLink { KnowledgeEdit(kb: kb, item: KnowledgeItem(title: "", text: "", kind: onlySkills ? "навык" : "знание")) } label: { Image(systemName: "plus") }
            }
        }
    }
}

struct KnowledgeEdit: View {
    @ObservedObject var kb: KnowledgeBase
    @State var item: KnowledgeItem
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        Form {
            TextField(item.isSkill ? "Название навыка" : "Тема", text: $item.title)
            if item.isSkill {
                Text("Версия \(item.version) · \(item.source)" + (item.history.isEmpty ? "" : " · прошлых версий: \(item.history.count)"))
                    .font(.caption).foregroundColor(.secondary)
                if !item.history.isEmpty {
                    Button("Вернуть прошлую версию") {
                        _ = kb.rollback(skill: item.title)
                        if let fresh = kb.items.first(where: { $0.id == item.id }) { item = fresh }
                    }
                }
            } else {
                Toggle("Основа — помнить всегда", isOn: $item.pinned)
            }
            TextEditor(text: $item.text).frame(minHeight: 260)
        }
        .navigationTitle(item.title.isEmpty ? "Новая запись" : item.title)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("Сохранить") {
                    if item.isSkill {
                        if let u = kb.saveSkill(title: item.title, text: item.text, source: "вы") { kb.pendingUpdates.append(u) }
                    } else if kb.items.contains(where: { $0.id == item.id }) { kb.update(item) }
                    else { kb.add(title: item.title, text: item.text, source: "вы", pinned: item.pinned) }
                    dismiss()
                }.disabled(item.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
    }
}

/// Камера для фото в чат Помощника.
struct CameraPicker: UIViewControllerRepresentable {
    let done: (UIImage) -> Void
    @Environment(\.dismiss) private var dismiss

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let p = UIImagePickerController()
        p.sourceType = .camera
        p.delegate = context.coordinator
        return p
    }

    func updateUIViewController(_ vc: UIImagePickerController, context: Context) {}

    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let parent: CameraPicker
        init(_ p: CameraPicker) { parent = p }
        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            if let im = info[.originalImage] as? UIImage { parent.done(im) }
            parent.dismiss()
        }
        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) { parent.dismiss() }
    }
}
