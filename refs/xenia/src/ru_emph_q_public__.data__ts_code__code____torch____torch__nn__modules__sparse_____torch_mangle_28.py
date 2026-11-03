class Embedding(Module):
  __parameters__ = ["weight", ]
  __buffers__ = []
  weight : Tensor
  training : bool
  _is_full_backward_hook : NoneType
  padding_idx : Final[NoneType] = None
  scale_grad_by_freq : Final[bool] = False
  max_norm : Final[NoneType] = None
  embedding_dim : Final[int] = 64
  norm_type : Final[float] = 2.
  num_embeddings : Final[int] = 4
  sparse : Final[bool] = False
  def forward(self: __torch__.torch.nn.modules.sparse.___torch_mangle_28.Embedding,
    input: Tensor) -> Tensor:
    _0 = __torch__.torch.nn.functional.___torch_mangle_23.embedding
    weight = self.weight
    _1 = _0(input, weight, None, None, 2., False, False, )
    return _1
