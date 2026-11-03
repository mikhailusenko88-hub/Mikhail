class MultiTTSModel(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  energy_predictor : NoneType
  punkt_symbols : List[int]
  point_id : int
  comma_ids : List[int]
  mean_std_coef : List[float]
  sil_value : float
  tacotron : __torch__.jit_forward_model.JitMultiForward
  vocoder : __torch__.vocoder.hifigan.jit_vocoder.JitV4
  dur_predictor : __torch__.jit_forward_model.JitDurPredictor
  pitch_predictor : __torch__.jit_forward_model.JitPitchPredictorIC
  def forward(self: __torch__.silero_vocoder.jit_model.MultiTTSModel,
    sequence: Tensor,
    speaker_ids: Tensor,
    sr: int=48000,
    symb_durs: Optional[Dict[int, int]]=None,
    durs_rate: Optional[Tensor]=None,
    pitch_coefs: Optional[Tensor]=None,
    gt_durs: Optional[Tensor]=None,
    gt_pitch: Optional[Tensor]=None,
    device: str="cpu",
    accent_word: int=-1,
    question: bool=False,
    type_ids: Optional[Tensor]=None,
    focus_mask: Optional[Tensor]=None,
    emphasis: Optional[Tensor]=None) -> Tuple[Tensor, Tensor]:
    _0 = __torch__.tacotron2.fastpitch_layers.make_token_len_mask
    _1 = _0(torch.transpose(sequence, 0, 1), )
    orig_mask = torch.to(_1, torch.device(device))
    if torch.__isnot__(type_ids, None):
      type_ids1 = unchecked_cast(Tensor, type_ids)
      _2 = torch.select(torch.select(type_ids1, 0, 0), 0, 0)
      emph, type_ids0 = torch.ge(int(_2), 6), type_ids1
    else:
      emph, type_ids0 = False, type_ids
    if emph:
      sos_cap = 20
    else:
      sos_cap = 5
    if torch.__isnot__(symb_durs, None):
      symb_durs1 = unchecked_cast(Dict[int, int], symb_durs)
      _4 = torch.gt(torch.len(symb_durs1), 0)
      _3, symb_durs0 = _4, symb_durs1
    else:
      _3, symb_durs0 = False, symb_durs
    if _3:
      symb_durs3 = unchecked_cast(Dict[int, int], symb_durs0)
      support_ids0 = (self).get_support_ids(sequence, symb_durs3, )
      support_ids, symb_durs2 = support_ids0, symb_durs3
    else:
      support_ids, symb_durs2 = None, symb_durs0
    if torch.__isnot__(support_ids, None):
      support_ids2 = unchecked_cast(List[int], support_ids)
      support_sequence0 = (self).replace_comma(sequence, support_ids2, )
      support_ids1, support_sequence = support_ids2, support_sequence0
    else:
      support_ids1, support_sequence = support_ids, sequence
    if torch.__is__(gt_durs, None):
      if torch.__isnot__(symb_durs2, None):
        symb_durs6 = unchecked_cast(Dict[int, int], symb_durs2)
        _6 = torch.gt(torch.len(symb_durs6), 0)
        _5, symb_durs5 = _6, symb_durs6
      else:
        _5, symb_durs5 = False, symb_durs2
      if _5:
        symb_durs8 = unchecked_cast(Dict[int, int], symb_durs5)
        _8 = torch.__isnot__(support_ids1, None)
        _7, symb_durs7 = _8, symb_durs8
      else:
        _7, symb_durs7 = False, symb_durs5
      if _7:
        symb_durs10 = unchecked_cast(Dict[int, int], symb_durs7)
        support_ids4 = unchecked_cast(List[int], support_ids1)
        _9 = torch.eq((torch.size(sequence))[0], 1)
        if _9:
          pass
        else:
          ops.prim.RaiseException("AssertionError: ")
        support_sequence1 = torch.to(support_sequence, torch.device(device))
        dur_predictor = self.dur_predictor
        _10 = torch.cat([sequence, support_sequence1])
        _11 = torch.cat([orig_mask, orig_mask])
        pred_log_dur0 = (dur_predictor).forward(_10, speaker_ids, _11, 1., None, type_ids0, focus_mask, emphasis, )
        pred_log_dur, symb_durs9, support_ids3 = pred_log_dur0, symb_durs10, support_ids4
      else:
        dur_predictor0 = self.dur_predictor
        pred_log_dur1 = (dur_predictor0).forward(sequence, speaker_ids, orig_mask, 1., None, type_ids0, focus_mask, emphasis, )
        pred_log_dur, symb_durs9, support_ids3 = pred_log_dur1, symb_durs7, support_ids1
      pred_log_dur2 = torch.sub(torch.exp(pred_log_dur), 1)
      _12 = torch.lt(pred_log_dur2, 0.)
      _13 = torch.tensor(0., dtype=ops.prim.dtype(pred_log_dur2), device=ops.prim.device(pred_log_dur2))
      _14 = annotate(List[Optional[Tensor]], [_12])
      _15 = torch.index_put_(pred_log_dur2, _14, _13)
      dur_hat0 = (self).cap_sos(torch.round(pred_log_dur2), sos_cap, )
      if torch.__isnot__(symb_durs9, None):
        symb_durs12 = unchecked_cast(Dict[int, int], symb_durs9)
        _17 = torch.gt(torch.len(symb_durs12), 0)
        _16, symb_durs11 = _17, symb_durs12
      else:
        _16, symb_durs11 = False, symb_durs9
      if _16:
        symb_durs14 = unchecked_cast(Dict[int, int], symb_durs11)
        _18 = torch.__isnot__(support_ids3, None)
        if _18:
          support_ids5 = unchecked_cast(List[int], support_ids3)
          sdurs = annotate(List[int], [])
          for _19 in range(torch.len(support_ids5)):
            sid = support_ids5[_19]
            _20 = torch.append(sdurs, symb_durs14[sid])
          pause_len = ops.prim.max(sdurs)
          dur_hat3 = (self).process_pauses(pred_log_dur2, support_ids5, pause_len, )
          dur_hat2 = dur_hat3
        else:
          dur_hat2 = dur_hat0
        dur_hat1, symb_durs13 = dur_hat2, symb_durs14
      else:
        dur_hat1, symb_durs13 = dur_hat0, symb_durs11
      dur_hat, symb_durs4 = dur_hat1, symb_durs13
    else:
      gt_durs0 = unchecked_cast(Tensor, gt_durs)
      _21 = torch.lt(gt_durs0, 0.)
      _22 = torch.tensor(0., dtype=ops.prim.dtype(gt_durs0), device=ops.prim.device(gt_durs0))
      _23 = annotate(List[Optional[Tensor]], [_21])
      _24 = torch.index_put_(gt_durs0, _23, _22)
      dur_hat4 = (self).cap_sos(torch.round(gt_durs0), sos_cap, )
      dur_hat, symb_durs4 = dur_hat4, symb_durs2
    if torch.__isnot__(durs_rate, None):
      durs_rate0 = unchecked_cast(Tensor, durs_rate)
      _25 = torch.eq(torch.size(durs_rate0), torch.size(dur_hat))
      if _25:
        pass
      else:
        ops.prim.RaiseException("AssertionError: ")
      dur_hat6 = torch.round(torch.div(dur_hat, durs_rate0))
      dur_hat5 = dur_hat6
    else:
      dur_hat5 = dur_hat
    if torch.__isnot__(symb_durs4, None):
      symb_durs16 = unchecked_cast(Dict[int, int], symb_durs4)
      _27 = torch.gt(torch.len(symb_durs16), 0)
      _26, symb_durs15 = _27, symb_durs16
    else:
      _26, symb_durs15 = False, symb_durs4
    if _26:
      symb_durs18 = unchecked_cast(Dict[int, int], symb_durs15)
      _28 = torch.items(symb_durs18)
      for _29 in range(torch.len(_28)):
        sid0, sdur, = _28[_29]
        _30 = torch.select(torch.select(dur_hat5, 0, 0), 0, sid0)
        _31 = torch.tensor(sdur, dtype=ops.prim.dtype(_30), device=ops.prim.device(_30))
        _32 = torch.copy_(_30, _31)
      symb_durs17 : Optional[Dict[int, int]] = symb_durs18
    else:
      symb_durs17 = symb_durs15
    dur_hat7 = (self).fx_durs(dur_hat5, sos_cap, emph, )
    if torch.__is__(gt_pitch, None):
      _33 = torch.__isnot__(pitch_coefs, None)
      if _33:
        pitch_coefs0 = unchecked_cast(Tensor, pitch_coefs)
        pitch_coefs_exp0 = torch.select(pitch_coefs0, 0, 0)
        pitch_coefs_exp : Optional[Tensor] = pitch_coefs_exp0
      else:
        pitch_coefs_exp = None
      pitch_predictor = self.pitch_predictor
      pitch_hat0 = (pitch_predictor).forward(sequence, speaker_ids, orig_mask, type_ids0, focus_mask, emphasis, )
      _34 = torch.__isnot__(pitch_coefs_exp, None)
      if _34:
        pitch_coefs_exp1 = unchecked_cast(Tensor, pitch_coefs_exp)
        _35 = torch.unsqueeze(pitch_coefs_exp1, 0)
        pitch_hat2 = (self).update_pitch_coef(pitch_hat0, _35, speaker_ids, )
        pitch_hat1 = pitch_hat2
      else:
        pitch_hat1 = pitch_hat0
      pitch_hat = pitch_hat1
    else:
      pitch_hat = unchecked_cast(Tensor, gt_pitch)
    durs_cum = torch.cumsum(torch.pad(dur_hat7, [1, 0]), 0)
    _36 = torch.len(dur_hat7)
    _37 = torch.slice(durs_cum, 0, None, -1)
    _38 = torch.slice(durs_cum, 0, 1)
    _39 = [_36, torch.len(_37), torch.len(_38), torch.len(sequence)]
    for idx in range(ops.prim.min(_39)):
      a = torch.select(_37, 0, idx)
      b = torch.select(_38, 0, idx)
      char_id = torch.select(sequence, 0, idx)
      punkt_symbols = self.punkt_symbols
      _40 = torch.__contains__(punkt_symbols, annotate(int, char_id))
      if _40:
        _41 = torch.slice(pitch_hat, 0, annotate(int, a), annotate(int, b))
        _42 = torch.tensor(0, dtype=ops.prim.dtype(_41), device=ops.prim.device(_41))
        _43 = torch.copy_(_41, _42)
      else:
        pass
    tacotron = self.tacotron
    mel_outputs = (tacotron).forward(sequence, speaker_ids, orig_mask, dur_hat7, pitch_hat, None, )
    if torch.__isnot__(symb_durs17, None):
      symb_durs20 = unchecked_cast(Dict[int, int], symb_durs17)
      _45 = torch.gt(torch.len(symb_durs20), 0)
      _44, symb_durs19 = _45, symb_durs20
    else:
      _44, symb_durs19 = False, symb_durs17
    if _44:
      symb_durs21 = unchecked_cast(Dict[int, int], symb_durs19)
      mel_outputs1 = (self).fx_pauses(mel_outputs, dur_hat7, symb_durs21, )
      mel_outputs0 = mel_outputs1
    else:
      mel_outputs0 = mel_outputs
    vocoder = self.vocoder
    audio = (vocoder).forward(mel_outputs0, sr, 0., True, )
    return (audio, dur_hat7)
  def get_support_ids(self: __torch__.silero_vocoder.jit_model.MultiTTSModel,
    sequence: Tensor,
    symb_durs: Dict[int, int]) -> Optional[List[int]]:
    temp_ids = annotate(List[int], [])
    _46 = torch.keys(symb_durs)
    for _47 in range(torch.len(_46)):
      sid = _46[_47]
      _48 = torch.select(torch.select(sequence, 0, 0), 0, sid)
      comma_ids = self.comma_ids
      _49 = torch.__contains__(comma_ids, annotate(int, _48))
      if _49:
        _50 = torch.append(temp_ids, sid)
      else:
        pass
    if torch.gt(torch.len(temp_ids), 0):
      support_ids : Optional[List[int]] = temp_ids
    else:
      support_ids = None
    return support_ids
  def replace_comma(self: __torch__.silero_vocoder.jit_model.MultiTTSModel,
    sequence: Tensor,
    support_ids: List[int]) -> Tensor:
    support_sequence = torch.clone(sequence)
    point_id = self.point_id
    _51 = torch.tensor(support_ids, dtype=4)
    _52 = torch.slice(support_sequence)
    _53 = torch.tensor(point_id, dtype=ops.prim.dtype(_52), device=ops.prim.device(_52))
    _54 = annotate(List[Optional[Tensor]], [None, _51])
    _55 = torch.index_put_(_52, _54, _53)
    return support_sequence
  def cap_sos(self: __torch__.silero_vocoder.jit_model.MultiTTSModel,
    dur_hat: Tensor,
    sos_cap: int) -> Tensor:
    _56 = torch.select(torch.select(dur_hat, 0, 0), 0, 0)
    if bool(torch.gt(_56, sos_cap)):
      _57 = torch.select(torch.select(dur_hat, 0, 0), 0, 0)
      _58 = torch.tensor(sos_cap, dtype=ops.prim.dtype(_57), device=ops.prim.device(_57))
      _59 = torch.copy_(_57, _58)
    else:
      pass
    return dur_hat
  def process_pauses(self: __torch__.silero_vocoder.jit_model.MultiTTSModel,
    comma_point_durs: Tensor,
    comma_ids: List[int],
    pause_len: int) -> Tensor:
    _60 = torch.tensor(comma_ids, dtype=4)
    _61 = torch.slice(comma_point_durs)
    _62 = annotate(List[Optional[Tensor]], [None, _60])
    _63, _64 = torch.min(torch.index(_61, _62), 1)
    comma_len = torch.item(torch.select(_63, 0, 0))
    point_len = torch.item(torch.select(_63, 0, 1))
    if torch.gt(comma_len, point_len):
      _65 = True
    else:
      _65 = torch.le(pause_len, comma_len)
    if _65:
      final_dur0 = torch.select(comma_point_durs, 0, 0)
      final_dur = final_dur0
    else:
      if torch.ge(pause_len, point_len):
        final_dur2 = torch.select(comma_point_durs, 0, 1)
        final_dur1 = final_dur2
      else:
        point_cf = torch.div(torch.sub(pause_len, comma_len), torch.sub(point_len, comma_len))
        comma_cf = torch.div(torch.sub(point_len, pause_len), torch.sub(point_len, comma_len))
        _66 = torch.select(comma_point_durs, 0, 0)
        _67 = torch.mul(_66, comma_cf)
        _68 = torch.select(comma_point_durs, 0, 1)
        final_dur3 = torch.add(_67, torch.mul(_68, point_cf))
        final_dur1 = final_dur3
      final_dur = final_dur1
    final_dur4 = torch.unsqueeze(final_dur, 0)
    return torch.round(final_dur4)
  def fx_durs(self: __torch__.silero_vocoder.jit_model.MultiTTSModel,
    dur_hat: Tensor,
    sos_cap: int,
    emph: bool) -> Tensor:
    dur_hat8 = (self).cap_sos(dur_hat, sos_cap, )
    if emph:
      _69 = torch.sub((torch.size(dur_hat8))[1], 1)
      n = ops.prim.min(5, _69)
      _70 = torch.slice(torch.select(dur_hat8, 0, 0), 0, 1, n)
      _71 = torch.clamp(_70, 5.)
      _72 = torch.slice(torch.select(dur_hat8, 0, 0), 0, 1, n)
      _73 = torch.copy_(_72, _71)
    else:
      pass
    _74 = torch.select(torch.select(dur_hat8, 0, 0), 0, -1)
    if bool(torch.gt(_74, 7)):
      _75 = torch.select(torch.select(dur_hat8, 0, 0), 0, -1)
      _76 = torch.tensor(7, dtype=ops.prim.dtype(_75), device=ops.prim.device(_75))
      _77 = torch.copy_(_75, _76)
    else:
      pass
    _78 = torch.select(torch.select(dur_hat8, 0, 0), 0, -2)
    _79 = torch.tensor(13, dtype=ops.prim.dtype(_78), device=ops.prim.device(_78))
    _80 = torch.copy_(_78, _79)
    _81 = torch.select(torch.select(dur_hat8, 0, 0), 0, -3)
    if bool(torch.gt(_81, 13)):
      _82 = torch.select(torch.select(dur_hat8, 0, 0), 0, -3)
      _83 = torch.tensor(13, dtype=ops.prim.dtype(_82), device=ops.prim.device(_82))
      _84 = torch.copy_(_82, _83)
    else:
      pass
    return dur_hat8
  def update_pitch_coef(self: __torch__.silero_vocoder.jit_model.MultiTTSModel,
    norm_pitch: Tensor,
    pitch_coef: Tensor,
    speaker_ids: Tensor) -> Tensor:
    _85 = torch.lt(ops.prim.abs(norm_pitch), 0.001)
    _86 = torch.tensor(0., dtype=ops.prim.dtype(norm_pitch), device=ops.prim.device(norm_pitch))
    _87 = annotate(List[Optional[Tensor]], [_85])
    _88 = torch.index_put_(norm_pitch, _87, _86)
    norm_pitch_coefd = torch.mul(norm_pitch, pitch_coef)
    _89 = torch.eq(torch.select(pitch_coef, 0, 0), 0)
    _90 = (torch.where(_89))[0]
    _91 = torch.slice(pitch_coef)
    _92 = torch.tensor(1., dtype=ops.prim.dtype(_91), device=ops.prim.device(_91))
    _93 = annotate(List[Optional[Tensor]], [None, _90])
    _94 = torch.index_put_(_91, _93, _92)
    mean_std_coef = self.mean_std_coef
    _95 = mean_std_coef[int(torch.item(speaker_ids))]
    mean_std_shift = torch.mul(torch.sub(pitch_coef, 1.), _95)
    _96 = torch.select(norm_pitch_coefd, 0, 0)
    _97 = torch.eq(_96, 0)
    _98 = torch.tensor(0, dtype=ops.prim.dtype(mean_std_shift), device=ops.prim.device(mean_std_shift))
    _99 = annotate(List[Optional[Tensor]], [_97])
    _100 = torch.index_put_(mean_std_shift, _99, _98)
    norm_pitch_shift = torch.add(norm_pitch_coefd, mean_std_shift)
    return norm_pitch_shift
  def fx_pauses(self: __torch__.silero_vocoder.jit_model.MultiTTSModel,
    mel_outputs: Tensor,
    dur_hat: Tensor,
    symb_durs: Dict[int, int]) -> Tensor:
    _101 = torch.keys(symb_durs)
    for _102 in range(torch.len(_101)):
      sid = _101[_102]
      _103 = torch.slice(torch.select(dur_hat, 0, 0), 0, None, sid)
      dur_sum = int(torch.item(torch.sum(_103)))
      _104 = torch.select(torch.select(dur_hat, 0, 0), 0, sid)
      sdur = int(torch.item(_104))
      if torch.gt(sdur, 10):
        sil_value = self.sil_value
        _105 = torch.slice(torch.slice(mel_outputs), 1)
        _106 = torch.slice(_105, 2, torch.add(dur_sum, 10), torch.add(dur_sum, sdur))
        _107 = torch.tensor(sil_value, dtype=ops.prim.dtype(_106), device=ops.prim.device(_106))
        _108 = torch.copy_(_106, _107)
      else:
        sil_value0 = self.sil_value
        _109 = torch.slice(torch.slice(mel_outputs), 1)
        _110 = torch.slice(_109, 2, dur_sum, torch.add(dur_sum, sdur))
        _111 = torch.tensor(sil_value0, dtype=ops.prim.dtype(_110), device=ops.prim.device(_110))
        _112 = torch.copy_(_110, _111)
    return mel_outputs
