#!/usr/bin/env python3
"""아침 09:00~09:30(한국시간) 3분봉 사진과 가장 비슷한 날을 찾는다.

사용:
  python tools/pattern/find_similar.py 사진.png            # KORU, 결과 그림 저장
  python tools/pattern/find_similar.py 사진.png --sym soxl
  옵션: --crop x0,y0,x1,y1  (가격 차트 부분만 잘라 쓰기)
        --skip N / --take N   (사진 속 캔들 중 앞에서 N개 건너뛰기 / N개만 쓰기)
        --colors gr|rb         (gr=초록 상승·빨강 하락(바이낸스), rb=빨강 상승·파랑 하락(국내))
        --top K  --out 폴더  --before YYYY-MM-DD (그 날 이전만 비교)

비교 방법: 사진의 캔들 n개(보통 09:00~09:27 시작 10개)의 시가·고가·저가·종가를
첫 시가 기준, 전체 높낮이(최고-최저)로 나눠 모양만 남기고, 과거 각 날의 첫 n개
3분봉도 똑같이 바꿔서 차이(RMS)가 가장 작은 날을 고른다. 사진에는 가격 눈금이
없을 수 있으므로 "모양"만 비교한다.
"""
import argparse, json, os, sys
from datetime import date, timedelta
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------- 데이터 ----------
def load_days(sym):
    t = open(os.path.join(ROOT, 'chart/data', sym, 'data.js')).read()
    D = json.loads(t[t.index('=') + 1:].strip().rstrip(';'))
    days = {}
    for d, first, flat in D:
        a = np.array(flat, dtype=float).reshape(-1, 5) / 100.0
        full = np.full((480, 5), np.nan)
        full[first:first + len(a)] = a[:480 - first]
        days[d] = full
    return days


