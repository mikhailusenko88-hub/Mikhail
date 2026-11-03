def embedding_bag(input: Tensor,
    weight: Tensor,
    offsets: Optional[Tensor]=None,
    max_norm: Optional[float]=None,
    norm_type: float=2.,
    scale_grad_by_freq: bool=False,
    mode: str="mean",
    sparse: bool=False,
    per_sample_weights: Optional[Tensor]=None,
    include_last_offset: bool=False,
    padding_idx: Optional[int]=None) -> Tensor:
  _0 = "Argument order of nn.functional.embedding_bag was changed. Usage `embedding_bag(weight, input, ...)` is deprecated, and should now be `embedding_bag(input, weight, ...)`."
  _1 = "embedding_bag: If per_sample_weights ({}) is not None, then it must have the same shape as the input ({})"
  _2 = "if input is 2D, then offsets has to be None, as input is treated is a mini-batch of fixed length sequences. However, found offsets of type {}"
  _3 = "offsets has to be a 1D Tensor but got None"
  _4 = "input has to be 1D or 2D Tensor, but got Tensor of dimension {}"
  _5 = "max mode does not support scaling the gradient by the frequency"
  _6 = "max mode does not support sparse weights"
  _7 = "mode has to be one of sum, mean or max"
  _8 = "embedding_bag: per_sample_weights was not None. per_sample_weights is only supported for mode=\'sum\' (got mode=\'{}\'). Please open a feature request on GitHub."
  _9 = uninitialized(int)
  _10 = uninitialized(Tensor)
  _11 = uninitialized(Optional[Tensor])
  if torch.eq(ops.prim.dtype(weight), 4):
    _12 = torch.is_floating_point(input)
  else:
    _12 = False
  if _12:
    torch.warn(_0)
    input0, weight0 = weight, input
  else:
    input0, weight0 = input, weight
  _13 = torch.__isnot__(per_sample_weights, None)
  if _13:
    per_sample_weights1 = unchecked_cast(Tensor, per_sample_weights)
    _15 = torch.ne(torch.size(input0), torch.size(per_sample_weights1))
    _14, per_sample_weights0 = _15, per_sample_weights1
  else:
    _14, per_sample_weights0 = False, per_sample_weights
  if _14:
    per_sample_weights3 = unchecked_cast(Tensor, per_sample_weights0)
    _16 = torch.format(_1, torch.size(per_sample_weights3), torch.size(input0))
    ops.prim.RaiseException(_16, "builtins.ValueError")
    per_sample_weights2 : Optional[Tensor] = _11
  else:
    per_sample_weights2 = per_sample_weights0
  if torch.eq(torch.dim(input0), 2):
    if torch.__isnot__(offsets, None):
      ops.prim.RaiseException(torch.format(_2, "<unknown>"), "builtins.ValueError")
    else:
      pass
    offsets1 = torch.arange(0, torch.numel(input0), torch.size(input0, 1), dtype=ops.prim.dtype(input0), layout=None, device=ops.prim.device(input0))
    input2 = torch.reshape(input0, [-1])
    _17 = torch.__isnot__(per_sample_weights2, None)
    if _17:
      per_sample_weights6 = unchecked_cast(Tensor, per_sample_weights2)
      per_sample_weights7 = torch.reshape(per_sample_weights6, [-1])
      per_sample_weights5 : Optional[Tensor] = per_sample_weights7
    else:
      per_sample_weights5 = per_sample_weights2
    per_sample_weights4, input1, offsets0 = per_sample_weights5, input2, offsets1
  else:
    if torch.eq(torch.dim(input0), 1):
      if torch.__is__(offsets, None):
        ops.prim.RaiseException(_3, "builtins.ValueError")
        offsets3 = _10
      else:
        offsets3 = unchecked_cast(Tensor, offsets)
      if torch.ne(torch.dim(offsets3), 1):
        ops.prim.RaiseException("offsets has to be a 1D Tensor", "builtins.ValueError")
      else:
        pass
      offsets2 = offsets3
    else:
      _18 = torch.format(_4, torch.dim(input0))
      ops.prim.RaiseException(_18, "builtins.ValueError")
      offsets2 = _10
    per_sample_weights4, input1, offsets0 = per_sample_weights2, input0, offsets2
  if torch.eq(mode, "sum"):
    mode_enum = 0
  else:
    if torch.eq(mode, "mean"):
      mode_enum0 = 1
    else:
      if torch.eq(mode, "max"):
        if scale_grad_by_freq:
          ops.prim.RaiseException(_5, "builtins.ValueError")
        else:
          pass
        if sparse:
          ops.prim.RaiseException(_6, "builtins.ValueError")
        else:
          pass
        mode_enum1 = 2
      else:
        ops.prim.RaiseException(_7, "builtins.ValueError")
        mode_enum1 = _9
      mode_enum0 = mode_enum1
    mode_enum = mode_enum0
  _19 = torch.__isnot__(per_sample_weights4, None)
  if _19:
    per_sample_weights9 = unchecked_cast(Tensor, per_sample_weights4)
    _20, per_sample_weights8 = torch.ne(mode, "sum"), per_sample_weights9
  else:
    _20, per_sample_weights8 = False, per_sample_weights4
  if _20:
    ops.prim.RaiseException(torch.format(_8, mode), "builtins.NotImplementedError")
    per_sample_weights10 : Optional[Tensor] = _11
  else:
    per_sample_weights10 = per_sample_weights8
  ret, _21, _22, _23 = torch.embedding_bag(weight0, input1, offsets0, scale_grad_by_freq, mode_enum, sparse, per_sample_weights10, include_last_offset, padding_idx)
  return ret
