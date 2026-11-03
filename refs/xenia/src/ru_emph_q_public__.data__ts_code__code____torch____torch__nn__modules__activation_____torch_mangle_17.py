class ReLU(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : NoneType
  inplace : Final[bool] = False
  def forward(self: __torch__.torch.nn.modules.activation.___torch_mangle_17.ReLU,
    input: Tensor) -> Tensor:
    _0 = __torch__.torch.nn.functional.___torch_mangle_26.relu
    return _0(input, False, )
class MultiheadAttention(Module):
  __parameters__ = ["in_proj_weight", "q_proj_weight", "k_proj_weight", "v_proj_weight", "in_proj_bias", ]
  __buffers__ = []
  in_proj_weight : Tensor
  q_proj_weight : NoneType
  k_proj_weight : NoneType
  v_proj_weight : NoneType
  in_proj_bias : Tensor
  training : bool
  _is_full_backward_hook : NoneType
  embed_dim : int
  kdim : int
  vdim : int
  _qkv_same_embed_dim : bool
  num_heads : int
  dropout : float
  head_dim : int
  bias_k : Optional[Tensor]
  bias_v : Optional[Tensor]
  add_zero_attn : bool
  out_proj : __torch__.torch.nn.modules.linear.___torch_mangle_16.NonDynamicallyQuantizableLinear
  batch_first : Final[bool] = True
  def forward(self: __torch__.torch.nn.modules.activation.___torch_mangle_17.MultiheadAttention,
    query: Tensor,
    key: Tensor,
    value: Tensor,
    key_padding_mask: Optional[Tensor]=None,
    need_weights: bool=True,
    attn_mask: Optional[Tensor]=None,
    average_attn_weights: bool=True,
    is_causal: bool=False) -> Tuple[Tensor, Optional[Tensor]]:
    _1 = "AssertionError: Only allow causal mask or attn_mask"
    _2 = __torch__.torch.nn.functional._none_or_dtype
    _3 = __torch__.torch.nn.functional._canonical_mask
    _4 = "input not batched; expected query.dim() of 3 but got {}"
    why_not_fast_path = "non-self attention was used (query, key, and value are not the same Tensor)"
    _5 = "dtypes of query ({}) and self.in_proj_bias ({}) don\'t match"
    _6 = "dtypes of query ({}) and self.in_proj_weight ({}) don\'t match"
    why_not_fast_path0 = "supplying both src_key_padding_mask and src_mask at the same time                              is not supported with NestedTensor input"
    why_not_fast_path1 = "some Tensor argument is neither CUDA nor CPU"
    why_not_fast_path2 = "grad is enabled and at least one of query or the input/output projection weights or biases requires_grad"
    _7 = "The fast path was not hit because {}"
    _8 = "MultiheadAttention does not support NestedTensor outside of its fast path. "
    _9 = __torch__.torch.nn.functional.multi_head_attention_forward
    _10 = uninitialized(Tuple[Tensor, Tensor])
    _11 = uninitialized(Optional[Tensor])
    if torch.__isnot__(attn_mask, None):
      _12, attn_mask0 = is_causal, unchecked_cast(Tensor, attn_mask)
    else:
      _12, attn_mask0 = False, attn_mask
    if _12:
      ops.prim.RaiseException(_1)
      attn_mask1 : Optional[Tensor] = _11
    else:
      attn_mask1 = attn_mask0
    is_batched = torch.eq(torch.dim(query), 3)
    key_padding_mask0 = _3(key_padding_mask, "key_padding_mask", _2(attn_mask1, ), "attn_mask", ops.prim.dtype(query), True, )
    if torch.__not__(is_batched):
      why_not_fast_path4 = torch.format(_4, torch.dim(query))
      why_not_fast_path3, key_padding_mask1 = why_not_fast_path4, key_padding_mask0
    else:
      if torch.__isnot__(query, key):
        _13 = True
      else:
        _13 = torch.__isnot__(key, value)
      if _13:
        why_not_fast_path5, key_padding_mask2 = why_not_fast_path, key_padding_mask0
      else:
        _14 = ops.prim.dtype(query)
        in_proj_bias = self.in_proj_bias
        _15 = torch.ne(_14, ops.prim.dtype(in_proj_bias))
        if _15:
          _16 = ops.prim.dtype(query)
          in_proj_bias0 = self.in_proj_bias
          why_not_fast_path7 = torch.format(_5, _16, ops.prim.dtype(in_proj_bias0))
          why_not_fast_path6, key_padding_mask3 = why_not_fast_path7, key_padding_mask0
        else:
          _17 = ops.prim.dtype(query)
          in_proj_weight = self.in_proj_weight
          _18 = ops.prim.dtype(in_proj_weight)
          if torch.ne(_17, _18):
            _19 = ops.prim.dtype(query)
            in_proj_weight0 = self.in_proj_weight
            _20 = ops.prim.dtype(in_proj_weight0)
            why_not_fast_path8, key_padding_mask4 = torch.format(_6, _19, _20), key_padding_mask0
          else:
            training = self.training
            if training:
              why_not_fast_path9, key_padding_mask5 = "training is enabled", key_padding_mask0
            else:
              bias_k = self.bias_k
              _21 = torch.__isnot__(bias_k, None)
              if _21:
                why_not_fast_path10, key_padding_mask6 = "self.bias_k was not None", key_padding_mask0
              else:
                bias_v = self.bias_v
                _22 = torch.__isnot__(bias_v, None)
                if _22:
                  why_not_fast_path11, key_padding_mask7 = "self.bias_v was not None", key_padding_mask0
                else:
                  add_zero_attn = self.add_zero_attn
                  if add_zero_attn:
                    why_not_fast_path12, key_padding_mask8 = "add_zero_attn was enabled", key_padding_mask0
                  else:
                    _qkv_same_embed_dim = self._qkv_same_embed_dim
                    _23 = torch.__not__(_qkv_same_embed_dim)
                    if _23:
                      why_not_fast_path13, key_padding_mask9 = "_qkv_same_embed_dim was not True", key_padding_mask0
                    else:
                      _24 = ops.prim.is_nested(query)
                      if _24:
                        _26 = torch.__isnot__(key_padding_mask0, None)
                        if _26:
                          key_padding_mask12 = unchecked_cast(Tensor, key_padding_mask0)
                          _27, key_padding_mask11 = True, key_padding_mask12
                        else:
                          _28 = torch.__isnot__(attn_mask1, None)
                          _27, key_padding_mask11 = _28, key_padding_mask0
                        _25, key_padding_mask10 = _27, key_padding_mask11
                      else:
                        _25, key_padding_mask10 = False, key_padding_mask0
                      if _25:
                        why_not_fast_path14 = why_not_fast_path0
                      else:
                        _29 = torch.is_autocast_enabled()
                        if _29:
                          why_not_fast_path15 = "autocast is enabled"
                        else:
                          why_not_fast_path15 = ""
                        why_not_fast_path14 = why_not_fast_path15
                      why_not_fast_path13, key_padding_mask9 = why_not_fast_path14, key_padding_mask10
                    why_not_fast_path12, key_padding_mask8 = why_not_fast_path13, key_padding_mask9
                  why_not_fast_path11, key_padding_mask7 = why_not_fast_path12, key_padding_mask8
                why_not_fast_path10, key_padding_mask6 = why_not_fast_path11, key_padding_mask7
              why_not_fast_path9, key_padding_mask5 = why_not_fast_path10, key_padding_mask6
            why_not_fast_path8, key_padding_mask4 = why_not_fast_path9, key_padding_mask5
          why_not_fast_path6, key_padding_mask3 = why_not_fast_path8, key_padding_mask4
        why_not_fast_path5, key_padding_mask2 = why_not_fast_path6, key_padding_mask3
      why_not_fast_path3, key_padding_mask1 = why_not_fast_path5, key_padding_mask2
    _30 = torch.gt(torch.len(why_not_fast_path3), 0)
    if torch.__not__(_30):
      in_proj_weight1 = self.in_proj_weight
      in_proj_bias1 = self.in_proj_bias
      out_proj = self.out_proj
      weight = out_proj.weight
      out_proj0 = self.out_proj
      bias = out_proj0.bias
      _33 = annotate(List[bool], [])
      if ops.prim.is_cuda(query):
        _34 = True
      else:
        _35 = str(ops.prim.device(query))
        _36 = torch.find(_35, "cpu", 0, torch.len(_35))
        _34 = torch.ne(_36, -1)
      _37 = torch.append(_33, _34)
      if ops.prim.is_cuda(key):
        _38 = True
      else:
        _39 = str(ops.prim.device(key))
        _40 = torch.find(_39, "cpu", 0, torch.len(_39))
        _38 = torch.ne(_40, -1)
      _41 = torch.append(_33, _38)
      if ops.prim.is_cuda(value):
        _42 = True
      else:
        _43 = str(ops.prim.device(value))
        _44 = torch.find(_43, "cpu", 0, torch.len(_43))
        _42 = torch.ne(_44, -1)
      _45 = torch.append(_33, _42)
      if ops.prim.is_cuda(in_proj_weight1):
        _46 = True
      else:
        _47 = ops.prim.device(in_proj_weight1)
        _48 = str(_47)
        _49 = torch.find(_48, "cpu", 0, torch.len(_48))
        _46 = torch.ne(_49, -1)
      _50 = torch.append(_33, _46)
      if ops.prim.is_cuda(in_proj_bias1):
        _51 = True
      else:
        _52 = str(ops.prim.device(in_proj_bias1))
        _53 = torch.find(_52, "cpu", 0, torch.len(_52))
        _51 = torch.ne(_53, -1)
      _54 = torch.append(_33, _51)
      if ops.prim.is_cuda(weight):
        _55 = True
      else:
        _56 = str(ops.prim.device(weight))
        _57 = torch.find(_56, "cpu", 0, torch.len(_56))
        _55 = torch.ne(_57, -1)
      _58 = torch.append(_33, _55)
      if ops.prim.is_cuda(bias):
        _59 = True
      else:
        _60 = str(ops.prim.device(bias))
        _61 = torch.find(_60, "cpu", 0, torch.len(_60))
        _59 = torch.ne(_61, -1)
      _62 = torch.append(_33, _59)
      if torch.__not__(torch.all(_33)):
        why_not_fast_path17 = why_not_fast_path1
      else:
        if torch.is_grad_enabled():
          _64 = annotate(List[bool], [])
          _65 = torch.append(_64, ops.prim.requires_grad(query))
          _66 = torch.append(_64, ops.prim.requires_grad(key))
          _67 = torch.append(_64, ops.prim.requires_grad(value))
          _68 = ops.prim.requires_grad(in_proj_weight1)
          _69 = torch.append(_64, _68)
          _70 = ops.prim.requires_grad(in_proj_bias1)
          _71 = torch.append(_64, _70)
          _72 = ops.prim.requires_grad(weight)
          _73 = torch.append(_64, _72)
          _74 = torch.append(_64, ops.prim.requires_grad(bias))
          _63 = torch.any(_64)
        else:
          _63 = False
        if _63:
          why_not_fast_path18 = why_not_fast_path2
        else:
          why_not_fast_path18 = why_not_fast_path3
        why_not_fast_path17 = why_not_fast_path18
      _75 = torch.gt(torch.len(why_not_fast_path17), 0)
      if torch.__not__(_75):
        _78 = (self).merge_masks(attn_mask1, key_padding_mask1, query, )
        merged_mask, mask_type, = _78
        embed_dim = self.embed_dim
        num_heads = self.num_heads
        in_proj_weight2 = self.in_proj_weight
        in_proj_bias2 = self.in_proj_bias
        out_proj1 = self.out_proj
        weight0 = out_proj1.weight
        out_proj2 = self.out_proj
        bias0 = out_proj2.bias
        _79, _80 = torch._native_multi_head_attention(query, key, value, embed_dim, num_heads, in_proj_weight2, in_proj_bias2, weight0, bias0, merged_mask, need_weights, average_attn_weights, mask_type)
        _76, _77 = True, (_79, _80)
      else:
        _76, _77 = False, _10
      _31, _32, why_not_fast_path16 = _76, _77, why_not_fast_path17
    else:
      _31, _32, why_not_fast_path16 = False, _10, why_not_fast_path3
    if _31:
      _81 = _32
    else:
      if ops.prim.is_nested(query):
        _82 = True
      else:
        _82 = ops.prim.is_nested(key)
      if _82:
        any_nested = True
      else:
        any_nested = ops.prim.is_nested(value)
      if torch.__not__(any_nested):
        pass
      else:
        _83 = torch.format(_7, why_not_fast_path16)
        _84 = torch.add("AssertionError: ", torch.add(_8, _83))
        ops.prim.RaiseException(_84)
      if is_batched:
        if torch.__is__(key, value):
          if torch.__is__(query, key):
            _85 = torch.transpose(query, 1, 0)
            query2, key2, value2 = _85, _85, _85
          else:
            _86 = annotate(List[Tensor], [])
            _87 = torch.transpose(query, 1, 0)
            _88 = torch.append(_86, _87)
            _89 = torch.append(_86, torch.transpose(key, 1, 0))
            query3, key3, = _86
            query2, key2, value2 = query3, key3, key3
          query1, key1, value1 = query2, key2, value2
        else:
          _90 = annotate(List[Tensor], [])
          _91 = torch.append(_90, torch.transpose(query, 1, 0))
          _92 = torch.append(_90, torch.transpose(key, 1, 0))
          _93 = torch.append(_90, torch.transpose(value, 1, 0))
          query4, key4, value3, = _90
          query1, key1, value1 = query4, key4, value3
        query0, key0, value0 = query1, key1, value1
      else:
        query0, key0, value0 = query, key, value
      _qkv_same_embed_dim0 = self._qkv_same_embed_dim
      _94 = torch.__not__(_qkv_same_embed_dim0)
      if _94:
        embed_dim0 = self.embed_dim
        num_heads0 = self.num_heads
        in_proj_weight3 = self.in_proj_weight
        in_proj_bias3 = self.in_proj_bias
        bias_k0 = self.bias_k
        bias_v0 = self.bias_v
        add_zero_attn0 = self.add_zero_attn
        dropout = self.dropout
        out_proj3 = self.out_proj
        weight1 = out_proj3.weight
        out_proj4 = self.out_proj
        bias1 = out_proj4.bias
        training0 = self.training
        q_proj_weight = self.q_proj_weight
        k_proj_weight = self.k_proj_weight
        v_proj_weight = self.v_proj_weight
        _95 = _9(query0, key0, value0, embed_dim0, num_heads0, in_proj_weight3, in_proj_bias3, bias_k0, bias_v0, add_zero_attn0, dropout, weight1, bias1, training0, key_padding_mask1, need_weights, attn_mask1, True, q_proj_weight, k_proj_weight, v_proj_weight, None, None, average_attn_weights, is_causal, )
        attn_output0, attn_output_weights0, = _95
        attn_output, attn_output_weights = attn_output0, attn_output_weights0
      else:
        embed_dim1 = self.embed_dim
        num_heads1 = self.num_heads
        in_proj_weight4 = self.in_proj_weight
        in_proj_bias4 = self.in_proj_bias
        bias_k1 = self.bias_k
        bias_v1 = self.bias_v
        add_zero_attn1 = self.add_zero_attn
        dropout0 = self.dropout
        out_proj5 = self.out_proj
        weight2 = out_proj5.weight
        out_proj6 = self.out_proj
        bias2 = out_proj6.bias
        training1 = self.training
        _96 = _9(query0, key0, value0, embed_dim1, num_heads1, in_proj_weight4, in_proj_bias4, bias_k1, bias_v1, add_zero_attn1, dropout0, weight2, bias2, training1, key_padding_mask1, need_weights, attn_mask1, False, None, None, None, None, None, average_attn_weights, is_causal, )
        attn_output1, attn_output_weights1, = _96
        attn_output, attn_output_weights = attn_output1, attn_output_weights1
      if is_batched:
        _98 = torch.transpose(attn_output, 1, 0)
        _97 = (_98, attn_output_weights)
      else:
        _99 = (attn_output, attn_output_weights)
        _97 = _99
      _81 = _97
    return _81
  def merge_masks(self: __torch__.torch.nn.modules.activation.___torch_mangle_17.MultiheadAttention,
    attn_mask: Optional[Tensor],
    key_padding_mask: Optional[Tensor],
    query: Tensor) -> Tuple[Optional[Tensor], Optional[int]]:
    _100 = __torch__.torch.nn.functional._none_or_dtype
    _101 = __torch__.torch.nn.functional._canonical_mask
    attn_mask2 = _101(attn_mask, "attn_mask", _100(key_padding_mask, ), "key_padding_mask", ops.prim.dtype(query), False, )
    if torch.__isnot__(attn_mask2, None):
      attn_mask4 = unchecked_cast(Tensor, attn_mask2)
      merged_mask, mask_type, attn_mask3 = attn_mask4, 0, attn_mask4
    else:
      merged_mask, mask_type, attn_mask3 = None, None, attn_mask2
    _102 = torch.__isnot__(key_padding_mask, None)
    if _102:
      key_padding_mask14 = unchecked_cast(Tensor, key_padding_mask)
      key_padding_mask13, merged_mask0, mask_type0 = key_padding_mask14, key_padding_mask14, 1
    else:
      key_padding_mask13, merged_mask0, mask_type0 = key_padding_mask, merged_mask, mask_type
    if torch.__isnot__(attn_mask3, None):
      attn_mask6 = unchecked_cast(Tensor, attn_mask3)
      _104 = torch.__isnot__(key_padding_mask13, None)
      _103, attn_mask5 = _104, attn_mask6
    else:
      _103, attn_mask5 = False, attn_mask3
    if _103:
      attn_mask7 = unchecked_cast(Tensor, attn_mask5)
      key_padding_mask15 = unchecked_cast(Tensor, key_padding_mask13)
      batch_size, seq_len, _105, = torch.size(query)
      _106 = torch.view(key_padding_mask15, [batch_size, 1, 1, seq_len])
      num_heads = self.num_heads
      key_padding_mask_expanded = torch.expand(_106, [-1, num_heads, -1, -1])
      _107 = torch.view(attn_mask7, [1, 1, seq_len, seq_len])
      num_heads2 = self.num_heads
      attn_mask_expanded = torch.expand(_107, [batch_size, num_heads2, -1, -1])
      merged_mask2 = torch.add(attn_mask_expanded, key_padding_mask_expanded)
      merged_mask1, mask_type1 = merged_mask2, 2
    else:
      merged_mask1, mask_type1 = merged_mask0, mask_type0
    return (merged_mask1, mask_type1)
