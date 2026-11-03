# Нейроголос в телефоне (Silero v5 CIS, MIT)

Файлы голоса в git ветки `mebel-3d` не лежат (≈155 МБ) — они в ветке **`multik-voice`**:
`voice/` (front/enc/dec/voc.onnx, tts.json, stress.json, stress_emb.f16, homo.onnx, homo.json, homo_emb.q8) и `ort/` (onnxruntime-web).
Их надо положить в `Resources/Mebel/voice/` и `Resources/Mebel/ort/` на Маке перед сборкой в Xcode.
Без них приложение берёт голос с сервера (`tools/multik/tts`), а без сервера — голос iPhone.

- `build_voice.py` — как собраны модели: части Silero переписаны обычным PyTorch с теми же весами
  (внимание вручную, HourGlass с дополнением нулями), экспорт в ONNX opset 17, сверка с оригиналом (corr 1.0000).
  ISTFT считается в JS. Ударения — как silero-stress целиком: n-граммная модель (JS) + омографы (фразы-регулярки и маленький BERT `homo.onnx`, таблица слов int8 `homo_emb.q8`) — `build_homo.py`. Совпадение с Python 15/15 фраз.
- Запуск: ветка `multik-tts-test`, workflow `tts-test` (Actions сам публикует ветку `multik-voice`).
- `Resources/Mebel/multik-voice.js` — MKVoice.speak(text, {speaker, rate, pitch}) и MKStress.accent(text, lex).

## Голос Барсика — xenia (Silero v5_6_ru)
Утверждённый голос Барсика: спикер `xenia`, потом тон ×1,12 (как `asetrate=53760` при 48 кГц) и темп ×0,9286 (как `atempo`).
- `build_xenia.py` (ветка `multik-tts-test`, workflow `tts-test`) → ветка `multik-voice`: `voice/xenia/` (front/enc/dec/voc.onnx, tts.json) и эталоны `refs/xenia/`.
  У этой модели предсказатели длительностей и высоты берут ещё **тип предложения** (утверждение, вопрос «кто/что», общий, альтернативный, «разделительный», восклицание)
  и «фокус» (0): в ONNX входы `typ`, `foc`; в JS — `typeIds()` в `multik-voice.js` (как `classify_sentence` + `build_type_ids_tokens`). Сверено: corr 1.00000 на 5 фразах,
  JS совпадает с ONNX до отсчёта.
- В приложении: `MK.HERO_NEURAL` / `MK.heroNeural(lib, who)` (multik-engine.js) — у Барсика по умолчанию; в карточке «🎙 Голос» — «Нейроголос» (по умолчанию / xenia / выключен).
  `MKVoice.speak(text, {model: 'xenia', speaker: 'xenia'})`; в памяти одна модель голоса — `prepare()` озвучивает сначала все реплики одной модели, потом другой.
  Тон и темп — `shiftVoice()` в multik.html (кубическая интерполяция + WSOLA из multik-laugh.js). Нет файлов `voice/xenia/` в телефоне — Барсик говорит голосом iPhone.
- md5: front 46f787e455d16c1d809e4abc4d8fa8ac, enc 9f4a34b03cdeea2f0dfd5888240516a3, dec 3190f0afc6997cffc41baa4b430932d9, voc 395fdfb2f166564548e1614c5f253142.