def relu(input: Tensor,
    inplace: bool=False) -> Tensor:
  if inplace:
    result = torch.relu_(input)
  else:
    result = torch.relu(input)
  return result
def embedding(input: Tensor,
    weight: Tensor,
    padding_idx: Optional[int]=None,
    max_norm: Optional[float]=None,
    norm_type: float=2.,
    scale_grad_by_freq: bool=False,
    sparse: bool=False) -> Tensor:
  _24 = "AssertionError: Padding_idx must be within num_embeddings"
  if torch.__isnot__(padding_idx, None):
    padding_idx1 = unchecked_cast(int, padding_idx)
    if torch.gt(padding_idx1, 0):
      _25 = torch.lt(padding_idx1, torch.size(weight, 0))
      if _25:
        pass
      else:
        ops.prim.RaiseException(_24)
      padding_idx2 = padding_idx1
    else:
      if torch.lt(padding_idx1, 0):
        _26 = torch.neg(torch.size(weight, 0))
        if torch.ge(padding_idx1, _26):
          pass
        else:
          ops.prim.RaiseException(_24)
        padding_idx4 = torch.add(torch.size(weight, 0), padding_idx1)
        padding_idx3 = padding_idx4
      else:
        padding_idx3 = padding_idx1
      padding_idx2 = padding_idx3
    padding_idx0 = padding_idx2
  else:
    padding_idx0 = -1
  if torch.__isnot__(max_norm, None):
    input0 = torch.contiguous(input)
  else:
    input0 = input
  _27 = torch.embedding(weight, input0, padding_idx0, scale_grad_by_freq, sparse)
  return _27
def layer_norm(input: Tensor,
    normalized_shape: List[int],
    weight: Optional[Tensor]=None,
    bias: Optional[Tensor]=None,
    eps: float=1.0000000000000001e-05) -> Tensor:
  _28 = torch.layer_norm(input, normalized_shape, weight, bias, eps)
  return _28
def dropout(input: Tensor,
    p: float=0.5,
    training: bool=True,
    inplace: bool=False) -> Tensor:
  _29 = "dropout probability has to be between 0 and 1, but got {}"
  if torch.lt(p, 0.):
    _30 = True
  else:
    _30 = torch.gt(p, 1.)
  if _30:
    ops.prim.RaiseException(torch.format(_29, p), "builtins.ValueError")
  else:
    pass
  if inplace:
    _31 = torch.dropout_(input, p, training)
  else:
    _31 = torch.dropout(input, p, training)
  return _31
def softmax(input: Tensor,
    dim: Optional[int]=None,
    _stacklevel: int=3,
    dtype: Optional[int]=None) -> Tensor:
  _32 = __torch__.torch.nn.functional._get_softmax_dim
  if torch.__is__(dim, None):
    dim1 = _32("softmax", torch.dim(input), _stacklevel, )
    dim0 = dim1
  else:
    dim0 = unchecked_cast(int, dim)
  if torch.__is__(dtype, None):
    ret = torch.softmax(input, dim0)
  else:
    dtype0 = unchecked_cast(int, dtype)
    ret = torch.softmax(input, dim0, dtype0)
  return ret
def _get_softmax_dim(name: str,
    ndim: int,
    stacklevel: int) -> int:
  _33 = "Implicit dimension choice for {} has been deprecated. Change the call to include dim=X as an argument."
  torch.warn(torch.format(_33, name), stacklevel)
  if torch.eq(ndim, 0):
    _34 = True
  else:
    _34 = torch.eq(ndim, 1)
  if _34:
    _35 = True
  else:
    _35 = torch.eq(ndim, 3)
  if _35:
    ret = 0
  else:
    ret = 1
  return ret
def _none_or_dtype(input: Optional[Tensor]) -> Optional[int]:
  if torch.__is__(input, None):
    _36 : Optional[int] = None
  else:
    input1 = unchecked_cast(Tensor, input)
    input2 = unchecked_cast(Tensor, input1)
    _36 = ops.prim.dtype(input2)
  return _36
def _canonical_mask(mask: Optional[Tensor],
    mask_name: str,
    other_type: Optional[int],
    other_name: str,
    target_type: int,
    check_other: bool=True) -> Optional[Tensor]:
  _37 = "only bool and floating types of {} are supported"
  _38 = "Support for mismatched {} and {} is deprecated. Use same type for both instead."
  if torch.__isnot__(mask, None):
    mask1 = unchecked_cast(Tensor, mask)
    _mask_dtype = ops.prim.dtype(mask1)
    _mask_is_float = torch.is_floating_point(mask1)
    if torch.ne(_mask_dtype, 11):
      _39 = torch.__not__(_mask_is_float)
    else:
      _39 = False
    if _39:
      _40 = torch.add("AssertionError: ", torch.format(_37, mask_name))
      ops.prim.RaiseException(_40)
    else:
      pass
    if check_other:
      _41 = torch.__isnot__(other_type, None)
    else:
      _41 = False
    if _41:
      other_type0 = unchecked_cast(int, other_type)
      _42 = torch.ne(_mask_dtype, other_type0)
      if _42:
        _43 = torch.format(_38, mask_name, other_name)
        torch.warn(_43)
      else:
        pass
    else:
      pass
    if torch.__not__(_mask_is_float):
      _44 = torch.zeros_like(mask1, dtype=target_type)
      mask3 = torch.masked_fill_(_44, mask1, -inf)
      mask2 = mask3
    else:
      mask2 = mask1
    mask0 : Optional[Tensor] = mask2
  else:
    mask0 = mask
  return mask0
