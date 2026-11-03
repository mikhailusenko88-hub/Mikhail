class Dropout(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : NoneType
  p : Final[float] = 0.10000000000000001
  inplace : Final[bool] = False
  def forward(self: __torch__.torch.nn.modules.dropout.___torch_mangle_14.Dropout,
    input: Tensor) -> Tensor:
    _0 = __torch__.torch.nn.functional.___torch_mangle_24.dropout
    training = self.training
    _1 = _0(input, 0.10000000000000001, training, False, )
    return _1