# ---------- 사진에서 캔들 뽑기 ----------
def extract(path, crop=None, colors=None):
    im = np.asarray(Image.open(path).convert('RGB')).astype(int)
    if crop:
        x0, y0, x1, y1 = crop
        im = im[y0:y1, x0:x1]
    H, W, _ = im.shape
    flat = im.reshape(-1, 3)
    vals, cnt = np.unique(flat // 4, axis=0, return_counts=True)
    bg = vals[cnt.argmax()] * 4 + 2
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    mx, mn = im.max(2), im.min(2)
    sat = (mx - mn) > 50
    red = sat & (r > g + 40) & (r > b + 30) & (g < 0.55 * r)  # 주황 제외
    grn = sat & (g > r + 30) & (g >= b - 10)
    blu = sat & (b > r + 40) & (b > g + 10) & (g > r) & ~grn  # 보라 제외
    if colors is None:
        colors = 'gr' if grn.sum() > blu.sum() else 'rb'
    if colors == 'gr':
        up, dn = grn, red
    else:
        up, dn = red, blu
    col = up | dn
    # 가격 패널 고르기: 색 픽셀이 있는 행들을 띠로 나눠 가장 키 큰 띠
    rows = col.sum(1) > 0
    bands, s = [], None
    gap = 0
    for y in range(H + 1):
        on = y < H and rows[y]
        if on:
            if s is None: s = y
            gap = 0; e = y
        elif s is not None:
            gap += 1
            if gap > max(8, H // 40) or y == H:
                bands.append((s, e)); s = None
    if not bands:
        raise SystemExit('사진에서 캔들 색을 찾지 못했습니다')
    by0, by1 = max(bands, key=lambda b: (b[1] - b[0]) * 1.0 + col[b[0]:b[1] + 1].sum() * 1e-6)
    colm = col[by0:by1 + 1]
    cols = colm.sum(0)
    # 캔들 = 색 픽셀이 있는 열의 연속 구간
    runs, s = [], None
    for x in range(W + 1):
        on = x < W and cols[x] > 0
        if on and s is None: s = x
        if not on and s is not None:
            runs.append((s, x - 1)); s = None
    wmax = max(e - s + 1 for s, e in runs)
    runs = [rr for rr in runs if (rr[1] - rr[0] + 1) >= max(2, wmax * 0.35)]
    bgd = np.abs(im - bg).sum(2) > 45  # 배경과 다른 픽셀(회색 꼬리 포함)
    out = []
    for x0, x1 in runs:
        w = x1 - x0 + 1
        sub = colm[:, x0:x1 + 1]
        widths = sub.sum(1)
        body = np.where(widths >= max(1, 0.6 * w))[0]
        if len(body) == 0:
            continue
        top, bot = by0 + body.min(), by0 + body.max()
        upc = up[by0:by1 + 1, x0:x1 + 1].sum() >= dn[by0:by1 + 1, x0:x1 + 1].sum()
        cx = (x0 + x1) // 2
        xs = [x for x in (cx - 1, cx, cx + 1) if 0 <= x < W]
        okcol = {}
        for x in xs:  # 세로 격자선 색은 꼬리로 치지 않기
            colv = im[by0:by1 + 1, x]
            q = colv // 8
            v, k = np.unique(q, axis=0, return_counts=True)
            m = v[k.argmax()] * 8 + 4
            grid = k.max() > 0.6 * len(colv) and np.abs(m - bg).sum() > 20
            okcol[x] = bgd[:, x] & (~(np.abs(im[:, x] - m).sum(1) < 30) if grid else True)
        isw = lambda y: any(okcol[x][y] for x in xs)
        hi = top
        while hi - 1 >= max(0, by0 - 2) and isw(hi - 1):
            hi -= 1
        lo = bot
        while lo + 1 < min(H, by1 + 3) and isw(lo + 1):
            lo += 1
        # 가격 = -y (위가 높음)
        o, c = (-bot, -top) if upc else (-top, -bot)
        out.append(dict(x0=x0, x1=x1, o=o, h=-hi, l=-lo, c=c, up=bool(upc)))
    return out, (by0, by1), colors, im


def debug_overlay(im, cs, path):
    from PIL import ImageDraw
    img = Image.fromarray(im.astype(np.uint8)).convert('RGB')
    d = ImageDraw.Draw(img)
    for i, c in enumerate(cs):
        d.rectangle([c['x0'] - 1, -c['h'], c['x1'] + 1, -c['l']], outline=(255, 160, 0))
        d.text((c['x0'], -c['l'] + 2), str(i + 1), fill=(255, 120, 0))
    img.save(path)


# ---------- 비교 ----------
def norm(ohlc):
    a = np.asarray(ohlc, float)
    rng = np.nanmax(a[:, 1]) - np.nanmin(a[:, 2])
    return (a[:, :4] - a[0, 0]) / (rng if rng > 0 else 1)


def rank(q, days, before=None, start=0, exclude=()):
    qn = norm(q)
    n = len(q)
    res = []
    for d, a in days.items():
        if before and d >= before:
            continue
        if d in exclude:
            continue
        seg = a[start:start + n, :4]
        if np.isnan(seg).any():
            continue
        cn = norm(seg)
        # 종가·시가 비중을 조금 더
        w = np.array([1.2, 0.8, 0.8, 1.2])
        dist = float(np.sqrt((((qn - cn) ** 2) * w).mean()))
        res.append((dist, d))
    res.sort()
    return res


# ---------- 그림 ----------
def draw_candles(ax, a, x0=0, up='#d6283a', dn='#1f5fd1', wick='#8a919c', width=0.62):
    for i, (o, h, l, c) in enumerate(a[:, :4]):
        if np.isnan(o):
            continue
        x = x0 + i
        colr = up if c >= o else dn
        ax.vlines(x, l, h, color=wick if len(a) > 60 else colr, lw=0.6 if len(a) > 60 else 1.0, zorder=1)
        ax.add_patch(__import__('matplotlib').patches.Rectangle(
            (x - width / 2, min(o, c)), width, max(abs(c - o), (np.nanmax(a[:, 1]) - np.nanmin(a[:, 2])) * 0.012), color=colr, lw=0, zorder=2))


def hhmm(i):
    m = 9 * 60 + 3 * i
    return f'{(m // 60) % 24:02d}:{m % 60:02d}'


def render(qohlc, best, days, sym, out, others, start=0):
    import matplotlib, logging
    matplotlib.use('Agg')
    logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for f in ['WenQuanYi Zen Hei', 'Noto Sans CJK KR', 'NanumGothic']:
        if any(f in x.name for x in font_manager.fontManager.ttflist):
            plt.rcParams['font.family'] = f; break
    plt.rcParams['axes.unicode_minus'] = False
    dist, d = best
    a = days[d]
    n = len(qohlc)
    wd = '월화수목금토일'[date.fromisoformat(d).weekday()]
    fig = plt.figure(figsize=(14, 8.6), dpi=110)
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.55], width_ratios=[1, 1], hspace=0.32, wspace=0.12)
    # 1) 사진에서 읽은 모양
    ax1 = fig.add_subplot(gs[0, 0])
    qn = norm(qohlc)
    draw_candles(ax1, np.c_[qn, np.zeros(n)])
    ax1.set_title(f'보내준 사진 (캔들 {n}개, 모양만)', fontsize=12)
    ax1.set_yticks([]); ax1.set_xticks(range(n)); ax1.set_xticklabels([hhmm(start + i) for i in range(n)], fontsize=7, rotation=45)
    ax1.set_xlim(-0.8, n - 0.2)
    # 2) 찾은 날 09:00~
    ax2 = fig.add_subplot(gs[0, 1])
    seg = a[start:start + n]
    draw_candles(ax2, seg)
    chg = (seg[-1, 3] / seg[0, 0] - 1) * 100
    ax2.set_title(f'{d} ({wd}) {hhmm(start)}~{hhmm(start + n)}  |  {seg[0,0]:.2f}→{seg[-1,3]:.2f} ({chg:+.2f}%)  차이 {dist:.3f}', fontsize=12)
    ax2.set_xticks(range(n)); ax2.set_xticklabels([hhmm(start + i) for i in range(n)], fontsize=7, rotation=45)
    ax2.set_xlim(-0.8, n - 0.2); ax2.tick_params(axis='y', labelsize=8); ax2.grid(alpha=.25)
    # 3) 그 날 하루 전체
    ax3 = fig.add_subplot(gs[1, :])
    ax3.axvspan(start - 0.5, start + n - 0.5, color='#f0a43a', alpha=0.18, lw=0)
    us = (290, 420)
    try:
        t = open(os.path.join(ROOT, 'chart/data', sym, 'stock.js')).read()
        st = json.loads(t[t.index('=') + 1:].strip().rstrip(';'))
        if d in st: us = (st[d][2], st[d][3])
    except Exception:
        pass
    ax3.axvspan(us[0], us[1], color='#a0aabe', alpha=0.12, lw=0)
    draw_candles(ax3, a)
    o0 = a[0, 0]
    lo, hi = np.nanmin(a[:, 2]), np.nanmax(a[:, 1])
    endc = a[~np.isnan(a[:, 3])][-1, 3]
    ax3.axhline(o0, color='#888', lw=0.7, ls=':')
    ax3.set_title(f'{sym.upper()} {d} ({wd}) 하루 전체 3분봉  09:00 → 다음날 09:00   '
                  f'시가 {o0:.2f}  고가 {hi:.2f}({(hi/o0-1)*100:+.1f}%)  저가 {lo:.2f}({(lo/o0-1)*100:+.1f}%)  '
                  f'마감 {endc:.2f}({(endc/o0-1)*100:+.1f}%)', fontsize=11.5)
    ticks = list(range(0, 481, 20))
    ax3.set_xticks(ticks); ax3.set_xticklabels([hhmm(i) for i in ticks], fontsize=8, rotation=45)
    ax3.set_xlim(-3, 483); ax3.grid(alpha=.25); ax3.tick_params(axis='y', labelsize=8)
    ax3.text(start + n + 2, 0.98, '◀ 비교 구간', transform=ax3.get_xaxis_transform(), ha='left', va='top', fontsize=9, color='#b06a00')
    ax3.text((us[0] + us[1]) / 2, 0.98, '미국 정규장', transform=ax3.get_xaxis_transform(), ha='center', va='top', fontsize=9, color='#666')
    if others:
        fig.text(0.5, 0.005, '다음으로 비슷한 날: ' + ',  '.join(f'{dd}({"월화수목금토일"[date.fromisoformat(dd).weekday()]}) {x:.3f}' for x, dd in others),
                 ha='center', fontsize=10)
    fig.savefig(out, bbox_inches='tight')
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('image', help='사진 경로, 또는 day:YYYY-MM-DD (그 날 데이터를 그대로 질문으로 사용)')
    p.add_argument('--start', default='09:00', help='사진 첫 캔들 시각(한국시간)')
    p.add_argument('--n', type=int, help='day: 질문일 때 캔들 개수')
    p.add_argument('--exclude', default='', help='뺄 날짜들, 쉼표로')
    p.add_argument('--sym', default='koru')
    p.add_argument('--crop')
    p.add_argument('--skip', type=int, default=0)
    p.add_argument('--take', type=int)
    p.add_argument('--colors', choices=['gr', 'rb'])
    p.add_argument('--top', type=int, default=5)
    p.add_argument('--before')
    p.add_argument('--out', default='.')
    p.add_argument('--render', type=int, default=5, help='그림으로 만들 상위 개수')
    a = p.parse_args()
    crop = tuple(int(v) for v in a.crop.split(',')) if a.crop else None
    hh, mm = map(int, a.start.split(':'))
    start = (((hh * 60 + mm) - 540) % 1440) // 3
    os.makedirs(a.out, exist_ok=True)
    days = load_days(a.sym)
    exclude = set(x for x in a.exclude.split(',') if x)
    if a.image.startswith('day:'):
        qd = a.image[4:]
        q = days[qd][start:start + (a.n or 10), :4]
        exclude.add(qd)
        print(f'질문: {qd} {a.start}부터 {len(q)}개 (데이터 그대로)')
    else:
        cs, band, colors, im = extract(a.image, crop, a.colors)
        cs = cs[a.skip:]
        if a.take:
            cs = cs[:a.take]
        debug_overlay(im, cs, os.path.join(a.out, 'detected.png'))
        q = np.array([[c['o'], c['h'], c['l'], c['c']] for c in cs], float)
        print(f'캔들 {len(cs)}개 인식 (색 규칙 {colors}, 가격 영역 y={band})')
        for i, c in enumerate(cs):
            print(f'  {i+1:2d} {hhmm(start + i)} {"상승" if c["up"] else "하락"}  o{c["o"]} h{c["h"]} l{c["l"]} c{c["c"]}')
    res = rank(q, days, a.before, start, exclude)
    print('비슷한 날 (차이 작을수록 비슷):')
    for x, d in res[:a.top]:
        print(f'  {d} ({"월화수목금토일"[date.fromisoformat(d).weekday()]})  {x:.3f}')
    for k in range(min(a.render, len(res))):
        out = os.path.join(a.out, f'{a.sym.upper()}_match{k+1}_{res[k][1]}.png')
        render(q, res[k], days, a.sym, out, [r for r in res[:a.top] if r != res[k]][:4] if k == 0 else None, start)
        print('그림:', out)


if __name__ == '__main__':
    main()
