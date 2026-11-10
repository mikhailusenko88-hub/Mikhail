# 3D-модели для дизайнеров (OBJ, FBX, DAE, GLB, DXF)

Архив «Наш декор — 3D-модели для дизайнеров.zip»: 105 позиций (A80L, A100L — нет сечения), инструкция и каталог в PDF.
Архив в публичный репозиторий не кладём: дизайнер получает его после заявки (сайт → форма «Пришлём 3D-модели» → CRM, отправляет Юлия).

Пересборка:
1. Создать временную ветку `models-build`: эти файлы + `catalog.json` (из сайта: window.P страниц товаров и PROF из index.html),
   `fetch_assets.py` (из корня ветки paneli-render), `models.yml.txt` → `.github/workflows/models.yml`, `go.txt` = `prev=1`.
2. Push — Actions: Poly Haven текстуры → make_textures.py (цвет под фото каталога) → Blender 4.2 build_models.py → out/ коммитится в ветку.
3. Забрать out/, локально: `python3 make_guide.py "<папка Наш декор — 3D-модели>"`, упаковать zip.
4. Проверка импорта: в go.txt дописать строку со словом verify и запушить коммит с «verify» в сообщении → out/verify.txt.
5. Удалить временную ветку: `git push origin --delete models-build`.
