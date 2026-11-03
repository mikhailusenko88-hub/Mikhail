class JitMultiForward(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  device : Device
  n_mel_channels : int
  encoder_type : str
  pitch_strength : float
  energy_strength : float
  pitch_emb_type : str
  padding_value : float
  log_dur : bool
  embedding : __torch__.torch.nn.modules.sparse.___torch_mangle_12.Embedding
  speaker_embedding : __torch__.torch.nn.modules.sparse.___torch_mangle_13.Embedding
  encoder : __torch__.tacotron2.fastpitch_layers.ForwardTransformer
  len_reg : __torch__.tacotron2.forward_layers.LengthRegulator
  pitch_proj : __torch__.torch.nn.modules.conv.___torch_mangle_2.Conv1d
  energy_proj : __torch__.torch.nn.modules.conv.___torch_mangle_2.Conv1d
  decoder : __torch__.tacotron2.fastpitch_layers.HourGlassTransformer
  lin : __torch__.torch.nn.modules.linear.___torch_mangle_19.Linear
  def forward(self: __torch__.jit_forward_model.JitMultiForward,
    inputs: Tensor,
    speaker_ids: Tensor,
    orig_mask: Tensor,
    dur_hat: Tensor,
    pitch_hat: Tensor,
    energy_hat: Optional[Tensor]=None) -> Tensor:
    embedding = self.embedding
    cond_embedded_inputs = (embedding).forward(inputs, )
    seq_len = torch.size(cond_embedded_inputs, 1)
    speaker_embedding = self.speaker_embedding
    _0 = (speaker_embedding).forward(speaker_ids, )
    speaker_embeds = torch.repeat(torch.unsqueeze(_0, 1), [1, seq_len, 1])
    encoder = self.encoder
    encoder_outputs = (encoder).forward(cond_embedded_inputs, orig_mask, None, )
    cond_encoder_outputs = torch.add(encoder_outputs, speaker_embeds)
    pitch_proj = self.pitch_proj
    pitch_proj0 = (pitch_proj).forward(pitch_hat, )
    pitch_proj1 = torch.transpose(pitch_proj0, 1, 2)
    pitch_emb_type = self.pitch_emb_type
    if torch.eq(pitch_emb_type, "default"):
      pitch_strength = self.pitch_strength
      _1 = torch.mul(pitch_proj1, pitch_strength)
      cond_encoder_outputs1 = torch.add(cond_encoder_outputs, _1)
      cond_encoder_outputs0 = cond_encoder_outputs1
    else:
      cond_encoder_outputs0 = cond_encoder_outputs
    _2 = torch.__not__(torch.__is__(energy_hat, None))
    if _2:
      energy_hat0 = unchecked_cast(Tensor, energy_hat)
      energy_proj = self.energy_proj
      _3 = (energy_proj).forward(energy_hat0, )
      energy_proj0 = torch.transpose(_3, 1, 2)
      energy_strength = self.energy_strength
      _4 = torch.mul(energy_proj0, energy_strength)
      cond_encoder_outputs3 = torch.add(cond_encoder_outputs0, _4)
      cond_encoder_outputs2 = cond_encoder_outputs3
    else:
      cond_encoder_outputs2 = cond_encoder_outputs0
    len_reg = self.len_reg
    encoder_outputs_expanded = (len_reg).forward(cond_encoder_outputs2, dur_hat, )
    pitch_emb_type0 = self.pitch_emb_type
    _5 = torch.eq(pitch_emb_type0, "mel_frame")
    if _5:
      pitch_strength0 = self.pitch_strength
      _6 = torch.mul(pitch_proj1, pitch_strength0)
      encoder_outputs_expanded1 = torch.add(encoder_outputs_expanded, _6)
      encoder_outputs_expanded0 = encoder_outputs_expanded1
    else:
      encoder_outputs_expanded0 = encoder_outputs_expanded
    decoder = self.decoder
    outputs_expanded = (decoder).forward(encoder_outputs_expanded0, None, None, )
    lin = self.lin
    mel_outputs = (lin).forward(outputs_expanded, )
    return torch.transpose(mel_outputs, 1, 2)
class JitDurPredictor(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  device : Device
  dur_class_type : NoneType
  log_dur : bool
  speaker_emb : str
  dur_pred : __torch__.jit_forward_model.TransformerSeriesPredictor
  def forward(self: __torch__.jit_forward_model.JitDurPredictor,
    text: Tensor,
    speaker_ids: Tensor,
    orig_mask: Optional[Tensor]=None,
    alpha: float=1.,
    coef_speakers: Optional[Tensor]=None,
    type_ids: Optional[Tensor]=None,
    focus_mask: Optional[Tensor]=None,
    emphasis: Optional[Tensor]=None) -> Tensor:
    dur_pred = self.dur_pred
    dur_hat = (dur_pred).forward(text, speaker_ids, orig_mask, alpha, coef_speakers, type_ids, focus_mask, emphasis, )
    return torch.squeeze(dur_hat, -1)
class TransformerSeriesPredictor(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  speaker_emb : str
  utt_type_emb : bool
  focus_emb : bool
  emphasis_emb : bool
  embedding : __torch__.torch.nn.modules.sparse.___torch_mangle_21.Embedding
  transformer : __torch__.tacotron2.fastpitch_layers.___torch_mangle_23.ForwardTransformer
  lin : __torch__.torch.nn.modules.linear.___torch_mangle_24.Linear
  speaker_embedding : __torch__.torch.nn.modules.sparse.___torch_mangle_25.Embedding
  emotion_embedding : __torch__.torch.nn.modules.sparse.___torch_mangle_26.Embedding
  type_embedding : __torch__.torch.nn.modules.sparse.___torch_mangle_27.Embedding
  focus_embedding : __torch__.torch.nn.modules.sparse.___torch_mangle_28.Embedding
  emphasis_embedding : __torch__.torch.nn.modules.sparse.___torch_mangle_29.Embedding
  def forward(self: __torch__.jit_forward_model.TransformerSeriesPredictor,
    x: Tensor,
    speaker_ids: Tensor,
    src_pad_mask: Optional[Tensor]=None,
    alpha: float=1.,
    coef_speakers: Optional[Tensor]=None,
    type_ids: Optional[Tensor]=None,
    focus_mask: Optional[Tensor]=None,
    emphasis: Optional[Tensor]=None) -> Tensor:
    embedding = self.embedding
    x0 = (embedding).forward(x, )
    seq_len = torch.size(x0, 1)
    if torch.__is__(coef_speakers, None):
      speaker_embedding = self.speaker_embedding
      speaker_embeds0 = (speaker_embedding).forward(speaker_ids, )
      speaker_embeds = speaker_embeds0
    else:
      coef_speakers0 = unchecked_cast(Tensor, coef_speakers)
      speaker_embedding0 = self.speaker_embedding
      weight = speaker_embedding0.weight
      _7 = torch.reshape(coef_speakers0, [-1, 1])
      speaker_embeds_weighted = torch.mul(weight, _7)
      _8 = annotate(List[Optional[Tensor]], [torch.ne(coef_speakers0, 0)])
      _9 = torch.index(speaker_embeds_weighted, _8)
      speaker_embeds1 = torch.unsqueeze(torch.sum(_9, [0]), 0)
      speaker_embeds = speaker_embeds1
    speaker_embeds2 = torch.repeat(torch.unsqueeze(speaker_embeds, 1), [1, seq_len, 1])
    x1 = torch.add(x0, speaker_embeds2)
    utt_type_emb = self.utt_type_emb
    if utt_type_emb:
      _10 = torch.__isnot__(type_ids, None)
    else:
      _10 = False
    if _10:
      type_ids0 = unchecked_cast(Tensor, type_ids)
      type_embedding = self.type_embedding
      _11 = (type_embedding).forward(type_ids0, )
      x2 = torch.add(x1, _11)
    else:
      x2 = x1
    focus_emb = self.focus_emb
    if focus_emb:
      _12 = torch.__isnot__(focus_mask, None)
    else:
      _12 = False
    if _12:
      focus_mask0 = unchecked_cast(Tensor, focus_mask)
      focus_embedding = self.focus_embedding
      _13 = (focus_embedding).forward(focus_mask0, )
      x3 = torch.add(x2, _13)
    else:
      x3 = x2
    emphasis_emb = self.emphasis_emb
    if emphasis_emb:
      _14 = torch.__isnot__(emphasis, None)
    else:
      _14 = False
    if _14:
      emphasis0 = unchecked_cast(Tensor, emphasis)
      emphasis_embedding = self.emphasis_embedding
      _15 = (emphasis_embedding).forward(emphasis0, )
      x4 = torch.add(x3, _15)
    else:
      x4 = x3
    transformer = self.transformer
    x5 = (transformer).forward(x4, src_pad_mask, None, )
    lin = self.lin
    output = (lin).forward(x5, )
    return torch.div(output, alpha)
class JitPitchPredictorIC(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  device : Device
  speaker_emb : str
  pitch_pred : __torch__.jit_forward_model.___torch_mangle_32.TransformerSeriesPredictor
  def forward(self: __torch__.jit_forward_model.JitPitchPredictorIC,
    text: Tensor,
    speaker_ids: Tensor,
    orig_mask: Optional[Tensor]=None,
    type_ids: Optional[Tensor]=None,
    focus_mask: Optional[Tensor]=None,
    emphasis: Optional[Tensor]=None) -> Tensor:
    pitch_pred = self.pitch_pred
    pitch_hat = (pitch_pred).forward(text, speaker_ids, orig_mask, 1., None, type_ids, focus_mask, emphasis, )
    return torch.transpose(pitch_hat, 1, 2)
