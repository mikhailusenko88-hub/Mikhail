import re
import wave
import torch
import warnings
import contextlib
from typing import List, Dict, Optional
import xml.etree.ElementTree as ET


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
                  lang=None):
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
                                             lang=lang)

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
                  lang=None):
        assert sample_rate in [8000, 24000, 48000], f"`sample_rate` should be in [8000, 24000, 48000], current value is {sample_rate}"
        assert speaker in self.speakers, f"`speaker` should be in {', '.join(self.speakers)}"
        assert text is not None or ssml_text is not None, "Both `text` and `ssml_text` are empty"
        assert symbol_durs is None or ssml_text is None, '`ssml_text` and `symbol_durs` are not compatible'
        if return_ts:
            assert hasattr(self.models[0], 'alphabet'), "This model doesn't support `return_ts`"

        if symbol_durs is not None:
            ssml_text = self.transform_durs_to_ssml(text, symbol_durs)

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

                model_kwargs = {'sequence': sequence.to(self.device),
                                'speaker_ids': sp_ids.to(self.device),
                                'sr': sample_rate,
                                'symb_durs': symb_durs,
                                'durs_rate': durs_rate.to(self.device),
                                'pitch_coefs': pitch_coefs.to(self.device),
                                'device': str(self.device)}

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
