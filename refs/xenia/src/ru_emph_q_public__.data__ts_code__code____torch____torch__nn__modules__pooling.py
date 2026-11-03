class AvgPool1d(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : NoneType
  count_include_pad : Final[bool] = True
  stride : Final[Tuple[int]] = (3,)
  padding : Final[Tuple[int]] = (0,)
  ceil_mode : Final[bool] = False
  kernel_size : Final[Tuple[int]] = (3,)
  def forward(self: __torch__.torch.nn.modules.pooling.AvgPool1d,
    input: Tensor) -> Tensor:
    _0 = torch.avg_pool1d(input, [3], [3], [0])
    return _0
