def embedding(input: Tensor,
    weight: Tensor,
    padding_idx: Optional[int]=None,
    max_norm: Optional[float]=None,
    norm_type: float=2.,
    scale_grad_by_freq: bool=False,
    sparse: bool=False) -> Tensor:
  _0 = "AssertionError: Padding_idx must be within num_embeddings"
  if torch.__isnot__(padding_idx, None):
    padding_idx1 = unchecked_cast(int, padding_idx)
    if torch.gt(padding_idx1, 0):
      _1 = torch.lt(padding_idx1, torch.size(weight, 0))
      if _1:
        pass
      else:
        ops.prim.RaiseException(_0)
      padding_idx2 = padding_idx1
    else:
      if torch.lt(padding_idx1, 0):
        _2 = torch.neg(torch.size(weight, 0))
        if torch.ge(padding_idx1, _2):
          pass
        else:
          ops.prim.RaiseException(_0)
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
  _3 = torch.embedding(weight, input0, padding_idx0, scale_grad_by_freq, sparse)
  return _3
