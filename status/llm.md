# Нейросеть для телефона — 2026-11-12 07:25 UTC

```
ответ API: 25083 байт
llama.cpp: v0.9.0 (2026-11-04T13:08:06Z)
--- все файлы выпуска:
nightly-tag.txt 7
--- последние выпуски с xcframework:
b12317 2026-11-12T06:58:35Z llama-b12317-xcframework.zip 65422712
b12316 2026-11-12T06:25:50Z llama-b12316-xcframework.zip 65422649
b12314 2026-11-12T05:22:52Z llama-b12314-xcframework.zip 65422656
b12311 2026-11-12T05:02:04Z llama-b12311-xcframework.zip 65422657
b12308 2026-11-12T04:32:11Z llama-b12308-xcframework.zip 65422657
b12307 2026-11-12T04:10:18Z llama-b12307-xcframework.zip 65422656
b12306 2026-11-12T03:45:58Z llama-b12306-xcframework.zip 65422474
b12304 2026-11-12T03:19:13Z llama-b12304-xcframework.zip 65422497
b12303 2026-11-12T02:55:34Z llama-b12303-xcframework.zip 65423030
b12302 2026-11-12T02:22:59Z llama-b12302-xcframework.zip 65423025
b12292 2026-11-11T20:15:19Z llama-b12292-xcframework.zip 65452134
b12291 2026-11-11T19:52:29Z llama-b12291-xcframework.zip 65452216
b12290 2026-11-11T19:32:52Z llama-b12290-xcframework.zip 65452137
b12289 2026-11-11T19:03:19Z llama-b12289-xcframework.zip 65452136
b12287 2026-11-11T18:15:36Z llama-b12287-xcframework.zip 65452133
b12284 2026-11-11T13:13:19Z llama-b12284-xcframework.zip 65452139
b12283 2026-11-11T06:17:37Z llama-b12283-xcframework.zip 65452138
b12282 2026-11-11T03:31:06Z llama-b12282-xcframework.zip 65452134
b12277 2026-11-11T03:11:17Z llama-b12277-xcframework.zip 65452200
b12274 2026-11-11T02:52:55Z llama-b12274-xcframework.zip 65474778
sha256: db87353dcfed41f2bd6474dd146fbd26ef0630d2f48c4e07a4b269f4646f7ec0
url: https://github.com/ggml-org/llama.cpp/releases/download/b12317/llama-b12317-xcframework.zip
распаковано: 36 файлов
/tmp/x
build-apple
build-apple/llama.xcframework
build-apple/llama.xcframework/ios-arm64
build-apple/llama.xcframework/ios-arm64/llama.framework
build-apple/llama.xcframework/ios-arm64/dSYMs
build-apple/llama.xcframework/macos-arm64_x86_64
build-apple/llama.xcframework/macos-arm64_x86_64/llama.framework
build-apple/llama.xcframework/macos-arm64_x86_64/dSYMs
4.0K	/tmp/x/build-apple/llama.xcframework/Info.plist
75M	/tmp/x/build-apple/llama.xcframework/ios-arm64
150M	/tmp/x/build-apple/llama.xcframework/macos-arm64_x86_64
llama.h: /tmp/x/build-apple/llama.xcframework/ios-arm64/llama.framework/Headers/llama.h
--- module.modulemap
framework module llama {
    umbrella "Headers"

    link "c++"
    link framework "Accelerate"
    link framework "Metal"
    link framework "Foundation"

    export *
}
--- Info.plist (xcframework)
--- бинарники ios-arm64:
-rwxr-xr-x 1 runner runner 12594496 Nov 12 06:33 /tmp/x/build-apple/llama.xcframework/ios-arm64/llama.framework/llama
/tmp/x/build-apple/llama.xcframework/ios-arm64/llama.framework/llama: Mach-O 64-bit arm64 dynamically linked shared library, flags:<NOUNDEFS|DYLDLINK|TWOLEVEL|WEAK_DEFINES|BINDS_TO_WEAK|NO_REEXPORTED_DYLIBS|HAS_TLV_DESCRIPTORS>

=== Hugging Face
Qwen/Qwen3.5-4B-GGUF: нет
unsloth/Qwen3.5-4B-GGUF:
  Qwen3.5-4B-Q4_0.gguf 2463 МБ
  Qwen3.5-4B-Q4_K_M.gguf 2613 МБ
  Qwen3.5-4B-Q5_K_M.gguf 2998 МБ
  Qwen3.5-4B-Q8_0.gguf 4274 МБ
  (картинки) mmproj-BF16.gguf
  (картинки) mmproj-F16.gguf
Qwen/Qwen3.5-2B-GGUF: нет
unsloth/Qwen3.5-2B-GGUF:
  Qwen3.5-2B-Q4_0.gguf 1158 МБ
  Qwen3.5-2B-Q4_K_M.gguf 1221 МБ
  Qwen3.5-2B-Q5_K_M.gguf 1368 МБ
  Qwen3.5-2B-Q8_0.gguf 1918 МБ
  (картинки) mmproj-BF16.gguf
  (картинки) mmproj-F16.gguf
unsloth/Qwen3-4B-Instruct-2507-GGUF:
  Qwen3-4B-Instruct-2507-Q4_0.gguf 2265 МБ
  Qwen3-4B-Instruct-2507-Q4_K_M.gguf 2381 МБ
  Qwen3-4B-Instruct-2507-Q5_K_M.gguf 2755 МБ
  Qwen3-4B-Instruct-2507-Q8_0.gguf 4082 МБ
Qwen/Qwen3-4B-Instruct-2507-GGUF: нет
bartowski/Qwen_Qwen3.5-4B-GGUF:
  Qwen_Qwen3.5-4B-Q4_0.gguf 2647 МБ
  Qwen_Qwen3.5-4B-Q4_K_M.gguf 2873 МБ
  Qwen_Qwen3.5-4B-Q5_K_M.gguf 3284 МБ
  Qwen_Qwen3.5-4B-Q8_0.gguf 4408 МБ
  (картинки) mmproj-Qwen_Qwen3.5-4B-bf16.gguf
  (картинки) mmproj-Qwen_Qwen3.5-4B-f16.gguf

=== проверка скачивания (первые 4 МБ) Qwen3.5-4B
https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf → 206 4194304 GGUF
https://huggingface.co/Qwen/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf → 401 29 Inva
```
