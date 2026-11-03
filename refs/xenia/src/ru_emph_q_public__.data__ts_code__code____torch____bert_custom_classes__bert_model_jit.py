class BertModelJIT(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  num_hidden_layers : int
  dtype : int
  dtype_min : float
  scale : Tensor
  zero_point : Tensor
  embeddings : __torch__.transformers.models.bert.modeling_bert.BertEmbeddings
  encoder : __torch__.transformers.models.bert.modeling_bert.BertEncoder
  pooler : __torch__.transformers.models.bert.modeling_bert.BertPooler
  def forward(self: __torch__.bert_custom_classes.bert_model_jit.BertModelJIT,
    input_ids: Optional[Tensor]=None,
    attention_mask: Optional[Tensor]=None,
    token_type_ids: Optional[Tensor]=None,
    position_ids: Optional[Tensor]=None,
    head_mask: Optional[Tensor]=None,
    inputs_embeds: Optional[Tensor]=None,
    encoder_hidden_states: Optional[Tensor]=None,
    encoder_attention_mask: Optional[Tensor]=None,
    past_key_values: Optional[List[Tensor]]=None,
    use_cache: Optional[bool]=None,
    output_attentions: Optional[bool]=None,
    output_hidden_states: Optional[bool]=None) -> Tuple[Tensor, Tensor]:
    _0 = "You cannot specify both input_ids and inputs_embeds at the same time"
    _1 = "You have to specify either input_ids or inputs_embeds"
    _2 = uninitialized(Tensor)
    _3 = uninitialized(Optional[Tensor])
    _4 = uninitialized(Tuple[int, int])
    _5 = uninitialized(Optional[Tensor])
    if torch.__isnot__(input_ids, None):
      input_ids1 = unchecked_cast(Tensor, input_ids)
      _7 = torch.__isnot__(inputs_embeds, None)
      _6, input_ids0 = _7, input_ids1
    else:
      _6, input_ids0 = False, input_ids
    if _6:
      ops.prim.RaiseException(_0, "builtins.ValueError")
      input_shape, input_ids2, inputs_embeds0 = _4, _3, _5
    else:
      if torch.__isnot__(input_ids0, None):
        input_ids4 = unchecked_cast(Tensor, input_ids0)
        input_shape1 = ((torch.size(input_ids4))[0], (torch.size(input_ids4))[1])
        input_shape0, input_ids3, inputs_embeds1 = input_shape1, input_ids4, inputs_embeds
      else:
        _8 = torch.__isnot__(inputs_embeds, None)
        if _8:
          inputs_embeds3 = unchecked_cast(Tensor, inputs_embeds)
          _9 = (torch.size(inputs_embeds3))[0]
          _10 = (torch.size(inputs_embeds3))[1]
          input_shape2, inputs_embeds2 = (_9, _10), inputs_embeds3
        else:
          ops.prim.RaiseException(_1, "builtins.ValueError")
          input_shape2, inputs_embeds2 = _4, _2
        input_shape0, input_ids3, inputs_embeds1 = input_shape2, input_ids0, inputs_embeds2
      input_shape, input_ids2, inputs_embeds0 = input_shape0, input_ids3, inputs_embeds1
    batch_size, seq_length, = input_shape
    if torch.__isnot__(input_ids2, None):
      input_ids6 = unchecked_cast(Tensor, input_ids2)
      device, input_ids5, inputs_embeds4 = ops.prim.device(input_ids6), input_ids6, inputs_embeds0
    else:
      _11 = torch.__isnot__(inputs_embeds0, None)
      if _11:
        inputs_embeds6 = unchecked_cast(Tensor, inputs_embeds0)
        device0, inputs_embeds5 = ops.prim.device(inputs_embeds6), inputs_embeds6
      else:
        device0, inputs_embeds5 = torch.device("cpu"), inputs_embeds0
      device, input_ids5, inputs_embeds4 = device0, input_ids2, inputs_embeds5
    _12 = torch.__isnot__(past_key_values, None)
    if _12:
      past_key_values0 = unchecked_cast(List[Tensor], past_key_values)
      _13 = torch.select(past_key_values0[0], 0, 0)
      past_key_values_length = (torch.size(_13))[2]
    else:
      past_key_values_length = 0
    if torch.__is__(attention_mask, None):
      _14 = torch.add(seq_length, past_key_values_length)
      attention_mask1 = torch.ones([batch_size, _14], dtype=None, layout=None, device=device)
      attention_mask0 = attention_mask1
    else:
      attention_mask2 = unchecked_cast(Tensor, attention_mask)
      attention_mask0 = attention_mask2
    if torch.__is__(token_type_ids, None):
      embeddings = self.embeddings
      token_type_ids1 = embeddings.token_type_ids
      buffered_token_type_ids = torch.slice(torch.slice(token_type_ids1), 1, None, seq_length)
      buffered_token_type_ids_expanded = torch.expand(buffered_token_type_ids, [batch_size, seq_length])
      token_type_ids0 = buffered_token_type_ids_expanded
    else:
      token_type_ids2 = unchecked_cast(Tensor, token_type_ids)
      token_type_ids0 = token_type_ids2
    extended_attention_mask = (self).get_extended_attention_mask(attention_mask0, input_shape, None, None, )
    num_hidden_layers = self.num_hidden_layers
    head_mask0 = (self).get_head_mask(head_mask, num_hidden_layers, False, )
    embeddings0 = self.embeddings
    embedding_output = (embeddings0).forward(input_ids5, token_type_ids0, position_ids, inputs_embeds4, past_key_values_length, )
    encoder = self.encoder
    encoder_outputs = (encoder).forward(embedding_output, extended_attention_mask, None, encoder_hidden_states, None, None, False, False, False, False, )
    sequence_output = (encoder_outputs)[0]
    pooler = self.pooler
    pooled_output = (pooler).forward(sequence_output, )
    return (sequence_output, pooled_output)
  def get_extended_attention_mask(self: __torch__.bert_custom_classes.bert_model_jit.BertModelJIT,
    attention_mask: Tensor,
    input_shape: Tuple[int, int],
    device: Optional[Device]=None,
    dtype: Optional[int]=None) -> Tensor:
    _15 = "Wrong shape for input_ids (shape {}) or attention_mask (shape {})"
    _16 = uninitialized(Tensor)
    if torch.__is__(dtype, None):
      dtype0 = self.dtype
    else:
      dtype0 = unchecked_cast(int, dtype)
    _17 = torch.eq(torch.dim(attention_mask), 3)
    if _17:
      _18 = torch.unsqueeze(torch.slice(attention_mask), 1)
      extended_attention_mask0 = torch.slice(torch.slice(_18, 2), 3)
      extended_attention_mask = extended_attention_mask0
    else:
      _19 = torch.eq(torch.dim(attention_mask), 2)
      if _19:
        _20 = torch.unsqueeze(torch.slice(attention_mask), 1)
        extended_attention_mask2 = torch.slice(torch.unsqueeze(_20, 2), 3)
        extended_attention_mask1 = extended_attention_mask2
      else:
        _21 = torch.format(_15, input_shape, torch.size(attention_mask))
        ops.prim.RaiseException(_21, "builtins.ValueError")
        extended_attention_mask1 = _16
      extended_attention_mask = extended_attention_mask1
    extended_attention_mask3 = torch.to(extended_attention_mask, dtype0)
    _22 = torch.add(torch.neg(extended_attention_mask3), 1.)
    dtype_min = self.dtype_min
    return torch.mul(_22, dtype_min)
  def get_head_mask(self: __torch__.bert_custom_classes.bert_model_jit.BertModelJIT,
    head_mask: Optional[Tensor],
    num_hidden_layers: int,
    is_attention_chunked: bool=False) -> List[NoneType]:
    head_mask1 = torch.mul([None], num_hidden_layers)
    return head_mask1
