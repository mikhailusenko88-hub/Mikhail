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
