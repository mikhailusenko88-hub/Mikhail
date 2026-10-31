# Сценарий серии для раздела «Мультики» (format multik/1)

Один файл = одна серия. Сценарии пишутся в чате, кладутся в ветку `multik` (файл + строка в `index.json`),
в приложении кнопка «⟳ Загрузить новые серии» их забирает. Можно и «📋 Вставить» текст JSON.

## Шапка
`series` (название сериала), `episode` (номер), `title`, `length` (цель, сек ≈300), `music` (настроение по умолчанию),
`subtitles` (true/false), `narrator.voice` (голос рассказчика, id «Р»), `youtube {title, description, tags}`,
`endText`/`endSub` (финальная заставка), `titleCard:false`/`endCard:false` — отключить заставки.

## Персонажи — строгий код
`characters: [{id:"К1", name, kind, age, height, colors{}, pattern[], acc[], hair{}, outfit{}, voice{base,pitch,rate}, speed, about}]`
- Код = id + хэш внешности и голоса (`К1-86C38C`). При первой загрузке персонаж замораживается в телефоне.
- В следующих сериях персонажа можно НЕ описывать (он уже в библиотеке) или повторить описание СЛОВО В СЛОВО.
  Любое отличие → ошибка «нельзя менять». Новый вид = новый id (К3, К4…). Имя/about в код не входят.
- kind: cat, dog, bear, rabbit, mouse, fox, pig, human. age: kid / adult / old (у human — пропорции).
- colors (животные): body, belly, inner, eyes, nose, stripe, outline. human: skin, hair, eyes.
- pattern: stripes, spots, muzzle, tailtip, socks, mask, patch, nobelly.
- acc: bow, hat, crown, glasses, flower, scarf, collar (строкой или {type,color}).
- human: hair {style: short|long|pigtails|bun|curly|bald, color}, outfit {shirt, pants, skirt, shoes, stripe}.
- voice: base male|female, pitch 0.5–2 (детский 1.35–1.7), rate 0.4–0.6 (0.5 норма).

## Локации — тоже с кодом
`locations: [{id:"Л1", name, type, time, weather, seed, opts}]`
type: forest, meadow, yard, room, kitchen, street, beach, winter, space, playground. time: day|evening|night. weather: none|rain|snow.

## Сцены
`scenes: [{id:"С1", location:"Л1", time?, weather?, music?, camera?, cast:[{who,x(0..1),z,face:left|right|camera,hidden,prop}], props:[{id:"П1",type,x,color}], steps:[…], tail}]`

Шаги идут по очереди; `with:true` — одновременно с предыдущим; `after:сек` — задержка.
- `{who, say:"текст", to:"К2", emotion, pause}` — реплика (Р — рассказчик, не рисуется).
- `{who, do:...}`: walk/run {to: x или id}, enter {from:left|right, to}, exit {side}, jump, wave, dance, spin, nod, shake,
  clap, point, think {text}, laugh, scared, cry, bow, surprise, fall, sit, sleep, stand, wake, turn/look {to: left|right|camera|id},
  take {prop}, drop, give {to}. Любой шаг может нести `emotion` и `face`.
- emotion: neutral, happy, laugh, sad, cry, angry, surprised, scared, sleepy, love, shy.
- Камера: `{camera: wide|medium|close|two|pan, on: id | [id,id] | x, zoom}`, `{shake: сек}`.
- `{wait: сек}`, `{sfx: boing|thud|whoosh|pop|clap|ding|sparkle|magic|splash|knock|bell|step|drum|meow|bark|laugh}`,
  `{music: happy|calm|tense|sad|adventure|magic|night|none}`.
- props type: ball, apple, fish, box, gift, flower, book, star, cake, bone, carrot, cheese, balloon, key, cup.

## Длина
≈ 5 мин серия: 8–12 сцен, 60–90 реплик. Длительность реплики = длине озвучки; ходьба 0.2 экрана/с, бег 0.42.
Проверка до отправки: `node tools/multik/check.js файл.json` (коды, ошибки, длительность).
