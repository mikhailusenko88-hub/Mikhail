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
