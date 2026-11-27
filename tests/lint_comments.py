# Ловит код, проглоченный комментарием: после «//» (вне строк) в той же строке идёт что-то похожее на код.
# Так трижды ломалась «Грязь»: правка скриптом вставляла «// пояснение» в середину однострочного оператора, и хвост строки молча исчезал.
# python3 tests/lint_comments.py файл.js [...] — код возврата 1, если есть подозрения
import re, sys, glob
bad = 0
files = sys.argv[1:] or sorted(f for f in glob.glob('g*/**/*.js', recursive=True) + glob.glob('core/*.js') + glob.glob('online/*.js') if '/promo/' not in f and not f.endswith('.min.js') and 'playgama-bridge' not in f)  # без аргументов — все игры: 27.11 запуск без файлов молча проверил ноль строк
for path in files:
    for n, line in enumerate(open(path, encoding='utf8').read().split('\n'), 1):
        k, ins, pos = 0, None, -1
        while k < len(line) - 1:
            ch = line[k]
            if ins:
                if ch == '\\': k += 2; continue
                if ch == ins: ins = None
            elif ch in "'\"`": ins = ch
            elif ch == '/' and line[k + 1] == '/' and (k == 0 or line[k - 1] != ':'): pos = k; break
            k += 1
        if pos < 0 or not line[:pos].strip(): continue  # строка-комментарий целиком — это просто текст
        tail = line[pos + 2:]
        if re.search(r"\)\s*;\s*[a-zA-Z_(]|;\s*(const |let |var |if \(|for \(|return\b|ctx\.|S\.|[a-zA-Z_.\[\]]+\s*(\+|-)?=[^=])", tail) or re.search(r"[а-яё.] [a-zA-Z_]+: [\[\d(a-zA-Z_]", tail) or re.search(r"[a-zA-Z_.\]]+ (\+|-)?= [^;]{1,60};\s*$", tail):
            bad += 1; print(f"{path}:{n}: после комментария похоже на код: {tail.strip()[:140]}")
print('файлов:', len(files), 'подозрений:', bad); sys.exit(1 if bad else 0)
