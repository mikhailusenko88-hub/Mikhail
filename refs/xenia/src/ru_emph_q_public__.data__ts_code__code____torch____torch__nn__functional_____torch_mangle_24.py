def dropout(input: Tensor,
    p: float=0.5,
    training: bool=True,
    inplace: bool=False) -> Tensor:
  _0 = "dropout probability has to be between 0 and 1, but got {}"
  if torch.lt(p, 0.):
    _1 = True
  else:
    _1 = torch.gt(p, 1.)
  if _1:
    ops.prim.RaiseException(torch.format(_0, p), "builtins.ValueError")
  else:
    pass
  if inplace:
    _2 = torch.dropout_(input, p, training)
  else:
    _2 = torch.dropout(input, p, training)
  return _2
