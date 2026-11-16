#!/usr/bin/env python3
"""KORUUSDT 계약 변경(2026-07-15 18:35 KST) 이전 가격을 지금 기준으로 맞춘다 (한 번만 실행).
변경 전 코인 가격은 KORU ETF의 정확히 20배였고(ETF 종가와 비교해 비율 19.9~20.1),
거래 중지 후 18:35 KST부터 ETF와 1:1 가격으로 다시 시작했다.
→ 그 이전 봉의 가격을 ÷20, 거래량을 ×20 (주식 분할 조정과 같은 방식). 이미 조정됐으면 아무것도 안 함."""
import json, os, glob
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'chart/data/koru')
CUT = '2026-07-15'

def adj(flat):
    out = list(flat)
    for i in range(0, len(out), 5):
        if out[i] >= 10000:  # 시가 100달러 이상 = 옛 가격(새 가격은 30달러 미만)
            for j in range(4):
                out[i + j] = round(out[i + j] / 20)
            out[i + 4] = out[i + 4] * 20
    return out

p = os.path.join(ROOT, 'data.js')
s = open(p).read(); i = s.index('=') + 1
D = json.loads(s[i:].strip().rstrip(';')); n = 0
for x in D:
    if x[0] <= CUT:
        new = adj(x[2]); n += new != x[2]; x[2] = new
open(p, 'w').write(s[:i] + json.dumps(D, separators=(',', ':')) + ';')
for k in ('m1', 'm5'):
    for f in sorted(glob.glob(os.path.join(ROOT, k, '2026-0[67].json'))):
        o = json.load(open(f))
        for d in o:
            if d <= CUT:
                new = adj(o[d][1]); n += new != o[d][1]; o[d][1] = new
        open(f, 'w').write(json.dumps(o, separators=(',', ':')))
print('조정한 날·파일 수:', n)
