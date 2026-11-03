import re
import wave
import torch
import warnings
import contextlib
from typing import List, Dict, Optional
import xml.etree.ElementTree as ET

TYPE2ID = {"st": 0, "wh_q": 1, "general_q": 2, "alternative_q": 3, "tag_q": 4, "exclam": 5}

WH_FORMS = {
    "кто", "кого", "кому", "кем", "ком",
    "что", "чего", "чему", "чем", "чём", "чё", "чо",
    "где", "куда", "откуда", "когда",
    "почему", "зачем", "как", "почём", "отчего", "насколько",
    "сколько", "скольких", "скольким", "сколькими",
    "какой", "какая", "какое", "какие",
    "какого", "каких", "какому", "каким",
    "какими", "каком", "какую",
    "чей", "чья", "чьё", "чье", "чьи",
    "чьего", "чьей", "чьих",
    "чьему", "чьим", "чьими",
    "чьём", "чьем", "чью",
    "который", "которая", "которое", "которые",
    "которого", "которой", "которых",
    "которому", "которым", "которыми",
    "котором", "которую",
    "каков", "какова", "каково", "каковы",
}

LEADING_FILLERS = {
    "а", "ну", "и", "так", "вот", "слышь", "слушай",
    "скажите", "скажи", "пожалуйста",
    "вобще", "вообще", "типа", "короче",
}

TAG_PATTERNS = [
    r"[,\s]+(правда|верно|да)\s*\?$",
    r"[,\s]+(не\s+так\s+ли|не\s+правда\s+ли|разве\s+не\s+так|ведь\s+так)\s*\?$",
    r"[,\s]+ведь\s*\?$",
    r"[,\s]+а\s*\?$",
]
TAG_RE = re.compile("|".join(f"(?:{p})" for p in TAG_PATTERNS), re.IGNORECASE)

QUOTE_OPEN = {'"', '«', chr(8220), chr(8222)}
QUOTE_CLOSE = {'"', '»', chr(8221), chr(8217)}
WORD_RE = re.compile(r"[а-яёa-z]+", re.IGNORECASE)
SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')
STAR_RE = re.compile(r'(\*{1,2})([^*\s]+)\1')
CORE_RE = re.compile(r'[^\W\d_]')
FOCUS_SKIP_CHARS = set('.,!?;:…–')

def _strip_outer_quotes(s):
    s = s.strip()
    while s and s[0] in QUOTE_OPEN:
        s = s[1:].strip()
    while s and s[-1] in QUOTE_CLOSE:
        s = s[:-1].strip()
    return s


def _normalize_for_clf(s):
    s = _strip_outer_quotes(s)
    s = s.replace("+", "")
    s = s.replace("ё", "е").replace("Ё", "Е")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _has_wh_prefix(text):
    words = WORD_RE.findall(text.lower())[:8]
    content = []
    for w in words:
        if w in LEADING_FILLERS:
            continue
        content.append(w)
        if len(content) >= 4:
            break
    return any(w in WH_FORMS for w in content)


def classify_sentence(s):
    s = s.strip()
    if not s:
        return "st"
    s_clean = _strip_outer_quotes(s)
    if not s_clean:
        return "st"
    tail = s_clean
    if tail.endswith("?!") or tail.endswith("?..") or tail.endswith("?..."):
        tail = tail.rstrip(".!")
    if tail.endswith("?"):
        q = _normalize_for_clf(tail)
        if TAG_RE.search(q):
            return "tag_q"
        if _has_wh_prefix(q):
            return "wh_q"
        if re.search(r"\bили\b", q, re.IGNORECASE):
            return "alternative_q"
        return "general_q"
    if s_clean.endswith("!"):
        return "exclam"
    return "st"


def classify_text(text):
    if not text or not text.strip():
        return "st"
    sentences = [s.strip() for s in SENT_SPLIT_RE.split(text.strip()) if s.strip()]
    types = [classify_sentence(s) for s in sentences]
    return "|".join(types)


class TTSModelMultiAcc_v3():
    def __init__(self,
                 packages):
        self.packages = packages
        self.speaker_to_package = {}
        for p_id, pack in enumerate(self.packages):
            self.speaker_to_package.update({sp: p_id for sp in pack.speakers})
        self.speakers = list(self.speaker_to_package.keys())
        self.symbols = self.packages[-1].symbols  # For TTS consumer

    def apply_tts(self, text=None,
                  ssml_text=None,
                  speaker: str = 'ru_zhadyra',
                  sample_rate: int = 48000,
                  put_accent=True,
                  put_stress_homo=True,
                  put_yo=True,
                  put_yo_homo=True,
                  stress_single_vowel=True,
                  voice_path=None,
                  symbol_durs=None,
                  return_ts=False, 
                  lang=None,
                  type_str=None,
                  intensity=3):
        p_id = self.speaker_to_package.get(speaker, None)
        if p_id is None:
            raise ValueError(f"`speaker` should be in {', '.join(self.speakers)}")
        return self.packages[p_id].apply_tts(text=text,
                                             ssml_text=ssml_text,
                                             speaker=speaker,
                                             sample_rate=sample_rate,
                                             put_accent=put_accent,
                                             put_stress_homo=put_stress_homo,
                                             put_yo=put_yo,
                                             put_yo_homo=put_yo_homo,
                                             stress_single_vowel=stress_single_vowel,
                                             voice_path=voice_path,
                                             symbol_durs=symbol_durs,
                                             return_ts=return_ts,
                                             lang=lang,
                                             type_str=type_str,
                                             intensity=intensity)

    def save_wav(self, text=None,
                 ssml_text=None,
                 speaker: str = 'xenia',
                 audio_path: str = '',
                 sample_rate: int = 48000,
                 put_accent=True,
                 put_yo=True):
        p_id = self.speaker_to_package.get(speaker, None)
        if p_id is None:
            raise ValueError(f"`speaker` should be in {', '.join(self.speakers)}")
        return self.packages[p_id].save_wav(text=text,
                                            ssml_text=ssml_text,
                                            speaker=speaker,
                                            audio_path=audio_path,
                                            sample_rate=sample_rate,
                                            put_accent=put_accent,
                                            put_yo=put_yo)

    def to(self, device):
        for package in self.packages:
            package.to(device)
        self.device = device

    def unpack_q_model(self):
        for package in self.packages:
            package.unpack_q_model()