def multi_head_attention_forward(query: Tensor,
    key: Tensor,
    value: Tensor,
    embed_dim_to_check: int,
    num_heads: int,
    in_proj_weight: Optional[Tensor],
    in_proj_bias: Optional[Tensor],
    bias_k: Optional[Tensor],
    bias_v: Optional[Tensor],
    add_zero_attn: bool,
    dropout_p: float,
    out_proj_weight: Tensor,
    out_proj_bias: Optional[Tensor],
    training: bool=True,
    key_padding_mask: Optional[Tensor]=None,
    need_weights: bool=True,
    attn_mask: Optional[Tensor]=None,
    use_separate_proj_weight: bool=False,
    q_proj_weight: Optional[Tensor]=None,
    k_proj_weight: Optional[Tensor]=None,
    v_proj_weight: Optional[Tensor]=None,
    static_k: Optional[Tensor]=None,
    static_v: Optional[Tensor]=None,
    average_attn_weights: bool=True,
    is_causal: bool=False) -> Tuple[Tensor, Optional[Tensor]]:
  _45 = __torch__.torch.nn.functional._mha_shape_check
  _46 = __torch__.torch.nn.functional._none_or_dtype
  _47 = __torch__.torch.nn.functional._canonical_mask
  _48 = "was expecting embedding dimension of {}, but got {}"
  _49 = "embed_dim {} not divisible by num_heads {}"
  _50 = "key\'s sequence and batch dims {} do not match value\'s {}"
  _51 = "key shape {} does not match value shape {}"
  _52 = "AssertionError: use_separate_proj_weight is False but in_proj_weight is None"
  _53 = __torch__.torch.nn.functional._in_projection_packed
  _54 = "AssertionError: use_separate_proj_weight is True but q_proj_weight is None"
  _55 = "AssertionError: use_separate_proj_weight is True but k_proj_weight is None"
  _56 = "AssertionError: use_separate_proj_weight is True but v_proj_weight is None"
  _57 = __torch__.torch.nn.functional._in_projection
  _58 = "The shape of the 2D attn_mask is {}, but should be {}."
  _59 = "The shape of the 3D attn_mask is {}, but should be {}."
  _60 = "attn_mask\'s dimension {} is not supported"
  _61 = "AssertionError: bias cannot be added to static key."
  _62 = "AssertionError: bias cannot be added to static value."
  _63 = "expecting static_k.size(0) of {}, but got {}"
  _64 = "expecting static_k.size(2) of {}, but got {}"
  _65 = "expecting static_v.size(0) of {}, but got {}"
  _66 = "expecting static_v.size(2) of {}, but got {}"
  _67 = "expecting key_padding_mask shape of {}, but got {}"
  _68 = __torch__.torch.nn.functional.___torch_mangle_27.softmax
  _69 = __torch__.torch.nn.functional.___torch_mangle_24.dropout
  _70 = uninitialized(Optional[Tensor])
  _71 = uninitialized(Optional[Tensor])
  _72 = uninitialized(Tensor)
  is_batched = _45(query, key, value, key_padding_mask, attn_mask, num_heads, )
  if torch.__not__(is_batched):
    query1 = torch.unsqueeze(query, 1)
    key1 = torch.unsqueeze(key, 1)
    value1 = torch.unsqueeze(value, 1)
    _73 = torch.__isnot__(key_padding_mask, None)
    if _73:
      key_padding_mask2 = unchecked_cast(Tensor, key_padding_mask)
      key_padding_mask3 = torch.unsqueeze(key_padding_mask2, 0)
      key_padding_mask1 : Optional[Tensor] = key_padding_mask3
    else:
      key_padding_mask1 = key_padding_mask
    query0, key0, key_padding_mask0, value0 = query1, key1, key_padding_mask1, value1
  else:
    query0, key0, key_padding_mask0, value0 = query, key, key_padding_mask, value
  tgt_len, bsz, embed_dim, = torch.size(query0)
  src_len, _74, _75, = torch.size(key0)
  key_padding_mask4 = _47(key_padding_mask0, "key_padding_mask", _46(attn_mask, ), "attn_mask", ops.prim.dtype(query0), True, )
  if is_causal:
    attn_mask0 : Optional[Tensor] = None
  else:
    attn_mask0 = attn_mask
  _76 = torch.eq(embed_dim, embed_dim_to_check)
  if _76:
    pass
  else:
    _77 = torch.format(_48, embed_dim_to_check, embed_dim)
    ops.prim.RaiseException(torch.add("AssertionError: ", _77))
  embed_dim0 = unchecked_cast(int, embed_dim)
  head_dim = torch.floordiv(embed_dim0, num_heads)
  _78 = torch.eq(torch.mul(head_dim, num_heads), embed_dim0)
  if _78:
    pass
  else:
    _79 = torch.format(_49, embed_dim0, num_heads)
    ops.prim.RaiseException(torch.add("AssertionError: ", _79))
  if use_separate_proj_weight:
    _80 = torch.slice(torch.size(key0), None, 2)
    _81 = torch.slice(torch.size(value0), None, 2)
    if torch.eq(_80, _81):
      pass
    else:
      _82 = torch.slice(torch.size(key0), None, 2)
      _83 = torch.slice(torch.size(value0), None, 2)
      _84 = torch.add("AssertionError: ", torch.format(_50, _82, _83))
      ops.prim.RaiseException(_84)
  else:
    _85 = torch.eq(torch.size(key0), torch.size(value0))
    if _85:
      pass
    else:
      _86 = torch.format(_51, torch.size(key0), torch.size(value0))
      _87 = torch.add("AssertionError: ", _86)
      ops.prim.RaiseException(_87)
  _88 = torch.__not__(use_separate_proj_weight)
  if _88:
    _89 = torch.__isnot__(in_proj_weight, None)
    if _89:
      in_proj_weight1 = unchecked_cast(Tensor, in_proj_weight)
      in_proj_weight0 = in_proj_weight1
    else:
      ops.prim.RaiseException(_52)
      in_proj_weight0 = _72
    _90 = _53(query0, key0, value0, in_proj_weight0, in_proj_bias, )
    q0, k0, v0, = _90
    q, k, v = q0, k0, v0
  else:
    _91 = torch.__isnot__(q_proj_weight, None)
    if _91:
      q_proj_weight1 = unchecked_cast(Tensor, q_proj_weight)
      q_proj_weight0 = q_proj_weight1
    else:
      ops.prim.RaiseException(_54)
      q_proj_weight0 = _72
    _92 = torch.__isnot__(k_proj_weight, None)
    if _92:
      k_proj_weight1 = unchecked_cast(Tensor, k_proj_weight)
      k_proj_weight0 = k_proj_weight1
    else:
      ops.prim.RaiseException(_55)
      k_proj_weight0 = _72
    _93 = torch.__isnot__(v_proj_weight, None)
    if _93:
      v_proj_weight1 = unchecked_cast(Tensor, v_proj_weight)
      v_proj_weight0 = v_proj_weight1
    else:
      ops.prim.RaiseException(_56)
      v_proj_weight0 = _72
    if torch.__is__(in_proj_bias, None):
      b_q, b_k, b_v = None, None, None
    else:
      in_proj_bias0 = unchecked_cast(Tensor, in_proj_bias)
      b_q0, b_k0, b_v0, = torch.chunk(in_proj_bias0, 3)
      b_q, b_k, b_v = b_q0, b_k0, b_v0
    _94 = _57(query0, key0, value0, q_proj_weight0, k_proj_weight0, v_proj_weight0, b_q, b_k, b_v, )
    q1, k1, v1, = _94
    q, k, v = q1, k1, v1
  attn_mask1 = _47(attn_mask0, "attn_mask", _46(key_padding_mask4, ), "key_padding_mask", ops.prim.dtype(q), False, )
  if torch.__isnot__(attn_mask1, None):
    attn_mask3 = unchecked_cast(Tensor, attn_mask1)
    if torch.eq(torch.dim(attn_mask3), 2):
      correct_2d_size = (tgt_len, src_len)
      _95 = torch.ne(torch.size(attn_mask3), [tgt_len, src_len])
      if _95:
        _96 = torch.format(_58, torch.size(attn_mask3), correct_2d_size)
        ops.prim.RaiseException(_96, "builtins.RuntimeError")
      else:
        pass
      attn_mask4 = torch.unsqueeze(attn_mask3, 0)
    else:
      _97 = torch.eq(torch.dim(attn_mask3), 3)
      if _97:
        _98 = torch.mul(bsz, num_heads)
        correct_3d_size = (_98, tgt_len, src_len)
        _99 = torch.ne(torch.size(attn_mask3), [_98, tgt_len, src_len])
        if _99:
          _100 = torch.format(_59, torch.size(attn_mask3), correct_3d_size)
          ops.prim.RaiseException(_100, "builtins.RuntimeError")
        else:
          pass
      else:
        _101 = torch.format(_60, torch.dim(attn_mask3))
        ops.prim.RaiseException(_101, "builtins.RuntimeError")
      attn_mask4 = attn_mask3
    attn_mask2 : Optional[Tensor] = attn_mask4
  else:
    attn_mask2 = attn_mask1
  if torch.__isnot__(bias_k, None):
    bias_k1 = unchecked_cast(Tensor, bias_k)
    _102, bias_k0 = torch.__isnot__(bias_v, None), bias_k1
  else:
    _102, bias_k0 = False, bias_k
  if _102:
    bias_k2 = unchecked_cast(Tensor, bias_k0)
    bias_v0 = unchecked_cast(Tensor, bias_v)
    if torch.__is__(static_k, None):
      static_k1 : Optional[Tensor] = static_k
    else:
      ops.prim.RaiseException(_61)
      static_k1 = _71
    if torch.__is__(static_v, None):
      static_v1 : Optional[Tensor] = static_v
    else:
      ops.prim.RaiseException(_62)
      static_v1 = _70
    _103 = [k, torch.repeat(bias_k2, [1, bsz, 1])]
    k3 = torch.cat(_103)
    _104 = [v, torch.repeat(bias_v0, [1, bsz, 1])]
    v3 = torch.cat(_104)
    if torch.__isnot__(attn_mask2, None):
      attn_mask7 = unchecked_cast(Tensor, attn_mask2)
      attn_mask6 : Optional[Tensor] = torch.pad(attn_mask7, [0, 1])
    else:
      attn_mask6 = attn_mask2
    _105 = torch.__isnot__(key_padding_mask4, None)
    if _105:
      key_padding_mask7 = unchecked_cast(Tensor, key_padding_mask4)
      key_padding_mask8 = torch.pad(key_padding_mask7, [0, 1])
      key_padding_mask6 : Optional[Tensor] = key_padding_mask8
    else:
      key_padding_mask6 = key_padding_mask4
    static_k0, k2, static_v0, v2, attn_mask5, key_padding_mask5 = static_k1, k3, static_v1, v3, attn_mask6, key_padding_mask6
  else:
    if torch.__is__(bias_k0, None):
      pass
    else:
      ops.prim.RaiseException("AssertionError: ")
    if torch.__is__(bias_v, None):
      pass
    else:
      ops.prim.RaiseException("AssertionError: ")
    static_k0, k2, static_v0, v2, attn_mask5, key_padding_mask5 = static_k, k, static_v, v, attn_mask2, key_padding_mask4
  _106 = [tgt_len, torch.mul(bsz, num_heads), head_dim]
  q2 = torch.transpose(torch.view(q, _106), 0, 1)
  if torch.__is__(static_k0, None):
    _107 = [(torch.size(k2))[0], torch.mul(bsz, num_heads), head_dim]
    k5 = torch.transpose(torch.view(k2, _107), 0, 1)
    k4 = k5
  else:
    static_k2 = unchecked_cast(Tensor, static_k0)
    _108 = torch.eq(torch.size(static_k2, 0), torch.mul(bsz, num_heads))
    if _108:
      pass
    else:
      _109 = torch.format(_63, torch.mul(bsz, num_heads), torch.size(static_k2, 0))
      _110 = torch.add("AssertionError: ", _109)
      ops.prim.RaiseException(_110)
    _111 = torch.eq(torch.size(static_k2, 2), head_dim)
    if _111:
      pass
    else:
      _112 = torch.format(_64, head_dim, torch.size(static_k2, 2))
      _113 = torch.add("AssertionError: ", _112)
      ops.prim.RaiseException(_113)
    k4 = static_k2
  if torch.__is__(static_v0, None):
    _114 = [(torch.size(v2))[0], torch.mul(bsz, num_heads), head_dim]
    v5 = torch.transpose(torch.view(v2, _114), 0, 1)
    v4 = v5
  else:
    static_v2 = unchecked_cast(Tensor, static_v0)
    _115 = torch.eq(torch.size(static_v2, 0), torch.mul(bsz, num_heads))
    if _115:
      pass
    else:
      _116 = torch.format(_65, torch.mul(bsz, num_heads), torch.size(static_v2, 0))
      _117 = torch.add("AssertionError: ", _116)
      ops.prim.RaiseException(_117)
    _118 = torch.eq(torch.size(static_v2, 2), head_dim)
    if _118:
      pass
    else:
      _119 = torch.format(_66, head_dim, torch.size(static_v2, 2))
      _120 = torch.add("AssertionError: ", _119)
      ops.prim.RaiseException(_120)
    v4 = static_v2
  if add_zero_attn:
    _121 = torch.mul(bsz, num_heads)
    _122 = ops.prim.dtype(k4)
    _123 = ops.prim.device(k4)
    _124 = torch.zeros([_121, 1, head_dim], dtype=_122, layout=None, device=_123)
    k7 = torch.cat([k4, _124], 1)
    _125 = ops.prim.dtype(v4)
    _126 = ops.prim.device(v4)
    _127 = torch.zeros([_121, 1, head_dim], dtype=_125, layout=None, device=_126)
    v7 = torch.cat([v4, _127], 1)
    if torch.__isnot__(attn_mask5, None):
      attn_mask10 = unchecked_cast(Tensor, attn_mask5)
      attn_mask9 : Optional[Tensor] = torch.pad(attn_mask10, [0, 1])
    else:
      attn_mask9 = attn_mask5
    _128 = torch.__isnot__(key_padding_mask5, None)
    if _128:
      key_padding_mask11 = unchecked_cast(Tensor, key_padding_mask5)
      key_padding_mask12 = torch.pad(key_padding_mask11, [0, 1])
      key_padding_mask10 : Optional[Tensor] = key_padding_mask12
    else:
      key_padding_mask10 = key_padding_mask5
    k6, key_padding_mask9, attn_mask8, v6 = k7, key_padding_mask10, attn_mask9, v7
  else:
    k6, key_padding_mask9, attn_mask8, v6 = k4, key_padding_mask5, attn_mask5, v4
  src_len0 = torch.size(k6, 1)
  _129 = torch.__isnot__(key_padding_mask9, None)
  if _129:
    key_padding_mask13 = unchecked_cast(Tensor, key_padding_mask9)
    _130 = torch.eq(torch.size(key_padding_mask13), [bsz, src_len0])
    if _130:
      pass
    else:
      _131 = torch.format(_67, (bsz, src_len0), torch.size(key_padding_mask13))
      _132 = torch.add("AssertionError: ", _131)
      ops.prim.RaiseException(_132)
    _133 = torch.view(key_padding_mask13, [bsz, 1, 1, src_len0])
    _134 = torch.expand(_133, [-1, num_heads, -1, -1])
    _135 = [torch.mul(bsz, num_heads), 1, src_len0]
    key_padding_mask14 = torch.reshape(_134, _135)
    if torch.__is__(attn_mask8, None):
      attn_mask12 = key_padding_mask14
    else:
      attn_mask13 = unchecked_cast(Tensor, attn_mask8)
      attn_mask14 = torch.add(attn_mask13, key_padding_mask14)
      attn_mask12 = attn_mask14
    attn_mask11 : Optional[Tensor] = attn_mask12
  else:
    attn_mask11 = attn_mask8
  if torch.__not__(training):
    dropout_p0 = 0.
  else:
    dropout_p0 = dropout_p
  if need_weights:
    B, Nt, E, = torch.size(q2)
    q_scaled = torch.div(q2, torch.sqrt(E))
    if torch.__isnot__(attn_mask11, None):
      attn_mask15 = unchecked_cast(Tensor, attn_mask11)
      attn_output_weights0 = torch.baddbmm(attn_mask15, q_scaled, torch.transpose(k6, -2, -1))
      attn_output_weights = attn_output_weights0
    else:
      attn_output_weights1 = torch.bmm(q_scaled, torch.transpose(k6, -2, -1))
      attn_output_weights = attn_output_weights1
    attn_output_weights2 = _68(attn_output_weights, -1, 3, None, )
    if torch.gt(dropout_p0, 0.):
      attn_output_weights4 = _69(attn_output_weights2, dropout_p0, True, False, )
      attn_output_weights3 = attn_output_weights4
    else:
      attn_output_weights3 = attn_output_weights2
    attn_output = torch.bmm(attn_output_weights3, v6)
    _137 = torch.contiguous(torch.transpose(attn_output, 0, 1))
    _138 = [torch.mul(tgt_len, bsz), embed_dim0]
    attn_output0 = torch.view(_137, _138)
    attn_output1 = torch.linear(attn_output0, out_proj_weight, out_proj_bias)
    _139 = [tgt_len, bsz, torch.size(attn_output1, 1)]
    attn_output2 = torch.view(attn_output1, _139)
    attn_output_weights5 = torch.view(attn_output_weights3, [bsz, num_heads, tgt_len, src_len0])
    if average_attn_weights:
      attn_output_weights7 = torch.mean(attn_output_weights5, [1])
      attn_output_weights6 = attn_output_weights7
    else:
      attn_output_weights6 = attn_output_weights5
    if torch.__not__(is_batched):
      attn_output4 = torch.squeeze(attn_output2, 1)
      attn_output_weights9 = torch.squeeze(attn_output_weights6, 0)
      attn_output3, attn_output_weights8 = attn_output4, attn_output_weights9
    else:
      attn_output3, attn_output_weights8 = attn_output2, attn_output_weights6
    _140 = (attn_output3, attn_output_weights8)
    _136 = _140
  else:
    if torch.__isnot__(attn_mask11, None):
      attn_mask17 = unchecked_cast(Tensor, attn_mask11)
      _141 = torch.eq(torch.size(attn_mask17, 0), 1)
      if _141:
        _143 = torch.eq(torch.dim(attn_mask17), 3)
        _142 = _143
      else:
        _142 = False
      if _142:
        attn_mask18 = torch.unsqueeze(attn_mask17, 0)
      else:
        attn_mask19 = torch.view(attn_mask17, [bsz, num_heads, -1, src_len0])
        attn_mask18 = attn_mask19
      attn_mask16 : Optional[Tensor] = attn_mask18
    else:
      attn_mask16 = attn_mask11
    q3 = torch.view(q2, [bsz, num_heads, tgt_len, head_dim])
    _144 = [bsz, num_heads, src_len0, head_dim]
    k8 = torch.view(k6, _144)
    _145 = [bsz, num_heads, src_len0, head_dim]
    v8 = torch.view(v6, _145)
    attn_output5 = torch.scaled_dot_product_attention(q3, k8, v8, attn_mask16, dropout_p0, is_causal)
    _146 = torch.permute(attn_output5, [2, 0, 1, 3])
    _147 = torch.contiguous(_146)
    _148 = [torch.mul(bsz, tgt_len), embed_dim0]
    attn_output6 = torch.view(_147, _148)
    attn_output7 = torch.linear(attn_output6, out_proj_weight, out_proj_bias)
    _149 = [tgt_len, bsz, torch.size(attn_output7, 1)]
    attn_output8 = torch.view(attn_output7, _149)
    if torch.__not__(is_batched):
      attn_output9 = torch.squeeze(attn_output8, 1)
    else:
      attn_output9 = attn_output8
    _136 = (attn_output9, None)
  return _136
