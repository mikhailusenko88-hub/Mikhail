class HomoSolverClean(Module):
  __parameters__ = []
  __buffers__ = []
  training : bool
  _is_full_backward_hook : Optional[bool]
  bert : __torch__.bert_custom_classes.bert_model_jit.BertModelJIT
  homo_clf : __torch__.torch.nn.modules.container.___torch_mangle_7.Sequential
  def forward(self: __torch__.homo_solver.models.model.HomoSolverClean,
    input_ids: Tensor,
    homo_start_ids: Tensor,
    homo_end_ids: Tensor) -> Tensor:
    bert = self.bert
    outputs = (bert).forward(input_ids, None, None, None, None, None, None, None, None, None, None, None, )
    hidden = (outputs)[0]
    _0 = annotate(List[Tensor], [])
    for i in range(torch.len(homo_start_ids)):
      _1 = torch.select(homo_start_ids, 0, i)
      _2 = torch.select(hidden, 0, i)
      _3 = annotate(List[Optional[Tensor]], [_1])
      marker_emb = torch.index(_2, _3)
      _4 = torch.select(homo_start_ids, 0, i)
      start = torch.add(_4, 1)
      end = torch.select(homo_end_ids, 0, i)
      _5 = torch.slice(torch.select(hidden, 0, i), 0, annotate(int, start), annotate(int, end))
      word_emb = torch.mean(_5, [0])
      _6 = torch.append(_0, torch.cat([marker_emb, word_emb]))
    homo_clf = self.homo_clf
    logits = (homo_clf).forward(torch.stack(_0), )
    return logits
