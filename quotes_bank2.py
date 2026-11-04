# -*- coding: utf-8 -*-
"""Банк цитат, часть 2: русская классика. mood: light/dark/any."""


def q(ru, en, a_ru, a_en, mood="any"):
    return dict(ru=ru, en=en, author_ru=a_ru, author_en=a_en, mood=mood)


PU = ("Александр Пушкин", "Alexander Pushkin")
LE = ("Михаил Лермонтов", "Mikhail Lermontov")
TU = ("Фёдор Тютчев", "Fyodor Tyutchev")
TO = ("Лев Толстой", "Leo Tolstoy")
DO = ("Фёдор Достоевский", "Fyodor Dostoevsky")
CH = ("Антон Чехов", "Anton Chekhov")
TG = ("Иван Тургенев", "Ivan Turgenev")
GO = ("Николай Гоголь", "Nikolai Gogol")


def A(pair, work_ru="", work_en=""):
    a_ru = pair[0] + ("  ·  " + work_ru if work_ru else "")
    a_en = pair[1] + ("  ·  " + work_en if work_en else "")
    return a_ru, a_en


QUOTES2 = {
    # ---------------- Пушкин
    "pushkin_muses": q("Служенье муз не терпит суеты; прекрасное должно быть величаво.", "The service of the Muses brooks no vanity; the beautiful must be majestic.", *A(PU, "«19 октября», 1825", "1825")),
    "pushkin_moment": q(["Я помню чудное мгновенье:", "передо мной явилась ты,", "как мимолётное виденье,", "как гений чистой красоты."], ["I remember a wondrous moment:", "before me you appeared,", "like a fleeting vision,", "like a spirit of pure beauty."], *A(PU, "1825", "1825"), "light"),
    "pushkin_heart": q(["Сердце в будущем живёт;", "настоящее уныло:", "всё мгновенно, всё пройдёт;", "что пройдёт, то будет мило."], ["The heart lives in the future;", "the present is dreary:", "all is fleeting, all will pass;", "and what has passed will be dear."], *A(PU, "«Если жизнь тебя обманет», 1825", "1825")),
    "pushkin_habit": q("Привычка свыше нам дана: замена счастию она.", "Habit is given to us from above: it is a substitute for happiness.", *A(PU, "«Евгений Онегин»", "Eugene Onegin")),
    "pushkin_young": q("Блажен, кто смолоду был молод, блажен, кто вовремя созрел.", "Blessed is he who was young in his youth, blessed is he who ripened in time.", *A(PU, "«Евгений Онегин»", "Eugene Onegin")),
    "pushkin_ages": q("Любви все возрасты покорны.", "All ages are subject to love.", *A(PU, "«Евгений Онегин»", "Eugene Onegin"), "light"),
    "pushkin_peace": q("На свете счастья нет, но есть покой и воля.", "There is no happiness in the world, but there is peace and freedom.", *A(PU, "«Пора, мой друг, пора», 1834", "1834")),
    "pushkin_loved": q(["Я вас любил так искренно, так нежно,", "как дай вам Бог любимой быть другим."], ["I loved you so sincerely, so tenderly,", "as God grant you to be loved by another."], *A(PU, "«Я вас любил», 1829", "1829")),
    # ---------------- Лермонтов
    "lermontov_road": q(["Выхожу один я на дорогу;", "сквозь туман кремнистый путь блестит;", "ночь тиха. Пустыня внемлет Богу,", "и звезда с звездою говорит."], ["Alone I set out on the road;", "through the mist the flinty way gleams;", "the night is still. The wilderness listens to God,", "and star speaks to star."], *A(LE, "1841", "1841")),
    "lermontov_struggle": q("Так жизнь скучна, когда боренья нет.", "Life is so dull when there is no struggle.", *A(LE, "1831", "1831")),
    "lermontov_words": q("Есть речи — значенье темно иль ничтожно, но им без волненья внимать невозможно.", "There are words whose meaning is obscure or trifling, yet one cannot hear them without being stirred.", *A(LE, "1840", "1840")),
    "lermontov_sad": q("И скучно и грустно, и некому руку подать в минуту душевной невзгоды…", "Weary and sad, and no one to give a hand in a moment of heartache…", *A(LE, "1840", "1840"), "dark"),
    # ---------------- Тютчев
    "tyutchev_miracle": q("Чему бы жизнь нас ни учила, но сердце верит в чудеса.", "Whatever life may teach us, the heart believes in miracles.", *A(TU, "1870", "1870"), "light"),
    "tyutchev_autumn": q("Есть в осени первоначальной короткая, но дивная пора.", "There is in early autumn a brief but wondrous time.", *A(TU, "1857", "1857"), "light"),
    "tyutchev_storm": q("Люблю грозу в начале мая, когда весенний, первый гром…", "I love a storm in early May, when the first thunder of spring…", *A(TU, "1828", "1828"), "light"),
    "tyutchev_silence": q("Мысль изречённая есть ложь.", "A thought once uttered is a lie.", *A(TU, "«Silentium!»", "Silentium!")),
    # ---------------- Фет, Некрасов, Жуковский, Блок, Есенин, Маяковский
    "fet_beauty": q("Целый мир от красоты, от велика и до мала, и напрасно ищешь ты отыскать её начало.", "The whole world is made of beauty, from the great to the small, and in vain you seek to find its beginning.", "Афанасий Фет  ·  1880-е", "Afanasy Fet  ·  1880s", "light"),
    "fet_morning": q("Я пришёл к тебе с приветом, рассказать, что солнце встало.", "I came to you with greetings, to tell you that the sun has risen.", "Афанасий Фет  ·  1843", "Afanasy Fet  ·  1843", "light"),
    "nekrasov_will": q("Воля и труд человека дивные дивы творят!", "The will and labour of man work wondrous wonders!", "Николай Некрасов  ·  «Дедушка», 1870", "Nikolai Nekrasov  ·  1870", "light"),
    "zhukovsky_were": q("Не говори с тоской: их нет, но с благодарностию: были.", "Do not say with sorrow: they are gone, but with gratitude: they were.", "Василий Жуковский  ·  «Воспоминание», 1821", "Vasily Zhukovsky  ·  1821"),
    "zhukovsky_means": q("Всё в жизни к великому средство.", "Everything in life is a means to the great.", "Василий Жуковский", "Vasily Zhukovsky"),
    "blok_live": q(["О, я хочу безумно жить:", "всё сущее — увековечить,", "безличное — вочеловечить,", "несбывшееся — воплотить!"], ["Oh, I want madly to live:", "to make all that exists eternal,", "to give the impersonal a human face,", "to embody what never came true!"], "Александр Блок  ·  1914", "Alexander Blok  ·  1914"),
    "blok_world": q("Сотри случайные черты — и ты увидишь: мир прекрасен.", "Erase the accidental features — and you will see: the world is beautiful.", "Александр Блок  ·  «Возмездие»", "Alexander Blok  ·  Retribution", "light"),
    "blok_love": q("Только влюблённый имеет право на звание человека.", "Only one who is in love has the right to be called human.", "Александр Блок  ·  1908", "Alexander Blok  ·  1908"),
    "yesenin_bless": q("Будь же ты вовек благословенно, что пришло процвесть и умереть.", "Be forever blessed, you who came to bloom and die.", "Сергей Есенин  ·  1921", "Sergei Yesenin  ·  1921"),
    "yesenin_simple": q("Жить нужно легче, жить нужно проще, всё принимая, что есть на свете.", "One must live lighter, live simpler, accepting all that is in the world.", "Сергей Есенин  ·  1925", "Sergei Yesenin  ·  1925", "light"),
    "mayakovsky_shine": q(["Светить всегда, светить везде,", "до дней последних донца,", "светить — и никаких гвоздей!", "Вот лозунг мой — и солнца!"], ["To shine always, to shine everywhere,", "to the very last of days,", "to shine — and no excuses!", "That is my motto — and the sun's!"], "Владимир Маяковский  ·  1920", "Vladimir Mayakovsky  ·  1920", "light"),
    "mayakovsky_stars": q("Если звёзды зажигают — значит, это кому-нибудь нужно?", "If the stars are lit — it means someone needs it?", "Владимир Маяковский  ·  «Послушайте!», 1914", "Vladimir Mayakovsky  ·  Listen!, 1914"),
    # ---------------- Гоголь, Тургенев
    "gogol_youth": q("Молодость счастлива тем, что у неё есть будущее.", "Youth is happy because it has a future.", *A(GO, "«Мёртвые души»", "Dead Souls"), "light"),
    "gogol_truths": q("Чем выше истины, тем нужно быть осторожней с ними.", "The higher the truths, the more careful one must be with them.", *A(GO)),
    "turgenev_suffer": q("Хочешь быть счастливым? Выучись сперва страдать.", "Do you want to be happy? First learn to suffer.", *A(TG)),
    "turgenev_time": q("Время летит иногда птицей, иногда ползёт червяком; но человеку особенно хорошо, когда он даже не замечает, как оно проходит.", "Time sometimes flies like a bird, sometimes crawls like a worm; but a man is happiest when he does not even notice it passing.", *A(TG, "«Отцы и дети»", "Fathers and Sons")),
    "turgenev_health": q("Счастье — как здоровье: когда его не замечаешь, значит, оно есть.", "Happiness is like health: when you do not notice it, it means it is there.", *A(TG), "light"),
    # ---------------- Достоевский
    "dostoevsky_beauty": q("Красота спасёт мир.", "Beauty will save the world.", *A(DO, "«Идиот»", "The Idiot"), "light"),
    "dostoevsky_lovelife": q("Надо любить жизнь больше, чем смысл жизни.", "One must love life more than the meaning of life.", *A(DO, "«Братья Карамазовы»", "The Brothers Karamazov")),
    "dostoevsky_self": q("Если хочешь победить весь мир, победи себя.", "If you want to conquer the whole world, conquer yourself.", *A(DO, "«Бесы»", "Demons")),
    "dostoevsky_lie": q("Главное — самому себе не лгите.", "Above all, do not lie to yourself.", *A(DO, "«Братья Карамазовы»", "The Brothers Karamazov")),
    "dostoevsky_love": q("Любовь столь всесильна, что перерождает и нас самих.", "Love is so all-powerful that it transforms even ourselves.", *A(DO), "light"),
    "dostoevsky_happiness": q("Счастье не в счастье, а лишь в его достижении.", "Happiness lies not in happiness itself, but in attaining it.", *A(DO)),
    "dostoevsky_compassion": q("Сострадание есть главнейший и, может быть, единственный закон бытия всего человечества.", "Compassion is the chief and perhaps the only law of all human existence.", *A(DO, "«Идиот»", "The Idiot")),
    "dostoevsky_mind": q("Чтобы умно поступать, одного ума мало.", "To act wisely, intelligence alone is not enough.", *A(DO, "«Преступление и наказание»", "Crime and Punishment")),
    # ---------------- Толстой
    "tolstoy_wait": q("Всё приходит вовремя для того, кто умеет ждать.", "Everything comes in time to him who knows how to wait.", *A(TO, "«Война и мир»", "War and Peace")),
    "tolstoy_honest": q("Чтобы жить честно, надо рваться, путаться, биться, ошибаться, начинать и бросать… А спокойствие — душевная подлость.", "To live honestly one must strive, get confused, struggle, make mistakes, begin and quit… Calm is a meanness of the soul.", *A(TO, "из письма, 1857", "Letter, 1857")),
    "tolstoy_think": q("Думай хорошо, и мысли созреют в добрые поступки.", "Think well, and your thoughts will ripen into good deeds.", *A(TO), "light"),
    "tolstoy_want": q("Счастье не в том, чтобы делать всегда, что хочешь, а в том, чтобы всегда хотеть того, что делаешь.", "Happiness is not in always doing what you want, but in always wanting what you do.", *A(TO), "light"),
    "tolstoy_simple": q("Сильные люди всегда просты.", "Strong people are always simple.", *A(TO)),
    "tolstoy_moral": q("Разумное и нравственное всегда совпадают.", "The reasonable and the moral always coincide.", *A(TO)),
    "tolstoy_word": q("Время проходит, но сказанное слово остаётся.", "Time passes, but a spoken word remains.", *A(TO)),
    "tolstoy_thoughts": q("Все мысли, которые имеют огромные последствия, всегда просты.", "All thoughts that have enormous consequences are always simple.", *A(TO, "«Война и мир»", "War and Peace")),
    "tolstoy_change": q("Каждый хочет изменить человечество, но никто не задумывается о том, как изменить себя.", "Everyone wants to change humanity, but no one thinks about changing himself.", *A(TO)),
    "tolstoy_knowledge": q("Важно не количество знаний, а качество их.", "What matters is not the quantity of knowledge, but its quality.", *A(TO)),
    # ---------------- Чехов
    "chekhov_brevity": q("Краткость — сестра таланта.", "Brevity is the sister of talent.", *A(CH, "из письма, 1889", "Letter, 1889")),
    "chekhov_human": q("Берегите в себе человека.", "Take care of the human being within you.", *A(CH)),
    "chekhov_deeds": q("Дела определяются их целями: то дело называется великим, у которого велика цель.", "Deeds are defined by their aims: that deed is called great which has a great aim.", *A(CH)),
    "chekhov_bred": q("Воспитанные люди уважают человеческую личность, а потому всегда снисходительны, мягки, вежливы, уступчивы.", "Well-bred people respect the human personality, and therefore are always indulgent, gentle, polite and yielding.", *A(CH, "из письма брату, 1886", "Letter to his brother, 1886")),
    "chekhov_good": q("Пока молоды, сильны, бодры, не уставайте делать добро!", "While you are young, strong and vigorous, do not tire of doing good!", *A(CH, "«Крыжовник»", "Gooseberries"), "light"),
    "chekhov_sauce": q("Хорошее воспитание не в том, что ты не прольёшь соуса на скатерть, а в том, что ты не заметишь, если это сделает кто-нибудь другой.", "Good breeding is not in never spilling sauce on the tablecloth, but in not noticing when someone else does.", *A(CH), "light"),
    "chekhov_clear": q("Надо быть ясным умом, чистым нравственно и опрятным физически.", "One must be clear in mind, pure in morals and tidy in body.", *A(CH, "из письма", "Letter")),
    # ---------------- Горький, Ключевский, Суворов, Ломоносов, Крылов, Грибоедов, Прутков, Белинский
    "gorky_feat": q("В жизни всегда есть место подвигу.", "In life there is always room for a heroic deed.", "Максим Горький  ·  «Старуха Изергиль»", "Maxim Gorky  ·  Old Izergil", "light"),
    "gorky_work": q("Когда труд — удовольствие, жизнь — хороша!", "When work is a pleasure, life is good!", "Максим Горький  ·  «На дне»", "Maxim Gorky  ·  The Lower Depths", "light"),
    "gorky_brave": q("Безумство храбрых — вот мудрость жизни!", "The madness of the brave — that is the wisdom of life!", "Максим Горький  ·  «Песня о Соколе»", "Maxim Gorky  ·  Song of the Falcon"),
    "gorky_proud": q("Человек — это звучит гордо!", "Man — that has a proud sound!", "Максим Горький  ·  «На дне»", "Maxim Gorky  ·  The Lower Depths"),
    "klyuchevsky_feel": q("Жизнь не в том, чтобы жить, а в том, чтобы чувствовать, что живёшь.", "Life is not about living, but about feeling that you are alive.", "Василий Ключевский", "Vasily Klyuchevsky", "light"),
    "suvorov_training": q("Тяжело в учении — легко в бою.", "Hard in training — easy in battle.", "Александр Суворов", "Alexander Suvorov"),
    "suvorov_comrade": q("Сам погибай, а товарища выручай.", "Perish yourself, but rescue your comrade.", "Александр Суворов", "Alexander Suvorov"),
    "lomonosov_labour": q("Неусыпный труд препятствия преодолевает.", "Tireless labour overcomes obstacles.", "Михаил Ломоносов", "Mikhail Lomonosov", "light"),
    "lomonosov_better": q("Ошибки замечать немногого стоит: дать нечто лучшее — вот что приличествует достойному человеку.", "To notice mistakes costs little; to offer something better — that befits a worthy man.", "Михаил Ломоносов", "Mikhail Lomonosov"),
    "krylov_accord": q("Когда в товарищах согласья нет, на лад их дело не пойдёт.", "When there is no accord among comrades, their business will not prosper.", "Иван Крылов  ·  «Лебедь, Щука и Рак»", "Ivan Krylov  ·  The Swan, the Pike and the Crab"),
    "griboyedov_hours": q("Счастливые часов не наблюдают.", "The happy do not watch the clock.", "Александр Грибоедов  ·  «Горе от ума»", "Alexander Griboyedov  ·  Woe from Wit", "light"),
    "griboyedov_serve": q("Служить бы рад, прислуживаться тошно.", "I would gladly serve, but being servile sickens me.", "Александр Грибоедов  ·  «Горе от ума»", "Alexander Griboyedov  ·  Woe from Wit"),
    "prutkov_root": q("Зри в корень!", "Look to the root!", "Козьма Прутков  ·  «Плоды раздумья»", "Kozma Prutkov  ·  Fruits of Reflection"),
    "prutkov_embrace": q("Никто не обнимет необъятного.", "No one can embrace the unembraceable.", "Козьма Прутков  ·  «Плоды раздумья»", "Kozma Prutkov  ·  Fruits of Reflection"),
    "prutkov_keep": q("Что имеем — не храним; потерявши — плачем.", "What we have, we do not treasure; having lost it, we weep.", "Козьма Прутков", "Kozma Prutkov"),
    "belinsky_love": q("Любовь — поэзия и солнце жизни.", "Love is the poetry and the sun of life.", "Виссарион Белинский", "Vissarion Belinsky", "light"),
    # ---------------- Абай
    "abai_brick": q("И ты — кирпич в стене этого мира: найди своё место и встань в неё.", "You too are a brick in the wall of this world: find your place and take it.", "Абай Кунанбаев  ·  1886", "Abai Kunanbaiuly  ·  1886"),
    "abai_son": q("Будь не сыном своего отца — будь сыном человечества.", "Be not merely the son of your father — be a son of humankind.", "Абай Кунанбаев  ·  «Слова назидания»", "Abai Kunanbaiuly  ·  Book of Words"),
}