def fold(input: Tensor,
    output_size: List[int],
    kernel_size: List[int],
    dilation: List[int]=[1, 1],
    padding: List[int]=[0, 0],
    stride: List[int]=[1, 1]) -> Tensor:
  _150 = torch.col2im(input, output_size, kernel_size, dilation, padding, stride)
  return _150
def _mha_shape_check(query: Tensor,
    key: Tensor,
    value: Tensor,
    key_padding_mask: Optional[Tensor],
    attn_mask: Optional[Tensor],
    num_heads: int) -> bool:
  _151 = "For batched (3-D) `query`, expected `key` and `value` to be 3-D but found {}-D and {}-D tensors respectively"
  _152 = "For batched (3-D) `query`, expected `key_padding_mask` to be `None` or 2-D but found {}-D tensor instead"
  _153 = "For batched (3-D) `query`, expected `attn_mask` to be `None`, 2-D or 3-D but found {}-D tensor instead"
  _154 = "For unbatched (2-D) `query`, expected `key` and `value` to be 2-D but found {}-D and {}-D tensors respectively"
  _155 = "For unbatched (2-D) `query`, expected `key_padding_mask` to be `None` or 1-D but found {}-D tensor instead"
  _156 = "For unbatched (2-D) `query`, expected `attn_mask` to be `None`, 2-D or 3-D but found {}-D tensor instead"
  _157 = "Expected `attn_mask` shape to be {} but got {}"
  _158 = "query should be unbatched 2D or batched 3D tensor but received {}-D query tensor"
  _159 = uninitialized(bool)
  if torch.eq(torch.dim(query), 3):
    if torch.eq(torch.dim(key), 3):
      _160 = torch.eq(torch.dim(value), 3)
    else:
      _160 = False
    if _160:
      pass
    else:
      _161 = torch.format(_151, torch.dim(key), torch.dim(value))
      _162 = torch.add("AssertionError: ", _161)
      ops.prim.RaiseException(_162)
    _163 = torch.__isnot__(key_padding_mask, None)
    if _163:
      key_padding_mask15 = unchecked_cast(Tensor, key_padding_mask)
      _164 = torch.eq(torch.dim(key_padding_mask15), 2)
      if _164:
        pass
      else:
        _165 = torch.format(_152, torch.dim(key_padding_mask15))
        _166 = torch.add("AssertionError: ", _165)
        ops.prim.RaiseException(_166)
    else:
      pass
    if torch.__isnot__(attn_mask, None):
      attn_mask20 = unchecked_cast(Tensor, attn_mask)
      _167 = torch.dim(attn_mask20)
      if torch.__contains__([2, 3], _167):
        pass
      else:
        _168 = torch.format(_153, torch.dim(attn_mask20))
        _169 = torch.add("AssertionError: ", _168)
        ops.prim.RaiseException(_169)
    else:
      pass
    is_batched = True
  else:
    if torch.eq(torch.dim(query), 2):
      if torch.eq(torch.dim(key), 2):
        _170 = torch.eq(torch.dim(value), 2)
      else:
        _170 = False
      if _170:
        pass
      else:
        _171 = torch.format(_154, torch.dim(key), torch.dim(value))
        _172 = torch.add("AssertionError: ", _171)
        ops.prim.RaiseException(_172)
      _173 = torch.__isnot__(key_padding_mask, None)
      if _173:
        key_padding_mask16 = unchecked_cast(Tensor, key_padding_mask)
        _174 = torch.eq(torch.dim(key_padding_mask16), 1)
        if _174:
          pass
        else:
          _175 = torch.format(_155, torch.dim(key_padding_mask16))
          _176 = torch.add("AssertionError: ", _175)
          ops.prim.RaiseException(_176)
      else:
        pass
      if torch.__isnot__(attn_mask, None):
        attn_mask21 = unchecked_cast(Tensor, attn_mask)
        _177 = torch.dim(attn_mask21)
        _178 = torch.__contains__([2, 3], _177)
        if _178:
          pass
        else:
          _179 = torch.format(_156, torch.dim(attn_mask21))
          _180 = torch.add("AssertionError: ", _179)
          ops.prim.RaiseException(_180)
        _181 = torch.eq(torch.dim(attn_mask21), 3)
        if _181:
          _182 = (torch.size(query))[0]
          _183 = (torch.size(key))[0]
          expected_shape = (num_heads, _182, _183)
          _184 = torch.eq(torch.size(attn_mask21), [num_heads, _182, _183])
          if _184:
            pass
          else:
            _185 = torch.format(_157, expected_shape, torch.size(attn_mask21))
            _186 = torch.add("AssertionError: ", _185)
            ops.prim.RaiseException(_186)
        else:
          pass
      else:
        pass
      is_batched0 = False
    else:
      _187 = torch.format(_158, torch.dim(query))
      _188 = torch.add("AssertionError: ", _187)
      ops.prim.RaiseException(_188)
      is_batched0 = _159
    is_batched = is_batched0
  return is_batched
