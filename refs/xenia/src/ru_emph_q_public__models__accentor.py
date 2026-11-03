import re
import gzip

import torch


def init_jit_model(model_path: str):
    torch.set_grad_enabled(False)
    model = torch.jit.load(model_path, map_location=torch.device('cpu'))
    model.eval()
    return model


def validate_ngrams(model, inputs):
    with torch.no_grad():
        outs = model(inputs)
    return outs


class AccentorNgram():
    def __init__(self, path_to_model, path_to_ngrams,
                 path_to_exceptions=None,
                 stress_token='+'):
        self.model = self._loadmodel(path_to_model, path_to_ngrams)
        self.exceptions = self._getexceptions(path_to_exceptions)
        self.stress_token = stress_token

        self.re_cond = r'[^А-Яа-яёЁ]'
        self.vowels = 'аоуыэиеяёю'

    def __call__(self, sentence, put_stress=True, put_yo=True, stress_single_vowel=True, skip_stress_words=None, skip_yo_words=None, words_to_ignore=None):
        skip_stress_words = skip_stress_words if skip_stress_words is not None else []
        skip_yo_words = skip_yo_words if skip_yo_words is not None else []

        if not (put_stress or put_yo):
            return sentence

        raw_tokens, clean_tokens, prediction_mask = self._tokenize(sentence, words_to_ignore)

        # stress_probs and yo_probs are used as confidence measure;
        # stress_preds is a list of stressed syllable indices (aka vowel indices) for each word.
        # yo_probs is a list of "yoed" syllable indices for each word.
        #   Vowels always counts from 1 and 0 stands for "no 'ё'" ('капуста': 0, 'котёнок': 1)
        stress_probs, stress_preds, yo_probs, yo_preds = self._get_model_preds(clean_tokens)

        accented_sentence = []
        for word_idx, (raw_word, clean_word, need_processing) in enumerate(zip(raw_tokens, clean_tokens, prediction_mask)):
            raw_word_lower = raw_word.lower()

            # Before prediction some "words" can be converted to '' and dropped from batch.
            # For example, sentence 'Я - кот, а ты?' will be tokenized into ['я', '', 'а', 'ты']).
            # But batch for model will contain only ['я', 'а', 'ты']
            # So model outputs shape and len(splitted_sentence) may not be the same.
            # Also this skips punct-only words 
            if not need_processing:
                accented_sentence.append(raw_word)
                continue

            # Check if we should put stresses, 'ё' letters or both.
            # If user has set stress and 'ё' letters, we will not further process word.
            # If user has set only 'ё' letters, we will only assign stress to those letters, without using model predictions.
            #
            # If user hasn't set 'ё' letters, we will accentuate word with model (or exception dict) according to next rules:
            #     - if user has set stress, 'ё' predictions will be adjusted to user's stress.
            #     - if user hasn't set stress, 'ё' predictions will be adjusted to model's stress predictions.
            have_stress = self.stress_token in raw_word_lower
            have_yo = 'ё' in raw_word_lower
            if have_stress is True and have_yo is True:
                accented_sentence.append(raw_word)
                continue
            if have_stress is False and have_yo is True and put_stress:
                if (sum(c in self.vowels for c in raw_word_lower) == 1 and not stress_single_vowel) or clean_word.replace('ё', 'е') in skip_stress_words:
                    accented_sentence.append(raw_word)
                    continue
                # User can set multiple 'ё' letters. We will set stress to each of them.
                user_yo_positions = [i for i, x in enumerate(raw_word_lower) if x == 'ё']
                for i, yo_pos in enumerate(user_yo_positions):
                    raw_word = raw_word[:(yo_pos + i)] + self.stress_token + raw_word[(yo_pos + i):]
                accented_sentence.append(raw_word)
                continue

            # From here we are assuming that user hasn't set 'ё' letters.

            # Handle exceptions
            # General rule:
            # 1. Check if user has already set stress.
            # 2.1 if have_stress and not have_yo, check if exception_dict's yo_position matches with user's stress.
            #     if it does, put 'ё' in word; otherwise, don't put 'ё'.
            # 2.2 if not have_stress and not have_yo, use stress and 'ё' from exception_dict.
            if clean_word in self.exceptions:
                accented_sentence.append(self._accentuate_exception(clean_word=clean_word, raw_word=raw_word, have_stress=have_stress))
                continue

            # Get vowel index (not char position) of stressed letter
            stressed_vowel_ids = [stress_preds[word_idx]]
            passed_stress_trs = stress_probs[word_idx][stressed_vowel_ids[0]] > (0.5 if put_stress else 1)
            # Use model predictions only if there is no user's input for stress
            set_stress = passed_stress_trs and not have_stress and (not clean_word.replace('ё', 'е') in skip_stress_words)

            # Get 'е' letter index (not char position) of a 'е' letter that should be converted to 'ё'.
            yo_vowel_ids = [yo_preds[word_idx]] if yo_preds is not None else [-10]
            passed_yo_trs = yo_preds is not None and yo_probs[word_idx][yo_vowel_ids[0]] > (0.5 if put_yo else 1)
            # Not assigning 'ё' if we don't know about stress
            set_yo = passed_yo_trs and (not clean_word.replace('ё', 'е') in skip_yo_words) # and (passed_stress_trs or have_stress)

            # If user has already set stress, correct stress and yo positions.
            if have_stress:
                stressed_vowel_ids = [sum(map(stressed_part.count, self.vowels))
                                      for stressed_part in raw_word_lower.split(self.stress_token)]

            # Remember that at this moment we can assume that user hasn't put 'ё' letter.
            # Probably should remove this line, but it is nice reminder, imho.
            if have_yo:
                pass

            # Finding char positions for stress and 'ё' letters.
            stress_positions, yo_positions, num_vowels, first_vowel_pos = self._get_positions(raw_word_lower,
                                                                                              stressed_vowel_ids,
                                                                                              yo_vowel_ids)
            # Skip words without vowels
            if num_vowels == 0:
                accented_sentence.append(raw_word)
                continue

            # Restore 'ё' in original word.
            #
            # If yo_position is consistent with any of stress_positions
            # then predicted yo_vowel_idx is bigger than actual number of vowels.
            for yo_pos in yo_positions:
                if yo_pos in stress_positions and set_yo:
                    if raw_word_lower[yo_pos] == 'е':
                        raw_word = raw_word[:yo_pos] + ('ё' if raw_word[yo_pos].islower() else 'Ё') + raw_word[(yo_pos + 1):]

            # Always restore stress in 1-syllable words
            if num_vowels == 1:
                stress_positions = [first_vowel_pos]
                set_stress = stress_single_vowel and put_stress

            # Restore stress in original word
            #
            # If word already have stress, we won't process it again.
            if not have_stress and set_stress:
                for i, stress_pos in enumerate(stress_positions):
                    raw_word = raw_word[:(stress_pos + i)] + self.stress_token + raw_word[(stress_pos + i):]

            accented_sentence.append(raw_word)

        return self._fuse_words_to_sentence(accented_sentence)

    def _get_positions(self, word, stressed_vowel_ids, yo_vowel_ids):
        # For a word 'приветствую' vowel_ids is [2, 4, 9, 10] -- indices of russian vowels
        vowel_ids = [i for i, c in enumerate(word) if c in self.vowels]
        # For a word 'приветствую' ye_ids is [4] -- index of russian 'е' letter
        ye_ids = [i for i, c in enumerate(word) if c == 'е']

        # stressed_vowel_idx is an ordinal number of an stressed vowel (counting all vowels), starting from 0
        # yo_vowel_idx is an ordinal number of russian 'е' letter which should be treated as 'ё' (counting only russian 'е' letters)
        stress_positions = [vowel_ids[idx]
                            for idx in stressed_vowel_ids
                            if (idx < len(vowel_ids)) and (len(vowel_ids) > 0)]
        yo_positions = [ye_ids[idx - 1]
                        for idx in yo_vowel_ids
                        if (idx > 0) and (idx - 1 < len(ye_ids)) and (len(ye_ids) > 0)]

        # We use num_vowels and first_vowel_pos to correctly set stress in 1-syllable words.
        # Also num_vowels is used to prevent accentuating for words without vowels.
        num_vowels = len(vowel_ids)
        first_vowel_pos = vowel_ids[0] if len(vowel_ids) > 0 else -1
        return stress_positions, yo_positions, num_vowels, first_vowel_pos

    def _get_model_preds(self, words):
        stress_logits, yo_logits = validate_ngrams(self.model, words)
        stress_probs = torch.softmax(stress_logits, dim=1)
        stress_preds = torch.argmax(stress_probs, dim=1)
        yo_probs = torch.softmax(yo_logits, dim=1)
        yo_preds = torch.argmax(yo_probs, dim=1)
        return stress_probs, stress_preds, yo_probs, yo_preds

    def _accentuate_exception(self, clean_word, raw_word, have_stress):
        # Handle exceptions
        #
        # General rule:
        # 1. Check if user has already set stress.
        # 2.1 if have_stress, check if exception_dict's yo_position matches with user's stress.
        #     if it does, put 'ё' in word like in exception dict; otherwise, don't put 'ё'.
        # 2.2 if not have_stress, use stress and 'ё' from exception_dict.
        #
        # Ideally, we should properly process exception_words even in case when user has already put 'ё'.
        # But for simplicity and readability, we will not add this functionality here.
        # Cases where user has already put 'ё' are processed before using exception dict, so we don't need 'ё' check here.
        # But we should understand that this function is not reusable outside of a class.
        exc_stress = self.exceptions[clean_word][0]
        exc_yo = self.exceptions[clean_word][1]

        if have_stress:
            # User can put multiple stress tokens
            # exc_yo is a char index; so we want to remove stress tokens, swap 'ё' to 'е', or vice-versa, and restore stress tokens. 
            user_stress_token_positions = [i for i, c in enumerate(raw_word) if c == self.stress_token]
            accentuated_word = raw_word.replace(self.stress_token, '')
            if exc_yo != -1 and (exc_yo + 1 in user_stress_token_positions):
                accentuated_word = accentuated_word[:exc_yo] + ('ё' if accentuated_word[exc_yo].islower() else 'Ё') + accentuated_word[(exc_yo + 1):]
            # Restoring stress tokens if needed.
            for stress_token_pos in user_stress_token_positions:
                accentuated_word = accentuated_word[:stress_token_pos] + self.stress_token + accentuated_word[stress_token_pos:]
        elif not have_stress:
            if exc_yo != -1:
                raw_word = raw_word[:exc_yo] + ('ё' if raw_word[exc_yo].islower() else 'Ё') + raw_word[(exc_yo + 1):]
            accentuated_word = raw_word[:exc_stress] + self.stress_token + raw_word[exc_stress:]
        return accentuated_word

    def _tokenize(self, sentence, words_to_ignore=None):
        words_to_ignore = words_to_ignore if words_to_ignore is not None else []

        tokens = []
        model_inputs = []
        prediction_mask = []

        for word in re.split(r'([\s.,!?;:<>=()/\\]+)', sentence):
            parts = word.split('-')

            if len(parts) == 1:
                cur_tokens = parts
                cur_prediction_mask = [True]
            else:
                cur_tokens = [part + '-' for part in parts[:-1]] + [parts[-1]]
                cur_prediction_mask = [True for p in parts[:-1]] + [parts[-1] != 'то']  # backward compatibility for words like "что-то", "кому-то", etc.

            cur_model_inputs = [re.sub(self.re_cond, '', token.lower()) for token in cur_tokens]
            cur_prediction_mask = [((len(x) > 0) and (x not in words_to_ignore)) & mask for x, mask in zip(cur_model_inputs, cur_prediction_mask)]

            tokens.extend(cur_tokens)
            model_inputs.extend(cur_model_inputs)
            prediction_mask.extend(cur_prediction_mask)
        return tokens, model_inputs, prediction_mask

    def _fuse_words_to_sentence(self, words):
        sentence = ''.join(words).replace('-', '-')
        return sentence

    def _getexceptions(self, path_to_exceptions, mode='txt'):
        if path_to_exceptions is None:
            exception_dict = {}
        try:
            with gzip.open(path_to_exceptions, 'rb') as f:
                model_exceptions = [x.decode().strip() for x in f.readlines()]
            exception_dict = exception_dict = {x.split()[0]: (int(x.split()[1]), int(x.split()[2])) for x in model_exceptions}
        except:
            exception_dict = {}
        return exception_dict

    def _loadmodel(self, path_to_model, path_to_ngrams):
        model = init_jit_model(path_to_model)
        quantized_weight = model.embedding.weight.data.clone()
        restored_weights = model.scale * (quantized_weight - model.zero_point)
        model.embedding.weight.data = restored_weights

        ngram_dict = self._loadngrams(path_to_ngrams)
        model.embedding.ngram_dict = ngram_dict
        return model

    def _loadngrams(self, path_to_ngrams):
        with gzip.open(path_to_ngrams, 'rb') as f:
            ngram_str = f.read().decode()
        return {gram: i for i, gram in enumerate(ngram_str.split())}
