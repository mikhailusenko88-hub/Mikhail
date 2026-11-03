import os
import torch
torch.set_num_threads(1)

from models.accentor import AccentorNgram
from models.homosolver import HomoSolver

torch.set_grad_enabled(False)


class SileroStress():
    def __init__(self, path_to_data_folder, device='cpu'):
        self.accentor = AccentorNgram(path_to_model=os.path.join(path_to_data_folder, 'accentor/ru/silero_accentor.jit'),
                                      path_to_ngrams=os.path.join(path_to_data_folder, 'accentor/ru/ngrams.gz'),
                                      path_to_exceptions=os.path.join(path_to_data_folder, 'accentor/ru/exceptions.gz'))
        self.homosolver = HomoSolver(model_dir=os.path.join(path_to_data_folder, 'homosolver/'), device=device)

    def __call__(self, sentence,
                 put_stress=True,
                 put_stress_homo=True,
                 put_yo=True,
                 put_yo_homo=True,
                 stress_single_vowel=True,
                 words_to_ignore=None):
        if type(words_to_ignore) not in [type(None), list, set, tuple]:
            raise ValueError(f"`words_to_ignore` should be either None or list/set/tuple")
        return self.accentor(self.homosolver(sentence, put_stress=put_stress_homo, put_yo=put_yo_homo, stress_single_vowel=stress_single_vowel, words_to_ignore=words_to_ignore),
                             put_stress=put_stress, put_yo=put_yo,
                             stress_single_vowel=stress_single_vowel,
                             skip_stress_words=(self.homosolver.homodict if not put_stress_homo else None),
                             skip_yo_words=(self.homosolver.yohomodict if not put_yo_homo else None),
                             words_to_ignore=words_to_ignore)

    def to(self, device):
        self.homosolver.to(device=device)