def _in_projection_packed(q: Tensor,
    k: Tensor,
    v: Tensor,
    w: Tensor,
    b: Optional[Tensor]=None) -> List[Tensor]:
  E = torch.size(q, -1)
  if torch.__is__(k, v):
    if torch.__is__(q, k):
      proj = torch.linear(q, w, b)
      _191 = torch.unsqueeze(torch.unflatten(proj, -1, [3, E]), 0)
      _192 = torch.squeeze(torch.transpose(_191, 0, -2), -2)
      proj0 = torch.contiguous(_192)
      _193 = [torch.select(proj0, 0, 0), torch.select(proj0, 0, 1), torch.select(proj0, 0, 2)]
      _190 = _193
    else:
      _194 = torch.split(w, [E, torch.mul(E, 2)])
      w_q, w_kv, = _194
      if torch.__is__(b, None):
        b_q, b_kv = None, None
      else:
        b0 = unchecked_cast(Tensor, b)
        _195 = torch.split(b0, [E, torch.mul(E, 2)])
        b_q1, b_kv0, = _195
        b_q, b_kv = b_q1, b_kv0
      q_proj = torch.linear(q, w_q, b_q)
      kv_proj = torch.linear(k, w_kv, b_kv)
      _196 = torch.unflatten(kv_proj, -1, [2, E])
      _197 = torch.transpose(torch.unsqueeze(_196, 0), 0, -2)
      kv_proj0 = torch.contiguous(torch.squeeze(_197, -2))
      _198 = [q_proj, torch.select(kv_proj0, 0, 0), torch.select(kv_proj0, 0, 1)]
      _190 = _198
    _189 = _190
  else:
    w_q0, w_k, w_v, = torch.chunk(w, 3)
    if torch.__is__(b, None):
      b_q2, b_k, b_v = None, None, None
    else:
      b1 = unchecked_cast(Tensor, b)
      b_q3, b_k1, b_v1, = torch.chunk(b1, 3)
      b_q2, b_k, b_v = b_q3, b_k1, b_v1
    _199 = [torch.linear(q, w_q0, b_q2), torch.linear(k, w_k, b_k), torch.linear(v, w_v, b_v)]
    _189 = _199
  return _189
