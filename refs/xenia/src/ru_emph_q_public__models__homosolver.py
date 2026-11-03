import os
import re
import json
import torch
from custom_tokenizers.bert_tokenizer import SimpleBertTokenizer


def capitalize_stress(stressed_word):
    stress_idx = stressed_word.index('+')
    return stressed_word[:stress_idx] + stressed_word[(stress_idx+1)].capitalize() + stressed_word[(stress_idx+2):]


def decapitalize_stress(stressed_word):
    for idx, char in enumerate(stressed_word):
        if char.isupper():
            return stressed_word[:idx] + "+" + stressed_word[idx:].lower()


class HomoSolver():
    def __init__(self, model_dir, device='cpu'):
        self.model_dir = model_dir
        self.model = self._load_model()
        self.tokenizer = SimpleBertTokenizer(tokenizer_dir=self.model_dir)
        self.homodict = self._load_homodict()
        self.yohomodict = {w: self.homodict[w] for w in self.homodict if any('ё' in v for v in self.homodict[w])}
        self.pattern = re.compile(r'(?=.*[а-яё])[а-яё+]+', re.IGNORECASE)
        self.vowels='аоуыэиеяёю'
        self.to(device=device)
        # Phrases regex
        compiled_phrases = self._load_phrases_dict(os.path.join(self.model_dir, "phrases.json"))
        self.compiled_phrases = compiled_phrases
        self.compiled_user_phrases = {}   # Placeholder for user-defined phrases
        self.compiled_user_patterns = {}  # Placeholder for user-defined regexes
        # Text-cleaning regex
        self._re_remove_extra = re.compile(r'[^a-zA-Zа-яА-ЯёЁ0-9\s.!?,\-]')
        self._re_spaces = re.compile(r'\s+')
        self._re_double_dash = re.compile(r'-{2,}')
        self._re_repeat_punct = re.compile(r'([.!?])\1+')
        self._re_repeat_comma = re.compile(r',{2,}')
        self._re_space_before_punct = re.compile(r'\s+([.,!?])')
        self._re_punct_add_space = re.compile(r'([.,!?])(?=\S)')
        self.window_size = 300   # char-window around selected homograph word; there is no need to make preds based on entire paragraphs.

    def __call__(self, sentence, put_stress=True, put_yo=True, stress_single_vowel=True, words_to_ignore=None):
        if not (put_stress or put_yo):
            return sentence

        tagged_sentences = self._find_and_tag_homos(sentence, words_to_ignore=words_to_ignore)

        batch_starts = []
        batch_ends = []
        batch_sents = []

        starts = []
        ends = []
        words = []
        regex_preds = []         # List[str]; regex-predicted variant.
        is_neural_preds = []     # List[bool]; True if word will be processed with homosolver, False if it was predicted with regex/phrases.
        for start, end, word, word_lower, raw_mark, raw_clean in tagged_sentences:
            if raw_mark is None:
                continue

            # Try to make regex prediction in priority
            regex_pred = None
            # 1. User-generated regex patterns
            if word_lower in self.compiled_user_patterns:
                regex_pred = self._predict_with_pattern(self.compiled_user_patterns[word_lower], raw_clean)
            # 2. User-generated phrases
            if (regex_pred is None) and (word_lower in self.compiled_user_phrases):
                regex_pred = self._predict_with_pattern(self.compiled_user_phrases[word_lower], raw_mark)
            # 3. Basic "integrated" phrases
            if regex_pred is None and word_lower in self.compiled_phrases:
                regex_pred = self._predict_with_pattern(self.compiled_phrases[word_lower], raw_mark)

            if regex_pred is not None:
                regex_preds.append(regex_pred)
            else:
                if word_lower not in self.homodict:
                    continue
                # If there was no match with regexes - send to homosolver
                bert_ids = torch.tensor(self.tokenizer(raw_mark)).to(device=self.device)
                homo_start = torch.where(bert_ids == self.tokenizer.homo_start_id)[0][0]
                homo_end = torch.where(bert_ids == self.tokenizer.homo_end_id)[0][0]
                # Model inputs
                batch_starts.append(homo_start)
                batch_ends.append(homo_end)
                batch_sents.append(bert_ids)

            # Indices of a words in a sentence to change
            starts.append(start)
            ends.append(end)
            words.append(word)
            is_neural_preds.append(regex_pred is None)

        # No homos found
        if len(words) == 0:
            return sentence

        # Make model preds
        if len(batch_sents) > 0: 
            batch_sents = torch.nn.utils.rnn.pad_sequence(batch_sents, batch_first=True, padding_value=self.tokenizer.pad_token_id)
            batch_starts = torch.LongTensor(batch_starts)
            batch_ends = torch.LongTensor(batch_ends)
            with torch.no_grad():
                logits = self.model(batch_sents, batch_starts, batch_ends)
                homosolver_preds = torch.round(torch.sigmoid(logits))

        # Collect word preds 
        regex_idx = 0
        homosolver_idx = 0
        word_preds = []
        for word, is_neural in zip(words, is_neural_preds):
            if is_neural:
                pred = homosolver_preds[homosolver_idx]
                pred = pred.int().item()
                word_pred = sorted(self.homodict[word.lower()])[pred]
                homosolver_idx += 1
            else:
                word_pred = regex_preds[regex_idx]
                regex_idx += 1
            word_preds.append(word_pred)

        # Transfer word preds to sentence
        stressed_sent = sentence
        offset = 0
        for start, end, word, word_pred in zip(starts, ends, words, word_preds):
            start = start + offset
            end = end + offset
            word_pred = word_pred if put_yo else word_pred.replace('ё', 'е')
            n_vowels = sum(c.lower() in self.vowels for c in word_pred)
            stress_idx = word_pred.index('+')
            word_pred = word_pred.replace('+', '')
            word_pred = ''.join([c2.lower() if c1.islower() else c2.upper() for c1, c2 in zip(word, word_pred)])
            if (n_vowels > 1 or stress_single_vowel) and (put_stress):
                word_pred = word_pred[:stress_idx] + '+' + word_pred[stress_idx:]
                offset += 1
            stressed_sent = stressed_sent[:start] + word_pred + stressed_sent[end:]

        return stressed_sent

    def _predict_with_pattern(self, pattern, text):
        match = pattern.search(text)
        if match:
            for group_name, matched_text in match.groupdict().items():
                if matched_text is not None:
                    return decapitalize_stress(group_name)
        return None

    def _find_and_tag_homos(self, sentence, words_to_ignore=None):
        words_to_ignore = words_to_ignore if words_to_ignore is not None else []
        tagged_sentences = []
        for match in self.pattern.finditer(sentence):   # any cyrillic char sequence 
            start, end = match.span()
            word = match.group()
            word_lower = word.lower()
            is_homograph = ((word_lower in self.homodict) or
                            (word_lower in self.compiled_phrases) or
                            (word_lower in self.compiled_user_phrases) or
                            (word_lower in self.compiled_user_patterns)) and (word_lower not in words_to_ignore)
            if is_homograph:
                raw_start_text = self._clean_text(sentence[:start], is_start=True)[(-self.window_size//2):]
                raw_end_text = self._clean_text(sentence[end:], is_start=False)[:(self.window_size//2)]
                raw_mark =  (raw_start_text + ' [HOMO] ' + word_lower + ' [/HOMO] ' + raw_end_text).strip()
                raw_clean = (raw_start_text + ' ' + word_lower + ' ' + raw_end_text).strip()
            else:
                raw_mark = None
                raw_clean = None
            tagged_sentences.append((start, end, word, word_lower, raw_mark, raw_clean))
        return tagged_sentences

    def _clean_text(self, text, is_start=True) -> str:
        if not text:
            return ""
        text = self._re_remove_extra.sub('', text)
        text = self._re_spaces.sub(' ', text)
        text = self._re_double_dash.sub(' - ', text)
        text = self._re_repeat_punct.sub(r'\1', text)
        text = self._re_repeat_comma.sub(',', text)
        text = self._re_space_before_punct.sub(r'\1', text)
        text = self._re_repeat_punct.sub(r'\1', text)
        text = self._re_repeat_comma.sub(',', text)
        text = self._re_punct_add_space.sub(r'\1 ', text)
        text = self._re_spaces.sub(' ', text).strip()
        if is_start:
            text = text.lstrip(' .,!?-')
            if text:
                text = text[0].upper() + text[1:].lower()
        else:
            if text:
                text = text[0] + text[1:].lower()
            if text and text[-1] not in '.!?':
                text += '.'
        return text

    def _load_model(self):
        model_path = os.path.join(self.model_dir, "model_emb_q.jit")
        model = torch.jit.load(model_path)
        model.eval()
        return model

    def _load_homodict(self):
        homodict_path = os.path.join(self.model_dir, "homodict.json")
        with open(homodict_path, 'r') as f:
            homodict = json.load(f)
        return homodict

    def _load_phrases_dict(self, phrases_dict_path):
        with open(phrases_dict_path, 'r', encoding='utf-8') as f:
            phrases_dict = json.load(f)
        compiled_phrases = {}
        for word, phrases_to_variants in phrases_dict.items():
            # Or we could've saved phrases.json in this format, but whatever
            variant_to_phrases = {}
            for phrase, variant in phrases_to_variants.items():
                if variant not in variant_to_phrases:
                    variant_to_phrases[variant] = []
                variant_to_phrases[variant].append(phrase)
            # Create single regex pattern for each variant
            variant_patterns = []
            for variant, phrases in variant_to_phrases.items():
                # Regex can't have "+" sign in group names, so we must convert "з+амок" to "зАмок"
                group_name = capitalize_stress(variant)
                # Better to sort phrases by length, because of "embedded" occurences.
                # We must match longer phrases first, because they carry more context.
                sorted_phrases = sorted(phrases, key=len, reverse=True)
                sorted_phrases = [p.replace(word, f'[HOMO] {word} [/HOMO]').strip() for p in sorted_phrases]
                joined_phrases = '|'.join(map(re.escape, sorted_phrases))
                variant_patterns.append(rf'(?P<{group_name}>(?<![а-яА-ЯёЁ\-])(?:{joined_phrases})(?![а-яА-ЯёЁ\-]))')
            # Combine variant patterns to single pattern for entire homograph
            homo_pattern_string = "|".join(variant_patterns)
            compiled_phrases[word] = re.compile(homo_pattern_string, re.IGNORECASE)
        return compiled_phrases

    def load_phrases_dict(self, phrases_dict_path):
        """
        Loads user-defined phrases dict from a JSON file.

        Expected JSON format:
        {
            "замок": {
                "старинный замок": "з+амок",
                "замок на холме": "з+амок",
                "закрыто на замок": "зам+ок",
            }
        }

        Args:
            phrases_dict_path (str): Path to the JSON file containing user phrases.
        """
        if not os.path.exists(phrases_dict_path):
            raise FileNotFoundError(f"There is no regex dict at: {phrases_dict_path}")
        compiled_phrases = self._load_phrases_dict(phrases_dict_path)
        self.compiled_user_phrases = compiled_phrases
        print(f'Loaded new phrases dict for {len(self.compiled_user_phrases)} words')

    def load_regex_dict(self, regex_dict_path):
        """
        Loads user-defined regular expressions from a JSON file.

        The execution priority of the patterns matches the exact order provided by the user in the JSON array.

        Expected JSON format:
        {
            "замок": {
                "з+амок": [
                    "regex1",
                    "regex2"
                ],
                "зам+ок": [
                    "regex3"
                ]
            }
        }

        Args:
            regex_dict_path (str): Path to the JSON file containing user regex rules.
        """
        if not os.path.exists(regex_dict_path):
            raise FileNotFoundError(f"There is no regex dict at: {regex_dict_path}")
        with open(regex_dict_path, 'r', encoding='utf-8') as f:
            regex_dict = json.load(f)
        for word, variant_to_regexes in regex_dict.items():
            variant_patterns = []
            # Create single regex pattern for each variant
            for variant, regexes in variant_to_regexes.items():
                group_name = capitalize_stress(variant)
                processed_rules = [f"(?:{r})" for r in regexes]
                joined_regexes = "|".join(processed_rules)
                variant_patterns.append(rf'(?P<{group_name}>(?<![а-яА-ЯёЁ])(?:{joined_regexes})(?![а-яА-ЯёЁ]))')
            # Combine variant patterns to single pattern for entire homograph
            homo_pattern_string = "|".join(variant_patterns)
            try:
                compiled_regex = re.compile(homo_pattern_string, re.IGNORECASE | re.UNICODE)
                self.compiled_user_patterns[word] = compiled_regex
                print(f'Loaded new regex dict for {len(self.compiled_user_patterns)} words')
            except re.error as e:
                raise ValueError(f"Error during regex compilation for word '{word}': {e}")

    def to(self, device):
        if device != 'cpu':
            devices = [f'cuda:{i}' for i in range(torch.cuda.device_count())]
            if device not in devices:
                raise ValueError(f'Wrong device identifier! Should be in {devices} or "cpu"')
        self.device = torch.device(device)
        self.model.to(device=self.device)