class PartTTSModelMultiAcc_v3():
    def __init__(self,
                 model_paths: List[str],
                 symbols: List[str],
                 speaker_to_ids: List[Dict],
                 symbol_to_id: Dict[str, int],
                 alphabet: str,
                 accentor=None,
                 accentor_public=True,
                 alph2replace=None,
                 sos_token='|',
                 eos_token='~',
                 emb_dim=128,
                 phons=False,
                 phon_sep=' ',
                 **kwargs):
        torch.set_grad_enabled(False)
        assert len(model_paths) == len(speaker_to_ids)
        self.accentor = accentor
        self.accentor_public = accentor_public
        models = []
        for model_path in model_paths:
            models.append(self.init_jit_model(model_path))
        self.models = models
        self.symbols = symbols
        self.phons = phons
        self.sos_token = sos_token
        self.eos_token = eos_token
        self.phon_sep = phon_sep
        if self.phons:
            self.alphabet = alphabet.split(self.phon_sep)
        else:
            self.alphabet = list(alphabet)
        self.device = torch.device('cpu')
        self.speaker_to_ids = speaker_to_ids
        self.speaker_to_model = {}
        for m_id, sp_dict in enumerate(speaker_to_ids):
            self.speaker_to_model.update({sp: m_id for sp in sp_dict.keys()})
        self.speakers = list(self.speaker_to_model.keys())

        self.symbol_to_id = symbol_to_id
        self.id_to_symbol = {v: k for k, v in symbol_to_id.items()}
        self.window = 0.0125

        self.ext_alph = alph2replace

        # ssml tags
        self.strength2time = {'x_weak': 25, 'weak': 75, 'medium': 150, 'strong': 300, 'x-strong': 1000}
        self.rate2value = {'x-slow': 0.5, 'slow': 0.8, 'medium': 1., 'fast': 1.2, 'x-fast': 1.5}
        self.pitch2value = {'x-low': 0.75, 'low': 0.85, 'medium': 1., 'high': 1.15, 'x-high': 1.25, 'robot': 0.}
        # old ssml tags
        # self.pitch2value = {'x-low': 0.75, 'low': 0.9, 'medium': 1., 'high': 1.1, 'x-high': 1.25, 'robot': 0.}
        # self.pitch2value = {'x-low': 0.96, 'low': 0.98, 'medium': 1., 'high': 1.02, 'x-high': 1.04, 'robot': 0.}
        # self.pitch2value = {'x-low': -2, 'low': -1, 'medium': 0, 'high': 1, 'x-high': 2}
        self.emb_dim = emb_dim

        self.random_emb = None
        self.debug = False
        # False = pitch predicted without the emphasis type shift (6-type pitch predictor), durs keep it
        self.emph_pitch = kwargs.get('emph_pitch', True)

        self.valid_tags = {'break': {'strength': list(self.strength2time.keys())},
                           'prosody': {'rate': list(self.rate2value.keys()),
                                       'pitch': list(self.pitch2value.keys())}}
        self.q_model_unpacked = False

        self.wrapped_jit_v = kwargs.get('wrapped_jit_v', None)

    def init_jit_model(self, model_path: str):
        torch.set_grad_enabled(False)
        model = torch.jit.load(model_path, map_location='cpu')
        model.eval()
        return model

    def strip_ssml_tags(self, ssml_text):
        # a tag becomes a space: segments are joined with a space downstream
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', ssml_text)).strip()

    @staticmethod
    def clean_focus_word(word):
        return re.sub(r'[\W\d_]+', '', word.lower().replace('+', ''))

    @staticmethod
    def mark_word(word):
        # stars wrap the word itself, punctuation stays outside to keep sentence splitting intact
        pos = [i for i, ch in enumerate(word) if ch == '+' or CORE_RE.match(ch)]
        a, b = pos[0], pos[-1] + 1
        return f'{word[:a]}*{word[a:b]}*{word[b:]}'

    def restore_focus_marks(self, text, marked_text):
        # re-mark the processed text by word index, markup is taken from the raw one
        marked = [w for w in marked_text.split() if self.clean_focus_word(w)]
        out, i = [], 0
        for w in text.split():
            cw = self.clean_focus_word(w)
            if not cw:
                out.append(w)
                continue
            if i < len(marked) and '*' in marked[i]:
                assert self.clean_focus_word(marked[i]) == cw, f'focus word moved: {marked[i]} vs {w}'
                out.append(self.mark_word(w))
            else:
                out.append(w)
            i += 1
        assert i == len(marked), f'ssml word count mismatch: {i} vs {len(marked)}'
        return ' '.join(out)

    @staticmethod
    def locate_emph_sents(marked_text, emph_idx):
        # sentences holding the emphasis star groups, numbered as in the markup
        out, k = set(), 0
        for si, s in enumerate(SENT_SPLIT_RE.split(marked_text.strip())):
            for _ in STAR_RE.finditer(s):
                if k in emph_idx:
                    out.add(si)
                k += 1
        return out

    def clean_star_text(self, text):
        text = text.replace('^', ' ^')
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('^ ', '^')
        text = re.sub(r'\^+', '^', text).strip()
        if len(text) != 0:
            text = text[:-1].strip() if text[-1] == '^' else text
        return text
    
    def convert_to_orig(self, x, lang):
        x = x.lower()
        letters_in_text = {ch for ch in x if ch.isalpha()}
        if not letters_in_text or letters_in_text <= set(self.alphabet) or not lang in self.ext_alph.keys():
            return x
        
        converted_chars = []
        for char in x:
            converted_chars.append(self.ext_alph[lang].get(char, char))
        return ''.join(converted_chars)

    def prepare_text_input(self, text, lang):
        if not self.phons:
            text = text.lower()
        text = text.replace('—', '–').replace('–', '–').replace('‑', '-')
        if self.ext_alph:
            text = self.convert_to_orig(text, lang)
        if self.phons:
            text = text.replace('$', '')
            text, found_phon_parts = self.replace_phonetic(text)
            text = re.sub(r'[^{}]'.format(self.symbols[3:] + '$'), '', text.lower())
        else:
            text = re.sub(r'[^{}]'.format(self.symbols[3:] + '\^'), '', text)
        sentence = self.clean_star_text(text)
        clean_sentence = re.sub(r'[^а-я\- ]', '', sentence)
        if self.phons:
            for phonetic in found_phon_parts:
                model_phon = phonetic.replace(' ', self.phon_sep)
                sentence = sentence.replace('$', f'{self.phon_sep}{model_phon}{self.phon_sep}', 1)
        
        has_text = len(clean_sentence.replace(' ', '')) > 0
        return sentence, clean_sentence, has_text

    def prepare_tts_model_input(self, text: str,
                                ssml: bool,
                                speaker_ids: list,
                                lang: str):
        text = text.strip()
        text = re.sub(r"\n", lambda m: " " if m.start() > 0 and text[m.start() - 1] in ",;:.!?" else ". ", text)
        if ssml:
            clean_text_list = self.process_ssml(text, lang)
        else:
            clean_text_list = self.process_simple_text(text, lang)

        sentences, clean_sentences, break_lens, prosody_rates, prosody_pitches = map(list, zip(*map(dict.values, clean_text_list)))
        full_text_len = sum([len(s) for s in sentences])
        # full_clean_text_len = sum([len(s) for s in clean_sentences])
        # if full_clean_text_len == 0:
        #     raise ValueError("Text is empty")
        if full_text_len > 1000:
            warnings.warn('Text string is longer than 1000 symbols.')

        speaker_ids = torch.LongTensor(speaker_ids)
        return sentences, clean_sentences, break_lens, prosody_rates, prosody_pitches, speaker_ids

    def to(self, device):
        device = str(device)
        device = 'cuda:0' if  device == 'cuda' else device
        for i in range(len(self.models)):
            self.models[i] = self.models[i].to(device)
        if self.accentor:
            self.accentor.to(device)
        self.device = device

    def get_speakers(self, speaker: str, voice_path=None):
        try:
            if speaker == 'random':
                self.load_random_voice(voice_path)
            model_id = self.speaker_to_model.get(speaker, None)
            if model_id is None:
                raise ValueError(f"`speaker` should be in {', '.join(self.speakers)}")
            speaker_id = self.speaker_to_ids[model_id][speaker]
        except Exception as e:
            raise ValueError(f'Failed to load speaker: {speaker}, error: {e}')
        return [speaker_id], model_id

    def process_simple_text(self, text, lang):
        sentence, clean_sentence, has_text = self.prepare_text_input(text, lang)
        if not has_text:
            raise ValueError
        simple_text_dict = [{'text': sentence,
                             'clean_text': clean_sentence,
                             'break_time': None,
                             'prosody_rate': 1.,
                             'prosody_pitch': 1.}]
        return simple_text_dict

    def process_ssml(self, ssml_text, lang):
        ssml_text = re.sub(r'\s+', ' ', ssml_text).strip()
        try:
            root = ET.fromstring(ssml_text)
        except Exception:
            raise ValueError("Invalid XML format")
        assert root.tag == 'speak', "Invalid SSML format: <speak> tag is essential"
        try:
            ssml_parsed = self.process_ssml_element(root, lang)
            if self.debug:
                print(ssml_parsed)
        except AssertionError as ae:
            raise ae
        except Exception as e:
            raise ValueError(f"Failed to parse SSML: {e}")
        try:
            clean_text_list = self.process_ssml_tag_dict(ssml_parsed, lang)
            if self.debug:
                print(clean_text_list)
        except Exception as e:
            raise ValueError(f"Failed to process SSML: {e}")
        return clean_text_list

    def process_ssml_tag_dict(self, text_break_list, lang):
        proc_text_break_list = []
        for i, text_break_prosody in enumerate(text_break_list):
            tbreak = text_break_prosody['break']
            tprosody = text_break_prosody['prosody']
            text, clean_text, has_text = self.prepare_text_input(text_break_prosody['text'], lang)
            break_time = int(tbreak['time']/12.5) if tbreak['time'] is not None else None
            if has_text or i == 0:
                text = self.check_text_break(text, tbreak)
                proc_text_break_list.append({'text': text,
                                             'clean_text': clean_text,
                                             'break_time': break_time,
                                             'prosody_rate': tprosody['rate'],
                                             'prosody_pitch': tprosody['pitch']})
            elif tbreak['strength'] is not None and len(proc_text_break_list) > 0:
                text = self.check_text_break(proc_text_break_list[-1]['text'], tbreak)
                proc_text_break_list[-1]['text'] = text
                if proc_text_break_list[-1]['break_time'] is None:
                    proc_text_break_list[-1]['break_time'] = break_time
                else:
                    proc_text_break_list[-1]['break_time'] = max(break_time, proc_text_break_list[-1]['break_time'])
        return proc_text_break_list

    def check_text_break(self, text, tbreak):
        if len(text) == 0 or tbreak['strength'] is not None and text[-1] not in '!,-.:;?–…':  # TODO fx dash
            text = text + '.'
        return text

    def process_ssml_element(self, element, lang, def_strength='strong', def_rate=1., def_pitch=1.):
        parsed = []
        last_tag = None
        head_text_parsed = self.process_head_tail_text(element.text, def_rate, def_pitch, lang)
        parsed.extend(head_text_parsed)

        for child in element:
            if child.tag == 'break':
                break_strength, break_ts = self.process_break_attrib(child.attrib)
                if len(parsed) == 0:
                    parsed.append({'text': '.',
                                   'break': {'strength': None,
                                             'time': None},
                                   'prosody': {'rate': def_rate,
                                               'pitch': def_pitch}})
                parsed[-1]['break'] = {'strength': break_strength,
                                       'time': break_ts}

            elif child.tag == 'prosody':
                prosody_rate, prosody_pitch, change_rate, change_pitch = self.process_prosody(child.attrib)
                child_rate = prosody_rate if change_rate else def_rate
                child_pitch = prosody_pitch if change_pitch else def_pitch
                child_parsed = self.process_ssml_element(child, lang, def_strength, child_rate, child_pitch)
                parsed.extend(child_parsed)

            elif child.tag in ['p', 's']:
                break_strength = 'strong' if child.tag == 's' else 'x-strong'
                child_parsed = self.process_ssml_element(child, lang, break_strength, def_rate, def_pitch)
                if len(parsed) > 0 and (parsed[-1]['text'] or last_tag is not None or last_tag != child.tag):
                    if parsed[-1]['break']['strength'] is None:
                        parsed[-1]['break'] = {'strength': break_strength,
                                               'time': self.strength2time[break_strength]}
                    else:
                        last_time = parsed[-1]['break']['time']
                        parsed[-1]['break'] = {'strength': break_strength,
                                               'time': max(last_time, self.strength2time[break_strength])}
                if len(child_parsed) > 0:
                    if child_parsed[-1]['break']['strength'] is None:
                        child_parsed[-1]['break'] = {'strength': break_strength,
                                                     'time': self.strength2time[break_strength]}
                    else:
                        last_time = child_parsed[-1]['break']['time']
                        child_parsed[-1]['break'] = {'strength': break_strength,
                                                     'time': max(last_time, self.strength2time[break_strength])}
                    parsed.extend(child_parsed)
            else:
                warnings.warn(f"Current model doesn't support SSML tag: {child.tag}")

            last_tag = child.tag

            if child.tail:
                tail_text = child.tail
                if tail_text[0] in '.,!?…–;:' and len(parsed) > 0:
                    lost_punct = tail_text[0]
                    parsed[-1]['text'] = parsed[-1]['text'].strip() + lost_punct
                    if len(tail_text) > 1:
                        tail_text = tail_text[1:]
                tail_text_parsed = self.process_head_tail_text(tail_text, def_rate, def_pitch, lang)
                parsed.extend(tail_text_parsed)
        return parsed

    def process_head_tail_text(self, element_text, def_rate, def_pitch, lang):
        text_parsed = []
        if element_text is None:
            return text_parsed
        element_text = self.convert_to_orig(element_text, lang)
        proc_text = re.sub(r'\s+', ' ', element_text).strip()
        text_parsed.append({'text': proc_text,
                            'break': {'strength': None,
                                      'time': None},
                            'prosody': {'rate': def_rate,
                                        'pitch': def_pitch}})
        return text_parsed

    def process_break_attrib(self, attrib):
        for k in attrib.keys():
            if k not in ['strength', 'time']:
                warnings.warn(f"Current model doesn't support SSML <break> attrib: {k}")
        strength = attrib.get('strength', 'medium')
        break_time = attrib.get('time', None)
        if break_time is not None:
            if break_time.endswith('ms'):
                break_ts = int(break_time[:-2])
            elif break_time.endswith('s'):
                break_ts = int(break_time[:-1]) * 1000
            else:
                raise AssertionError("Invalid <break> tag, time should end with 'ms' or 's'")

            if break_ts >= self.strength2time['x-strong']:
                strength = 'x-strong'
            elif break_ts >= self.strength2time['strong']:
                strength = 'strong'
        else:
            if strength in self.strength2time:
                break_ts = self.strength2time[strength]
            else:
                raise AssertionError(f"Invalid <break> tag, strength should be in {', '.join(self.valid_tags['break']['strength'])}")
        if break_ts > 5000:
            warnings.warn('Cuurent model supports pauses less than 5 sec')
            break_ts = 5000
        return strength, break_ts

    def process_prosody(self, attrib):
        for k in attrib.keys():
            if k not in ['rate', 'pitch']:
                warnings.warn(f"Current model doesn't support SSML <prosody> attrib: {k}")
        rate = attrib.get('rate', None)
        pitch = attrib.get('pitch', None)
        assert rate is not None or pitch is not None, "Empty <prosody> tag"
        if rate is not None:
            change_rate = True
            if rate.endswith('%'):
                rate_val = int(rate.replace('%', '')) / 100
            else:
                rate_val = self.rate2value.get(rate, None)
                if rate_val is None:
                    raise AssertionError(f"Invalid <prosody> tag, rate should be in {', '.join(self.valid_tags['prosody']['rate'])}")
        else:
            change_rate = False
            rate_val = 1.
        if pitch is not None:
            change_pitch = True
            if pitch.endswith('%'):
                pitch_val = int(pitch.replace('%', '')[1:]) / 100
                if pitch[0] == '+':
                    pitch_val = 1. + pitch_val
                else:
                    pitch_val = 1. - pitch_val
            else:
                pitch_val = self.pitch2value.get(pitch, None)
                if pitch_val is None:
                    raise AssertionError(f"Invalid <prosody> tag, pitch should be in {', '.join(self.valid_tags['prosody']['pitch'])}")
        else:
            change_pitch = False
            pitch_val = 1.
        return rate_val, pitch_val, change_rate, change_pitch

    def replace_phonetic(self, text):
        text = text.replace('[[', ' [[').replace(']]', ']] ')
        # found_phonetic = re.findall(r"\[\[(['16\:\@IU\\`abdefgijklmnoprstuvxz ]+)\]\]", text)
        found_phonetic = re.findall(r"\[\[(['16\:\"\%\@ADEINOSTUVZ\\`abdefghijklmnoprstuvwxz{ ]+)\]\]", text)
        for phonetic in found_phonetic:
            text = text.replace(f'[[{phonetic}]]', '$')
        return text, found_phonetic

    def transform_durs_to_ssml(self, text, symbol_durs):
        for s, dur in symbol_durs.items():
            text = text.replace(s, f'{s}<break time="{dur}ms"/>')
        text = '<speak>' + text + '</speak>'
        return text

    def get_word_ts(self, clean_sentences, out_durs, out_word_mask):
        clean_text = ' '.join(clean_sentences)
        clean_text = ''.join([self.id_to_symbol.get(s, s) for s in clean_text])
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        clean_words = clean_text.split(' ')

        ts = []
        cur_start = 0
        cur_end = 0
        last_mask = False
        cum_durs = torch.cumsum(out_durs.to('cpu').long().squeeze(), dim=0)
        cum_durs = torch.nn.functional.pad(cum_durs, (1, 0))
        for i, (dur, mask_value) in enumerate(zip(cum_durs, out_word_mask)):
            if last_mask == mask_value:
                continue
            elif last_mask:
                cur_end = dur.item() * self.window
                ts.append([cur_start, cur_end])
                last_mask = mask_value
            else:
                cur_start = dur.item() * self.window
                last_mask = mask_value

        assert len(ts) == len(clean_words)

        results = [[word, st_ts, en_ts] for word, (st_ts, en_ts) in zip(clean_words, ts)]
        return results

    def apply_tts(self, text=None,
                  ssml_text=None,
                  speaker: str = 'xenia',
                  sample_rate: int = 48000,
                  put_accent=True,
                  put_stress_homo=True,
                  put_yo=True,
                  put_yo_homo=True,
                  stress_single_vowel=True,
                  voice_path=None,
                  symbol_durs=None,
                  return_ts=False, 
                  lang=None,
                  type_str=None,
                  intensity=3):
        assert sample_rate in [8000, 24000, 48000], f"`sample_rate` should be in [8000, 24000, 48000], current value is {sample_rate}"
        assert speaker in self.speakers, f"`speaker` should be in {', '.join(self.speakers)}"
        assert text is not None or ssml_text is not None, "Both `text` and `ssml_text` are empty"
        assert symbol_durs is None or ssml_text is None, '`ssml_text` and `symbol_durs` are not compatible'
        if return_ts:
            assert hasattr(self.models[0], 'alphabet'), "This model doesn't support `return_ts`"

        if symbol_durs is not None:
            ssml_text = self.transform_durs_to_ssml(text, symbol_durs)

        if ssml_text is not None and '<intensity' in ssml_text:
            ssml_text, intensity = self.extract_intensity_from_ssml(ssml_text)

        has_emphasis = False
        emph_sents = set()
        emph_idx = set()
        if (text is not None and '**' in text) or (ssml_text is not None and '**' in ssml_text):
            target = text if text is not None else self.strip_ssml_tags(ssml_text)
            matches = re.findall(r'\*\*([^*\s]+)\*\*', target)
            if target.count('**') != 2 * len(matches):
                raise ValueError("Некорректная разметка эмфазы. Ожидается формат **слово**.")
            if len(matches) > 0:
                has_emphasis = True
                # which of the star groups are emphasis; their order survives processing
                emph_idx = {i for i, m in enumerate(STAR_RE.finditer(target))
                            if len(m.group(1)) == 2}
                if text is not None:
                    text = re.sub(r'\*\*([^*\s]+)\*\*', r'*\1*', text)
                if ssml_text is not None:
                    ssml_text = re.sub(r'\*\*([^*\s]+)\*\*', r'*\1*', ssml_text)

        has_focus = False
        original_text_for_focus = None
        ssml_marked_text = None
        if text is not None and '*' in text:
            has_focus = True
            original_text_for_focus = text
            text = text.replace('*', '')
        elif ssml_text is not None and '*' in ssml_text:
            has_focus = True
            ssml_marked_text = self.strip_ssml_tags(ssml_text)
            original_text_for_focus = ssml_marked_text
            ssml_text = ssml_text.replace('*', '')

        ssml = ssml_text is not None
        if ssml:
            input_text = ssml_text
        else:
            input_text = text
        speaker_ids, model_id = self.get_speakers(speaker, voice_path)
        if not lang and self.ext_alph:
            lang = speaker.split('_')[0]
        sentences, clean_sentences, break_lens, prosody_rates, prosody_pitches, sp_ids = self.prepare_tts_model_input(input_text,
                                                                                                                      ssml=ssml,
                                                                                                                      speaker_ids=speaker_ids,
                                                                                                                      lang=lang)
        # focus and types must come from the text the model gets, not from the raw ssml
        if has_focus and ssml_marked_text is not None and not self.phons:
            original_text_for_focus = self.restore_focus_marks(' '.join(sentences), ssml_marked_text)
        if has_emphasis and original_text_for_focus is not None:
            emph_sents = self.locate_emph_sents(original_text_for_focus, emph_idx)

        if not self.q_model_unpacked:
            torch._C._jit_set_profiling_mode(False)
            self.unpack_q_model()
            self.q_model_unpacked = True

        with torch.no_grad():
            try:
                sequence, symb_durs, durs_rate, pitch_coefs = self.merge_batch_model(sentences, 
                                                                                     break_lens, 
                                                                                     prosody_rates, 
                                                                                     prosody_pitches, 
                                                                                     put_accent=put_accent,
                                                                                     put_stress_homo=put_stress_homo,
                                                                                     put_yo=put_yo,
                                                                                     put_yo_homo=put_yo_homo,
                                                                                     stress_single_vowel=stress_single_vowel)

                if type_str is None:
                    if text is not None:
                        type_str = classify_text(text)
                    elif original_text_for_focus is not None:
                        type_str = classify_text(original_text_for_focus.replace('*', ''))
                    else:
                        clean_for_clf = re.sub(r'<[^>]+>', '', ssml_text) if ssml_text else ''
                        type_str = classify_text(clean_for_clf)

                if has_focus:
                    if self.accentor:
                        accented_text = self.accentor(original_text_for_focus.replace('*', ''),
                                                      put_stress=put_accent,
                                                      put_stress_homo=put_stress_homo,
                                                      put_yo=put_yo,
                                                      put_yo_homo=put_yo_homo,
                                                      stress_single_vowel=stress_single_vowel)
                    else:
                        accented_text = original_text_for_focus.replace('*', '')
                    focus_words = []
                    for word in original_text_for_focus.split():
                        if '*' in word:
                            focus_words.append(word.replace('*', '').replace('+', '').lower())
                    accented_with_focus = []
                    for word in accented_text.split():
                        clean_word = word.replace('+', '').lower()
                        if clean_word in focus_words:
                            accented_with_focus.append('*' + word + '*')
                            focus_words.remove(clean_word)
                        else:
                            accented_with_focus.append(word)
                    accented_focus_text = ' '.join(accented_with_focus)
                    _, focus_mask = self.parse_focus_from_text(accented_focus_text, sequence.shape[1], intensity=intensity)
                    focus_mask = focus_mask.to(self.device)
                else:
                    focus_mask = None

                if text is not None:
                    text_for_types = text
                elif original_text_for_focus is not None:
                    text_for_types = original_text_for_focus.replace('*', '')
                else:
                    text_for_types = re.sub(r'<[^>]+>', '', ssml_text) if ssml_text else ''

                if focus_mask is None:
                    focus_mask = torch.zeros(1, sequence.shape[1], dtype=torch.long).to(self.device)
                fm = focus_mask[0]
                fm_list = fm.tolist()

                if self.phons:
                    spans, sent_texts, emph_spans = [], [], set()
                    type_ids = self.build_type_ids_inference(
                        text_for_types, type_str, sequence.shape[1], emph_sents=emph_sents)
                    base_type_ids = type_ids
                else:
                    # types laid over the token sequence itself, same layout as training
                    spans, sent_texts = self.token_sent_spans(sequence[0])
                    types_list = type_str.split('|')
                    if len(types_list) != len(spans):
                        types_list = [classify_sentence(t.replace('+', '')) for t in sent_texts]
                    emph_spans = self.emph_spans_from_focus(spans, fm_list, emph_idx)
                    type_ids = self.build_type_ids_tokens(sequence[0], types_list, emph_spans)
                    base_type_ids = self.build_type_ids_tokens(sequence[0], types_list, set())
                type_ids = type_ids.to(self.device)
                base_type_ids = base_type_ids.to(self.device)

                # a pitch predictor that knows only the base types never sees the emphasis shift
                pitch_type_num = self.models[model_id].pitch_predictor.pitch_pred.type_embedding.weight.shape[0]
                emph_pitch = self.emph_pitch and pitch_type_num >= 2 * len(TYPE2ID)

                if self.debug:
                    print(''.join(self.id_to_symbol[i] for i in sequence[0].tolist()))
                    print(focus_mask[0].tolist())
                    print(type_ids[0].tolist())
                    print('emph_pitch', emph_pitch, 'pitch types', pitch_type_num)

                model_kwargs = {'sequence': sequence.to(self.device),
                                'speaker_ids': sp_ids.to(self.device),
                                'sr': sample_rate,
                                'symb_durs': symb_durs,
                                'durs_rate': durs_rate.to(self.device),
                                'pitch_coefs': pitch_coefs.to(self.device),
                                'device': str(self.device),
                                'type_ids': type_ids,
                                'focus_mask': focus_mask}

                if has_focus and len(spans) > 1:
                    seq_len = sequence.shape[1]
                    seq_dev = sequence.to(self.device)
                    sp_dev = sp_ids.to(self.device)
                    zero_focus = torch.zeros(1, seq_len, dtype=torch.long).to(self.device)
                    orig_mask_bool = torch.zeros(1, seq_len, dtype=torch.bool).to(self.device)

                    # context only: no emphasis type anywhere, focus sentences are replaced whole below
                    full_pitch = self.models[model_id].pitch_predictor(
                        seq_dev, sp_dev, orig_mask_bool, type_ids=base_type_ids, focus_mask=zero_focus)
                    full_durs = self.models[model_id].dur_predictor(
                        seq_dev, sp_dev, orig_mask_bool, type_ids=base_type_ids, focus_mask=zero_focus)
                    full_durs = torch.exp(full_durs) - 1

                    zero1 = torch.zeros_like(fm[:1])
                    for k, (a, b) in enumerate(spans):
                        if not any(fm_list[a:b]):
                            continue
                        tid = TYPE2ID.get(types_list[k], 0)
                        tid_pitch = tid
                        if k in emph_spans:
                            tid += len(TYPE2ID)
                            if emph_pitch:
                                tid_pitch = tid

                        # pitch: sentence alone, the predictor knows its contours as utterance-final
                        short_seq = self.wrap_window(seq_dev[0], a, b, seq_dev[0, :1], seq_dev[0, -1:])
                        short_focus = self.wrap_window(fm, a, b, fm[a:a + 1], zero1)
                        short_type = torch.full_like(short_seq, tid_pitch)
                        short_mask = torch.zeros_like(short_seq, dtype=torch.bool)
                        short_pitch = self.models[model_id].pitch_predictor(
                            short_seq, sp_dev, short_mask, type_ids=short_type, focus_mask=short_focus)
                        full_pitch[0, :, a:b] = short_pitch[0, :, 1:-1]

                        # durs: neighbours stay in the window as context, only the k slice is taken out of it
                        lo = spans[k - 1][0] if k > 0 else a
                        hi = spans[k + 1][1] if k + 1 < len(spans) else b
                        end_k = spans[k + 1][0] if k + 1 < len(spans) else b
                        focus_k = torch.zeros_like(fm)
                        focus_k[a:b] = fm[a:b]
                        type_k = base_type_ids[0].clone()
                        type_k[a:end_k] = tid

                        win_seq = self.wrap_window(seq_dev[0], lo, hi, seq_dev[0, :1], seq_dev[0, -1:])
                        win_focus = self.wrap_window(focus_k, lo, hi, focus_k[lo:lo + 1], zero1)
                        win_type = self.wrap_window(type_k, lo, hi, type_k[lo:lo + 1], type_k[hi - 1:hi])
                        win_mask = torch.zeros_like(win_seq, dtype=torch.bool)
                        win_durs = self.models[model_id].dur_predictor(
                            win_seq, sp_dev, win_mask, type_ids=win_type, focus_mask=win_focus)
                        win_durs = torch.exp(win_durs) - 1

                        # the emphatic dur predictor dumps utterance-initial silence on the first token
                        # of its type region (the jit caps the same on sos): keep the base value there
                        a0 = a + 1 if k in emph_spans else a
                        s = a0 - lo + 1
                        if full_durs.dim() == 2:
                            full_durs[0, a0:b] = win_durs[0, s:s + b - a0]
                        else:
                            full_durs[0, :, a0:b] = win_durs[0, :, s:s + b - a0]

                    if self.debug:
                        toks = [self.id_to_symbol[i] for i in sequence[0].tolist()]
                        print('durs', [(t, int(d)) for t, d in zip(toks, full_durs[0].round().tolist())])

                    model_kwargs_refined = model_kwargs.copy()
                    model_kwargs_refined['gt_pitch'] = full_pitch
                    model_kwargs_refined['gt_durs'] = full_durs
                    out, out_add = self.models[model_id](**model_kwargs_refined)
                else:
                    if has_emphasis and not emph_pitch:
                        model_kwargs['gt_pitch'] = self.models[model_id].pitch_predictor(
                            sequence.to(self.device), sp_ids.to(self.device),
                            torch.zeros(1, sequence.shape[1], dtype=torch.bool).to(self.device),
                            type_ids=base_type_ids, focus_mask=focus_mask)
                    out, out_add = self.models[model_id](**model_kwargs)
            except RuntimeError:
                raise Exception("Model couldn't generate your text, probably it's too long")
            except torch.jit.Error as e:
                if 'AssertionError:' in str(e):
                    short_msg = f'Неизвестный символ в [[ ]]. Допустимые символы: {" ".join(self.phon_symbols)}'
                elif 'RuntimeError' in str(e):
                    short_msg = str(e).split('RuntimeError: ')[-1]
                else:
                    short_msg = str(e)
                raise RuntimeError(short_msg) from None
        if type(out) == tuple:
            out = self.wrapped_jit_v(out, sample_rate)
        audio = out.to('cpu')[0]
        if return_ts:
            out_durs, out_word_mask = out_add
            ts = self.get_word_ts(clean_sentences, out_durs, out_word_mask)
            return audio, ts
        else:
            return audio    
    
    def extract_intensity_from_ssml(self, ssml_text):
        pattern = r'<intensity=(\d+)>'
        intensities = re.findall(pattern, ssml_text)
        cleaned = re.sub(pattern, '', ssml_text)
        cleaned = cleaned.replace('</intensity>', '')
        intensity_val = int(intensities[0]) if intensities else 3
        return cleaned, intensity_val

    def parse_focus_from_text(self, text, seq_len, intensity=3):
        level = int(intensity)
        focus_flags_raw = []
        in_focus = False
        for ch in text:
            if ch == '*':
                in_focus = not in_focus
                continue
            focus_flags_raw.append(in_focus)
        clean_text = text.replace('*', '')
        processed = clean_text.lower().replace('-', ' ')
        values = []
        for i, ch in enumerate(processed):
            if ch in self.symbol_to_id:
                flag = focus_flags_raw[i] if i < len(focus_flags_raw) else False
                values.append(level if flag and ch not in FOCUS_SKIP_CHARS else 0)
        return clean_text, self.place_tokens(values, seq_len)

    def char_sent_ids(self, text):
        # separator whitespace belongs to the preceding sentence
        ids = []
        pos, sent_idx = 0, 0
        for m in SENT_SPLIT_RE.finditer(text):
            ids.extend([sent_idx] * (m.end() - pos))
            pos = m.end()
            sent_idx += 1
        ids.extend([sent_idx] * (len(text) - pos))
        return ids

    def token_sent_spans(self, sequence):
        # sentence spans over the token sequence itself: sos, eos and separator whitespace excluded
        toks = [self.id_to_symbol[i] for i in sequence.tolist()]
        sent_ids = self.char_sent_ids(''.join(toks[1:-1]))
        spans = []
        for k in range(sent_ids[-1] + 1 if sent_ids else 0):
            idx = [i + 1 for i, s in enumerate(sent_ids) if s == k]
            a, b = idx[0], idx[-1] + 1
            while b > a and toks[b - 1] == ' ':
                b -= 1
            spans.append((a, b))
        return spans, [''.join(toks[a:b]) for a, b in spans]

    @staticmethod
    def emph_spans_from_focus(spans, fm_list, emph_idx):
        # emphasis is known per focus word in markup order, map it onto sentences
        span_of = {p: k for k, (a, b) in enumerate(spans) for p in range(a, b)}
        out, g = set(), -1
        for p in range(1, len(fm_list) - 1):
            if fm_list[p] > 0 and (p == 1 or fm_list[p - 1] == 0):
                g += 1
                if g in emph_idx and p in span_of:
                    out.add(span_of[p])
        return out

    @staticmethod
    def wrap_window(x, lo, hi, sos, eos):
        # slice of a full-length vector in the sos/eos layout of place_tokens
        return torch.cat([sos, x[lo:hi], eos]).unsqueeze(0)

    def build_type_ids_tokens(self, sequence, types_list, emph_spans):
        tids = [TYPE2ID.get(t, 0) + (len(TYPE2ID) if k in emph_spans else 0) for k, t in enumerate(types_list)]
        toks = [self.id_to_symbol[i] for i in sequence.tolist()]
        sent_ids = self.char_sent_ids(''.join(toks[1:-1]))
        values = [tids[min(s, len(tids) - 1)] for s in sent_ids]
        return self.place_tokens(values, len(toks), tail=values[-1] if values else 0)

    def place_tokens(self, values, seq_len, tail=0):
        out = torch.zeros(1, seq_len, dtype=torch.long)
        if not values:
            return out
        offset = 1 if self.sos_token != '' else 0
        for i, v in enumerate(values):
            j = i + offset
            if j < seq_len - offset:
                out[0, j] = v
        if offset:
            out[0, 0] = values[0]
            out[0, -1] = tail
        return out

    def build_type_ids_inference(self, text, type_str, seq_len, emph_sents=None):
        # emphasis shifts the type only in the sentences that carry it
        emph_sents = emph_sents or set()
        tids = [TYPE2ID.get(t, 0) + (len(TYPE2ID) if i in emph_sents else 0)
                for i, t in enumerate(type_str.split('|'))]

        sent_ids = self.char_sent_ids(text)
        processed = text.lower().replace('-', ' ')
        values = []
        for i, ch in enumerate(processed):
            if ch in self.symbol_to_id:
                si = sent_ids[i] if i < len(sent_ids) else len(tids) - 1
                values.append(tids[si] if si < len(tids) else tids[-1])

        tail = values[-1] if values else 0
        return self.place_tokens(values, seq_len, tail=tail)

    def merge_batch_model(self,
                          texts: List[str],
                          break_lens: List[Optional[int]],
                          prosody_rates: List[float],
                          prosody_pitches: List[float],
                          put_accent=True,
                          put_stress_homo=True,
                          put_yo=True,
                          put_yo_homo=True,
                          stress_single_vowel=True):

        if self.accentor:
            full_text = self.accentor(' '.join(texts),
                                      put_stress=put_accent,
                                      put_stress_homo=put_stress_homo,
                                      put_yo=put_yo,
                                      put_yo_homo=put_yo_homo,
                                      stress_single_vowel=stress_single_vowel).split(' ') # TODO: add put_yo and put_accent
        else:
            full_text = ' '.join(texts).split(' ')
        texts_len = torch.cumsum(torch.tensor([len(x.split(' ')) for x in texts]), dim=0)
        texts_len = torch.nn.functional.pad(texts_len, (1, 0))
        texts = [' '.join(full_text[a:b]) for a, b in zip(texts_len[:-1], texts_len[1:])]

        split_texts = torch.jit.annotate(List[List[str]], [])
        for t in texts:
            if self.phons:
                split_texts.append(t.split(self.phon_sep))  #
            else:
                split_texts.append(list(t))

        symb_durs = torch.jit.annotate(Dict[int, int], {})
        text_len = -1
        cur_text_len = 0
        final_rates = torch.jit.annotate(List[float], [])
        final_pitches = torch.jit.annotate(List[float], [])

        for i, break_len in enumerate(break_lens):  # Ignore the last one
            if i < len(break_lens) - 1:
                cur_text_len = len(split_texts[i]) + 1  # +space
            else:
                cur_text_len = len(split_texts[i]) + 2  # +space +eos
            if self.phons and i == 0:
                # why? - no sos
                cur_text_len -= 1
            text_len += cur_text_len
            if break_len is not None:
                if i < len(break_lens) - 1:
                    symb_durs[text_len] = break_len
                else:
                    symb_durs[text_len - 1] = break_len

            rate = prosody_rates[i]
            final_rates.extend([rate] * cur_text_len)
            pitch = prosody_pitches[i]
            final_pitches.extend([pitch] * cur_text_len)

        if self.phons:
            if self.phon_sep == ' ':
                full_text = ' <sep> '.join(texts)
            else:
                full_text = f'{self.phon_sep} {self.phon_sep}'.join(texts)
        else:
            full_text = ' '.join(texts)
        text_tensor, _ = self.preprocess_tacotron(full_text)
        text_tensor = text_tensor.unsqueeze(0)
        rate_tensor = torch.tensor(final_rates).unsqueeze(0)
        pitch_tensor = torch.tensor(final_pitches).unsqueeze(0)
        return text_tensor, symb_durs, rate_tensor, pitch_tensor
    
    def preprocess_tacotron(self, text: str):
        if self.phons:
            text = text + self.phon_sep + self.eos_token  # sos_token bug
            split_text = text.split(self.phon_sep)
        else:
            text = self.sos_token + text + self.eos_token
            split_text = list(text)

        text_ohe = torch.jit.annotate(List[int], [])
        word_mask = torch.jit.annotate(List[bool], [])
        for s in split_text:
            text_ohe.append(self.symbol_to_id[s])
            word_mask.append(s in self.alphabet)
        text_tensor = torch.tensor(text_ohe).long()
        return text_tensor, word_mask

    @staticmethod
    def write_wave(path, audio, sample_rate):
        """Writes a .wav file.
        Takes path, PCM audio data, and sample rate.
        """
        with contextlib.closing(wave.open(path, 'wb')) as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio)

    def save_wav(self, text=None,
                 ssml_text=None,
                 speaker: str = 'xenia',
                 audio_path: str = '',
                 sample_rate: int = 48000,
                 put_accent=True,
                 put_yo=True):

        if not audio_path:
            audio_path = 'test.wav'

        audio = self.apply_tts(text=text,
                               ssml_text=ssml_text,
                               speaker=speaker,
                               sample_rate=sample_rate,
                               put_yo=put_yo,
                               put_accent=put_accent)
        self.write_wave(path=audio_path,
                        audio=(audio * 32767).numpy().astype('int16'),
                        sample_rate=sample_rate)
        return audio_path

    def load_random_voice(self, voice_path=None):
        # TODO
        assert len(self.models) == 1
        if voice_path is None:
            random_emb = torch.randn(2, self.emb_dim, requires_grad=False).to(self.device)
            self.random_emb = random_emb
            print("Generated new voice")
        else:
            random_emb = torch.load(voice_path, map_location=self.device)
            print(f"Loaded voice from {voice_path}")
            if self.random_emb is not None and torch.equal(self.random_emb, random_emb):
                return
        mel_weight = random_emb[0]
        dur_weight = random_emb[1, :self.emb_dim//2]
        p_weight = random_emb[1, self.emb_dim//2:]

        self.models[0].tts_model.tacotron.speaker_embedding.weight[-1] = mel_weight
        self.models[0].tts_model.dur_predictor.dur_pred.speaker_embedding.weight[-1] = dur_weight
        self.models[0].tts_model.pitch_predictor.pitch_pred.speaker_embedding.weight[-1] = p_weight

    def save_random_voice(self, voice_path):
        assert self.random_emb is not None, "No generated random voice"
        torch.save(self.random_emb, voice_path)
        print(f"Saved generated voice to {voice_path}")

    def unpack_q_model(self):
        if self.accentor_public:
            quantized_weight = self.accentor.homosolver.model.bert.embeddings.word_embeddings.weight.data.clone()
            restored_weights = self.accentor.homosolver.model.bert.scale * (quantized_weight - self.accentor.homosolver.model.bert.zero_point)
            self.accentor.homosolver.model.bert.embeddings.word_embeddings.weight.data = restored_weights
