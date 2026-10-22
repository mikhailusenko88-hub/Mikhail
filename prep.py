import json
b = json.load(open('/root/clips-bot/topics.json', encoding='utf-8'))
s = next(x for x in b if x['title'].startswith('Сутки на Венере'))
json.dump(s, open('script.json', 'w', encoding='utf-8'), ensure_ascii=False)
# ударения для Silero: «+» перед ударной гласной
fix = {'своей оси': 'своей +оси', 'облетает': 'облет+ает', 'встаёт': 'вста+ёт'}
acc = []
for l in s['lines']:
    for a, z in fix.items():
        l = l.replace(a, z)
    acc.append(l.replace('—', ','))
json.dump(acc, open('lines.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('Сценарий:', s['title'])
