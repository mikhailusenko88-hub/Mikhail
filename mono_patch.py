#!/usr/bin/env python3
"""Проба (только для golos-probe, ветки бота не меняются): короткие слова из одного слога получают ударение,
кроме предлогов, частиц и союзов. Без ударения модель читает их как безударные: «он» → «ан», «пять» → «пить», «ток» → «так»."""
import sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
old = '''def _bot_part(w):
    if sum(c in VOW for c in w) <= 1:
        return w.replace("+", "")          # односложные — без ударения
'''
new = '''_CLIT = {"в", "во", "к", "ко", "с", "со", "у", "о", "об", "от", "до", "по", "за", "на", "над", "под", "из", "при", "про",
         "для", "без", "не", "ни", "же", "бы", "ли", "ль", "то", "и", "а", "да"}


def _bot_part(w):
    if sum(c in VOW for c in w) <= 1:
        if w.replace("+", "").lower() in _CLIT or not any(c in VOW for c in w):
            return w.replace("+", "")      # предлоги, частицы, союзы — без ударения
        if "+" in w:
            return w
        i = next(i for i, c in enumerate(w) if c in VOW)
        return w[:i] + "+" + w[i:]         # «он», «пять», «ток» — с ударением, иначе звучат «ан», «пить», «так»
'''
assert s.count(old) == 1, "не нашёл правило для односложных"
open(p, "w", encoding="utf-8").write(s.replace(old, new)); print("односложные: ударение ставится, кроме служебных слов")
