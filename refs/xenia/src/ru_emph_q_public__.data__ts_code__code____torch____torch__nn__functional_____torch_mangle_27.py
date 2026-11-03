def softmax(input: Tensor,
    dim: Optional[int]=None,
    _stacklevel: int=3,
    dtype: Optional[int]=None) -> Tensor:
  _0 = __torch__.torch.nn.functional.___torch_mangle_28._get_softmax_dim
  if torch.__is__(dim, None):
    dim1 = _0("softmax", torch.dim(input), _stacklevel, )
    dim0 = dim1
  else:
    dim0 = unchecked_cast(int, dim)
  if torch.__is__(dtype, None):
    ret = torch.softmax(input, dim0)
  else:
    dtype0 = unchecked_cast(int, dtype)
    ret = torch.softmax(input, dim0, dtype0)
  return ret
