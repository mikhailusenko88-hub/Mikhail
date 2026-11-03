class NewFastTextEmbeddingBag(Module):
  __parameters__ = ["weight", ]
  __buffers__ = []
  weight : Tensor
  device : NoneType
  ngram_dict : Dict[str, int]
  training : bool
  _is_full_backward_hook : NoneType
  att_module : NoneType
  num_embeddings : Final[int] = 126523
  include_last_offset : Final[bool] = False
  scale_grad_by_freq : Final[bool] = False
  sparse : Final[bool] = False
  max_norm : Final[NoneType] = None
  mode : Final[str] = "mean"
  norm_type : Final[float] = 2.
  padding_idx : Final[NoneType] = None
  embedding_dim : Final[int] = 16
  def forward(self: __torch__.models.modules.NewFastTextEmbeddingBag,
    words: List[str]) -> Tensor:
    _0 = __torch__.models.modules.word_ngrams
    _1 = __torch__.torch.nn.functional.embedding_bag
    word_subinds = annotate(List[int], [])
    word_offsets = [0]
    for _2 in range(torch.len(words)):
      word = words[_2]
      subinds = annotate(List[int], [])
      _3 = _0(word, 1, torch.add(torch.len(word), 3), )
      for _4 in range(torch.len(_3)):
        gram = _3[_4]
        ngram_dict = self.ngram_dict
        _5 = torch.__contains__(ngram_dict, gram)
        if _5:
          ngram_dict0 = self.ngram_dict
          _6 = torch.append(subinds, ngram_dict0[gram])
        else:
          pass
      if torch.eq(torch.len(subinds), 0):
        ngram_dict1 = self.ngram_dict
        _7 = torch.append(subinds, ngram_dict1["UNK"])
      else:
        pass
      torch.extend(word_subinds, subinds)
      _8 = torch.add(word_offsets[-1], torch.len(subinds))
      _9 = torch.append(word_offsets, _8)
    _word_offsets = torch.slice(word_offsets, None, -1)
    _10 = torch.tensor(word_subinds)
    device = self.device
    ind = torch.to(_10, device)
    _11 = torch.tensor(_word_offsets)
    device0 = self.device
    offsets = torch.to(_11, device0)
    weight = self.weight
    _12 = _1(ind, weight, offsets, None, 2., False, "mean", False, None, False, None, )
    return _12
def word_ngrams(text: str,
    min_len: int=3,
    max_len: int=6) -> List[str]:
  ngrams = annotate(List[str], [])
  _13 = torch.__range_length(min_len, torch.add(max_len, 1), 1)
  for _14 in range(_13):
    i = torch.__derive_index(_14, min_len, 1)
    _15 = torch.add(torch.add("<", text), ">")
    _16 = __torch__.models.modules.find_ngrams(_15, i, )
    torch.extend(ngrams, _16)
  if torch.lt(torch.len(text), min_len):
    _17 = torch.append(ngrams, text)
  else:
    pass
  return ngrams
def find_ngrams(text: str,
    n: int) -> List[str]:
  ngrams = annotate(List[str], [])
  _18 = torch.add(torch.sub(torch.len(text), n), 1)
  for i in range(_18):
    _19 = torch.slice(text, i, torch.add(i, n))
    _20 = torch.append(ngrams, torch.join("", [_19]))
  return ngrams
