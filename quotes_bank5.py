# -*- coding: utf-8 -*-
"""Банк цитат, часть 5 (второй месяц): русская классика, Казахстан, пословицы.
Только авторы без авторских прав; английский перевод свой. mood: light/dark/any; sc — подходящие картины."""


def q(ru, en, a_ru, a_en, mood="any", sc=None):
    d = dict(ru=ru, en=en, author_ru=a_ru, author_en=a_en, mood=mood)
    if sc:
        d["sc"] = sc
    return d


def A(pair, work_ru="", work_en=""):
    return pair[0] + ("  ·  " + work_ru if work_ru else ""), pair[1] + ("  ·  " + work_en if work_en else "")


PU = ("Александр Пушкин", "Alexander Pushkin")
LE = ("Михаил Лермонтов", "Mikhail Lermontov")
TU = ("Фёдор Тютчев", "Fyodor Tyutchev")
FE = ("Афанасий Фет", "Afanasy Fet")
NE = ("Николай Некрасов", "Nikolai Nekrasov")
BL = ("Александр Блок", "Alexander Blok")
BU = ("Иван Бунин", "Ivan Bunin")
TS = ("Марина Цветаева", "Marina Tsvetaeva")
YE = ("Сергей Есенин", "Sergei Yesenin")
MB = ("Михаил Булгаков", "Mikhail Bulgakov")
GR = ("Александр Грибоедов", "Alexander Griboyedov")
KR = ("Иван Крылов", "Ivan Krylov")
CH = ("Антон Чехов", "Anton Chekhov")
TO = ("Лев Толстой", "Leo Tolstoy")
DO = ("Фёдор Достоевский", "Fyodor Dostoevsky")
TG = ("Иван Тургенев", "Ivan Turgenev")
AB = ("Абай Кунанбаев", "Abai Kunanbaiuly")
KZ = ("Казахская пословица", "Kazakh proverb")
RU = ("Русская пословица", "Russian proverb")
WINTER = ["winter", "winter_village", "cabin", "deer", "xmas_tree", "birch"]
AUTUMN = ["autumn", "birch", "apple_orchard", "forest_rays"]
SEA = ["sea", "lighthouse", "moon_sea", "boat_dusk"]

