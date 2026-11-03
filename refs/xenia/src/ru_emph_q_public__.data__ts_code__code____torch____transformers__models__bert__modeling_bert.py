class BertEmbeddings(Module):
  __parameters__ = []
  __buffers__ = ["position_ids", "token_type_ids", ]
  position_ids : Tensor
  token_type_ids : Tensor
  training : bool
  _is_full_backward_hook : Optional[bool]
  position_embedding_type : str
  _is_hf_initialized : bool
  word_embeddings : __torch__.torch.nn.modules.sparse.Embedding
  position_embeddings : __torch__.torch.nn.modules.sparse.___torch_mangle_0.Embedding
  token_type_embeddings : __torch__.torch.nn.modules.sparse.___torch_mangle_1.Embedding
  LayerNorm : __torch__.torch.nn.modules.normalization.LayerNorm
  dropout : __torch__.torch.nn.modules.dropout.Dropout
  def forward(self: __torch__.transformers.models.bert.modeling_bert.BertEmbeddings,
    input_ids: Optional[Tensor]=None,
    token_type_ids: Optional[Tensor]=None,
    position_ids: Optional[Tensor]=None,
    inputs_embeds: Optional[Tensor]=None,
    past_key_values_length: int=0) -> Tensor:
    if torch.__isnot__(input_ids, None):
      input_ids1 = unchecked_cast(Tensor, input_ids)
      input_shape, inputs_embeds0, input_ids0 = torch.size(input_ids1), inputs_embeds, input_ids1
    else:
      _0 = torch.__isnot__(inputs_embeds, None)
      if _0:
        inputs_embeds2 = unchecked_cast(Tensor, inputs_embeds)
        _1 = torch.slice(torch.size(inputs_embeds2), None, -1)
        input_shape0, inputs_embeds1 = _1, inputs_embeds2
      else:
        input_shape0, inputs_embeds1 = None, inputs_embeds
      input_shape, inputs_embeds0, input_ids0 = input_shape0, inputs_embeds1, input_ids
    if torch.__is__(input_shape, None):
      _2 = torch.zeros([1, 312])
    else:
      input_shape1 = unchecked_cast(List[int], input_shape)
      seq_length = input_shape1[1]
      if torch.__is__(position_ids, None):
        position_ids1 = self.position_ids
        _3 = torch.slice(position_ids1)
        _4 = torch.add(seq_length, past_key_values_length)
        position_ids2 = torch.slice(_3, 1, past_key_values_length, _4)
        position_ids0 = position_ids2
      else:
        position_ids3 = unchecked_cast(Tensor, position_ids)
        position_ids0 = position_ids3
      _5 = torch.__is__(token_type_ids, None)
      if _5:
        token_type_ids1 = self.token_type_ids
        buffered_token_type_ids = torch.slice(torch.slice(token_type_ids1), 1, None, seq_length)
        buffered_token_type_ids_expanded = torch.expand(buffered_token_type_ids, [input_shape1[0], seq_length])
        token_type_ids0 = buffered_token_type_ids_expanded
      else:
        token_type_ids2 = unchecked_cast(Tensor, token_type_ids)
        token_type_ids0 = token_type_ids2
      _6 = torch.__is__(inputs_embeds0, None)
      if _6:
        _7 = torch.__isnot__(input_ids0, None)
        if _7:
          input_ids2 = unchecked_cast(Tensor, input_ids0)
          word_embeddings = self.word_embeddings
          inputs_embeds5 = (word_embeddings).forward(input_ids2, )
          inputs_embeds4 : Optional[Tensor] = inputs_embeds5
        else:
          inputs_embeds4 = inputs_embeds0
        inputs_embeds3 : Optional[Tensor] = inputs_embeds4
      else:
        inputs_embeds6 = unchecked_cast(Tensor, inputs_embeds0)
        inputs_embeds3 = inputs_embeds6
      _8 = torch.__is__(inputs_embeds3, None)
      if _8:
        _9 = torch.zeros([1, 312])
      else:
        inputs_embeds7 = unchecked_cast(Tensor, inputs_embeds3)
        token_type_embeddings = self.token_type_embeddings
        token_type_embeddings0 = (token_type_embeddings).forward(token_type_ids0, )
        embeddings = torch.add(inputs_embeds7, token_type_embeddings0)
        position_embedding_type = self.position_embedding_type
        _10 = torch.eq(position_embedding_type, "absolute")
        if _10:
          position_embeddings = self.position_embeddings
          position_embeddings0 = (position_embeddings).forward(position_ids0, )
          embeddings1 = torch.add_(embeddings, position_embeddings0)
          embeddings0 = embeddings1
        else:
          embeddings0 = embeddings
        LayerNorm = self.LayerNorm
        embeddings2 = (LayerNorm).forward(embeddings0, )
        dropout = self.dropout
        embeddings3 = (dropout).forward(embeddings2, )
        _9 = embeddings3
      _2 = _9
    return _2
