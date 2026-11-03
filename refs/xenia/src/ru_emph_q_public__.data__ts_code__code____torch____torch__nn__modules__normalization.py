class LayerNorm(Module):
  __parameters__ = ["weight", "bias", ]
  __buffers__ = []
  weight : Tensor
  bias : Tensor
  training : bool
  _is_full_backward_hook : NoneType
  _is_hf_initialized : bool
  elementwise_affine : Final[bool] = True
  normalized_shape : Final[Tuple[int]] = (312,)
  eps : Final[float] = 9.9999999999999998e-13
  def forward(self: __torch__.torch.nn.modules.normalization.LayerNorm,
    input: Tensor) -> Tensor:
    _0 = __torch__.torch.nn.functional.layer_norm
    weight = self.weight
    bias = self.bias
    _1 = _0(input, [312], weight, bias, 9.9999999999999998e-13, )
    return _1
