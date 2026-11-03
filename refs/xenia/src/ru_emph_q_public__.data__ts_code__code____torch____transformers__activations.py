class GELUActivation(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  _is_hf_initialized : bool
  def forward(self: __torch__.transformers.activations.GELUActivation,
    input: Tensor) -> Tensor:
    return torch.gelu(input)