def _in_projection(q: Tensor,
    k: Tensor,
    v: Tensor,
    w_q: Tensor,
    w_k: Tensor,
    w_v: Tensor,
    b_q: Optional[Tensor]=None,
    b_k: Optional[Tensor]=None,
    b_v: Optional[Tensor]=None) -> Tuple[Tensor, Tensor, Tensor]:
  _200 = "expecting query weights shape of {}, but got {}"
  _201 = "expecting key weights shape of {}, but got {}"
  _202 = "expecting value weights shape of {}, but got {}"
  _203 = "expecting query bias shape of {}, but got {}"
  _204 = "expecting key bias shape of {}, but got {}"
  _205 = "expecting value bias shape of {}, but got {}"
  _206 = uninitialized(Optional[Tensor])
  _207 = uninitialized(Optional[Tensor])
  _208 = uninitialized(Optional[Tensor])
  Eq = torch.size(q, -1)
  Ek = torch.size(k, -1)
  Ev = torch.size(v, -1)
  if torch.eq(torch.size(w_q), [Eq, Eq]):
    pass
  else:
    _209 = torch.format(_200, (Eq, Eq), torch.size(w_q))
    ops.prim.RaiseException(torch.add("AssertionError: ", _209))
  if torch.eq(torch.size(w_k), [Eq, Ek]):
    pass
  else:
    _210 = torch.format(_201, (Eq, Ek), torch.size(w_k))
    ops.prim.RaiseException(torch.add("AssertionError: ", _210))
  if torch.eq(torch.size(w_v), [Eq, Ev]):
    pass
  else:
    _211 = torch.format(_202, (Eq, Ev), torch.size(w_v))
    ops.prim.RaiseException(torch.add("AssertionError: ", _211))
  if torch.__is__(b_q, None):
    _212, b_q4 = True, b_q
  else:
    b_q5 = unchecked_cast(Tensor, b_q)
    _212, b_q4 = torch.eq(torch.size(b_q5), [Eq]), b_q5
  if _212:
    b_q6 : Optional[Tensor] = b_q4
  else:
    b_q7 = unchecked_cast(Tensor, b_q4)
    _213 = torch.format(_203, (Eq,), torch.size(b_q7))
    ops.prim.RaiseException(torch.add("AssertionError: ", _213))
    b_q6 = _208
  if torch.__is__(b_k, None):
    _214, b_k2 = True, b_k
  else:
    b_k3 = unchecked_cast(Tensor, b_k)
    _214, b_k2 = torch.eq(torch.size(b_k3), [Eq]), b_k3
  if _214:
    b_k4 : Optional[Tensor] = b_k2
  else:
    b_k5 = unchecked_cast(Tensor, b_k2)
    _215 = torch.format(_204, (Eq,), torch.size(b_k5))
    ops.prim.RaiseException(torch.add("AssertionError: ", _215))
    b_k4 = _207
  if torch.__is__(b_v, None):
    _216, b_v2 = True, b_v
  else:
    b_v3 = unchecked_cast(Tensor, b_v)
    _216, b_v2 = torch.eq(torch.size(b_v3), [Eq]), b_v3
  if _216:
    b_v4 : Optional[Tensor] = b_v2
  else:
    b_v5 = unchecked_cast(Tensor, b_v2)
    _217 = torch.format(_205, (Eq,), torch.size(b_v5))
    ops.prim.RaiseException(torch.add("AssertionError: ", _217))
    b_v4 = _206
  _218 = (torch.linear(q, w_q, b_q6), torch.linear(k, w_k, b_k4), torch.linear(v, w_v, b_v4))
  return _218
