class AccentorNgramClean(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  scale : Tensor
  zero_point : Tensor
  embedding : __torch__.models.modules.NewFastTextEmbeddingBag
  stress_clf : __torch__.torch.nn.modules.container.Sequential
  yo_clf : __torch__.torch.nn.modules.container.___torch_mangle_4.Sequential
  def forward(self: __torch__.models.accentor.AccentorNgramClean,
    words: List[str]) -> Tuple[Tensor, Tensor]:
    embedding = self.embedding
    embeddings = (embedding).forward(words, )
    stress_clf = self.stress_clf
    logits_stress = (stress_clf).forward(embeddings, )
    yo_clf = self.yo_clf
    logits_yo = (yo_clf).forward(embeddings, )
    return (logits_stress, logits_yo)