QUOTES5 = {
    # ---------------- Пушкин
    "pushkin5_frost": q(["Мороз и солнце; день чудесный!", "Ещё ты дремлешь, друг прелестный —", "пора, красавица, проснись…"],
                        ["Frost and sunshine — a wondrous day!", "You are still drowsing, my lovely friend —", "it's time, my beauty, to wake…"],
                        *A(PU, "«Зимнее утро», 1829", "Winter Morning, 1829"), "light", WINTER),
    "pushkin5_storm": q(["Буря мглою небо кроет,", "вихри снежные крутя;", "то, как зверь, она завоет,", "то заплачет, как дитя."],
                        ["The storm veils the sky in darkness,", "whirling snowy gusts;", "now it howls like a wild beast,", "now it weeps like a child."],
                        *A(PU, "«Зимний вечер», 1825", "Winter Evening, 1825"), "dark", ["cabin", "winter_village", "winter"]),
    "pushkin5_heart": q("И сердце вновь горит и любит — оттого, что не любить оно не может.",
                        "And my heart burns and loves again — because it cannot help but love.",
                        *A(PU, "«На холмах Грузии», 1829", "On the Hills of Georgia, 1829"), "light"),
    "pushkin5_autumn": q(["Унылая пора! Очей очарованье!", "Приятна мне твоя прощальная краса —", "люблю я пышное природы увяданье,", "в багрец и в золото одетые леса."],
                         ["A doleful time! Enchantment of the eyes!", "Your farewell beauty is dear to me —", "I love the lavish fading of nature,", "the forests dressed in crimson and gold."],
                         *A(PU, "«Осень», 1833", "Autumn, 1833"), "any", AUTUMN),
    "pushkin5_bloom": q("И с каждой осенью я расцветаю вновь.", "And with every autumn I bloom anew.", *A(PU, "«Осень», 1833", "Autumn, 1833"), "light", AUTUMN),
    "pushkin5_union": q(["Друзья мои, прекрасен наш союз!", "Он, как душа, неразделим и вечен."], ["My friends, how beautiful our union is!", "Like the soul, it is indivisible and eternal."],
                        *A(PU, "«19 октября», 1825", "October 19, 1825"), "light"),
    "pushkin5_feelings": q(["И долго буду тем любезен я народу,", "что чувства добрые я лирой пробуждал."], ["And long the people will hold me dear", "for awakening kind feelings with my lyre."],
                           *A(PU, "«Я памятник себе воздвиг…», 1836", "1836")),
    "pushkin5_deceive": q(["Ах, обмануть меня не трудно!..", "Я сам обманываться рад!"], ["Oh, it is not hard to deceive me!..", "I am glad to be deceived myself!"],
                          *A(PU, "«Признание», 1826", "Confession, 1826"), "light"),
    "pushkin5_learned": q(["Мы все учились понемногу", "чему-нибудь и как-нибудь."], ["We all have learned a little", "of something, somehow."], *A(PU, "«Евгений Онегин»", "Eugene Onegin"), "light"),
    "pushkin5_tale": q("Сказка ложь, да в ней намёк! Добрым молодцам урок.", "A tale is a lie, but with a hint in it — a lesson for good young folk.",
                       *A(PU, "«Сказка о золотом петушке»", "The Tale of the Golden Cockerel"), "light"),
    "pushkin5_great": q("Следовать за мыслями великого человека есть наука самая занимательная.", "To follow the thoughts of a great man is the most fascinating of sciences.",
                        *A(PU, "«Арап Петра Великого»", "The Moor of Peter the Great")),
    "pushkin5_verb": q("Глаголом жги сердца людей.", "Set people's hearts on fire with the word.", *A(PU, "«Пророк», 1826", "The Prophet, 1826")),
    "vyazemsky_hurry": q("И жить торопится, и чувствовать спешит.", "He hurries to live and rushes to feel.", "Пётр Вяземский  ·  «Первый снег»", "Pyotr Vyazemsky  ·  The First Snow", "light"),
    # ---------------- Лермонтов
    "lermontov5_sail": q(["Белеет парус одинокий", "в тумане моря голубом!..", "Что ищет он в стране далёкой?", "Что кинул он в краю родном?.."],
                         ["A lonely sail is gleaming white", "in the blue mist of the sea!..", "What does it seek in a distant land?", "What has it left in its native shore?.."],
                         *A(LE, "«Парус», 1832", "The Sail, 1832"), "any", SEA),
    "lermontov5_storm": q(["А он, мятежный, просит бури,", "как будто в бурях есть покой!"], ["And it, rebellious, begs for storms,", "as if in storms there were peace!"],
                          *A(LE, "«Парус», 1832", "The Sail, 1832"), "any", SEA),
    "lermontov5_cloud": q(["Ночевала тучка золотая", "на груди утёса-великана;", "утром в путь она умчалась рано,", "по лазури весело играя."],
                          ["A golden cloud spent the night", "on the breast of a giant cliff;", "in the morning it rushed off early,", "playing merrily across the azure."],
                          *A(LE, "«Утёс», 1841", "The Cliff, 1841"), "light", ["alpine", "almaty_lake", "canyon"]),
    "lermontov5_prayer": q(["В минуту жизни трудную", "теснится ль в сердце грусть,", "одну молитву чудную", "твержу я наизусть."],
                           ["In a hard moment of life,", "when sorrow crowds the heart,", "one wondrous prayer", "I repeat by heart."], *A(LE, "«Молитва», 1839", "A Prayer, 1839"), "dark"),
    # ---------------- Тютчев, Фет и другие поэты XIX века
    "tyutchev5_met": q(["Я встретил вас — и всё былое", "в отжившем сердце ожило."], ["I met you — and all the past", "came alive in my weary heart."], *A(TU, "«К. Б.», 1870", "1870"), "light"),
    "tyutchev5_winter": q(["Чародейкою Зимою", "околдован, лес стоит —", "и под снежной бахромою", "чудной жизнью он блестит."],
                          ["Bewitched by the sorceress Winter,", "the forest stands —", "and under its fringe of snow", "it glitters with a wondrous life."],
                          *A(TU, "1852", "1852"), "light", ["winter", "deer", "xmas_tree", "cabin"]),
    "tyutchev5_nature": q(["Не то, что мните вы, природа:", "не слепок, не бездушный лик —", "в ней есть душа, в ней есть свобода,", "в ней есть любовь, в ней есть язык…"],
                          ["Nature is not what you suppose:", "no cast, no soulless face —", "it has a soul, it has freedom,", "it has love, it has a tongue…"], *A(TU, "1836", "1836"), "any",
                          ["forest_rays", "waterfall", "meadow", "almaty_lake"]),
    "tyutchev5_dontfuss": q(["Не рассуждай, не хлопочи!..", "Безумство ищет, глупость судит;", "дневные раны сном лечи,", "а завтра быть чему, то будет."],
                            ["Don't reason, don't fuss!..", "Madness seeks, folly judges;", "heal the day's wounds with sleep,", "and what must be tomorrow, will be."], *A(TU, "1850", "1850"), "any",
                            ["night", "moon_sea", "candle"]),
    "fet5_picture": q(["Чудная картина,", "как ты мне родна:", "белая равнина,", "полная луна…"], ["Wondrous picture,", "how dear you are to me:", "a white plain,", "a full moon…"],
                      *A(FE, "1842", "1842"), "light", ["winter", "winter_village", "cabin"]),
    "fet5_spring": q(["Но верь весне. Её промчится гений,", "опять теплом и жизнию дыша.", "Для ясных дней, для новых откровений", "переболит скорбящая душа."],
                     ["But trust in spring. Its spirit will rush by,", "breathing warmth and life again.", "For clear days, for new revelations", "the grieving soul will heal."],
                     *A(FE, "«Учись у них — у дуба, у берёзы…», 1883", "1883"), "any", ["birch", "winter", "poppies"]),
    "fet5_night": q("Сияла ночь. Луной был полон сад.", "The night was shining. The garden was full of moonlight.", *A(FE, "1877", "1877"), "light", ["moon_sea", "night", "apple_orchard"]),
    "nekrasov5_frost": q(["Не ветер бушует над бором,", "не с гор побежали ручьи —", "Мороз-воевода дозором", "обходит владенья свои."],
                         ["It's not the wind raging over the pinewood,", "nor streams running down from the hills —", "Frost the Governor on patrol", "walks around his domain."],
                         *A(NE, "«Мороз, Красный нос»", "Red-Nosed Frost"), "light", ["winter", "deer", "cabin", "winter_village"]),
    "nekrasov5_citizen": q("Поэтом можешь ты не быть, но гражданином быть обязан.", "You need not be a poet, but you must be a citizen.", *A(NE, "«Поэт и гражданин»", "The Poet and the Citizen")),
    "surikov_snow": q(["Белый снег пушистый", "в воздухе кружится", "и на землю тихо", "падает, ложится."], ["Fluffy white snow", "whirls in the air", "and quietly to the ground", "falls and settles."],
                      "Иван Суриков  ·  «Зима»", "Ivan Surikov  ·  Winter", "light", ["winter", "winter_village", "xmas_tree", "deer"]),
    "nikitin_morning": q(["Звёзды меркнут и гаснут. В огне облака.", "Белый пар по лугам расстилается."], ["The stars grow dim and go out. The clouds are on fire.", "White mist spreads over the meadows."],
                         "Иван Никитин  ·  «Утро»", "Ivan Nikitin  ·  Morning", "light", ["sunrise", "meadow", "steppe_yurts"]),
    "baratynsky_gift": q(["Мой дар убог, и голос мой не громок,", "но я живу, и на земли моё", "кому-нибудь любезно бытие."],
                         ["My gift is poor, my voice is not loud,", "but I live, and my being on this earth", "is dear to someone."], "Евгений Баратынский  ·  1828", "Yevgeny Baratynsky  ·  1828"),
    "derzhavin_river": q(["Река времён в своём стремленьи", "уносит все дела людей…"], ["The river of time in its rushing", "carries away all the deeds of men…"],
                         "Гавриил Державин  ·  1816", "Gavrila Derzhavin  ·  1816", "dark", ["waterfall", "canyon", "boat_dusk"]),
    "lomonosov_abyss": q(["Открылась бездна звёзд полна;", "звездам числа нет, бездне — дна."], ["An abyss has opened, full of stars;", "the stars are numberless, the abyss is bottomless."],
                         "Михаил Ломоносов  ·  1743", "Mikhail Lomonosov  ·  1743", "dark", ["night", "aurora", "xmas_tree"]),
    # ---------------- Серебряный век
    "blok5_battle": q("И вечный бой! Покой нам только снится.", "And eternal battle! We only dream of peace.", *A(BL, "«На поле Куликовом», 1908", "1908")),
    "blok5_spring": q(["О, весна без конца и без краю —", "без конца и без краю мечта!", "Узнаю тебя, жизнь! Принимаю!", "И приветствую звоном щита!"],
                      ["O spring without end and without edge —", "a dream without end and without edge!", "I know you, life! I accept you!", "And I greet you with the ring of a shield!"],
                      *A(BL, "1907", "1907"), "light", ["poppies", "apple_orchard", "meadow", "sakura"]),
    "bunin5_happiness": q(["О счастье мы всегда лишь вспоминаем.", "А счастье всюду. Может быть, оно —", "вот этот сад осенний за сараем", "и чистый воздух, льющийся в окно."],
                          ["We only ever remember happiness.", "But happiness is everywhere. Perhaps it is", "this autumn garden behind the barn", "and the clean air pouring through the window."],
                          *A(BU, "«Вечер», 1909", "Evening, 1909"), "light", ["apple_orchard", "autumn", "birch"]),
    "bunin5_flowers": q(["И цветы, и шмели, и трава, и колосья,", "и лазурь, и полуденный зной…", "Срок настанет — Господь сына блудного спросит:", "«Был ли счастлив ты в жизни земной?»"],
                        ["Flowers and bumblebees, grass and ears of wheat,", "the azure and the midday heat…", "The time will come — the Lord will ask the prodigal son:", "“Were you happy in your earthly life?”"],
                        *A(BU, "1918", "1918"), "light", ["wheat", "poppies", "sunflowers", "meadow"]),
    "bunin5_forest": q(["Лес, точно терем расписной,", "лиловый, золотой, багряный,", "весёлой, пёстрою стеной", "стоит над светлою поляной."],
                       ["The forest, like a painted tower,", "lilac, golden, crimson,", "stands like a gay, motley wall", "above the bright clearing."], *A(BU, "«Листопад», 1900", "Falling Leaves, 1900"), "light", AUTUMN),
    "bunin5_passes": q("Всё проходит, да не всё забывается.", "Everything passes, but not everything is forgotten.", *A(BU, "«Тёмные аллеи»", "Dark Avenues")),
    "tsvetaeva5_like": q(["Мне нравится, что вы больны не мной,", "мне нравится, что я больна не вами,", "что никогда тяжёлый шар земной", "не уплывёт под нашими ногами."],
                         ["I like that you are not sick with me,", "I like that I am not sick with you,", "that the heavy globe of the earth", "will never float away beneath our feet."], *A(TS, "1915", "1915"), "light"),
    "tsvetaeva5_wines": q(["Моим стихам, как драгоценным винам,", "настанет свой черёд."], ["My poems, like precious wines,", "will have their time."], *A(TS, "1913", "1913")),
    "tsvetaeva5_love": q("Любить — видеть человека таким, каким его задумал Бог и не осуществили родители.",
                         "To love is to see a person as God intended them and their parents failed to make them.", *A(TS, "«Записные книжки»", "Notebooks")),
    "gumilev_giraffe": q(["Сегодня, я вижу, особенно грустен твой взгляд…", "Послушай: далёко, далёко, на озере Чад", "изысканный бродит жираф."],
                         ["Today, I see, your gaze is especially sad…", "Listen: far, far away, on Lake Chad", "an exquisite giraffe roams."], "Николай Гумилёв  ·  «Жираф», 1907", "Nikolai Gumilev  ·  The Giraffe, 1907", "light", ["savanna"]),
    "mandelstam_homer": q(["Бессонница. Гомер. Тугие паруса.", "Я список кораблей прочёл до середины."], ["Insomnia. Homer. Taut sails.", "I have read the catalogue of ships halfway through."],
                          "Осип Мандельштам  ·  1915", "Osip Mandelstam  ·  1915", "any", SEA + ["candle"]),
    "balmont_sun": q(["Я в этот мир пришёл, чтоб видеть Солнце", "и синий кругозор."], ["I came into this world to see the Sun", "and the blue horizon."],
                     "Константин Бальмонт  ·  1902", "Konstantin Balmont  ·  1902", "light", ["sunrise", "steppe_yurts", "sunflowers", "beach"]),
    "yesenin5_apple": q(["Не жалею, не зову, не плачу,", "всё пройдёт, как с белых яблонь дым.", "Увяданья золотом охваченный,", "я не буду больше молодым."],
                        ["I don't regret, I don't call, I don't cry,", "all will pass like smoke from white apple trees.", "Seized by the gold of fading,", "I shall never be young again."], *A(YE, "1921", "1921"), "any", ["apple_orchard"]),
    "yesenin5_birch": q(["Белая берёза", "под моим окном", "принакрылась снегом,", "точно серебром."], ["The white birch", "beneath my window", "has wrapped itself in snow,", "as if in silver."],
                        *A(YE, "«Берёза», 1913", "The Birch, 1913"), "light", ["birch", "winter", "winter_village"]),
    "yesenin5_distance": q(["Лицом к лицу", "лица не увидать.", "Большое видится на расстоянье."], ["Face to face", "you cannot see a face.", "Great things are seen from a distance."],
                           *A(YE, "«Письмо к женщине», 1924", "Letter to a Woman, 1924")),
    "yesenin5_burned": q(["Кто любил, уж тот любить не может,", "кто сгорел, того не подожжёшь."], ["One who has loved can love no more;", "one who has burned cannot be set on fire."],
                         *A(YE, "1925", "1925"), "dark"),
    "yesenin5_grove": q(["Отговорила роща золотая", "берёзовым, весёлым языком…"], ["The golden grove has fallen silent,", "its merry birch-tongue stilled…"], *A(YE, "1924", "1924"), "any", ["birch", "autumn"]),
    # ---------------- проза XX века
    "bulgakov_ask": q("Никогда и ничего не просите! Никогда и ничего, и в особенности у тех, кто сильнее вас. Сами предложат и сами всё дадут!",
                      "Never ask for anything! Never, and especially not from those stronger than you. They will offer and give everything themselves!",
                      *A(MB, "«Мастер и Маргарита»", "The Master and Margarita")),
    "bulgakov_manuscripts": q("Рукописи не горят.", "Manuscripts don't burn.", *A(MB, "«Мастер и Маргарита»", "The Master and Margarita"), "any", ["candle"]),
    "bulgakov_truth": q("Правду говорить легко и приятно.", "To speak the truth is easy and pleasant.", *A(MB, "«Мастер и Маргарита»", "The Master and Margarita"), "light"),
    "bulgakov_cowardice": q("Трусость — самый страшный порок.", "Cowardice is the most terrible vice.", *A(MB, "«Мастер и Маргарита»", "The Master and Margarita")),
    "bulgakov_love": q("За мной, читатель! Кто сказал тебе, что нет на свете настоящей, верной, вечной любви?",
                       "Follow me, reader! Who told you there is no true, faithful, eternal love in this world?", *A(MB, "«Мастер и Маргарита»", "The Master and Margarita"), "light"),
    "bulgakov_share": q("Кто любит, тот должен разделять участь того, кого он любит.", "Whoever loves must share the fate of the one they love.",
                        *A(MB, "«Мастер и Маргарита»", "The Master and Margarita")),
    "bulgakov_lamp": q("Никогда не сдёргивайте абажур с лампы! Абажур священен.", "Never pull the shade off a lamp! The lampshade is sacred.",
                       *A(MB, "«Белая гвардия»", "The White Guard"), "any", ["candle", "cabin", "winter_village"]),
    "kuprin_love": q("Любовь должна быть трагедией. Величайшей тайной в мире!", "Love must be a tragedy. The greatest mystery in the world!",
                     "Александр Куприн  ·  «Гранатовый браслет»", "Alexander Kuprin  ·  The Garnet Bracelet"),
    "grin_miracles": q("Я понял одну нехитрую истину. Она в том, чтобы делать так называемые чудеса своими руками.",
                       "I have understood one simple truth: it is to make so-called miracles with your own hands.",
                       "Александр Грин  ·  «Алые паруса»", "Alexander Grin  ·  Scarlet Sails", "light", SEA),
    "korolenko_bird": q("Человек создан для счастья, как птица для полёта.", "Man is created for happiness, as a bird is for flight.",
                        "Владимир Короленко  ·  «Парадокс»", "Vladimir Korolenko  ·  Paradox", "light"),
    "ostrovsky_life": q("Жизнь даётся человеку один раз, и прожить её надо так, чтобы не было мучительно больно за бесцельно прожитые годы.",
                        "Life is given to us only once, and it must be lived so that there is no agonising pain for years lived without purpose.",
                        "Николай Островский  ·  «Как закалялась сталь»", "Nikolai Ostrovsky  ·  How the Steel Was Tempered"),
    "gaidar_happiness": q("Что такое счастье — это каждый понимал по-своему.", "What happiness is — everyone understood in their own way.",
                          "Аркадий Гайдар  ·  «Голубая чашка»", "Arkady Gaidar  ·  The Blue Cup", "light"),
    "platonov_people": q("Без меня народ неполный.", "Without me the people are incomplete.", "Андрей Платонов  ·  «Котлован»", "Andrei Platonov  ·  The Foundation Pit"),
    "tsiolkovsky_cradle": q("Планета есть колыбель разума, но нельзя вечно жить в колыбели.", "A planet is the cradle of mind, but one cannot live in a cradle forever.",
                            "Константин Циолковский  ·  из письма, 1911", "Konstantin Tsiolkovsky  ·  Letter, 1911", "any", ["night", "aurora", "moon_sea"]),
    "ilf_drowning": q("Спасение утопающих — дело рук самих утопающих.", "Saving the drowning is the business of the drowning themselves.",
                      "Ильф и Петров  ·  «Двенадцать стульев»", "Ilf and Petrov  ·  The Twelve Chairs", "light"),
    "ilf_ice": q("Лёд тронулся, господа присяжные заседатели!", "The ice has broken, gentlemen of the jury!", "Ильф и Петров  ·  «Двенадцать стульев»", "Ilf and Petrov  ·  The Twelve Chairs", "light",
                 ["boat_dusk", "winter"]),
    # ---------------- басни и комедии
    "griboedov_believe": q("Блажен, кто верует, — тепло ему на свете!", "Blessed is he who believes — he is warm in this world!", *A(GR, "«Горе от ума»", "Woe from Wit"), "light"),
    "griboedov_wrath": q(["Минуй нас пуще всех печалей", "и барский гнев, и барская любовь."], ["Spare us, more than any sorrow,", "both the master's wrath and the master's love."], *A(GR, "«Горе от ума»", "Woe from Wit")),
    "griboedov_smoke": q("И дым Отечества нам сладок и приятен!", "Even the smoke of the Fatherland is sweet and pleasant to us!", *A(GR, "«Горе от ума»", "Woe from Wit"), "light",
                         ["winter_village", "steppe_yurts", "cabin"]),
    "krylov_fool": q("Услужливый дурак опаснее врага.", "An obliging fool is more dangerous than an enemy.", *A(KR, "«Пустынник и Медведь»", "The Hermit and the Bear")),
    "krylov_pies": q(["Беда, коль пироги начнёт печи сапожник,", "а сапоги тачать пирожник."], ["Trouble comes when a shoemaker starts baking pies", "and a pie-maker starts stitching boots."],
                     *A(KR, "«Щука и Кот»", "The Pike and the Cat"), "light"),
    "krylov_gossip": q(["Чем кумушек считать трудиться,", "не лучше ль на себя, кума, оборотиться?"], ["Instead of toiling to count your gossips,", "wouldn't it be better, dear, to look at yourself?"],
                       *A(KR, "«Зеркало и Обезьяна»", "The Mirror and the Monkey"), "light"),
    "krylov_quartet": q(["А вы, друзья, как ни садитесь,", "всё в музыканты не годитесь."], ["And you, my friends, however you sit,", "you're still not fit to be musicians."],
                        *A(KR, "«Квартет»", "The Quartet"), "light"),
    "karamzin_love": q("И крестьянки любить умеют!", "Even peasant girls know how to love!", "Николай Карамзин  ·  «Бедная Лиза»", "Nikolai Karamzin  ·  Poor Liza", "light", ["meadow", "birch", "swans"]),
    "prutkov_fountain": q("Если у тебя есть фонтан, заткни его; дай отдохнуть и фонтану.", "If you have a fountain, plug it; let the fountain rest too.",
                          "Козьма Прутков", "Kozma Prutkov", "light", ["waterfall"]),
    "gogol_troika": q("И какой же русский не любит быстрой езды?", "And what Russian does not love fast driving?", "Николай Гоголь  ·  «Мёртвые души»", "Nikolai Gogol  ·  Dead Souls", "light",
                      ["winter", "winter_village", "steppe_yurts"]),
    # ---------------- великие романы
    "chekhov5_diamonds": q("Мы отдохнём! Мы услышим ангелов, мы увидим всё небо в алмазах.", "We shall rest! We shall hear the angels, we shall see the whole sky sparkling with diamonds.",
                           *A(CH, "«Дядя Ваня»", "Uncle Vanya"), "light", ["night", "aurora", "moon_sea"]),
    "chekhov5_garden": q("Вся Россия — наш сад.", "All Russia is our garden.", *A(CH, "«Вишнёвый сад»", "The Cherry Orchard"), "light", ["apple_orchard", "sakura"]),
    "chekhov5_globe": q("Человеку нужно не три аршина земли, не усадьба, а весь земной шар, вся природа.", "Man needs not three arshins of earth, not a country estate, but the whole globe, all of nature.",
                        *A(CH, "«Крыжовник»", "Gooseberries"), "any", ["steppe_yurts", "almaty_lake", "canyon", "alpine"]),
    "tolstoy5_light": q("Вся прелесть, вся красота жизни слагается из тени и света.", "All the charm, all the beauty of life is made of shadow and light.",
                        *A(TO, "«Анна Каренина»", "Anna Karenina"), "any", ["forest_rays", "sunrise", "boat_dusk"]),
    "tolstoy5_understand": q("Всё, что я понимаю, я понимаю только потому, что люблю.", "Everything I understand, I understand only because I love.", *A(TO, "«Война и мир»", "War and Peace"), "light"),
    "tolstoy5_now": q("Помни: самое важное время — сейчас, самый нужный человек — тот, с кем ты сейчас, а самое важное дело — делать ему добро.",
                      "Remember: the most important time is now, the most necessary person is the one you are with, and the most important deed is to do them good.",
                      *A(TO, "«Три вопроса»", "Three Questions")),
    "dostoevsky5_minute": q("Боже мой! Целая минута блаженства! Да разве этого мало хоть бы и на всю жизнь человеческую?..",
                            "My God! A whole minute of bliss! Is that too little, even for a whole human life?..", *A(DO, "«Белые ночи»", "White Nights"), "any", ["boat_dusk", "moon_sea", "night"]),
    "dostoevsky5_sand": q("Любите всё создание Божие, и целое, и каждую песчинку.", "Love all of God's creation, the whole of it and every grain of sand.",
                          *A(DO, "«Братья Карамазовы»", "The Brothers Karamazov"), "light", ["beach", "dunes", "meadow"]),
    "dostoevsky5_hell": q("Ад есть страдание о том, что нельзя уже более любить.", "Hell is the suffering of being no longer able to love.", *A(DO, "«Братья Карамазовы»", "The Brothers Karamazov"), "dark"),
    "dostoevsky5_earn": q("Человек не родится для счастья. Человек заслуживает своё счастье, и всегда страданием.",
                          "Man is not born for happiness. Man earns his happiness, and always through suffering.", *A(DO, "Черновики «Преступления и наказания»", "Notes for Crime and Punishment"), "dark"),
    "dostoevsky5_money": q("Деньги есть чеканенная свобода.", "Money is coined freedom.", *A(DO, "«Записки из Мёртвого дома»", "Notes from the House of the Dead")),
    "turgenev5_workshop": q("Природа не храм, а мастерская, и человек в ней работник.", "Nature is not a temple but a workshop, and man is the worker in it.",
                            *A(TG, "«Отцы и дети»", "Fathers and Sons"), "any", ["wheat", "windmill", "steppe_yurts"]),
    "turgenev5_moment": q("У счастья нет завтрашнего дня; у него нет и вчерашнего… у него есть настоящее — и то не день, а мгновенье.",
                          "Happiness has no tomorrow, and no yesterday either… it has only the present — and not a day, but an instant.",
                          *A(TG, "«Ася»", "Asya"), "light"),
    "turgenev5_roses": q("Как хороши, как свежи были розы…", "How lovely, how fresh the roses were…", *A(TG, "«Стихотворения в прозе»", "Poems in Prose"), "any", ["poppies", "meadow"]),
    "klyuchevsky_learn": q("Жизнь учит лишь тех, кто её изучает.", "Life teaches only those who study it.", "Василий Ключевский", "Vasily Klyuchevsky"),
    "gorky5_crawl": q("Рождённый ползать — летать не может!", "One born to crawl cannot fly!", "Максим Горький  ·  «Песня о Соколе»", "Maxim Gorky  ·  The Song of the Falcon", "any",
                      ["canyon", "alpine", "almaty_lake"]),
    # ---------------- Казахстан
    "abai_five": q("Стремление, труд, глубокая мысль, умеренность и доброта — пять драгоценных дел.",
                   "Aspiration, labour, deep thought, contentment and kindness — five precious deeds.",
                   *A(AB, "«Ғылым таппай мақтанба», 1886", "1886"), "any", ["steppe_yurts", "almaty_lake"]),
    "abai_heart": q("Воля, разум и сердце должны быть вместе, а вести их должно сердце.", "Will, reason and heart must be together, and the heart must lead them.",
                    *A(AB, "«Слова назидания», 17", "Book of Words, 17"), "any", ["steppe_yurts", "almaty_lake", "poppies"]),
    "altynsarin_learn": q("Придите, дети, будем учиться!", "Come, children, let us learn!", "Ыбырай Алтынсарин", "Ibrai Altynsarin", "light", ["steppe_yurts", "apple_orchard"]),
    "farabi_happiness": q("Счастье — это благо, к которому стремятся ради него самого.", "Happiness is the good that is sought for its own sake.",
                          "Аль-Фараби  ·  «О достижении счастья»", "Al-Farabi  ·  The Attainment of Happiness", "light", ["steppe_yurts", "canyon"]),
    "kzprov5_roots": q("Дерево крепко корнями, а человек — друзьями.", "A tree is strong by its roots, a man by his friends.", *KZ, "light", ["apple_orchard", "steppe_yurts"]),
    "kzprov5_unity": q("Где единство — там и жизнь.", "Where there is unity, there is life.", *KZ, "light", ["steppe_yurts"]),
    "kzprov5_parents": q("Почитай отца и мать — и дети будут почитать тебя.", "Honour your father and mother, and your children will honour you.", *KZ, "light", ["steppe_yurts", "apple_orchard"]),
    "kzprov5_patience": q("Конец терпения — чистое золото.", "The end of patience is pure gold.", *KZ, "light", ["steppe_yurts", "wheat"]),
    "kzprov5_friends": q("Тысяча друзей — мало, один враг — много.", "A thousand friends are too few; one enemy is too many.", *KZ, "any", ["steppe_yurts"]),
    "kzprov5_knowledge": q("Знание — клад, который не иссякнет.", "Knowledge is a treasure that never runs out.", *KZ, "light", ["steppe_yurts", "canyon"]),
    "kzprov5_mother": q("Сердце матери — в ребёнке, а сердце ребёнка — в степи.", "A mother's heart is with her child; the child's heart is out in the steppe.", *KZ, "any", ["steppe_yurts", "poppies"]),
    "kzprov5_word": q("Начало всякого искусства — слово.", "The beginning of every art is the word.", *KZ, "any", ["steppe_yurts", "candle"]),
    # ---------------- русские пословицы
    "ruprov5_friend": q("Старый друг лучше новых двух.", "An old friend is better than two new ones.", *RU, "light"),
    "ruprov5_trouble": q("Друзья познаются в беде.", "Friends are known in trouble.", *RU),
    "ruprov5_learn": q("Век живи — век учись.", "Live a century, learn a century.", *RU, "light"),
    "ruprov5_gods": q("Не боги горшки обжигают.", "It is not gods who fire the pots.", *RU, "light"),
    "ruprov5_spoon": q("Дорога ложка к обеду.", "A spoon is precious at dinnertime.", *RU),
    "ruprov5_slow": q("Тише едешь — дальше будешь.", "The slower you ride, the farther you get.", *RU, "light", ["winter", "steppe_yurts"]),
    "ruprov5_hands": q("Глаза боятся, а руки делают.", "The eyes are afraid, but the hands do the work.", *RU, "light"),
    "ruprov5_luck": q("Не было бы счастья, да несчастье помогло.", "There would be no luck, but misfortune helped.", *RU, "light"),
    "ruprov5_home": q("Где родился, там и пригодился.", "Where you were born, there you are useful.", *RU, "light", ["winter_village", "steppe_yurts", "birch"]),
    "ruprov5_light": q("Ученье — свет, а неученье — тьма.", "Learning is light, and ignorance is darkness.", *RU, "light", ["candle", "sunrise"]),
    "ruprov5_honour": q("Береги честь смолоду.", "Guard your honour from youth.", *RU),
}
