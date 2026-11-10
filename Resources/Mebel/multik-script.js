/* «Мой сценарий»: текст в виде пьесы → серии в формате движка (без интернета).
   СЦЕНА: лес, ночь · Имя: реплика · (Имя прыгает) · Имя входит справа. · ПЕРСОНАЖ: Имя — описание · СЕРИЯ: 2. Название */
'use strict';
(function (global) {
const S = {};
const low = s => String(s || '').toLowerCase().replace(/ё/g, 'е');
const has = (t, re) => re.test(t);

const PLACES = [[/(двор|у дома|возле дома|около дома|крыльц|(^|[^а-я])сад(а|у|ом|е|ик|ике)?(?![а-я])|огород)/, 'yard'], [/(космос|планет|ракет|луна)/, 'space'], [/(пляж|мор[еяю]|берег|океан|речк|рек[аеиу]|озер|пруд)/, 'beach'], [/(зим|снег|сугроб)/, 'winter'], [/(кухн)/, 'kitchen'],
  [/(площадк|качел|горк)/, 'playground'], [/(улиц|город|магазин|парк)/, 'street'], [/(комнат|спальн|дома(?![а-я])|домой|в доме|гостин|квартир|детск|домик|избушк|игров)/, 'room'],
  [/(двор|у дома|возле дома|крыльц|сад)/, 'yard'], [/(луг|пол[ея]|поляна|полянк)/, 'meadow'], [/(лес|роща|чащ)/, 'forest']];
const TIMES = [[/(ночь|ночью|ночн|темно)/, 'night'], [/(вечер|закат)/, 'evening'], [/(утро|утром|день|дн[её]м)/, 'day']];
const MUSIC = [[/(смешн|забавн|шутлив|комичн|дурашл|озорн)/, 'funny'], [/(таинств|загадоч|жутк|хэллоуин|хеллоуин|страшилк|мистич|призрач)/, 'spooky'], [/(груст|печал)/, 'sad'], [/(тревож|страшн|напряж|погон)/, 'tense'], [/(приключ|бодр)/, 'adventure'], [/(волшеб|сказоч|чудес)/, 'magic'], [/(ночн|колыбел|тих)/, 'night'], [/(спокойн|нежн|мягк)/, 'calm'], [/(весел|радост)/, 'happy'], [/(без музыки|нет|тишин)/, 'none']];
const SFX = [[/(бум|удар|бах|грох)/, 'thud'], [/(дзынь|динь)/, 'ding'], [/(волшеб|магия|чудо)/, 'magic'], [/(искр|блеск)/, 'sparkle'], [/(стук)/, 'knock'], [/(звонок|колокол)/, 'bell'],
  [/(мяу)/, 'meow'], [/(гав)/, 'bark'], [/(смех|хаха)/, 'laugh'], [/(всплеск|плюх)/, 'splash'], [/(хлоп)/, 'clap'], [/(вжух|свист|ух)/, 'whoosh'], [/(барабан)/, 'drum'], [/(прыг|боинг)/, 'boing'], [/(шаг)/, 'step'], [/(хлопок|чпок|поп)/, 'pop']];
const PROPS = [[/^тыкв/, 'pumpkin'], [/^(гриб|грибок)/, 'mushroom'], [/^зонт/, 'umbrella'], [/^(конфет|карамел)/, 'candy'], [/^морожен/, 'icecream'], [/^леденец|^леденц/, 'lollipop'],
  [/^банан/, 'banana'], [/^груш/, 'pear'], [/^арбуз/, 'watermelon'], [/^(мед$|мёд|меда|мёда|медом|мёдом|бочонок|бочонк)/, 'honey'], [/^(ведр|ведёр|ведер)/, 'bucket'], [/^(лопат|совок|совоч)/, 'shovel'],
  [/^(машинк|машин)/, 'car'], [/^(мишк|медвежон)(?=.*игруш)|^игрушк/, 'teddy'], [/^барабан/, 'drum'], [/^гитар/, 'guitar'], [/^палочк/, 'wand'], [/^(фонар|фонарик)/, 'lantern'],
  [/^карт[аеуы]$|^картой$/, 'map'], [/^(письм|конверт)/, 'letter'], [/^(корзин|лукошк)/, 'basket'], [/^(сундук|клад$|клада$|кладом$|кладе$|клады$|кладов$)/, 'chest'], [/^(монет|монетк)/, 'coin'], [/^(яйц|яичк)/, 'egg'],
  [/^(пирог|пирож)/, 'pie'], [/^(печень)/, 'cookie'], [/^(молок|бутылк)/, 'milk'], [/^(часы|часики|будильник)/, 'clock'], [/^(свеч)/, 'candle'], [/^(лист|листик|листок)/, 'leaf'],
  [/^(камень|камешек|камн|камуш)/, 'rock'], [/^(палк|ветк|прут)/, 'stick'], [/^(телефон|смартфон)/, 'phone'], [/^(змей|змея)/, 'kite'], [/^(сумк|сумоч|портфел)/, 'bag'],
  [/^мяч/, 'ball'], [/^яблок/, 'apple'], [/^рыб/, 'fish'], [/^(коробк|ящик)/, 'box'], [/^подар/, 'gift'], [/^цвет(ок|оч|к)/, 'flower'], [/^книг/, 'book'], [/^зв[её]зд/, 'star'],
  [/^бинокл/, 'binoculars'], [/^(лупа|лупу|лупы|лупой|лупе|лупочк)$/, 'magnifier'], [/^компас/, 'compass'], [/^(рюкзак|ранец|ранц)/, 'backpack'], [/^(шляп|панам|шапк|шапочк|кепочк)/, 'hat'], [/^(очки|очков|очками|очкам)$/, 'glasses'],
  [/^(лестниц|стремянк)/, 'ladder'], [/^(веревк|верев|канат)/, 'rope'], [/^(удочк|удочек|удилищ)/, 'rod'], [/^(лодк|лодоч|кораблик)/, 'boat'], [/^(велосипед|велик$|велика$|велике$|великом$)/, 'bike'], [/^самокат/, 'scooter'],
  [/^(телескоп|подзорн)/, 'telescope'], [/^ракет/, 'rocket'], [/^корон/, 'crown'], [/^(флаг|флажок|флажк)/, 'flag'], [/^(краск|кисточк|кисть$|кисти$|палитр)/, 'paints'], [/^(карандаш|фломастер|мелок|мелки$|мелков$|мелками$)/, 'pencil'],
  [/^(кастрюл|котел|котелок|котелк)/, 'pot'], [/^(тарелк|тарелоч|блюдц|миск)/, 'plate'], [/^(ложк|ложечк)/, 'spoon'], [/^чайник/, 'teapot'], [/^(бутерброд|сэндвич|сендвич)/, 'sandwich'], [/^пицц/, 'pizza'],
  [/^(клубник|земляник|ягод|малин|черник)/, 'strawberry'], [/^виноград/, 'grapes'], [/^(вишн|вишен|черешн)/, 'cherry'], [/^(желуд|орех|орешек|орешк)/, 'acorn'], [/^(шишк|шишек)/, 'pinecone'], [/^(снежок|снежк|снежки)/, 'snowball'],
  [/^(санк|сани$|санях$|салазк)/, 'sled'], [/^(колокольчик|колокол)/, 'bell'], [/^(зеркал)/, 'mirror'], [/^(банк[аиуе]$|банкой$|баночк|варень|джем)/, 'jar'], [/^(перо$|пера$|пером$|перышк)/, 'feather'],
  [/^(самолет|самолетик)/, 'plane'], [/^(подушк)/, 'pillow'], [/^(бабочк|бабочек)/, 'butterfly'], [/^(сачок|сачк)/, 'net'], [/^(дудочк|дудк|флейт|свирел)/, 'flute'],
  [/^торт/, 'cake'], [/^кост/, 'bone'], [/^морков/, 'carrot'], [/^сыр/, 'cheese'], [/^(шарик|шар$|шара|шаром)/, 'balloon'], [/^ключ/, 'key'], [/^(чашк|кружк)/, 'cup']];
// Крупные вещи «в мире сцены»: появляются, когда о них говорят
const DECOR = [[/^двер/, 'door'], [/^(лун[аыеу]$|луной|месяц)/, 'moon'], [/^(привидени|призрак|приведени)/, 'ghost'], [/^(летуч)/, 'bat'],
  [/^(гирлянд|огоньк|фонарики$)/, 'garland'], [/^(украшени)/, 'decor'], [/^(лиц[аоу]?$|рожиц|рож[иа]$)/, 'faces'], [/^(дерев|ёлк|елк|ел[иь]$|елочк|дуб$|дуба$|дубу$|дубом$|дубе$|дубок|дубочек|сосн|берез|берёз|клен|клён|осин|рябин|яблон|ив[аыуе]$|пальм)/, 'tree'], [/^(портал)/, 'door'],
  [/^(сугроб|снегови)/, 'snowman'], [/^(костер|костёр|костр)/, 'fire'], [/^(шатер|шатёр|палатк)/, 'tent'], [/^(замок|замк)$/, 'castle'], [/^(радуг)/, 'rainbow'], [/^(мольберт)/, 'easel']];
const CLOSE_DO = new Set(['read', 'peer', 'write', 'paint', 'play', 'drink', 'sniff']);
const KEY_PROPS = new Set(['map', 'letter', 'compass', 'key', 'book', 'magnifier', 'crown', 'gift', 'mirror', 'jar', 'feather', 'flower', 'acorn', 'butterfly']);
const EVENT_DECOR = new Set(['rainbow']);   // не стоят с начала сцены: появляются в тот момент, когда их увидели
const NOW_CUE = /(смотри|гляди|глянь|(^|[^а-я])вот(?![а-я])|(^|[^а-я])ого(?![а-я])|(^|[^а-я])ух ты|появил|появля|возник|засия|вспыхн|загорел|зажгл|выросл|раскинул|(^|[^а-я])над (нами|домом|поляной|лесом))/;
const FUTURE = /(появится|появятся|(^|[^а-я])(будет|будут|будем|станет|когда|пойд[её]м|поед[её]м|завтра|скоро|потом|позже|когда-нибудь)(?![а-я])|получится|купл[юя]|купим|купишь|принесу|принес[её]м|возьму|возьм[её]м|приготовлю|приготовим|испеку|испеч[её]м|сделаю|сделаем|подарю|подарим|угощу|угостим)/;   // «На пляже будет мороженое», «Завтра принесу торт» — этого здесь пока нет
// «там, на пляже…», «в лесу растут…» — речь о другом месте, а не о том, где сейчас герои
const ELSEWHERE = /(^|[^а-я])(на|в|во|к|у|из|с)\s+(пляж\S*|мор[еяюи]\S*|берег\S*|лес[ау]?(?![а-я])|лесу|чащ\S*|пол[ея](?![а-я])|поляну|поляне|полянк\S*|луг\S*|двор\S*|сад(у|а|ом|е|ик\S*)?(?![а-я])|огород\S*|кухн\S*|комнат\S*|дом(е|а|ой)?(?![а-я])|домик\S*|город\S*|парк\S*|площадк\S*|реке|реку|речк\S*|озер\S*|космос\S*|улиц\S*|магазин\S*|зоопарк\S*)/;
// какое дерево: берёза — белый ствол с полосками, ёлка/сосна — хвойное, остальные — лиственное
const TREE_KIND = [[/^(берез|берёз)/, 'birch'], [/^(ёлк|елк|ел[иь]$|ель$|елочк|ёлочк|сосн|пихт|кедр)/, 'fir'], [/^пальм/, 'palm'], [/^яблон/, 'apple'], [/^(дуб|клен|клён|рябин|осин|ив[аыуе]$|лип)/, 'leafy']];
const BIG_DEFAULT = new Set(['door', 'moon', 'ghost', 'tree', 'snowman', 'tent', 'castle', 'rainbow', 'fire', 'rocket']);
// крупные сами по себе (велосипед, лестница) — в кадре не раздуваем, как мелочь
const MID_DEFAULT = new Set(['bike', 'scooter', 'ladder', 'telescope', 'boat', 'sled', 'rod', 'net', 'flag']);
const SEE = /(смотри|гляди|глянь|глядите|(^|[^а-я])вот(?![а-я])|(^|[^а-я])это(?![а-я])|видишь|видите|вижу|(^|[^а-я])там(?![а-я])|(^|[^а-я])тут(?![а-я])|здесь|появил|появля|возник|исчез|пропал|растаял|засвет|светит|светя|свечен|сверка|горит|сия|лежит|лежат|стоит|висит|везде|кругом|огромн|громадн|гигантск|^\s*как(ая|ой|ие|ое)(?![а-я])|ещ[её] одн|(^|[^а-я])наш(а|е|и|у|его|ей|ем|ему|им|ими|их)?(?![а-я])|у меня|у нас|держ|оставил|оставлен|принес|принёс|двига|кати|покати|шевел|открыва|открыл|распахн|отвори|(^|[^а-я])сам[аио]?(?![а-я]))/;
// Вещи, о которых говорят, но их нет рядом: «Где наш торт?», «Верни торт!», «Мы не нашли торт», «Хочу попробовать торт»
const ABSENT = /(^|[^а-я])(где|куда|откуда|верн[иу]|отдай|найт|найд|нашл|ищ|иска|потеря|забра|украл|укра|похит|съел|съест|съеш|доел|попроб|хотел|хочу|хоч|мечта|любим|вспомина|без|нет|не было|пропаж)/;
const THEMES = [[/(хэллоуин|хеллоуин|halloween)/, 'halloween'], [/(новый год|новог|нового года|новым годом|дед мороз|снегурочк)/, 'newyear'], [/(день рождени|дня рождени|днем рождени|именин)/, 'birthday']];
// эмоция по самой реплике, если в сценарии её не указали («Ура!», «Ого!», «Боюсь…», «Извини…») — лицо и голос живее
const AUTO_EMO = [[/(^|[^а-я])(я догадал(ся|ась)|догадалась|догадался|я понял[а]?|я знаю|придумал[а]?|нашёл|нашел|нашла|нашлось|нашлась)(?![а-я])/, 'happy'], [/(^|[^а-я])(ура+|здорово|отлично|получилось|получается|мы разгадали|молод(ец|цы)|какая красота|как красиво|вот это да|класс(но)?|я так рад|я рада|я рад|весело)(?![а-я])/, 'happy'],
  [/^(ого|ух ты|ничего себе|не может быть|вот это да)/, 'surprised'], [/(^|[^а-я])(боюсь|страшно|ой-ой|мне страшно)(?![а-я])/, 'scared'],
  [/(^|[^а-я])(извини(те)?|прости(те)?|я поспешил|я поспешила|мне стыдно|неловко|я лучше посмотрю|вдруг я всё испорчу|вдруг я все испорчу)(?![а-я])/, 'shy'],
  [/(^|[^а-я])(жаль|жалко|грустно|не получилось|не получится|не отвечает|не нашли|потерял[аи]?|пропал[аи]?|испорчу)(?![а-я])/, 'sad'],
  [/^(хм+|кажется|наверное|интересно|подождите|подожди|странно|погодите)(?![а-я])/, 'frown'], [/^(привет|здравствуй|доброе утро|смотрите|давайте|пойдём|пойдем)(?![а-я])/, 'smile']];
const EMO = [[/(улыба|с улыбкой)/, 'smile'], [/(хмур|насуп|сосредоточ|задумчив)/, 'frown'], [/(радост|весел|счастлив|довольн|горд)/, 'happy'], [/(сме[ея]|хохоч|смешн|смех|хихик|усмеха)/, 'laugh'], [/(груст|печал|расстро)/, 'sad'], [/(плач|рыда|сл[её]з)/, 'cry'],
  [/(злит|сердит|зло(?![а-я])|злой|злая|гневн|обиж)/, 'angry'], [/(удивл|изумл|(^|[^а-я])ого(?![а-я]))/, 'surprised'], [/(испуг|страшн|бои|боя|дрож)/, 'scared'], [/(сонн|зева|устал)/, 'sleepy'],
  [/(влюбл|нежно|с любов)/, 'love'], [/(смущ|стесн|винова)/, 'shy'], [/(спокойн|обычн)/, 'neutral']];
// подача голоса из ремарки: «(шёпотом)», «(громко кричит)» — голос героя шепчет или кричит (БАРС-актёр); на лицо и движения не влияет
const mannerOf = s => /(ш[её]пот|шепч|шепн|еле слышно|тихонько|вполголоса)/.test(s || '') ? 'whisper' : /(крич|крикн|ор[её]т|вопит|громко|во весь голос)/.test(s || '') ? 'shout' : null;
const VERBS = [ // stem → действие (порядок важен)
  // новые действия: читает карту, смотрит в бинокль, копает, стучит, толкает, тянет, пьёт, рисует, пишет, играет, нюхает, слушает, ликует, ищет, пожимает плечами
  [/^(стоит|стоят|стоял|стояла|стояли|ждет|ждут|ждал|ждала|ждали)$/, 'wait'],
  [/^(читает|читают|читал|читала|прочитал|прочитала|прочел|прочла|разглядыва|разглядел|рассматрива|рассмотрел|изуча|изучил|развернул|развернула|разворачива)/, 'read'],
  [/^(копа|копнул|выкопал|выкопала|раскопал|рыл$|рыла$|роет|роют)/, 'dig'], [/^(стуч|постуч|стукнул|постукал)/, 'knock'],
  [/^(толка|толкнул|подтолкнул|пихнул|пихает)/, 'push'], [/^(тянет|тянут|тянул|потянул$|потянула$|потянули$|тащит|тащат|тащил|вытащил|вытащила|вытянул|дернул|дергает)/, 'pull'],
  [/^(пьет|пьют|пил$|пила$|пили$|выпил|выпила|попил|попила|отпил|глотну)/, 'drink'], [/^(рису|нарисовал|нарисовала|раскраш|раскрасил|красит|покрасил)/, 'paint'],
  [/^(пишет|пишут|писал|написал|написала|записал|записала|записыва)/, 'write'], [/^(играет|играют|играл|играла|сыграл|сыграла|заиграл|заиграла|бренчит|дудит|подудел)/, 'play'],
  [/^(нюха|понюхал|принюхал|обнюхал)/, 'sniff'], [/^(слушает|слушают|слушал|прислушал|прислушива|послушал)/, 'listen'],
  [/^(ликует|ликуют|ликовал|обрадовал|радуется|радуются|запрыгал от радости)/, 'cheer'], [/^(огляд|осматрива|осмотрел|ищет|ищут|искал|искала|искали|поискал|разыскива)/, 'lookaround'],
  [/^(пожал|пожала|пожима)/, 'shrug'],
  // прошедшее время и «начал делать» — так обычно пишут сказки
  [/^(подбежал|подбежала|подбежали|прибежал|прибежала|прибежали)$/, 'run'], [/^(побежал|побежала|побежали|помчал|помчалс|понесл|рванул)/, 'run'],
  [/^(выпрыгнул|выскочил|выскочила|выбежал|выбежала|вбежал|вбежала|вошел|вошла|вошли|пришел|пришла|пришли|появил|прилетел|приполз|заглянул)/, 'enter'],
  [/^(ушел|ушла|ушли|убежал|убежала|убежали|улетел|улетела|исчез|скрыл)/, 'exit'], [/^(подошел|подошла|подошли|пошел|пошла|пошли|зашагал|шагал|шел$|шла$|шли$|направил|двинул|отправил|поплел)/, 'walk'],
  [/^(прыгнул|подпрыгнул|запрыгал|прыгал|скакал|поскакал)/, 'jump'], [/^(помахал|махнул|замахал|махал)/, 'wave'], [/^(станцевал|затанцевал|танцевал|сплясал|заплясал)/, 'dance'],
  [/^(закружил|покружил|кружил|завертел)/, 'spin'], [/^(кивнул|кивнула|закивал)/, 'nod'], [/^(покачал|замотал|помотал)/, 'shake'], [/^(хлопнул|захлопал|похлопал|хлопал|зааплодир)/, 'clap'],
  [/^(показал|указал|ткнул)/, 'point'], [/^(задумал|подумал|думал|призадумал|размечтал)/, 'think'], [/^(засмеял|рассмеял|смеял|захихикал|хихикнул|хохотал|расхохотал|захохотал|усмехнул)/, 'laugh'],
  [/^(испугал|перепугал|задрожал|струсил)/, 'scared'], [/^(заплакал|расплакал|плакал|зарыдал|всхлипнул)/, 'cry'], [/^(поклонил|кланял)/, 'bow'], [/^(удивил|изумил|ахнул|опешил)/, 'surprise'],
  [/^(упал|упала|упали|споткнул|поскользнул|свалил|грохнул|шлепнул|плюхнул)/, 'fall'], [/^(сел$|села$|сели$|присел|присела|уселс|уселась|сидел|сидела)/, 'sit'], [/^(уснул|уснула|уснули|заснул|заснула|спал$|спала$|задремал)/, 'sleep'],
  [/^(встал|встала|встали|поднялс|поднялась|проснул|вскочил)/, 'stand'], [/^(повернул|обернул|посмотрел|посмотрела|взглянул|оглянул|глянул|уставил)/, 'turn'],
  [/^(взял|взяла|взяли|забрал|забрала|забрали|поднял|подняла|подобрал|схватил|схватила|нашел|нашла|достал|достала|собирал|собрала|сорвал|сорвала)/, 'take'], [/^(дал$|дала$|отдал|подарил|протянул|передал|угостил|вручил)/, 'give'], [/^(поблагодар|благодар)/, 'bow'],
  [/^(положил|уронил|поставил|опустил)/, 'drop'], [/^(принес|принесла|принесли|притащил|притащила|прикатил)/, 'take'], [/^(пина|пнут)/, 'kick'], [/^(танцев|потанцев)/, 'dance'], [/^(вышел|вышла|вышли)$/, 'exit'], [/^(обнял|обняла|обняли|обнимал|прижал)/, 'hug'], [/^(почесал|чесал|почесыва)/, 'scratch'], [/^(зевнул|зевнула|зевал)/, 'yawn'], [/^(потянулс|потянулась|потягивал)/, 'stretch'],
  [/^(чихнул|чихнула|чихал)/, 'sneeze'], [/^(съел|съела|поел|поела|ела$|ели$|ел$|жевал|грыз|откусил|слопал|скушал)/, 'eat'], [/^(топнул|топал|затопал)/, 'stomp'], [/^(пригнул|присел)/, 'crouch'],
  [/^(спрятал|спряталась|прятал)/, 'hide'], [/^(спел|пел$|пела$|запел|запела|напевал)/, 'sing'], [/^(пнул|пнула|ударил|пинал)/, 'kick'], [/^(бросил|бросила|кинул|кинула|швырнул|подбросил)/, 'throw'],
  [/^(крикнул|крикнула|закричал|закричала|кричал|завопил|заорал)/, 'shout'], [/^(лег$|легла|легли|улегс|лежал|лежала|прилег)/, 'lie'], [/^(покатил|катал|кувыркнул|кувыркал)/, 'roll'], [/^(пополз|полз)/, 'crawl'], [/^(подкрал|крал)/, 'sneak'],
  [/^(катает|катают|валяет|валяют|покатил)/, 'roll'], [/^(кувырк|сальто)/, 'somersault'], [/^(ползет|ползёт|ползут|ползает|полз|ползк)/, 'crawl'],
  [/^(крадет|крадёт|крадут|подкрад|крадучись)/, 'sneak'], [/^(лежит|лежат|ложит|леж|улегл|улёгся|разлегл)/, 'lie'], [/^(обнима|обнял|обнимет)/, 'hug'],
  [/^(чешет|почесал|чешут|почёсыва|почесыва)/, 'scratch'], [/^(зева|зевнул)/, 'yawn'], [/^(потягива|потянул)/, 'stretch'], [/^(чиха|чихнул)/, 'sneeze'],
  [/^(ест$|едят|кушает|кушают|жует|жуёт|грызет|грызёт|лопает|уплета|съел|ел$|поедает)/, 'eat'], [/^(топает|топают|топнул|топочет)/, 'stomp'],
  [/^(присед|присел|пригнул|пригиба)/, 'crouch'], [/^(прячет|прячут|спрятал|спрята|прятал)/, 'hide'], [/^(поет|поёт|поют|напева|запел|спел)/, 'sing'],
  [/^(пинает|пнул|пинают|бьет|бьёт|ударил)/, 'kick'], [/^(бросает|бросил|кидает|кинул|бросают|швыря)/, 'throw'], [/^(кричит|крикнул|закричал|орет|орёт|вопит)/, 'shout'],
  [/^(вход(ит|ят|я$)|приход(ит|ят|я$)|появля|прибега(ет|ют)|заход(ит|ят|я$)|прилета(ет|ют)|выбега(ет|ют))/, 'enter'], [/^(уход(ит|ят|я$)|убега(ет|ют)|выход(ит|ят|я$)|исчеза(ет|ют)|улета(ет|ют))/, 'exit'],
  [/^(бежит|бегут|бега|мчит|несет|несут)/, 'run'], [/^(ид[её]т|идут|подход|шага|направля|подбега)/, 'walk'],
  [/^(прыга|подпрыг|скач)/, 'jump'], [/^(маш[еу]т|помаха)/, 'wave'], [/^(танцу|пляш)/, 'dance'], [/^(кружит|крутит|вертит)/, 'spin'], [/^(кива)/, 'nod'],
  [/^(кача|мота)/, 'shake'], [/^(хлопа|аплодир)/, 'clap'], [/^(показыва|указыва)/, 'point'], [/^(дума|размышля|мечта|задума)/, 'think'],
  [/^(смеет|смеют|хохоч|хихика)/, 'laugh'], [/^(пуга|испуга|дрож|боит)/, 'scared'], [/^(плач|рыда)/, 'cry'], [/^(кланя|поклон)/, 'bow'], [/^(удивля)/, 'surprise'],
  [/^(пада|упал|спотыка|поскальз)/, 'fall'], [/^(сад|присажива|сел$|сели$)/, 'sit'], [/^(засыпа|спит|спят|усну|ложит)/, 'sleep'], [/^(вста|просыпа|проснул|поднялс|поднима[её]тся)/, 'stand'],
  [/^(поворач|оборач|смотр|гляд|взгляну)/, 'turn'], [/^(бер[её]т|берут|поднима|хвата|наход|наш[её]л)/, 'take'], [/^(отда|дарит|передает|протягива|угоща)/, 'give'], [/^(клад|полож|ставит|роня|опуска)/, 'drop'],
];
const SAYV = /(сказал|ответил|спросил|крикнул|закричал|прошептал|воскликнул|произн[её]с|произнесл|добавил|засмеял|рассмеял|пискнул|буркнул|улыбнул|вздохнул|обрадовал|удивил|испугал|заплакал|захихикал|пропел|запел|позвал|попросил|согласил|предложил|заметил|подумал|возмутил|ахнул|охнул|вскрикнул)/;
const NARR = /^(рассказчик|автор|голос за кадром|за кадром|диктор)/;
const GENERIC = new Set('кот кошка котик котенок пес собака щенок мышонок мышка мышь медведь медвежонок заяц зайчик зайка лиса лисенок поросенок свинка мальчик девочка бабушка дедушка мама папа тетя дядя'.split(' '));

const AUTO_HERO = new Set('заяц зайчик зайка лиса лисичка лисёнок лисенок волк волчонок медведь медвежонок мишка ёжик ежик ёж еж белка бельчонок мышка мышонок кот кошка котёнок котенок собака пёс пес щенок сова совёнок совенок птичка птица воробей утка утёнок утенок цыплёнок цыпленок курица лев львёнок львенок слон слонёнок слоненок корова дракон робот лягушка лягушонок поросёнок поросенок свинка мама папа бабушка дедушка мальчик девочка учитель учительница'.split(' '));
/** Индекс имён: имя → id. */
function nameIndex(chars) {
  const idx = [];
  for (const [id, c] of Object.entries(chars)) { const n = low(c.name || c.spec && c.spec.name || ''); if (!n) continue; idx.push([n, id]); const w = n.split(/\s+/); if (w.length > 1) { for (const x of w) if (x.length > 2 && !GENERIC.has(x)) idx.push([x, id]); } }
  return idx.sort((a, b) => b[0].length - a[0].length);
}
function findNameAt(text, idx) { // имя в начале строки
  const t = low(text).trim();
  for (const [n, id] of idx) { if (t.startsWith(n)) { const rest = t.slice(n.length); const m = rest.match(/^[а-яa-z]{0,3}/); if (!rest || /^[^а-яa-z]/.test(rest) || (m && /^(а|у|ом|ой|е|ы|ой|ю|я|ем|ей|ам)?(\s|$|[,.:!?()])/.test(rest))) return { id, len: n.length + ((rest.match(/^[а-я]{0,3}/) || [''])[0].length) }; } }
  return null;
}
function namesIn(text, idx) { const out = []; const t = low(text); for (const [n, id] of idx) { const re = new RegExp('(^|[^а-яa-z])' + n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[а-я]{0,3}(?=$|[^а-яa-z])', 'g'); if (re.test(t) && !out.includes(id)) out.push(id); } return out; }
function pick(list, t) { for (const [re, v] of list) if (re.test(t)) return v; return null; }

/** Разобрать текст. lib — библиотека (characters, locations). opts: {series}. → {episodes:[ep], errors, warnings, newChars} */
S.parse = function (text, lib, opts) {
  opts = opts || {};
  const errors = [], warnings = [];
  const chars = {}; for (const [id, c] of Object.entries(lib.characters || {})) chars[id] = { name: c.spec.name, spec: c.spec, old: true };
  const locs = Object.assign({}, lib.locations || {});
  const newChars = {}, newLocs = {};
  let nextC = 100, nextL = 100;
  for (const id of Object.keys(chars)) { const m = id.match(/^К(\d+)$/); if (m) nextC = Math.max(nextC, +m[1]); }
  for (const id of Object.keys(locs)) { const m = id.match(/^Л(\d+)$/); if (m) nextL = Math.max(nextL, +m[1]); }
  const lex = opts.lexicon || {};
  const userVerbs = Object.entries(lex.verbs || {}); // [слово, действие]
  const aliasMap = {}; let lastSubj = null; const autoMade = {};
  const nameIndexL = () => { const i = nameIndex(chars); for (const [a, id] of Object.entries(lex.names || {})) if (chars[id] || id === 'Р') i.push([low(a), id]); for (const [a, id] of Object.entries(aliasMap)) i.push([a, id]); return i.sort((a, b) => b[0].length - a[0].length); };
  let idx = nameIndexL();
  const unknownNames = new Set(), unknownWords = new Map();
  let series = opts.series || 'Мой мультик', music = 'happy';
  const eps = []; let ep = null, sc = null, lastSpeaker = null, sceneSpeakers = [];
  const newEp = (num, title) => { ep = { format: 'multik/1', series, episode: num, title: title || '', music, scenes: [], characters: [], locations: [] }; eps.push(ep); sc = null; };
  const ensureScene = () => { if (!sc) newScene('двор, день'); };
  const lines = String(text || '').replace(/\r/g, '').split('\n');
  // 1-й проход: персонажи
  for (const raw of lines) {
    const m = raw.trim().match(/^(?:персонаж|герой|новый персонаж)\s*[:\-—]\s*([^—–\-:]+?)\s*[—–\-:]\s*(.+)$/i);
    if (!m) continue;
    const name = m[1].trim(), desc = m[2].trim(), existing = findNameAt(name, idx);
    if (existing && low(chars[existing.id].name) === low(name)) { if (!chars[existing.id].old) continue; warnings.push(`«${name}» уже есть (${existing.id}) — беру готового, описание пропускаю.`); continue; }
    if (!global.MKMaker) { errors.push('Нет модуля создания персонажей'); continue; }
    const r = global.MKMaker.apply(null, desc + ', зовут ' + name); r.spec.name = name;
    const id = 'К' + (++nextC); const spec = global.MKMaker.finalize(r.spec, id); spec.about = desc;
    chars[id] = { name, spec }; newChars[id] = spec; idx = nameIndexL();
    if (r.unknown.length) warnings.push(`${name}: не понял слова «${r.unknown.join(', ')}» — остальное учёл.`);
  }
  const placeX = (side) => { const used = Object.values(sc._x); const lo = used.length ? Math.min(...used) : null, hi = used.length ? Math.max(...used) : null;
    const near = side === 'right' ? (hi != null ? [hi + .15, hi + .28] : [.6, .7]) : side === 'left' ? (lo != null ? [lo - .15, lo - .28] : [.4, .3]) : (hi != null ? [hi + .15, lo - .15] : [.45]);
    for (const x of near.concat(side === 'right' ? [.72, .84, .52] : side === 'left' ? [.28, .16, .48] : []).concat([.35, .62, .2, .78, .5, .1, .9])) if (x >= .1 && x <= .9 && !used.some(u => Math.abs(u - x) < .12)) return x; return .5; };
  const castOf = (id, hidden, side) => { if (id === 'Р') return; if (!sc._cast[id]) { const x = placeX(side); sc._cast[id] = { who: id, x, hidden: !!hidden }; sc._x[id] = x; sc.cast.push(sc._cast[id]); } };
  function newScene(desc) {
    if (!ep) newEp(1, '');
    const d = low(desc), type = pick(PLACES, d) || (sc && sc._type) || 'yard', time = pick(TIMES, d) || 'day', weather = /дожд/.test(d) ? 'rain' : /снег|снежн/.test(d) ? 'snow' : 'none';
    // сад (дедушкин сад, огород) — двор, но другое место: свой домик, грядки и яблони, без будки и качелей
    const variant = type === 'yard' && /((^|[^а-я])сад(а|у|ом|е|ик|ике)?(?![а-я])|огород)/.test(d) ? 'garden' : null;
    let lid = Object.keys(locs).find(id => { const s = locs[id].spec; return s.type === type && (s.time || 'day') === time && (s.weather || 'none') === weather && (s.variant || null) === variant; });
    if (!lid) { lid = 'Л' + (++nextL); const spec = { id: lid, name: desc.trim().slice(0, 40) || type, type, time, weather, seed: nextL }; if (variant) spec.variant = variant; locs[lid] = { spec }; newLocs[lid] = spec; }
    const carry = {}; if (sc && ep.scenes.includes(sc)) { Object.assign(carry, sc._carry || {}); for (const p of sc.props) if (p._held && !p._gone) carry[p._held] = { type: p.type, color: p.color }; }   // что у героя осталось в лапах — несёт дальше
    sc = { id: 'С' + (ep.scenes.length + 1), location: lid, cast: [], props: [], steps: [], _cast: {}, _x: {}, _type: type, _variant: variant, _carry: carry, _out: {} };
    { const th = themeWord(d); if (th) theme = th; } if (theme && type !== 'space') sc.theme = theme;
    const mu = pick(MUSIC, d); if (mu) sc.music = mu;
    { const prev = ep.scenes.slice().reverse().find(s => s._type === type && (s._variant || null) === variant); if (prev) for (const p of prev.props) if (!p._gone && !p._held && !p.holder && !p.decor && !p.hidden && p._used) sc.props.push({ id: 'П' + (sc.props.length + 1), type: p.type, x: p.x, color: p.color, _used: true, _carried: true }); }
    ep.scenes.push(sc); lastSpeaker = null; sceneSpeakers = [];
  }
  // ---- мир сцены: всё, что упомянуто в репликах, становится видно в кадре ----
  const shown = [], unknownObj = new Map(); let theme = null;
  const themeWord = (d) => { for (const [re, th] of THEMES) if (re.test(d)) return th; return null; };
  const userObj = Object.entries(lex.objects || {});
  function objOf(w) { const u = userObj.find(([k]) => w === k || (k.length > 4 && w.startsWith(k.slice(0, -1)))); if (u) return u[1]; return pick(DECOR, w) || pick(PROPS, w); }
  function freeSpot(big) { const used = sc.props.filter(p => !p._gone).map(p => p.x); for (const x of big ? [.5, .3, .7, .18, .82] : [.42, .6, .3, .72, .5]) if (!used.some(u => Math.abs(u - x) < .12)) return x; return .2 + Math.random() * .6; }
  function vanishNow(pr) { // исчезает на последнем звуке «вжух/волшебство/хлоп», если он был только что, иначе — сейчас
    let at = -1; for (let k = sc.steps.length - 1; k >= Math.max(0, sc.steps.length - 4); k--) if (sc.steps[k].sfx && /^(whoosh|magic|pop|sparkle)$/.test(sc.steps[k].sfx)) { at = k; break; }
    const st = { prop: pr.id, state: 'vanish', with: true }; if (at >= 0) sc.steps.splice(at + 1, 0, st); else sc.steps.push(st); pr._gone = true; }
  function elsewhere(d) { const m = d.match(ELSEWHERE); if (!m) return false; const t2 = pick(PLACES, m[0]); if (!t2) return false; if (t2 !== sc._type) return true;
    const g2 = t2 === 'yard' && /(сад|огород)/.test(m[0]) ? 'garden' : null; return t2 === 'yard' && /(сад|огород|двор)/.test(m[0]) && g2 !== (sc._variant || null); }
  function stage(text, who) { // реплика → вещи в кадре
    const d0 = low(text); const sents = d0.match(/[^.!?…]+[.!?…]*/g) || [d0]; const lineCue = SEE.test(d0); let firstId = null;
    sc._ln = (sc._ln || 0) + 1;
    if (/(рисун|нарисован|картинк|в книге|на карте|на странице|в записке|в письме)/.test(d0)) return;   // «На рисунке дерево, цветок и дверь» — это в книжке, а не вокруг
    sents.forEach((d) => {
      const words = d.split(/[^а-яa-z]+/).filter(Boolean); const cue = SEE.test(d) || (lineCue && !/\?\s*$/.test(d));
      const isQ = /\?\s*$/.test(d) && !SEE.test(d), maybe = /(может|вдруг|наверн|если|(^|[^а-я])бы(?![а-я])|хоч)/.test(d) || FUTURE.test(d) || elsewhere(d);
      const glowNow = /(засвет|зажгл|загорел|засия|вспыхн)/.test(d), glowAdj = /(свет|сия|горит|сверка|блест)/.test(d);
      const absent = ABSENT.test(d), opening = /(открыва|открыл|распахн|отвори|отворя)/.test(d), closing = /(закрыва|закрыл|захлопн)/.test(d), moving = /(двига|кати|покати|шевел|сам[аио]? (по)?(ехал|полз|прыг)|прыгает сам|убега)/.test(d);
      let found = false;
      words.forEach((w, wi) => {
        let type = objOf(w);
        if (!type) { if (cue && wi > 0 && /^(огромн|больш|волшебн|страшн|светящ|чудесн|странн|необычн)/.test(words[wi - 1]) && w.length > 3 && !/^(одн|свет|цвет|друг|сам|так|очен|как|кто|что|след|потол|небо|неб|ж[её]лт|красн|зел[её]н|син|рыж|бел|ч[её]рн|сер|розов|голуб|оранж|фиолет|коричн)/.test(w) && !GENERIC.has(w) && !idx.some(([n]) => w.startsWith(n.slice(0, 4)))) unknownObj.set(w, text.trim()); return; }
        const vanish0 = /(исчез|пропал|растаял|улетел|нет больше)/.test(d);
        if (!absent) { sc._said = sc._said || {}; if (!sc._said[type]) sc._said[type] = { at: sc.steps.length, who: who && who !== 'Р' ? who : null }; }
        // «Где наш торт?» — если торт тут лежал, он пропадает (на звук «вжух», если он был только что)
        if (absent && !vanish0) { if (/(^|[^а-я])где(?![а-я])/.test(d)) { const ex = sc.props.find(x => x.type === type && !x._gone && !x._held && !x.holder && !x.hidden); if (ex) vanishNow(ex); } return; }
        if (isQ || maybe || !cue) return; if (wi > 0 && words[wi - 1] === 'не') return;
        if (!SEE.test(d)) { let j = wi - 1; if (j >= 0 && /^(мо[йяеёю]|мое[йм]|моего|моему|мои[хм]?|тво|сво|наш|ваш|его|е[её]|их|эт|т[оае][йм]?$|больш|маленьк|стар|нов|друг)/.test(words[j])) j--; if (j >= 0 && /^(в|во|на|под|из|у|с|со|за|над|о|об|по|при|к|ко|от|до|без|про|через|около|возле|внутри)$/.test(words[j])) return; }   // «И в моей чашке» — где-то там, не здесь
        if (wi > 0 && objOf(words[wi - 1])) return;   // «карта клада», «коробка конфет» — вторая вещь только уточняет первую
        if (EVENT_DECOR.has(type) && (isQ || !NOW_CUE.test(d))) return;   // «Дедушка держит там радугу», «радуга ждёт» — не значит, что она уже тут
        const tkind = type === 'tree' ? pick(TREE_KIND, w) : null;
        if (type === 'tree' && sc._type === 'forest' && !/^(birch|palm|apple)$/.test(tkind || '')) return;   // в лесу и так деревья: показываем только особенное (берёзу)
        if (type === 'decor' || type === 'faces') { if (type === 'faces') { theme = theme || 'halloween'; type = 'jack'; } else { if (!theme) theme = null; return; } }
        found = true;
        if (theme === 'halloween' && (type === 'pumpkin' || type === 'lantern') && /(свет|глаз|лиц|фонар|страшн|горит)/.test(d)) type = 'jack';
        const near = words.slice(Math.max(0, wi - 3), wi).join(' ');
        const big = /(огромн|громадн|гигантск|больш)/.test(near) || BIG_DEFAULT.has(type), small = /(маленьк|крошечн|малюс)/.test(near);
        let color = null; for (const ww of words.slice(Math.max(0, wi - 2), wi)) { const c = global.MKMaker && global.MKMaker.colorOf(ww); if (c) color = c.hex; }
        const glow = (glowAdj && !glowNow) || type === 'garland', glowStatic = type === 'garland';
        const vanish = /(исчез|пропал|растаял|улетел|нет больше)/.test(d);
        const morph = !!(sc._vanishLn && sc._ln - sc._vanishLn <= 2 && !vanish); const appear = /(появил|возник|вырос|(^|[^а-я])вдруг)/.test(d) || (type === 'door' && /волшебн/.test(d)) || morph;
        const fresh = /(ещ[её] одн|друг[аоу]я|нов[аоы][яйе])/.test(d);
        const mine = /((^|[^а-я])наш(а|е|и|у)?|(^|[^а-я])мо[йяеё]|у меня|у нас)(?![а-я])/.test(near) && who && who !== 'Р' && !big;
        let pr = fresh ? null : sc.props.find(x => x.type === type && !x._gone && (type !== 'tree' || (x.kind || null) === (tkind || null))) || (vanish ? sc.props.find(x => x.type === type) : null);
        if (!pr && type === 'jack') pr = sc.props.find(x => x.type === 'pumpkin' && !x._gone);
        if (!pr) { pr = { id: 'П' + (sc.props.length + 1), type, x: freeSpot(big), decor: true }; if (tkind) pr.kind = tkind === 'fir' && theme === 'newyear' ? 'xmas' : tkind; if (EVENT_DECOR.has(type) && sc._ln > 1) pr.hidden = true; if (big && !small) pr.big = type === 'moon' ? 1 : MID_DEFAULT.has(type) ? 1 : 2.4; else if (MID_DEFAULT.has(type)) pr.big = .62; if (small) pr.big = .7; if (color) pr.color = color;
          if (appear && !vanish) pr.hidden = true;
          if (!pr.hidden && !big && !glowStatic && !mine && !vanish && sc.steps.some(st => st.say)) { pr.hidden = true; pr._quiet = true; const wx = who && who !== 'Р' ? sc._x[who] : null; if (wx != null) pr.x = Math.max(.08, Math.min(.92, wx + (wx > .5 ? -.1 : .1))); }
          if (glowStatic && !pr.hidden) pr.glow = true; if (mine) { pr.holder = who; castOf(who); delete pr.decor; } if (morph && sc._vanishHeld && !big) { pr.holder = sc._vanishHeld; delete pr.decor; } sc.props.push(pr);
          shown.push({ pr, type, scene: sc.id, how: [pr.kind ? ({ birch: 'берёза', fir: 'ёлка', xmas: 'новогодняя ёлка', apple: 'яблоня', palm: 'пальма', leafy: 'лиственное' })[pr.kind] || '' : '', pr.big > 1 ? 'большая' : '', glow || glowNow ? 'светится' : '', pr.hidden ? 'появляется' : '', vanish ? 'исчезает' : '', mine ? 'у героя в руках' : ''].filter(Boolean).join(', ') }); }
        if (pr.type === 'pumpkin' && type === 'jack') pr.type = 'jack';
        if (pr.hidden && !pr._shown) { const ap = { prop: pr.id, state: 'appear', with: true }; if (pr._quiet) ap.quiet = true; if (who && who !== 'Р') ap.who = who; sc.steps.push(ap); pr._shown = true; if (glow || glowNow) { sc.steps.push({ prop: pr.id, state: 'glow', with: true }); pr._glow = true; } }
        else if (vanish && !pr._gone) { sc.steps.push(Object.assign({ prop: pr.id, state: 'vanish', with: true }, who && who !== 'Р' ? { who } : {})); pr._gone = true; sc._vanishLn = sc._ln; sc._vanishHeld = pr._held || pr.holder || null; }
        else if ((glowNow || glowAdj) && !pr.glow && !pr._glow) { sc.steps.push({ prop: pr.id, state: 'glow', with: true }); pr._glow = true; }
        if (!vanish && type === 'door' && (opening || closing) && !!pr._open !== opening) { sc.steps.push({ prop: pr.id, state: opening ? 'open' : 'close', with: true }); pr._open = opening; }
        if (!vanish && moving && !pr.big && !pr._held && !pr.holder) sc.steps.push({ prop: pr.id, state: 'move', with: true });
        if (!vanish) { firstId = firstId || pr.id; sc._lastObj = pr.id; }
      });
      // «У неё светятся глаза!», «Она светится!» — про последнюю вещь
      if (!found && (glowNow || glowAdj) && !isQ && !maybe && sc._lastObj && /(она|он(?![а-я])|оно|у не[её]|у него|глаз|тоже)/.test(d)) { const pr = sc.props.find(x => x.id === sc._lastObj);
        if (pr && !pr._gone) { if (pr.type === 'pumpkin') pr.type = 'jack'; if (!pr.glow && !pr._glow) { sc.steps.push({ prop: pr.id, state: 'glow', with: true }); pr._glow = true; } } }
      if (!found && /(исчез|пропал)/.test(d) && sc._lastObj && /(она|он(?![а-я])|оно)/.test(d)) { const pr = sc.props.find(x => x.id === sc._lastObj); if (pr && !pr._gone) { sc.steps.push({ prop: pr.id, state: 'vanish', with: true }); pr._gone = true; sc._vanishLn = sc._ln; } }
    });
    if (firstId && /(смотри|гляди|глянь|вот(?![а-я])|видите|видишь)/.test(d0)) sc.steps.push({ look: firstId, who: who && who !== 'Р' ? who : undefined, with: true });
    else if (who && who !== 'Р' && !FUTURE.test(d0) && !ABSENT.test(d0)) {   // говорит о вещи, которая тут есть, — смотрит на неё (один говорящий, без смены плана)
      for (const w of d0.split(/[^а-яё-]+/)) { const t = w && objOf(w); if (!t) continue; const pr = sc.props.find(x => x.type === t && !x._gone && (!x.hidden || x._shown) && x._held !== who); if (pr) { sc.steps.push({ look: pr.id, who, with: true, solo: true }); break; } } }
  }
  let lineNo = 0, narrated = 0;
  const applyTheme = () => { if (theme && sc && !sc.theme && sc._type !== 'space') sc.theme = theme; };
  for (const raw0 of lines) {
    applyTheme(); lineNo++;
    let raw = raw0.trim(); if (!raw || /^(персонаж|герой|новый персонаж)\s*[:\-—]/i.test(raw) || /^\/\//.test(raw)) continue;
    const L = low(raw);
    let m;
    if ((m = raw.match(/^(?:сериал|мультик|мультфильм)\s*[:\-—]\s*(.+)$/i))) { series = m[1].trim(); if (ep) ep.series = series; continue; }
    if ((m = raw.match(/^серия\s*[:\-—]?\s*(\d+)?\s*[.:\-—]?\s*(.*)$/i))) { theme = null; newEp(m[1] ? +m[1] : (eps.length ? eps[eps.length - 1].episode + 1 : (opts.nextEpisode || 1)), m[2].trim()); continue; }
    if ((m = raw.match(/^(?:сцена|место|локация)\s*\d*\s*[:.\-—]?\s*(.*)$/i))) { if (!ep) newEp(opts.nextEpisode || 1, ''); newScene(m[1] || ''); continue; }
    if ((m = raw.match(/^музыка\s*[:\-—]\s*(.+)$/i))) { const mu = pick(MUSIC, low(m[1])) || 'happy'; if (sc) sc.steps.push({ music: mu }); else music = mu; continue; }
    if ((m = raw.match(/^(?:звук|шум)\s*[:\-—]\s*(.+)$/i))) { ensureScene(); const s = pick(SFX, low(m[1])); if (s) sc.steps.push({ sfx: s }); else warnings.push(`Строка ${lineNo}: не знаю звук «${m[1]}»`); continue; }
    if ((m = L.match(/^пауза\s*(\d+(?:[.,]\d+)?)?/))) { ensureScene(); sc.steps.push({ wait: m[1] ? +m[1].replace(',', '.') : 1 }); continue; }
    if ((m = raw.match(/^(?:камера|план)\s*[:\-—]\s*(.+)$/i)) || /^\(?\s*(крупн|общий план|средний план|оба в кадре)/.test(L)) { ensureScene(); camera(m ? m[1] : raw); continue; }
    if (!ep) newEp(opts.nextEpisode || 1, '');
    ensureScene();
    // реплика в кавычках внутри рассказа: «Он почесал затылок и сказал: „Это мухомор“», «Заяц засмеялся: "Я Ушастик!"»
    { const q = raw.match(/^(.*?)[:,—–-]?\s*[«"„“]([^»"“”]+)[»"“”]\s*[.!?…]*\s*(?:[—–-]\s*(.+))?$/);
      if (q && !/^\s*[—–-]/.test(raw)) { const pre = (q[1] || '').trim(), after = (q[3] || '').trim(), ctx = low(pre + ' ' + after);
        let who = null; const d0 = low(pre || after);
        const ids = namesIn(ctx, idx); if (ids.length) who = ids.sort((a, b) => ctx.search(low(chars[a].name).slice(0, 4)) - ctx.search(low(chars[b].name).slice(0, 4)))[0];
        if (!who) { const sj = subjectsOf(d0); if (sj && sj.length === 1) who = sj[0]; }
        if (!who && lastSpeaker && lastSpeaker !== 'Р') who = lastSpeaker;
        if (who) { castOf(who); backIn(who); lastSubj = who;
          const actPart = pre.replace(/(,?\s*(и\s+)?(сказал|сказала|сказали|ответил|ответила|спросил|спросила|крикнул|крикнула|закричал|закричала|прошептал|прошептала|воскликнул|воскликнула|произн[её]с|произнесла|добавил|добавила|пискнул|пискнула|буркнул|заявил|объявил)[а-я]*)\s*$/i, '').trim();
          if (actPart && actPart !== pre) { if (action(actPart)) { const sj2 = sc.steps[sc.steps.length - 1]; if (sj2) sj2.with = false; } } else if (actPart && pick(EMO, low(actPart))) {}
          const cl = global.MK ? global.MK.cleanSpeech(q[2].trim()) : { text: q[2].trim(), removed: [] };
          const step = { who, say: cl.text }; const e = pick(EMO, ctx); if (e) step.emotion = e; { const mn = mannerOf(ctx); if (mn) step.manner = mn; } const vv = verbOf(low(pre)); if (vv && ['laugh', 'cry', 'shout', 'jump', 'wave', 'nod', 'shake', 'point', 'scared', 'surprise', 'dance'].includes(vv)) step.do = vv;
          const other = lastSpeaker && lastSpeaker !== who && lastSpeaker !== 'Р' ? lastSpeaker : sceneSpeakers.filter(x => x !== who && x !== 'Р').slice(-1)[0]; if (other) step.to = other;
          autoCam(who); sc.steps.push(step); lastSpeaker = who; if (!sceneSpeakers.includes(who)) sceneSpeakers.push(who); nameFromLine(who, cl.text); stage(cl.text, who); continue; } } }
    // реплика «Имя (как): текст»
    m = raw.match(/^([^:()]{1,40}?)\s*(?:\(([^)]*)\))?\s*:\s*(.+)$/);
    if (m) {
      let who = NARR.test(low(m[1].trim())) ? 'Р' : (findNameAt(m[1], idx) || {}).id;
      if (!who) { const w0 = m[1].trim().split(/\s+/)[0]; const sj = subjectsOf(low(m[1].trim())); if (sj && sj.length === 1) who = sj[0]; else if (AUTO_HERO.has(low(w0))) who = autoHero(w0); }
      if (!who && sc && /^(все|все вместе|вместе|хором|все хором|друзья|все друзья)$/.test(low(m[1].trim()))) { const list = Object.keys(sc._cast).filter(id => id !== 'Р' && !sc._out[id]);
        const cl = global.MK ? global.MK.cleanSpeech(m[3].trim()) : { text: m[3].trim() }; const e = m[2] ? pick(EMO, low(m[2])) : null;
        if (list.length && cl.text) { list.forEach((w, k) => { const st = { who: w, say: cl.text }; if (k) st.with = true; if (e) st.emotion = e; sc.steps.push(st); }); lastSpeaker = list[0]; continue; } }
      if (!who) { if (/^[А-ЯЁA-Z]/.test(m[1].trim()) && m[1].trim().split(/\s+/).length <= 3) { unknownNames.add(m[1].trim()); errors.push(`Строка ${lineNo}: кто такой «${m[1].trim()}»? Выбери ниже, кто это, или добавь строку «ПЕРСОНАЖ: ${m[1].trim()} — описание».`); continue; }
        m = null; } else {
      castOf(who);
      const cl = global.MK ? global.MK.cleanSpeech(m[3].replace(/^["«]|["»]$/g, '').trim()) : { text: m[3], removed: [] };
      if (cl.removed.length) warnings.push(`Строка ${lineNo}: убрал из озвучки лишнее: ${cl.removed.join(' ')}`);
      if (!cl.text) continue;
      const step = { who, say: cl.text };
      if (m[2]) { const e = pick(EMO, low(m[2])); if (e) step.emotion = e; const mn = mannerOf(low(m[2])); if (mn) step.manner = mn; const v = verbOf(low(m[2])); if (v && who !== 'Р') step.do = v; }
      { const rest = low(m[1]).replace(/^\S+\s*/, ''); const v2 = rest && who !== 'Р' ? verbOf(rest) : null; if (v2 && !step.do) step.do = v2; const e2 = rest ? pick(EMO, rest) : null; if (e2 && !step.emotion) step.emotion = e2; }
      if (who !== 'Р' && !step.emotion) { const ae = pick(AUTO_EMO, low(cl.text).replace(/^[\s«"—-]+/, '')); if (ae) { step.emotion = ae; step._auto = true; } }
      if (who !== 'Р') { const other = lastSpeaker && lastSpeaker !== who && lastSpeaker !== 'Р' ? lastSpeaker : sceneSpeakers.filter(x => x !== who && x !== 'Р').slice(-1)[0]; if (other) step.to = other;
        backIn(who); autoCam(who); }
      { const lt = low(cl.text), painting = sc.props.some(x => (x.type === 'easel' || x.type === 'paints') && !x._gone) || /(краск|кисточк|кисть|мольберт)/.test(lt);
        if (who !== 'Р' && painting && /(картин|нарису|порису|рисова|рисуем|рисую|дорису)/.test(lt) && !/(нарисовано|на рисунке)/.test(lt)) easel();
        if (who !== 'Р' && !step.do && sc.props.some(x => x.type === 'easel' && !x._gone) && /((^|[^а-я])нарису[юе]|(^|[^а-я])рисую|дорису|(^|[^а-я])добавлю|(^|[^а-я])добавим|раскрашу|нарисовал|дорисовал|(^|[^а-я])законч(ил|ила|или)|теперь мне нравится|ещё раз|еще раз)/.test(lt) && !/(\?\s*$|(^|[^а-я])не (буду|хочу|могу))/.test(lt)) step.do = 'paint'; }
      sc.steps.push(step); if (step.do === 'paint' && who !== 'Р') stroke(who); lastSpeaker = who; if (!sceneSpeakers.includes(who)) sceneSpeakers.push(who); if (who !== 'Р') lastSubj = who; nameFromLine(who, cl.text);
      { const th = themeWord(low(cl.text)); if (th && !theme) theme = th; }
      stage(cl.text, who);
      if (who === 'Р') { // рассказчик описывает, что делают герои, — они это делают, пока он говорит
        for (const s0 of (cl.text.match(/[^.!?…]+[.!?…]*/g) || [cl.text])) { const s1 = s0.trim(), ls = low(s1);
          if (!s1 || /\?\s*$/.test(s1) || /(если|может|будто|наверн|хоч|(^|[^а-я])бы(?![а-я])|завтра|скоро|когда-нибудь)/.test(ls) || !namesIn(ls, idx).length) continue;
          const n0 = sc.steps.length; if (actPieces(s1.replace(/[.!?…]+$/, ''))) for (const st of sc.steps.slice(n0)) if (st.do) st.with = true; } }
      continue; }
    }
    // диалог через тире: «— Привет! — сказал Барсик.»
    if (/^[—–-]\s*\S/.test(raw)) { if (dashLine(raw)) continue; }
    if (/^[^—–«"]{1,80}?[!?.…,]\s+[—–]\s+\S/.test(raw) && SAYV.test(low(raw.split(/\s+[—–]\s+/)[1] || ''))) { if (dashLine('— ' + raw)) continue; }
    // действие: «(Барсик прыгает)», «Пик входит справа.», «Барсик и Пик танцуют»
    const bracket = /^\(.*\)$/.test(raw);
    const t = raw.replace(/^\(|\)$/g, '').trim();
    const sentences = t.match(/[^.!?…]+[.!?…]*/g) || [t];
    for (const sent0 of sentences) { const sent = sent0.trim(); if (!sent) continue;
      placeShift(sent);
      const core = sent.replace(/[.!?…]+$/, '');
      const did = actPieces(core);
      const past = /[а-яё]+(?:ал|ял|ил|ел|ул|ыл|ла|ли|лся|лась|лись)(?![а-яё])/i.test(core) && core.split(/\s+/).length >= 3;
      if (did && past && !bracket) { sc.steps.push({ who: 'Р', say: sent, with: true }); }
      if (!did && !bracket) { sc.steps.push({ who: 'Р', say: sent }); narrated++; stage(sent, 'Р'); }
      else if (!did) warnings.push(`Строка ${lineNo}: не понял «${sent.slice(0, 50)}» — пропускаю.`);
    }
  }
  applyTheme();
  for (const e of eps) { if (e.scenes.some(x => x.theme)) continue; const th = themeWord(low(e.title)); if (th) e.scenes.forEach(x => { if (x._type !== 'space') x.theme = th; }); }
  function placeShift(sent) { // «Друзья пришли в лес» → новая сцена
    const d = low(sent); const type = pick(PLACES, d); const gard = type === 'yard' && /((^|[^а-я])сад(а|у|ом|е|ик|ике)?(?![а-я])|огород)/.test(d) ? 'garden' : null; if (!type || (type === sc._type && gard === (sc._variant || null))) return;
    if (!/(^|\s)(в|во|на|к|у)\s/.test(d) && !/домой/.test(d)) return;
    if (!/(пришл|приш[её]л|пош[её]л|пошли|побежал|отправил|оказал|вернул|прибежал|прилетел|полетел|поехал|приехал|^в |^на |^утром|^вечером|^ночью)/.test(d) && sc.steps.length) return;
    const time = pick(TIMES, d); const keepCast = Object.keys(sc._cast);
    newScene((gard ? { yard: 'сад' } : {})[type] || ({ space: 'космос', beach: 'пляж', winter: 'зима', kitchen: 'кухня', playground: 'площадка', street: 'улица', room: 'комната', yard: 'двор', meadow: 'луг', forest: 'лес' })[type] + (time ? ' ' + (time === 'night' ? 'ночь' : time === 'evening' ? 'вечер' : 'день') : ''));
    sc.location = sc.location; keepCast.forEach(id => { if (id !== 'Р') { castOf(id); } });
  }
  function dashLine(raw) { // — Реплика, — сказал Имя. — Продолжение.
    const parts = raw.replace(/^[—–-]\s*/, '').split(/\s+[—–]\s+/);
    let speech = [parts[0]], who = null, emo = null, group = null, act = null;
    for (let i = 1; i < parts.length; i++) { const d = low(parts[i]); const ids = namesIn(d, idx);
      if (!who && !group && SAYV.test(d)) { const sj = subjectsOf(d.replace(/^\S+\s+/, '')) || subjectsOf(d); if (ids.length) who = ids[0]; else if (sj && sj.length > 1) group = sj; else if (sj && sj.length === 1) who = sj[0];
        if (!who && !group && /^(он|она)\s/.test(d.replace(/^\S+\s+/, '') + ' ') && lastSubj) who = lastSubj; if (who || group) { emo = pick(EMO, d); const v = verbOf(d); if (v && ['laugh', 'cry', 'scared', 'surprise', 'jump', 'wave', 'shout', 'nod'].includes(v)) act = v; continue; } }
      speech.push(parts[i]); }
    if (!who && !group) { const cand = sceneSpeakers.filter(x => x !== 'Р'); who = cand.length >= 2 ? cand.find(x => x !== lastSpeaker) : (cand[0] || null); }
    if (!who && !group) return false;
    const text = speech.join(' ').replace(/[,]$/, '').replace(/,\s*$/, '.').trim();
    if (group) { const named = namesIn(low(text), idx); group = group.filter(id => !named.includes(id)); if (!group.length) return false; }
    const list = group ? (text.split(/\s+/).length <= 5 ? group : group.slice(0, 1)) : [who];
    list.forEach((w, k) => { castOf(w); backIn(w); const step = { who: w, say: text }; if (k) step.with = true; if (emo) step.emotion = emo; if (act) step.do = act;
      const other = sceneSpeakers.filter(x => x !== w && x !== 'Р').slice(-1)[0]; if (other && !group) step.to = other;
      if (!k) autoCam(w); sc.steps.push(step); lastSpeaker = w; lastSubj = w; if (!sceneSpeakers.includes(w)) sceneSpeakers.push(w); });
    return true;
  }
  function verbOf(t) { if (/(выход\S*|вышел|вышла|вышли)\s+(во|в|на)\s/.test(t) && !/(из|прочь)/.test(t)) return 'enter'; if (/(выход\S*|вышел|вышла|вышли|выглядыва\S*|выглянул\S*)\s+из-за\s/.test(t)) return 'enter'; if (/(^|\s)(ждал|ждала|ждали|ждет|ждут|стоял|стояла|стояли|сидел и ждал)(\s|$)/.test(t) && !/(встал|сел)/.test(t)) return 'wait'; for (const w of t.split(/[^а-яa-z]+/)) { const u = userVerbs.find(([k]) => w === k || (k.length > 4 && w.startsWith(k.slice(0, -1)))); if (u) return u[1]; const v = pick(VERBS, w); if (v) return v; } return null; }
  function backIn(id) { // говорит тот, кто ушёл, — сначала возвращается туда, где стоял
    if (!sc || !sc._out || !sc._out[id]) return; delete sc._out[id]; const x = sc._x[id] != null ? sc._x[id] : placeX(); sc.steps.push({ who: id, do: 'enter', from: x > .5 ? 'right' : 'left', to: x }); }
  function camera(t) { const d = low(t); const who = namesIn(d, idx);
    if (/(крупн|лицо)/.test(d) && who[0]) sc.steps.push({ camera: 'close', on: who[0] });
    else if (/(средн)/.test(d) && who[0]) sc.steps.push({ camera: 'medium', on: who[0] });
    else if (/(оба|вдво|двое)/.test(d) && who.length >= 2) sc.steps.push({ camera: 'two', on: who.slice(0, 2) });
    else if (/(тряс|дрож)/.test(d)) sc.steps.push({ shake: .6 });
    else sc.steps.push({ camera: 'wide' }); sc._cam = 'manual'; }
  function autoCam(who) { // простая режиссура, если камера не задана вручную
    if (sc._cam === 'manual') return; const n = sc.steps.filter(s => s.say && s.who !== 'Р').length;
    if (lastSpeaker === who && sc._cam !== 'medium:' + who) { sc.steps.push({ camera: 'medium', on: who, auto: true }); sc._cam = 'medium:' + who; }
    else if (lastSpeaker && lastSpeaker !== who && lastSpeaker !== 'Р' && n >= 1 && !String(sc._cam || '').startsWith('two')) { sc.steps.push({ camera: 'two', on: [lastSpeaker, who], auto: true }); sc._cam = 'two'; }
  }
  function nameFromLine(who, text) { // «Не бойтесь, я Ушастик!» — у созданного автоматически героя появляется имя
    if (!newChars[who] || !Object.values(autoMade).includes(who)) return; const m = String(text).match(/(?:^|[^А-Яа-яЁё])[Яя]\s*[—–-]?\s*([А-ЯЁ][а-яё]{2,})/); if (!m) return;
    const old = chars[who].name; aliasMap[low(old)] = who; chars[who].name = m[1]; newChars[who].name = m[1]; idx = nameIndexL(); warnings.push(`«${old}» назвался «${m[1]}» — дальше понимаю оба имени.`); }
  function autoHero(word) { const w = low(word); if (!AUTO_HERO.has(w) || !global.MKMaker) return null; if (autoMade[w]) return autoMade[w];
    for (const [id, c] of Object.entries(chars)) if (low(c.name) === w) return (autoMade[w] = id);
    const r = global.MKMaker.apply(null, w); const name = word[0].toUpperCase() + word.slice(1).toLowerCase(); r.spec.name = name; const id = 'К' + (++nextC); const spec = global.MKMaker.finalize(r.spec, id); spec.about = w;
    chars[id] = { name, spec }; newChars[id] = spec; idx = nameIndexL(); autoMade[w] = id; warnings.push(`Создал героя «${name}» (${global.MKMaker.describe(spec)}). Чтобы описать подробнее, добавьте строку «ПЕРСОНАЖ: ${name} — описание».`); return id; }
  function subjectsOf(d) { // «он/она» — последний, о ком шла речь; «они/все/друзья» — все в сцене
    if (/^(все|они|друзья|ребята|вместе|оба|обе|все вместе)(?![а-я])/.test(d)) return Object.keys(sc._cast).filter(x => x !== 'Р');
    if (/^(он|она|оно)(?![а-я])/.test(d) && lastSubj) return [lastSubj];
    const ws = d.replace(/^(вдруг|тут|потом|затем|тогда|и|а|но|однажды|утром|вечером|ночью|днём|днем|внезапно|наконец|сразу|из-за \S+|из \S+)\s+/g, '').split(/[^а-яё]+/).filter(Boolean).slice(0, 3);
    for (let k = 0; k < ws.length; k++) { const w0 = ws[k]; if (k > 0 && !verbOf(ws[k - 1])) break; if (AUTO_HERO.has(w0) && !idx.some(([n]) => n === w0)) { const id = autoHero(w0); if (id) return [id]; } if (k === 0 && !verbOf(w0)) break; }
    return null; }
  function actPieces(core) { // «Барсик взял лопату и начал копать» → два действия подряд, подлежащее переносится
    const pieces = core.split(/,\s*(?:а|но|и)\s+(?=[А-ЯЁ])|\s+и\s+(?=[а-яё]+(?:ет|ит|ут|ют|ат|ят|ется|ится|ал|ял|ил|ел|ул|ыл|ла|ли|лся|лась|лись|ся|сь)(?![а-яё]))/).filter(x => x && !/^(ет|ит|ут|ют|ат|ят|ется|ится|ал|ял|ил|ел|ул|ыл|ла|ли|лся|лась|лись|ся|сь)$/.test(x));
    let did = false, subjName = null;
    pieces.forEach((pc, k) => { let q = pc; const fw = (low(pc).match(/^[а-яё]+/) || [])[0]; if (k > 0 && subjName && (!namesIn(low(q), idx).length || (fw && verbOf(fw)))) q = subjName + ' ' + q; const ok = action(q); if (ok) { did = true; if (k === 0) { const ids = namesIn(low(pc), idx); if (ids[0]) subjName = chars[ids[0]] ? chars[ids[0]].name : null; } } });
    return did; }
  function action(sent) {
    const d = low(sent); let who = namesIn(d, idx).filter(id => { const n = findNameAt(d, idx); return true; }); let grpAll = null;
    { const sj = subjectsOf(d.replace(/^\s+/, '')); if (sj && sj.length > 1 && /^(все|они|друзья|ребята|вместе|оба|обе)(?![а-я])/.test(d.replace(/^\s+/, ''))) grpAll = sj.filter(id => !sc._out[id]); if (sj && sj.length) { who = sj.concat(who.filter(x => !sj.includes(x))); if (sj.length > 1) { const v = verbOf(d), e = pick(EMO, d); if ((v || e) && !['kick', 'throw', 'give', 'take', 'walk', 'run', 'enter', 'exit', 'hug'].includes(v)) { sj.forEach((id, k) => { castOf(id); const st = { who: id }; if (k) st.with = true; if (v && !['walk', 'run', 'enter', 'exit', 'give', 'take', 'hug', 'turn', 'kick', 'throw'].includes(v)) st.do = v; if (e) st.emotion = e; if (!st.do && !st.emotion) return; sc.steps.push(st); }); return true; } } } }
    // порядок имён по позиции в предложении
    who = who.map(id => [id, d.search(low(chars[id].name).split(' ').slice(-1)[0].slice(0, 4))]).sort((a, b) => a[1] - b[1]).map(x => x[0]);
    if (!who.length) { if (/(крупн|общий план)/.test(d)) { camera(d); return true; } const s = pick(SFX, d); if (s && /(звук|слышно|раздает)/.test(d)) { sc.steps.push({ sfx: s }); return true; } return false; }
    const verb = verbOf(d); const emo = pick(EMO, d);
    if (verb === 'wait') { who.forEach(id => castOf(id)); return true; }
    if (!verb && !emo) { const words = d.split(/[^а-яa-z]+/).filter(w => w.length > 3 && !idx.some(([n]) => w.startsWith(n.slice(0, 4))) && !/^(тоже|потом|сразу|снова|очень|когда|вдруг|затем|тогда|после|перед|около|возле|вместе)$/.test(w));
      if (words[0]) unknownWords.set(words[0], sent.trim()); return false; }
    // подлежащее — первые имена до глагола; остальные — цели
    const vpos = (() => { for (const w of d.split(/[^а-яa-z]+/)) if (pick(VERBS, w)) return d.indexOf(w); return 999; })();
    const pron = /^(он|она|оно)(?![а-я])/.test(d) && lastSubj ? lastSubj : null;
    const subj = pron ? [pron] : who.filter(id => { const nm = low(chars[id].name).split(' ').slice(-1)[0]; let p = d.indexOf(nm.slice(0, 4)); if (p < 0) { for (const [n2, id2] of idx) if (id2 === id) { const q = d.indexOf(n2.slice(0, 4)); if (q >= 0) { p = q; break; } } } return p >= 0 && p < vpos; });
    const S = subj.length ? subj : grpAll && grpAll.length ? grpAll : [who[0]]; lastSubj = S[0];   // «Все уходят» — уходят все, кто в сцене, а не один первый
    const targets = who.filter(id => !S.includes(id));
    let first = true;
    for (const id of S) {
      const step = { who: id }; if (!first) step.with = true; first = false;
      if (emo) step.emotion = emo;
      const tgt = targets[0];
      if (verb === 'enter') { delete sc._out[id]; const side = /(слева|левой)/.test(d) ? 'left' : /(справа|правой)/.test(d) ? 'right' : null; castOf(id, true, side); step.do = 'enter'; step.from = side || (sc._x[id] > .5 ? 'right' : 'left'); step.to = tgt && sc._x[tgt] != null ? tgt : sc._x[id]; if (step.to === undefined) delete step.to; }
      else {
        castOf(id);
        if (verb === 'exit') { sc._out[id] = true; step.do = 'exit'; step.side = /(влево|налево|слева)/.test(d) ? 'left' : /(вправо|направо|справа)/.test(d) ? 'right' : undefined; if (!step.side) delete step.side; }
        else if (verb === 'walk' || verb === 'run') { step.do = verb; if (tgt) { castOf(tgt); step.to = tgt; } else if (/(вправо|направо)/.test(d)) step.to = Math.min(.85, (sc._x[id] || .5) + .3); else if (/(влево|налево)/.test(d)) step.to = Math.max(.15, (sc._x[id] || .5) - .3); else if (/(центр|середин)/.test(d)) step.to = .5; else { const p = propIn(d); if (p) { const pr = ensureProp(p, id); step.to = Math.max(.08, Math.min(.92, pr.x - .06)); } else step.to = (sc._x[id] || .5) > .5 ? .3 : .7; }
          if (typeof step.to === 'number') sc._x[id] = step.to; else if (sc._x[step.to] != null) sc._x[id] = sc._x[step.to] + (sc._x[step.to] > sc._x[id] ? -.12 : .12); }
        else if (verb === 'think') { step.do = 'think'; const q = sent.match(/[«"]([^»"]+)[»"]/); step.text = q ? q[1] : (d.match(/(о|об|про)\s+(\S+)/) ? '?' : '?'); }
        else if ((verb === 'turn' || verb === 'read') && /(бинокл|телескоп|подзорн|лупу|лупой|лупа|в трубу)/.test(d)) { grab(id, propIn(d) || 'binoculars'); step.do = 'peer'; }
        else if (['read', 'dig', 'paint', 'write', 'play', 'drink'].includes(verb)) { const need = { read: null, dig: 'shovel', paint: 'paints', write: 'pencil', play: null, drink: 'cup' }[verb]; let p = propIn(d) || need; if (verb === 'drink' && !/^(milk|cup|jar)$/.test(p)) p = 'cup'; // пьёт чай/сок — из чашки
          if (verb === 'play' && !(p && /^(guitar|drum|flute|bell)$/.test(p))) { if (!step.emotion) step.emotion = 'happy'; }
          else { if (p) grab(id, p); step.do = verb; } }
        else if (['push', 'pull', 'sniff', 'knock'].includes(verb)) { const p = propIn(d); if (p) { if (verb === 'pull' && /^(rope|kite|sled|balloon)$/.test(p)) grab(id, p); else { const pr = ensureProp(p, id, true); pr._used = true; } } step.do = verb; }
        else if (verb === 'turn') { step.do = 'turn'; step.to = tgt || (/(на нас|в камеру|к зрител)/.test(d) ? 'camera' : /(влево|налево)/.test(d) ? 'left' : /(вправо|направо)/.test(d) ? 'right' : 'camera'); if (tgt) castOf(tgt); }
        else if (verb === 'hug') { step.do = 'hug'; if (tgt) { castOf(tgt); step.to = tgt; } }
        else if (verb === 'kick' || verb === 'throw') { step.do = verb; const p = propIn(d) || (verb === 'kick' ? 'ball' : null);
          if (verb === 'kick') { const pr = ensureProp(p, id, true); step.prop = pr.id; } else if (p && !sc.props.some(x => x._held === id)) { const pr = ensureProp(p, id); sc.steps.push({ who: id, do: 'take', prop: pr.id }); pr._held = id; }
          if (tgt) { castOf(tgt); step.to = tgt; } }
        else if (verb === 'crawl' || verb === 'sneak') { step.do = verb; if (tgt) { castOf(tgt); step.to = tgt; } else if (/(вправо|направо)/.test(d)) step.to = Math.min(.85, (sc._x[id] || .5) + .3); else if (/(влево|налево)/.test(d)) step.to = Math.max(.15, (sc._x[id] || .5) - .3); else step.to = (sc._x[id] || .5) > .5 ? .35 : .65; if (typeof step.to === 'number') sc._x[id] = step.to; }
        else if (verb === 'drop') { step.do = 'drop'; const p = propIn(d); const pr = sc.props.find(x => x._held === id && !x._gone && (!p || x.type === p)) || fromCarry(id, p); if (pr) { pr._held = null; step.prop = pr.id; } }
        else if (verb === 'take') { const p = propIn(d); if (!p) { if (!step.emotion) continue; } else { if (sc.props.some(x => x.type === p && x._held === id && !x._gone)) continue; if (fromCarry(id, p)) continue; if (sc._carry) delete sc._carry[id]; for (const c of sc.props.filter(x => x._held === id && !x._gone)) { sc.steps.push({ who: id, do: 'drop', prop: c.id }); c._held = null; } const pr = ensureProp(p, id); step.do = 'take'; step.prop = pr.id; pr._held = id; } }
        else if (verb === 'give') { step.do = 'give'; if (tgt) { castOf(tgt); step.to = tgt; const p = propIn(d); let pr = sc.props.find(x => x._held === id && !x._gone && (!p || x.type === p)); if (!pr && p) { pr = ensureProp(p, id); sc.steps.push({ who: id, do: 'take', prop: pr.id }); pr._held = id; } if (pr) pr._held = tgt; } else delete step.do; }
        else if (verb) step.do = verb;
      }
      if (!step.do && !step.emotion) { if (emo == null && !verb) return false; }
      if (!step.do) delete step.do;
      sc.steps.push(step); if (step.do === 'paint') stroke(id);
      if (step.do === 'jump' || step.do === 'enter' || step.do === 'dance' || step.do === 'fall') { if (sc._cam && sc._cam !== 'manual' && sc._cam !== 'wide') { sc.steps.push({ camera: 'wide', with: true, auto: true }); sc._cam = 'wide'; } }
      else if (sc._cam !== 'manual' && sc._cam !== 'medium:' + id && step.do && id !== 'Р') { // важная вещь в лапах или дело руками — камера подходит ближе
        const pt = step.prop && (sc.props.find(x => x.id === step.prop) || {}).type;
        if (CLOSE_DO.has(step.do) || (step.do === 'take' && KEY_PROPS.has(pt))) { sc.steps.push({ camera: 'medium', on: id, with: true, auto: true }); sc._cam = 'medium:' + id; } }
    }
    return true;
  }
  function fromCarry(id, p) { // «Рон кладёт зонтик», а зонтик он взял ещё в прошлой сцене — входит с ним в лапах
    const cr = sc._carry && sc._carry[id]; if (!cr || (p && cr.type !== p) || sc.props.some(x => x.type === cr.type && !x._gone && !x._held && !x.holder)) return null;
    const pr = { id: 'П' + (sc.props.length + 1), type: cr.type, x: sc._x[id] != null ? sc._x[id] : .5, holder: id, _used: true }; if (cr.color) pr.color = cr.color; pr._held = id; sc.props.push(pr); delete sc._carry[id]; return pr; }
  // рисуют картину: мольберт с холстом, на нём с каждым мазком прибавляется рисунок
  function easel() { let pr = sc.props.find(x => x.type === 'easel' && !x._gone); if (pr) return pr;
    const xs = Object.values(sc._x).filter(x => x != null).concat([.08, .92]).sort((a, b) => a - b); let best = .5, gap = 0; for (let i = 1; i < xs.length; i++) { const m0 = (xs[i] + xs[i - 1]) / 2; if (m0 < .2 || m0 > .8) continue; const g0 = xs[i] - xs[i - 1] - Math.abs(m0 - .5) * .2; if (g0 > gap) { gap = g0; best = m0; } }
    pr = { id: 'П' + (sc.props.length + 1), type: 'easel', x: best, decor: true, _used: true }; sc.props.push(pr); if (sc.steps.some(st => st.say)) { pr.hidden = true; sc.steps.push({ prop: pr.id, state: 'appear', quiet: true }); } /* мольберт ставят, когда решили рисовать */ shown.push({ pr, type: 'easel', scene: sc.id, how: 'холст для рисунка' }); return pr; }
  function stroke(id) { const e = easel(); sc.steps.push({ prop: e.id, state: 'paint', who: id, with: true }); }
  function grab(id, p) { // герой берёт вещь p; если в лапах уже другая — сначала кладёт её
    let pr = sc.props.find(x => x._held === id && x.type === p && !x._gone); if (pr) return pr; if ((pr = fromCarry(id, p))) return pr; if (sc._carry) delete sc._carry[id];
    for (const c of sc.props.filter(x => x._held === id && !x._gone)) { sc.steps.push({ who: id, do: 'drop', prop: c.id }); c._held = null; }
    pr = ensureProp(p, id); sc.steps.push({ who: id, do: 'take', prop: pr.id }); pr._held = id; return pr; }
  function propIn(d) { // сама вещь, а не место: «достал из рюкзака бинокль» → бинокль; «под дубом», «в корзине» — только если другой вещи нет
    const ws = d.split(/[^а-яa-z]+/).filter(Boolean); let loc = null;
    for (let i = 0; i < ws.length; i++) { const p = pick(PROPS, ws[i]); if (!p) continue; if (i > 0 && /^(из|в|во|под|на|у|от|с|со|за|возле|около|над|внутри|рядом)$/.test(ws[i - 1])) { loc = loc || p; continue; } return p; }
    return loc; }
  function ensureProp(type, nearId, ground) { let p = sc.props.find(x => x.type === type && !x._gone && !x._held); if (!p) { const x = Math.max(.08, Math.min(.92, (sc._x[nearId] != null ? sc._x[nearId] : .5) + .15)); const first = !sc.props.some(q => q.type === type); p = { id: 'П' + (sc.props.length + 1), type, x }; sc.props.push(p);
      // о вещи уже говорили («А вдруг в подарке…») — она появляется с той реплики рядом с тем, кто сказал; не говорили — герой достаёт её, когда берёт
      const m = !ground && first && sc._said && sc._said[type]; if (m) { p.hidden = true; p._shown = true; sc.steps.splice(m.at, 0, { prop: p.id, state: 'appear', quiet: true, with: true }); if (m.who && sc._x[m.who] != null) p.x = Math.max(.08, Math.min(.92, sc._x[m.who] + (sc._x[m.who] > .5 ? -.1 : .1))); }
      else if (!ground) { p.hidden = true; p._shown = true; } } p._used = true; if (p.decor && !p.big) delete p.decor; return p; }

  // чистка служебных полей, персонажи/локации в серии, автоделение длинных серий
  const out = [];
  for (const e of eps) {
    if (e.scenes.length > 1) e.scenes = e.scenes.filter(x => x.steps.length || x === e.scenes[e.scenes.length - 1]); e.scenes.forEach((x, i) => x.id = 'С' + (i + 1));
    if (!e.scenes.length) continue;
    for (const s of e.scenes) { delete s._cast; delete s._x; delete s._type; delete s._cam; s.props.forEach(p => { delete p._used; delete p._holder; delete p._held; delete p._gone; delete p._shown; delete p._glow; }); delete s._ln; delete s._vanishLn; delete s._lastObj; delete s._vanishHeld; if (!s.props.length) delete s.props; }
    const usedC = new Set(), usedL = new Set(); e.scenes.forEach(s => { usedL.add(s.location); s.cast.forEach(c => usedC.add(c.who)); s.steps.forEach(st => st.who && usedC.add(st.who)); });
    e.characters = [...usedC].filter(id => newChars[id]).map(id => newChars[id]);
    e.locations = [...usedL].filter(id => newLocs[id]).map(id => newLocs[id]);
    e.series = e.series || series;
    e.youtube = { title: `${e.series} — Серия ${e.episode}${e.title ? '. ' + e.title : ''}`, description: `${e.series}. Серия ${e.episode}${e.title ? ': ' + e.title : ''}. Мультфильм для детей.`, tags: ['мультик', 'мультфильм', e.series] };
    out.push(e);
  }
  return { episodes: out, errors, warnings, newChars: Object.values(newChars), newLocs: Object.values(newLocs), unknownNames: [...unknownNames], unknownWords: [...unknownWords].map(([w, s]) => ({ word: w, sentence: s })), unknownObjects: [...unknownObj].map(([w, s]) => ({ word: w, sentence: s })), shown: shown.map(x => ({ type: x.pr.type, scene: x.scene, how: x.how })), narrated };
};

/** Длинную серию делит на части ≈ target секунд по границам сцен. */
S.split = function (ep, lib, target) {
  target = target || 300; if (!global.MK) return [ep];
  const tmpLib = { characters: Object.assign({}, lib.characters), locations: Object.assign({}, lib.locations) };
  for (const c of ep.characters || []) tmpLib.characters[c.id] = { spec: c }; for (const l of ep.locations || []) tmpLib.locations[l.id] = { spec: l };
  const tl = global.MK.compile(Object.assign({}, ep, { titleCard: false, endCard: false }), tmpLib, {});
  const durs = tl.segs.filter(s => s.kind === 'scene').map(s => s.t1 - s.t0);
  const total = durs.reduce((a, b) => a + b, 0);
  if (total <= target * 1.08) return [ep]; // чуть длиннее лимита — не режем
  const n = Math.ceil(total / target), aim = total / n; // делим на равные части, а не «полная + огрызок»
  const parts = []; let cur = [], sum = 0;
  ep.scenes.forEach((s, i) => { if (cur.length && parts.length < n - 1 && sum + durs[i] / 2 > aim) { parts.push(cur); cur = []; sum = 0; } cur.push(s); sum += durs[i]; });
  if (cur.length) parts.push(cur);
  return parts.map((sc, k) => { const e = JSON.parse(JSON.stringify(ep)); e.episode = ep.episode + k; e.title = ep.title ? (parts.length > 1 ? `${ep.title} (часть ${k + 1})` : ep.title) : '';
    e.scenes = sc.map((s, j) => Object.assign(s, { id: 'С' + (j + 1) }));
    const usedC = new Set(), usedL = new Set(); e.scenes.forEach(s => { usedL.add(s.location); s.cast.forEach(c => usedC.add(c.who)); });
    e.characters = (ep.characters || []).filter(c => usedC.has(c.id)); e.locations = (ep.locations || []).filter(l => usedL.has(l.id));
    if (k < parts.length - 1) e.endText = 'Продолжение следует…';
    e.youtube = { title: `${e.series} — Серия ${e.episode}${e.title ? '. ' + e.title : ''}`, description: ep.youtube.description, tags: ep.youtube.tags };
    return e; });
};

S.EXAMPLE = `СЕРИАЛ: Кот Барсик
СЕРИЯ: 2. Клад в лесу
ПЕРСОНАЖ: Колючка — серый медвежонок с зелёным шарфом, голос мальчика

СЦЕНА: двор, утро
Рассказчик: Утром Барсик нашёл у крыльца старую карту.
Барсик разворачивает карту.
Барсик (удивлённо): Ого! Это же карта клада!
Пик входит справа.
Пик: Клад? Бежим искать!
Барсик и Пик прыгают.

СЦЕНА: лес, день
МУЗЫКА: приключения
Барсик входит слева.
Пик входит слева.
Колючка входит справа.
Колючка: Привет! Вы куда так спешите?
Барсик: Мы ищем клад!
Колючка (радостно): Я знаю, где большой дуб. Пойдёмте!
(Колючка идёт вправо)
Рассказчик: Что же найдут друзья под большим дубом?`;

S.OBJECTS = { pumpkin: 'тыква', jack: 'тыква-фонарь (светится)', door: 'дверь', moon: 'луна', ghost: 'привидение', bat: 'летучая мышь', garland: 'гирлянда', tree: 'дерево (берёза, ёлка, яблоня…)', snowman: 'снеговик', fire: 'костёр', tent: 'палатка', castle: 'замок', rainbow: 'радуга (появляется, когда её увидели)', easel: 'мольберт с картиной',
  gift: 'подарок', box: 'коробка', chest: 'сундук', key: 'ключ', star: 'звезда', balloon: 'шарик', ball: 'мяч', book: 'книга', letter: 'письмо', map: 'карта', lantern: 'фонарь', candle: 'свеча', clock: 'часы', coin: 'монета', wand: 'волшебная палочка',
  cake: 'торт', pie: 'пирог', candy: 'конфета', cookie: 'печенье', icecream: 'мороженое', apple: 'яблоко', banana: 'банан', pear: 'груша', watermelon: 'арбуз', carrot: 'морковка', cheese: 'сыр', fish: 'рыба', bone: 'кость', egg: 'яйцо', milk: 'молоко', honey: 'мёд', cup: 'чашка', mushroom: 'гриб', flower: 'цветок', leaf: 'листик', rock: 'камень', stick: 'палка',
  binoculars: 'бинокль', magnifier: 'лупа', compass: 'компас', backpack: 'рюкзак', hat: 'шляпа', glasses: 'очки', ladder: 'лестница', rope: 'верёвка', rod: 'удочка', boat: 'лодка', bike: 'велосипед', scooter: 'самокат',
  telescope: 'телескоп', rocket: 'ракета', crown: 'корона', flag: 'флаг', paints: 'краски с кисточкой', pencil: 'карандаш', pot: 'кастрюля', plate: 'тарелка', spoon: 'ложка', teapot: 'чайник', sandwich: 'бутерброд', pizza: 'пицца',
  strawberry: 'клубника', grapes: 'виноград', cherry: 'вишня', acorn: 'жёлудь', pinecone: 'шишка', snowball: 'снежок', sled: 'санки', bell: 'колокольчик', mirror: 'зеркальце', jar: 'банка варенья', feather: 'пёрышко',
  plane: 'самолётик', pillow: 'подушка', butterfly: 'бабочка', net: 'сачок', flute: 'дудочка',
  umbrella: 'зонтик', bucket: 'ведро', shovel: 'лопатка', basket: 'корзинка', bag: 'сумка', phone: 'телефон', car: 'машинка', teddy: 'мишка-игрушка', drum: 'барабан', guitar: 'гитара', kite: 'воздушный змей' };
/** Раскадровка простыми словами: что программа поняла из текста. */
S.storyboard = function (ep, lib, extraChars, extraLocs) {
  const nm = id => id === 'Р' ? 'Рассказчик' : ((extraChars || []).find(c => c.id === id) || (lib.characters[id] || {}).spec || {}).name || id;
  const PN = { space: 'космос', beach: 'пляж', winter: 'зима', kitchen: 'кухня', playground: 'площадка', street: 'улица', room: 'комната', yard: 'двор', meadow: 'луг', forest: 'лес' }, TN = { day: 'день', evening: 'вечер', night: 'ночь' };
  return (ep.scenes || []).map((sc, i) => { const loc = (extraLocs || []).find(l => l.id === sc.location) || (lib.locations[sc.location] || {}).spec || {};
    const lines = []; for (const st of sc.steps || []) { if (!st.who && st.prop && st.state) { const pr = (sc.props || []).find(p => p.id === st.prop); lines.push(`✨ ${(S.OBJECTS[pr && pr.type] || 'предмет')}: ${({ appear: 'появляется', vanish: 'исчезает', glow: 'светится', paint: 'на картине прибавился рисунок' })[st.state] || st.state}`); continue; }
      if (!st.who) { if (st.music) lines.push('🎵 музыка: ' + st.music); else if (st.sfx) lines.push('🔊 звук: ' + st.sfx); continue; }
      const who = nm(st.who); if (st.who === 'Р') { lines.push(`📖 ${st.say}`); continue; }
      let t = (st.with ? '   ' : '') + who; if (st.do) t += ' — ' + (S.ACTIONS[st.do] || st.do) + (st.to && typeof st.to === 'string' && st.to !== 'camera' ? ' (' + nm(st.to) + ')' : ''); if (st.say) t += ': «' + st.say + '»'; if (!st.do && !st.say && st.emotion) t += ' — ' + st.emotion; if (!st.do && !st.say && !st.emotion) continue; lines.push(t); }
    return { title: `Сцена ${i + 1}: ${loc.variant === 'garden' ? 'сад' : PN[loc.type] || loc.name || ''}${loc.time ? ', ' + TN[loc.time] : ''}${sc.theme ? ' 🎃' : ''}`, lines }; });
};
S.ACTIONS = { read: 'читает / разглядывает', peer: 'смотрит в бинокль', dig: 'копает', knock: 'стучит', push: 'толкает', pull: 'тянет', drink: 'пьёт', paint: 'рисует', write: 'пишет', play: 'играет на инструменте', sniff: 'нюхает', listen: 'прислушивается', cheer: 'ликует', lookaround: 'оглядывается, ищет', shrug: 'пожимает плечами', roll: 'катается по земле', somersault: 'кувыркается', crawl: 'ползёт', sneak: 'крадётся', lie: 'ложится', hug: 'обнимает', scratch: 'чешет голову', yawn: 'зевает', stretch: 'потягивается', sneeze: 'чихает', eat: 'ест', stomp: 'топает', crouch: 'приседает', hide: 'прячется', sing: 'поёт', kick: 'пинает', throw: 'бросает', shout: 'кричит', enter: 'входит', exit: 'уходит', walk: 'идёт', run: 'бежит', jump: 'прыгает', wave: 'машет', dance: 'танцует', spin: 'кружится', nod: 'кивает', shake: 'качает головой',
  clap: 'хлопает', point: 'показывает', think: 'думает', laugh: 'смеётся', scared: 'пугается', cry: 'плачет', bow: 'кланяется', surprise: 'удивляется', fall: 'падает', sit: 'садится',
  sleep: 'засыпает', stand: 'встаёт', turn: 'поворачивается', take: 'берёт', give: 'отдаёт', drop: 'кладёт', none: '— ничего, пусть читает рассказчик' };
global.MKScript = S;
})(typeof window !== 'undefined' ? window : globalThis);