class BertEncoder(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  gradient_checkpointing : bool
  _is_hf_initialized : bool
  layer : __torch__.torch.nn.modules.container.ModuleList
  def forward(self: __torch__.transformers.models.bert.modeling_bert.BertEncoder,
    hidden_states: Tensor,
    attention_mask: Optional[Tensor]=None,
    head_mask: Optional[Tensor]=None,
    encoder_hidden_states: Optional[Tensor]=None,
    encoder_attention_mask: Optional[Tensor]=None,
    past_key_values: Optional[Tuple[Tuple[Tensor]]]=None,
    use_cache: Optional[bool]=None,
    output_attentions: Optional[bool]=False,
    output_hidden_states: Optional[bool]=False,
    return_dict: Optional[bool]=True) -> Tuple[Tensor]:
    layer = self.layer
    _0 = getattr(layer, "0")
    _1 = getattr(layer, "1")
    _2 = getattr(layer, "2")
    if torch.__isnot__(head_mask, None):
      head_mask1 = unchecked_cast(Tensor, head_mask)
      layer_head_mask, head_mask0 = torch.select(head_mask1, 0, 0), head_mask1
    else:
      layer_head_mask, head_mask0 = None, head_mask
    layer_outputs = (_0).forward(hidden_states, attention_mask, layer_head_mask, encoder_hidden_states, encoder_attention_mask, None, output_attentions, )
    hidden_states0 = (layer_outputs)[0]
    if torch.__isnot__(head_mask0, None):
      head_mask3 = unchecked_cast(Tensor, head_mask0)
      layer_head_mask0, head_mask2 = torch.select(head_mask3, 0, 1), head_mask3
    else:
      layer_head_mask0, head_mask2 = None, head_mask0
    layer_outputs0 = (_1).forward(hidden_states0, attention_mask, layer_head_mask0, encoder_hidden_states, encoder_attention_mask, None, output_attentions, )
    hidden_states1 = (layer_outputs0)[0]
    if torch.__isnot__(head_mask2, None):
      head_mask4 = unchecked_cast(Tensor, head_mask2)
      layer_head_mask1 : Optional[Tensor] = torch.select(head_mask4, 0, 2)
    else:
      layer_head_mask1 = None
    layer_outputs1 = (_2).forward(hidden_states1, attention_mask, layer_head_mask1, encoder_hidden_states, encoder_attention_mask, None, output_attentions, )
    hidden_states2 = (layer_outputs1)[0]
    return (hidden_states2,)
class BertLayer(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  chunk_size_feed_forward : int
  seq_len_dim : int
  is_decoder : bool
  add_cross_attention : bool
  _is_hf_initialized : bool
  attention : __torch__.transformers.models.bert.modeling_bert.BertAttention
  intermediate : __torch__.transformers.models.bert.modeling_bert.BertIntermediate
  output : __torch__.transformers.models.bert.modeling_bert.BertOutput
  def forward(self: __torch__.transformers.models.bert.modeling_bert.BertLayer,
    hidden_states: Tensor,
    attention_mask: Optional[Tensor]=None,
    head_mask: Optional[Tensor]=None,
    encoder_hidden_states: Optional[Tensor]=None,
    encoder_attention_mask: Optional[Tensor]=None,
    past_key_value: Optional[Tuple[Tuple[Tensor]]]=None,
    output_attentions: Optional[bool]=False) -> Tuple[Tensor]:
    _11 = torch.__isnot__(past_key_value, None)
    if _11:
      past_key_value0 = unchecked_cast(Tuple[Tuple[Tensor]], past_key_value)
      self_attn_past_key_value : Optional[Tuple[Tuple[Tensor]]] = ((past_key_value0)[0],)
    else:
      self_attn_past_key_value = None
    attention = self.attention
    self_attention_outputs = (attention).forward(hidden_states, attention_mask, head_mask, None, None, self_attn_past_key_value, output_attentions, )
    attention_output = (self_attention_outputs)[0]
    layer_output = (self).feed_forward_chunk(attention_output, )
    return (layer_output,)
  def feed_forward_chunk(self: __torch__.transformers.models.bert.modeling_bert.BertLayer,
    attention_output: Tensor) -> Tensor:
    intermediate = self.intermediate
    intermediate_output = (intermediate).forward(attention_output, )
    output = self.output
    layer_output = (output).forward(intermediate_output, attention_output, )
    return layer_output
class BertAttention(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  _is_hf_initialized : bool
  self : __torch__.transformers.models.bert.modeling_bert.BertSelfAttention
  output : __torch__.transformers.models.bert.modeling_bert.BertSelfOutput
  def forward(self: __torch__.transformers.models.bert.modeling_bert.BertAttention,
    hidden_states: Tensor,
    attention_mask: Optional[Tensor]=None,
    head_mask: Optional[Tensor]=None,
    encoder_hidden_states: Optional[Tensor]=None,
    encoder_attention_mask: Optional[Tensor]=None,
    past_key_value: Optional[Tuple[Tuple[Tensor]]]=None,
    output_attentions: Optional[bool]=False) -> Tuple[Tensor]:
    self0 = self.self
    self_outputs = (self0).forward(hidden_states, attention_mask, head_mask, encoder_hidden_states, encoder_attention_mask, past_key_value, output_attentions, )
    output = self.output
    attention_output = (output).forward((self_outputs)[0], hidden_states, )
    return (attention_output,)
class BertSelfAttention(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  num_attention_heads : int
  attention_head_size : int
  all_head_size : int
  position_embedding_type : str
  is_decoder : bool
  _is_hf_initialized : bool
  query : __torch__.torch.nn.modules.linear.___torch_mangle_4.Linear
  key : __torch__.torch.nn.modules.linear.___torch_mangle_4.Linear
  value : __torch__.torch.nn.modules.linear.___torch_mangle_4.Linear
  dropout : __torch__.torch.nn.modules.dropout.Dropout
  def forward(self: __torch__.transformers.models.bert.modeling_bert.BertSelfAttention,
    hidden_states: Tensor,
    attention_mask: Optional[Tensor]=None,
    head_mask: Optional[Tensor]=None,
    encoder_hidden_states: Optional[Tensor]=None,
    encoder_attention_mask: Optional[Tensor]=None,
    past_key_value: Optional[Tuple[Tuple[Tensor]]]=None,
    output_attentions: Optional[bool]=False) -> Tuple[Tensor]:
    _12 = __torch__.torch.nn.functional.softmax
    query = self.query
    mixed_query_layer = (query).forward(hidden_states, )
    key = self.key
    key_layer = (self).transpose_for_scores((key).forward(hidden_states, ), )
    value = self.value
    value_layer = (self).transpose_for_scores((value).forward(hidden_states, ), )
    query_layer = (self).transpose_for_scores(mixed_query_layer, )
    attention_scores = torch.matmul(query_layer, torch.transpose(key_layer, -1, -2))
    attention_head_size = self.attention_head_size
    attention_scores0 = torch.div(attention_scores, torch.sqrt(attention_head_size))
    _13 = torch.__isnot__(attention_mask, None)
    if _13:
      attention_mask0 = unchecked_cast(Tensor, attention_mask)
      attention_scores2 = torch.add(attention_scores0, attention_mask0)
      attention_scores1 = attention_scores2
    else:
      attention_scores1 = attention_scores0
    attention_probs = _12(attention_scores1, -1, 3, None, )
    dropout = self.dropout
    attention_probs0 = (dropout).forward(attention_probs, )
    if torch.__isnot__(head_mask, None):
      head_mask5 = unchecked_cast(Tensor, head_mask)
      attention_probs2 = torch.mul(attention_probs0, head_mask5)
      attention_probs1 = attention_probs2
    else:
      attention_probs1 = attention_probs0
    context_layer = torch.matmul(attention_probs1, value_layer)
    _14 = torch.permute(context_layer, [0, 2, 1, 3])
    context_layer0 = torch.contiguous(_14)
    _15 = torch.slice(torch.size(context_layer0), None, -2)
    all_head_size = self.all_head_size
    new_context_layer_shape = torch.add(_15, [all_head_size])
    context_layer1 = torch.view(context_layer0, new_context_layer_shape)
    return (context_layer1,)
  def transpose_for_scores(self: __torch__.transformers.models.bert.modeling_bert.BertSelfAttention,
    x: Tensor) -> Tensor:
    _16 = torch.slice(torch.size(x), None, -1)
    num_attention_heads = self.num_attention_heads
    attention_head_size = self.attention_head_size
    _17 = [num_attention_heads, attention_head_size]
    new_x_shape = torch.add(_16, _17)
    x0 = torch.view(x, new_x_shape)
    return torch.permute(x0, [0, 2, 1, 3])
class BertSelfOutput(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  _is_hf_initialized : bool
  dense : __torch__.torch.nn.modules.linear.___torch_mangle_4.Linear
  LayerNorm : __torch__.torch.nn.modules.normalization.LayerNorm
  dropout : __torch__.torch.nn.modules.dropout.Dropout
  def forward(self: __torch__.transformers.models.bert.modeling_bert.BertSelfOutput,
    hidden_states: Tensor,
    input_tensor: Tensor) -> Tensor:
    dense = self.dense
    hidden_states3 = (dense).forward(hidden_states, )
    dropout = self.dropout
    hidden_states4 = (dropout).forward(hidden_states3, )
    LayerNorm = self.LayerNorm
    _18 = torch.add(hidden_states4, input_tensor)
    return (LayerNorm).forward(_18, )
class BertIntermediate(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  _is_hf_initialized : bool
  dense : __torch__.torch.nn.modules.linear.___torch_mangle_5.Linear
  intermediate_act_fn : __torch__.transformers.activations.GELUActivation
  def forward(self: __torch__.transformers.models.bert.modeling_bert.BertIntermediate,
    hidden_states: Tensor) -> Tensor:
    dense = self.dense
    hidden_states5 = (dense).forward(hidden_states, )
    intermediate_act_fn = self.intermediate_act_fn
    hidden_states6 = (intermediate_act_fn).forward(hidden_states5, )
    return hidden_states6
class BertOutput(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  _is_hf_initialized : bool
  dense : __torch__.torch.nn.modules.linear.___torch_mangle_6.Linear
  LayerNorm : __torch__.torch.nn.modules.normalization.LayerNorm
  dropout : __torch__.torch.nn.modules.dropout.Dropout
  def forward(self: __torch__.transformers.models.bert.modeling_bert.BertOutput,
    hidden_states: Tensor,
    input_tensor: Tensor) -> Tensor:
    dense = self.dense
    hidden_states7 = (dense).forward(hidden_states, )
    dropout = self.dropout
    hidden_states8 = (dropout).forward(hidden_states7, )
    LayerNorm = self.LayerNorm
    _19 = torch.add(hidden_states8, input_tensor)
    return (LayerNorm).forward(_19, )
class BertPooler(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  _is_hf_initialized : bool
  dense : __torch__.torch.nn.modules.linear.___torch_mangle_4.Linear
  activation : __torch__.torch.nn.modules.activation.Tanh
  def forward(self: __torch__.transformers.models.bert.modeling_bert.BertPooler,
    hidden_states: Tensor) -> Tensor:
    first_token_tensor = torch.select(torch.slice(hidden_states), 1, 0)
    dense = self.dense
    pooled_output = (dense).forward(first_token_tensor, )
    activation = self.activation
    pooled_output0 = (activation).forward(pooled_output, )
    return pooled_output0
