class Linear(Module):
  __parameters__ = ["weight", "bias", ]
  __buffers__ = []
  weight : Tensor
  bias : Tensor
  training : bool
  _is_full_backward_hook : NoneType
  out_features : Final[int] = 64
  in_features : Final[int] = 16
  def forward(self: __torch__.torch.nn.modules.linear.Linear,
    input: Tensor) -> Tensor:
    weight = self.weight
    bias = self.bias
    return torch.linear(input, weight, bias)
class NonDynamicallyQuantizableLinear(Module):
  __parameters__ = ["weight", "bias", ]
  __buffers__ = []
  weight : Tensor
  bias : Tensor
  training : bool
  _is_full_backward_hook : NoneType
  out_features : Final[int] = 128
  in_features : Final[int] = 128
  def forward(self: __torch__.torch.nn.modules.linear.NonDynamicallyQuantizableLinear,
    input: Tensor) -> Tensor:
    weight = self.weight
    bias = self.bias
    return torch.linear(input, weight, bias)
