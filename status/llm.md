# Нейросеть для телефона — 2026-11-12 10:19 UTC

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
  (картинки) mmproj-BF16.gguf 644 МБ sha256=302b92d565080b9cc0281186979ae75a7429ec23d14f6f7607a035539b21f3a6
  (картинки) mmproj-F16.gguf 641 МБ sha256=cd88edcf8d031894960bb0c9c5b9b7e1fea6ebee02b9f7ce925a00d12891f864
  (картинки) mmproj-F32.gguf 1272 МБ sha256=758b74e604c5374577c21026c5bdc3aec75560eccb4c67844c8f585d6ec74804
  sha256 Qwen3.5-4B-Q4_K_M.gguf 00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4
Qwen/Qwen3.5-2B-GGUF: нет
unsloth/Qwen3.5-2B-GGUF:
  Qwen3.5-2B-Q4_0.gguf 1158 МБ
  Qwen3.5-2B-Q4_K_M.gguf 1221 МБ
  Qwen3.5-2B-Q5_K_M.gguf 1368 МБ
  Qwen3.5-2B-Q8_0.gguf 1918 МБ
  (картинки) mmproj-BF16.gguf 640 МБ sha256=f17196c0d8fc756bc65be60075bd4a359917eee8a438505639511727c585d3c2
  (картинки) mmproj-F16.gguf 637 МБ sha256=7035e9cb8d7c6a9681d07eef9a364783e86ea4cd73faab2eabb4f43a101830c7
  (картинки) mmproj-F32.gguf 1264 МБ sha256=d23b0e7bd6fe4416151838434f6a33a1d5f116a82b35565a11579e37dc80ad78
  sha256 Qwen3.5-2B-Q4_K_M.gguf aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223
unsloth/Qwen3-4B-Instruct-2507-GGUF:
  Qwen3-4B-Instruct-2507-Q4_0.gguf 2265 МБ
  Qwen3-4B-Instruct-2507-Q4_K_M.gguf 2381 МБ
  Qwen3-4B-Instruct-2507-Q5_K_M.gguf 2755 МБ
  Qwen3-4B-Instruct-2507-Q8_0.gguf 4082 МБ
  sha256 Qwen3-4B-Instruct-2507-Q4_K_M.gguf 3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597
Qwen/Qwen3-4B-Instruct-2507-GGUF: нет
bartowski/Qwen_Qwen3.5-4B-GGUF:
  Qwen_Qwen3.5-4B-Q4_0.gguf 2647 МБ
  Qwen_Qwen3.5-4B-Q4_K_M.gguf 2873 МБ
  Qwen_Qwen3.5-4B-Q5_K_M.gguf 3284 МБ
  Qwen_Qwen3.5-4B-Q8_0.gguf 4408 МБ
  (картинки) mmproj-Qwen_Qwen3.5-4B-bf16.gguf 644 МБ sha256=463f39bd1c291c1186c319a8c90ff8640aafa678b14cbee2232d695113dfbb66
  (картинки) mmproj-Qwen_Qwen3.5-4B-f16.gguf 641 МБ sha256=659b59dd44b73b1cd34af6cc424669484b06dc80f4340adf8ea84ad776eef813
  sha256 Qwen_Qwen3.5-4B-Q4_K_M.gguf 13c16f426047e2de38cd075bdade4a7bcbc8c774384876f677740cda65f8a983

=== проверка скачивания (первые 4 МБ) Qwen3.5-4B
https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf → 206 4194304 GGUF
https://huggingface.co/Qwen/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf → 401 29 Inva
```
