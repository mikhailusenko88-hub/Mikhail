def layer_norm(input: Tensor,
    normalized_shape: List[int],
    weight: Optional[Tensor]=None,
    bias: Optional[Tensor]=None,
    eps: float=1.0000000000000001e-05) -> Tensor:
  _0 = torch.layer_norm(input, normalized_shape, weight, bias, eps)
  return _0
