def _get_softmax_dim(name: str,
    ndim: int,
    stacklevel: int) -> int:
  _0 = "Implicit dimension choice for {} has been deprecated. Change the call to include dim=X as an argument."
  torch.warn(torch.format(_0, name), stacklevel)
  if torch.eq(ndim, 0):
    _1 = True
  else:
    _1 = torch.eq(ndim, 1)
  if _1:
    _2 = True
  else:
    _2 = torch.eq(ndim, 3)
  if _2:
    ret = 0
  else:
    ret = 1
  return ret
