"""コスチューム（SVG）と効果音（WAV）を作る。

発車メロディ（Clarinet_Express 様の作曲、generator/sounds/melodies/）のほかは、
すべてプログラムで描いた・合成したオリジナル素材。
3D の中に置く物（標識・駅名標・木・建物など）は「20ピクセル＝1メートル」で描き、
回転中心を根元（下の中央）にしてある。改造で絵を足すときも同じ決まりで描くと
3D の中で正しい大きさになる。
"""
import io
import math
import os
import random as _random
import wave
from xml.sax.saxutils import escape

import numpy as np

FONT = 'Sans Serif'
PX_PER_M = 20
BLUE = '#1e5aa8'     # 信町ブルー（T25000系の帯色）
ORANGE = '#f39a1e'


def svg(w, h, body, defs=''):
    d = f'<defs>{defs}</defs>' if defs else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">{d}{body}</svg>')


def text(x, y, s, size, fill='#000', anchor='middle', weight='bold', extra=''):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{escape(s)}</text>')


def rect(x, y, w, h, fill, rx=0, extra=''):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" {extra}/>'


def poly(pts, fill, extra=''):
    p = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)
    return f'<polygon points="{p}" fill="{fill}" {extra}/>'


def line(x1, y1, x2, y2, stroke, w, extra=''):
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" '
            f'stroke-width="{w}" stroke-linecap="round" {extra}/>')


def circle(cx, cy, r, fill, extra=''):
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" {extra}/>'


# ---------------------------------------------------------------------------
# ステージの背景（空）。地平線はステージ座標 y=30 → SVG の y=150
# ---------------------------------------------------------------------------
HORIZON_SVG_Y = 150


def backdrop(kind, ground):
    stops = {
        '昼': [(0, '#3f82d4'), (0.7, '#a6cdef'), (1, '#e4f1fa')],
        '霧': [(0, '#8c959b'), (0.6, '#b9c0c4'), (1, '#d2d7d9')],
        '夕方': [(0, '#1f1a44'), (0.42, '#6e3c74'), (0.78, '#d4645b'), (1, '#f6b267')],
        '黒': [(0, '#05070c'), (1, '#0b1222')],
    }[kind]
    st = ''.join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    defs = f'<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">{st}</linearGradient>'
    body = rect(0, 0, 480, HORIZON_SVG_Y + 1, 'url(#sky)')
    if kind == '昼':
        rnd = _random.Random(3)
        for _ in range(7):
            cx, cy = rnd.uniform(0, 480), rnd.uniform(20, 110)
            for k in range(4):
                body += (f'<ellipse cx="{cx + rnd.uniform(-30, 30):.0f}" cy="{cy + rnd.uniform(-6, 6):.0f}" '
                         f'rx="{rnd.uniform(18, 40):.0f}" ry="{rnd.uniform(6, 12):.0f}" fill="#ffffff" opacity="0.75"/>')
    if kind == '夕方':
        defs += ('<radialGradient id="sun"><stop offset="0" stop-color="#fff1c0"/>'
                 '<stop offset="0.25" stop-color="#ffd27a" stop-opacity="0.9"/>'
                 '<stop offset="1" stop-color="#ff9a50" stop-opacity="0"/></radialGradient>')
        body += circle(350, 128, 70, 'url(#sun)')
    if kind == '黒':
        body = rect(0, 0, 480, 360, 'url(#sky)')
    else:
        body += rect(0, HORIZON_SVG_Y, 480, 360 - HORIZON_SVG_Y, ground)
    return svg(480, 360, body, defs)


# ---------------------------------------------------------------------------
# 遠景（地平線の上に貼る。幅960で左右がつながる）
# ---------------------------------------------------------------------------

def _ridge(rnd, base, amp, n_terms, w=960):
    terms = [(k, rnd.uniform(0.3, 1.0) / k ** 0.7, rnd.uniform(0, 2 * math.pi)) for k in range(1, n_terms + 1)]
    pts = []
    for x in range(0, w + 1, 6):
        v = sum(a * math.sin(2 * math.pi * k * x / w + ph) for k, a, ph in terms)
        pts.append((x, base - amp * (0.5 + 0.5 * v / sum(a for _, a, _ in terms))))
    return pts


def far_scenery(kind):
    w, h = 960, 170
    rnd = _random.Random(kind)
    body = ''
    if kind == '遠景_山':
        for base, amp, col, n in [(h - 30, 130, '#a5afb4', 9), (h - 10, 95, '#8e9b98', 12), (h, 55, '#76877c', 16)]:
            pts = _ridge(rnd, base, amp, n)
            body += poly([(0, h)] + pts + [(w, h)], col)
    elif kind == '遠景_海':
        pts = _ridge(rnd, h - 4, 46, 8)
        pts = [(x, max(y, h - 46) if 300 < x < 820 else y) for x, y in pts]
        body += poly([(0, h)] + pts + [(w, h)], '#9db6c4')
        for cx, ww, hh in [(380, 70, 12), (520, 40, 8), (700, 110, 18)]:
            body += f'<ellipse cx="{cx}" cy="{h}" rx="{ww}" ry="{hh}" fill="#7f9fb0"/>'
        body += rect(0, h - 1, w, 1, '#b9cfdb')
    elif kind == '遠景_街':
        x = 0
        while x < w:
            bw = rnd.randint(18, 46)
            bh = rnd.randint(30, 90)
            body += rect(x, h - bh - 20, bw, bh + 20, '#6f6283')
            x += bw + rnd.randint(-4, 4)
        body += rect(310, h - 150, 10, 150, '#5a4f6e') + rect(304, h - 120, 22, 10, '#5a4f6e')
        body += line(315, h - 150, 315, h - 168, '#5a4f6e', 2) + circle(315, h - 168, 2.5, '#ff5a5a')
        x = 0
        while x < w:
            bw = rnd.randint(22, 60)
            bh = rnd.randint(14, 70)
            body += rect(x, h - bh, bw, bh, '#463f5c')
            for wy in range(h - bh + 6, h - 4, 9):
                for wx in range(x + 4, x + bw - 6, 8):
                    if rnd.random() < 0.35:
                        body += rect(wx, wy, 4, 4, '#ffd98a', extra='opacity="0.85"')
            x += bw + rnd.randint(0, 6)
    # 2 周期ぶん並べ、回転中心を真ん中にする（どの位置に貼っても画面の幅を覆う）
    return svg(w * 2, h, body + f'<g transform="translate({w},0)">{body}</g>'), w, h


# ---------------------------------------------------------------------------
# 3D の中の物（20px = 1m、回転中心は根元）
# ---------------------------------------------------------------------------

def world(name, w_m, h_m, body_fn):
    w, h = round(w_m * PX_PER_M), round(h_m * PX_PER_M)
    return svg(w, h, body_fn(w, h)), w / 2, h


def scenery(name):
    rnd = _random.Random(name)
    if name == '松':
        def f(w, h):
            b = poly([(w * .47, h), (w * .53, h), (w * .58, h * .45), (w * .5, h * .4)], '#5b4330')
            for cx, cy, rx, ry in [(.5, .38, .42, .1), (.35, .52, .3, .08), (.65, .28, .3, .08), (.5, .16, .25, .08)]:
                b += f'<ellipse cx="{w * cx:.0f}" cy="{h * cy:.0f}" rx="{w * rx:.0f}" ry="{h * ry:.0f}" fill="#2f5a34"/>'
                b += f'<ellipse cx="{w * cx:.0f}" cy="{h * cy - 4:.0f}" rx="{w * rx * .8:.0f}" ry="{h * ry * .5:.0f}" fill="#3f7243"/>'
            return b
        return world(name, 6, 9, f)
    if name == '杉':
        def f(w, h):
            b = rect(w * .45, h * .7, w * .1, h * .3, '#4b3426')
            for i in range(6):
                y0 = h * (0.02 + i * 0.12)
                ww = w * (0.25 + i * 0.13)
                b += poly([(w / 2, y0), (w / 2 + ww / 2, y0 + h * .2), (w / 2 - ww / 2, y0 + h * .2)],
                          '#1f3d26' if i % 2 else '#28492c')
            return b
        return world(name, 4.5, 16, f)
    if name in ('広葉樹', '紅葉'):
        cols = ['#3d6b35', '#4f7f3f', '#5e9049'] if name == '広葉樹' else ['#b8321f', '#d9581f', '#e9932b']
        def f(w, h):
            b = rect(w * .45, h * .55, w * .1, h * .45, '#5a4230')
            for i, (cx, cy, r) in enumerate([(.5, .4, .38), (.32, .5, .24), (.68, .48, .24), (.5, .22, .26)]):
                b += circle(w * cx, h * cy, w * r, cols[i % 3])
            return b
        return world(name, 7 if name == '広葉樹' else 6, 10 if name == '広葉樹' else 8, f)
    if name == '家':
        def f(w, h):
            b = rect(w * .08, h * .42, w * .84, h * .58, '#e8dcc4')
            b += poly([(0, h * .45), (w * .15, h * .12), (w * .85, h * .12), (w, h * .45)], '#45505e')
            b += rect(w * .18, h * .58, w * .2, h * .18, '#7fa6c2') + rect(w * .55, h * .6, w * .25, h * .4, '#7a5a3e')
            return b
        return world(name, 9, 7, f)
    if name.startswith('ビル'):
        spec = {'ビル1': (14, 28, '#6f8296', '#9fb6cc'), 'ビル2': (18, 20, '#cdbfa6', '#8d8170'),
                'ビル3': (10, 40, '#3f4c63', '#6c7f9c')}[name]
        wm, hm, col, win = spec
        def f(w, h):
            b = rect(0, 0, w, h, col) + rect(0, 0, w, 6, '#00000033')
            nx = max(3, int(wm / 2.4))
            ny = max(3, int(hm / 3.2))
            for iy in range(ny):
                for ix in range(nx):
                    lit = rnd.random() < 0.45
                    wx = w * (ix + 0.2) / nx
                    wy = h * (iy + 0.25) / (ny + 0.3)
                    b += rect(f'{wx:.0f}', f'{wy:.0f}', f'{w / nx * .6:.0f}', f'{h / ny * .45:.0f}',
                              '#ffd98a' if lit else win)
            return b
        return world(name, wm, hm, f)
    if name == '電柱':
        def f(w, h):
            b = rect(w * .4, 0, w * .2, h, '#8d8a84')
            b += rect(0, h * .08, w, h * .03, '#6d6a64') + rect(w * .1, h * .2, w * .8, h * .025, '#6d6a64')
            return b
        return world(name, 1.6, 10, f)
    if name == '鳥居':
        def f(w, h):
            red = '#c8361f'
            b = rect(w * .14, h * .12, w * .09, h * .88, red) + rect(w * .77, h * .12, w * .09, h * .88, red)
            b += poly([(0, h * .02), (w, h * .02), (w * .96, h * .12), (w * .04, h * .12)], '#2a2422')
            b += rect(w * .03, h * .1, w * .94, h * .05, red) + rect(w * .08, h * .26, w * .84, h * .05, red)
            b += rect(w * .46, h * .15, w * .08, h * .11, red)
            return b
        return world(name, 7, 7, f)
    if name == '灯籠':
        def f(w, h):
            s = '#9a968e'
            b = rect(w * .3, h * .5, w * .4, h * .5, s) + rect(w * .15, h * .42, w * .7, h * .1, s)
            b += rect(w * .25, h * .22, w * .5, h * .2, s) + rect(w * .38, h * .27, w * .24, h * .1, '#ffcf6a')
            b += poly([(0, h * .24), (w / 2, h * .05), (w, h * .24)], s) + circle(w / 2, h * .04, w * .08, s)
            return b
        return world(name, 1.2, 2.6, f)
    if name.startswith('店_'):
        return shop(*next(sh for sh in SHOPS if sh[0] == name[2:]))
    if name.startswith(('空港_', '駐機_', '飛行機_', '飛行機前_')):
        return airport_object(name)
    raise KeyError(name)


# 沿線の店（コスチューム名は「店_店名」）。看板の文字はコスチュームの中の文字なので、
# Scratch のコスチュームエディタで書き換えられる。
#   (店名, 建物の形, 壁の色, 看板の色, 看板の文字の色)
#   形: 'low'=2階建ての店 / 'mid'=中くらいのビル（縦看板つき）/ 'roof'=屋上看板のビル / 'wa'=和風の店（のれん）
SHOPS = [
    # 信町本線（街なか）
    ('信町ストア', 'low', '#b9b2a8', BLUE, '#ffffff'),
    ('喫茶ひだまり', 'low', '#d9c6a5', '#6b3e26', '#ffe9c4'),
    ('信町書店', 'mid', '#c4c9cf', '#2f6b3a', '#ffffff'),
    ('みどり薬局', 'low', '#e8e6df', '#2aa05a', '#ffffff'),
    ('ラーメン信町軒', 'low', '#cfc2b0', '#c8361f', '#fff3a0'),
    ('信町銀行', 'mid', '#d6d2c8', '#1e3f7a', '#ffffff'),
    ('ホテル信町', 'roof', '#b8c2cc', '#7a3fa0', '#ffffff'),
    ('信町デンキ', 'roof', '#c9cdd2', '#f0c020', '#c8161f'),
    ('寿司 信', 'wa', '#e4d8c0', '#2b2b2b', '#ffffff'),
    ('花屋フローラ', 'low', '#efe3e8', '#e06a9a', '#ffffff'),
    ('信町ベーカリー', 'low', '#ecd9b8', '#a0642a', '#fff5e0'),
    ('信町歯科', 'mid', '#e6ebee', '#2a8fbf', '#ffffff'),
    # 神社線（門前町）
    ('門前そば', 'wa', '#d8c8a8', '#3a2a1a', '#ffffff'),
    ('みやげ 神社堂', 'wa', '#e0d2b4', '#8a1f1a', '#ffe9b0'),
    ('茶屋 杉の木', 'wa', '#cdbf9f', '#2e4a2b', '#f5ead0'),
    ('旅館 信町荘', 'wa', '#d9ccb0', '#4a3424', '#ffffff'),
    # 田原海岸線（海沿い）
    ('海の家しおさい', 'low', '#f3ecd8', '#2e8fd0', '#ffffff'),
    ('浜焼き 田原屋', 'wa', '#e6dcc6', '#d05a1e', '#ffffff'),
    ('民宿なぎさ', 'low', '#eef2f2', '#1f7a8c', '#ffffff'),
    ('釣具うみかぜ', 'low', '#e2e6e0', '#3a5a8a', '#ffe14d'),
    ('田原みやげ', 'roof', '#d8dee2', '#e0782a', '#ffffff'),
]
SHOP_SIZE = {'low': (11, 8), 'mid': (13, 17), 'roof': (15, 21), 'wa': (10, 7)}


def shop(name, style, wall, sign, ink):
    """看板つきの店。看板の文字は店名。"""
    wm, hm = SHOP_SIZE[style]
    rnd = _random.Random(name)

    def f(w, h):
        n = len(name)
        if style == 'wa':
            b = rect(w * .04, h * .38, w * .92, h * .62, wall)
            b += poly([(0, h * .42), (w * .1, h * .12), (w * .9, h * .12), (w, h * .42)], '#4a5560')
            b += rect(w * .1, h * .02, w * .8, h * .12, sign, rx=2)
            b += text(w / 2, h * .115, name, f'{min(h * .085, w * .72 / max(n, 1)):.1f}', ink)
            for i in range(4):
                b += rect(w * (.16 + i * .18), h * .62, w * .15, h * .16, sign, extra='opacity="0.9"')
            b += rect(w * .12, h * .78, w * .76, h * .22, '#5a4632')
            return b
        b = rect(0, 0, w, h, wall) + rect(0, 0, w, 3, '#00000033')
        floors = {'low': 2, 'mid': 5, 'roof': 6}[style]
        top = h * (.18 if style == 'roof' else 0)
        fh = (h - top) / floors
        for fl in range(1, floors):
            y = top + (fl - 1) * fh
            for ix in range(4):
                lit = rnd.random() < 0.5
                b += rect(f'{w * (.08 + ix * .23):.1f}', f'{y + fh * .25:.1f}', f'{w * .16:.1f}', f'{fh * .5:.1f}',
                          '#ffd98a' if lit else '#8fa3b5')
        gy = top + (floors - 1) * fh
        b += rect(0, gy, w, fh, '#3a3f46') + rect(w * .06, gy + fh * .3, w * .88, fh * .62, '#9fc4d8')
        b += rect(w * .42, gy + fh * .3, w * .16, fh * .7, '#5a6670')
        if style == 'roof':
            b += rect(w * .45, top * .7, w * .04, top * .3, '#666') + rect(w * .51, top * .7, w * .04, top * .3, '#666')
            b += rect(w * .04, 0, w * .92, top * .72, sign, rx=2)
            b += text(w / 2, top * .52, name, f'{min(top * .45, w * .84 / max(n, 1)):.1f}', ink)
        else:
            b += rect(w * .04, gy - fh * .28, w * .92, fh * .3, sign, rx=1.5)
            b += text(w / 2, gy - fh * .06, name, f'{min(fh * .22, w * .86 / max(n, 1)):.1f}', ink)
        if style == 'mid':
            b += rect(w * .86, h * .12, w * .12, h * .5, sign, rx=1.5)
            for i, ch in enumerate(name[:6]):
                b += text(w * .92, h * (.17 + i * .075), ch, f'{w * .085:.1f}', ink)
        return b
    return world(f'店_{name}', wm, hm, f)


# ---------------------------------------------------------------------------
# 信町空港（空港の建物・飛行機）。航空会社は架空。20px = 1m、回転中心は根元
# ---------------------------------------------------------------------------
# 航空会社: (会社名, 英語名, 胴体の帯の色, 帯の2色目, 尾翼の色, 尾翼の印の色)
AIRLINES = [
    ('信町航空', 'SHINMACHI AIR', BLUE, ORANGE, BLUE, ORANGE),
    ('そらいろ航空', 'SORAIRO AIRWAYS', '#3fa9f5', '#ffffff', '#3fa9f5', '#ffffff'),
]


def _airline(name):
    return next(a for a in AIRLINES if a[0] == name)


def airport_object(name):
    if name == '空港_ターミナル':
        def f(w, h):
            defs = ''
            b = rect(0, h * .22, w, h * .78, '#d9dde2')
            b += f'<path d="M 0 {h * .24:.0f} Q {w / 2:.0f} {h * .02:.0f} {w} {h * .24:.0f} Z" fill="#eef1f4"/>'
            b += rect(0, h * .22, w, h * .04, '#9aa3ad')
            # ガラスの壁
            b += rect(w * .03, h * .3, w * .94, h * .48, '#4d7fa6')
            for i in range(1, 24):
                x = w * (.03 + .94 * i / 24)
                b += line(x, h * .3, x, h * .78, '#c8d3dc', 2)
            b += line(w * .03, h * .54, w * .97, h * .54, '#c8d3dc', 2.5)
            b += rect(w * .03, h * .3, w * .94, h * .1, '#ffffff', extra='opacity="0.18"')
            # 入口と柱
            b += rect(w * .44, h * .62, w * .12, h * .38, '#2b3a48')
            b += rect(0, h * .78, w, h * .22, '#b8bec5')
            for i in range(9):
                b += rect(w * (.05 + i * .113), h * .78, w * .012, h * .22, '#8d949c')
            # 看板（ここを書き換えると空港の名前が変わる）
            b += rect(w * .3, h * .05, w * .4, h * .15, BLUE, rx=6)
            b += text(w * .43, h * .155, '信町空港', h * .1, '#ffffff', extra='letter-spacing="8"')
            b += text(w * .62, h * .15, 'SHINMACHI AIRPORT', h * .045, '#ffe2b0')
            # 搭乗橋（ボーディングブリッジ）
            for x0 in (.12, .72):
                b += rect(w * x0, h * .56, w * .14, h * .1, '#c3c9cf') + rect(w * (x0 + .13), h * .56, w * .02, h * .44, '#8d949c')
            return defs + b
        return world(name, 64, 18, f)
    if name == '空港_管制塔':
        def f(w, h):
            b = poly([(w * .36, h), (w * .64, h), (w * .58, h * .3), (w * .42, h * .3)], '#d3d7dc')
            b += rect(w * .45, h * .3, w * .1, h * .7, '#bfc5cb')
            b += poly([(w * .12, h * .2), (w * .88, h * .2), (w * .74, h * .3), (w * .26, h * .3)], '#c9ced3')
            b += poly([(w * .06, h * .1), (w * .94, h * .1), (w * .88, h * .2), (w * .12, h * .2)], '#26445e')
            b += line(w * .06, h * .1, w * .94, h * .1, '#e9edf0', 6)
            b += rect(w * .2, h * .05, w * .6, h * .05, '#e9edf0')
            b += line(w * .5, h * .05, w * .5, 0, '#8d949c', 4) + circle(w * .5, 6, 5, '#ff3b30')
            b += text(w * .5, h * .27, '信町空港', h * .022, '#1e3f7a')
            return b
        return world(name, 14, 46, f)
    if name == '空港_格納庫':
        def f(w, h):
            b = f'<path d="M 0 {h} V {h * .4:.0f} Q {w / 2:.0f} {-h * .15:.0f} {w} {h * .4:.0f} V {h} Z" fill="#c4cad0"/>'
            for i in range(1, 8):
                x = w * i / 8
                b += line(x, h * .32, x, h, '#a7aeb5', 3)
            b += rect(w * .08, h * .45, w * .84, h * .55, '#9aa3ad')
            for i in range(1, 6):
                b += line(w * (.08 + .84 * i / 6), h * .45, w * (.08 + .84 * i / 6), h, '#7d868f', 3)
            b += text(w / 2, h * .34, 'SHINMACHI AIR', h * .11, BLUE, extra='letter-spacing="3"')
            return b
        return world(name, 44, 20, f)
    if name == '空港_吹き流し':
        def f(w, h):
            b = rect(w * .1, h * .1, w * .07, h * .9, '#d0d4d8')
            for i in range(5):
                y0, y1 = h * (.1 + i * .012), h * (.3 - i * .012)
                x0, x1 = w * (.17 + i * .16), w * (.33 + i * .16)
                b += poly([(x0, y0), (x1, y0 + h * .01), (x1, y1 - h * .01), (x0, y1)], '#ff6a1a' if i % 2 == 0 else '#ffffff')
            return b
        return world(name, 3, 8, f)
    if name == '空港_看板':
        def f(w, h):
            b = rect(w * .1, h * .5, w * .05, h * .5, '#8d949c') + rect(w * .85, h * .5, w * .05, h * .5, '#8d949c')
            b += rect(0, 0, w, h * .6, BLUE, rx=6) + rect(0, h * .52, w, h * .08, ORANGE)
            # 飛行機のマーク
            cx, cy, s = w * .16, h * .28, h * .2
            b += poly([(cx - s, cy + s * .1), (cx + s, cy - s * .1), (cx + s * 1.1, cy), (cx + s, cy + s * .1),
                       (cx - s, cy + s * .25)], '#ffffff')
            b += poly([(cx - s * .1, cy), (cx + s * .3, cy - s * .8), (cx + s * .5, cy - s * .8), (cx + s * .35, cy)], '#ffffff')
            b += poly([(cx - s * .1, cy + s * .2), (cx + s * .25, cy + s * .9), (cx + s * .45, cy + s * .9), (cx + s * .3, cy + s * .2)],
                      '#ffffff')
            b += text(w * .6, h * .3, '信町空港', h * .2, '#ffffff', extra='letter-spacing="4"')
            b += text(w * .6, h * .45, 'Shinmachi Airport  →', h * .09, '#ffe2b0')
            return b
        return world(name, 12, 6, f)
    if name.startswith('駐機_'):
        _, en, c1, c2, fin, mark = _airline(name[3:])
        company = name[3:]

        def f(w, h):
            # 横から見た大型の旅客機（機首が左）。胴体の長さ 56m・高さ 17m
            fy, fh = h * .48, h * .3          # 胴体の上の端・太さ
            b = poly([(w * .78, fy + fh * .1), (w * .9, h * .02), (w * .98, h * .02), (w * .97, fy + fh * .5)], fin)
            b += circle(w * .93, h * .18, h * .07, mark)
            b += f'<path d="M {w * .1:.0f} {fy:.0f} H {w * .86:.0f} L {w * .99:.0f} {fy + fh * .35:.0f} L {w * .86:.0f} {fy + fh:.0f} H {w * .1:.0f} Q {w * .005:.0f} {fy + fh * .75:.0f} {w * .01:.0f} {fy + fh * .5:.0f} Q {w * .03:.0f} {fy:.0f} {w * .1:.0f} {fy:.0f} Z" fill="#f4f6f8"/>'
            b += rect(w * .06, fy + fh * .62, w * .82, fh * .12, c1) + rect(w * .06, fy + fh * .74, w * .82, fh * .06, c2)
            for i in range(34):
                b += rect(w * (.13 + i * .021), fy + fh * .3, w * .008, fh * .16, '#33475a', rx=1)
            b += poly([(w * .03, fy + fh * .32), (w * .07, fy + fh * .22), (w * .09, fy + fh * .22), (w * .08, fy + fh * .38)], '#22323f')
            b += text(w * .45, fy + fh * .26, company, fh * .2, c1 if c1 != '#ffffff' else '#3fa9f5')
            # 主翼・エンジン・脚
            b += poly([(w * .36, fy + fh * .8), (w * .6, fy + fh * .8), (w * .5, fy + fh * 1.05)], '#aeb6bf')
            b += rect(w * .36, fy + fh * .95, w * .1, fh * .4, '#d0d6dc', rx=fh * .18)
            b += rect(w * .44, fy + fh * 1.0, w * .025, fh * .3, '#3a3f46')
            for x in (.16, .5):
                b += rect(w * x, fy + fh, w * .008, h - fy - fh - h * .04, '#555')
                b += circle(w * x + w * .004, h - h * .04, h * .04, '#222')
            b += text(w * .65, fy + fh * .55, en, fh * .12, '#7d868f')
            return b
        return world(name, 56, 17, f)
    if name.startswith(('飛行機_', '飛行機前_')):
        front = name.startswith('飛行機前_')
        _, en, c1, c2, fin, mark = _airline(name.split('_', 1)[1])

        def f(w, h):
            # 後ろ（飛行機_）または前（飛行機前_）から見た大型の旅客機。翼幅 60m・高さ 17m。回転中心は車輪の下。
            # 遠くでも見えるように、胴体・翼・エンジンは本物より太めに描いている
            cx = w / 2
            fy = h * .6           # 胴体の中心の高さ（SVG の y）
            r = h * .23
            dark = '#2b3440'
            b = poly([(cx - w * .03, fy - r * .5), (cx + w * .03, fy - r * .5), (cx + w * .016, h * .01), (cx - w * .016, h * .01)], fin,
                     extra=f'stroke="{dark}" stroke-width="5"')
            b += circle(cx, h * .2, w * .014, mark)
            b += poly([(cx - w * .19, fy - r * .75), (cx + w * .19, fy - r * .75), (cx + w * .18, fy - r * .45), (cx - w * .18, fy - r * .45)],
                      '#b9c2cb', extra=f'stroke="{dark}" stroke-width="5"')
            # 主翼（付け根が厚く、先が薄いくさび形）
            b += poly([(cx - w * .495, fy - r * .1), (cx + w * .495, fy - r * .1), (cx + w * .495, fy + r * .12), (cx + r, fy + r * .65),
                       (cx - r, fy + r * .65), (cx - w * .495, fy + r * .12)], '#a9b3bd', extra=f'stroke="{dark}" stroke-width="6"')
            b += rect(0, fy - r * .15, w * .015, r * .3, '#ff3b30') + rect(w * .985, fy - r * .15, w * .015, r * .3, '#2ecc71')
            for sx in (-1, 1):
                ex = cx + sx * w * .19
                b += circle(ex, fy + r * .75, r * .62, '#e3e8ec', extra=f'stroke="{dark}" stroke-width="5"')
                b += circle(ex, fy + r * .75, r * .4, '#3a3f46')
                b += rect(cx + sx * w * .08 - w * .007, fy + r * .5, w * .014, h - fy - r * .5 - h * .07, '#555')
                b += circle(cx + sx * w * .08, h - h * .05, h * .05, '#222')
            b += circle(cx, fy, r, '#f4f6f8', extra=f'stroke="{dark}" stroke-width="6"')
            b += f'<path d="M {cx - r:.1f} {fy + r * .3:.1f} A {r:.1f} {r:.1f} 0 0 0 {cx + r:.1f} {fy + r * .3:.1f}" fill="none" stroke="{c1}" stroke-width="{r * .3:.1f}"/>'
            b += rect(cx - w * .005, fy + r, w * .01, h - fy - r - h * .07, '#555') + circle(cx, h - h * .05, h * .05, '#222')
            if front:
                # 操縦席の窓と着陸灯（こちらへ向かってくる飛行機）
                b += f'<path d="M {cx - r * .75:.1f} {fy - r * .4:.1f} Q {cx:.1f} {fy - r * .75:.1f} {cx + r * .75:.1f} {fy - r * .4:.1f} L {cx + r * .65:.1f} {fy - r * .18:.1f} Q {cx:.1f} {fy - r * .42:.1f} {cx - r * .65:.1f} {fy - r * .18:.1f} Z" fill="#1c2a36"/>'
                for sx in (-1, 1):
                    b += circle(cx + sx * w * .1, fy + r * .25, r * .3, '#fff8d0')
                    b += circle(cx + sx * w * .1, fy + r * .25, r * .8, '#fff8d0', extra='opacity="0.35"')
            else:
                b += circle(cx, fy, r * .35, '#d0d6dc')
            return b
        return world(name, 60, 17, f)
    raise KeyError(name)


AIRPORT_NAMES = ['空港_ターミナル', '空港_管制塔', '空港_格納庫', '空港_吹き流し', '空港_看板'] + \
    [f'駐機_{a[0]}' for a in AIRLINES]


# ---------------------------------------------------------------------------
# アクシデント（障害物・踏切・特殊信号発光機・信号機）。20px = 1m、回転中心は根元
# ---------------------------------------------------------------------------
def accident_object(name):
    if name == '障害_倒木':
        def f(w, h):
            b = poly([(w * .02, h * .78), (w * .96, h * .5), (w * .98, h * .66), (w * .04, h * .96)], '#6b4a2f')
            b += poly([(w * .02, h * .78), (w * .96, h * .5), (w * .96, h * .55), (w * .03, h * .83)], '#8a6340')
            for cx, cy, r in [(.72, .38, .2), (.86, .3, .16), (.6, .5, .14), (.93, .5, .12), (.8, .55, .13)]:
                b += circle(w * cx, h * cy, h * r * 1.6, '#2f5a34')
                b += circle(w * cx - h * .05, h * cy - h * .05, h * r, '#3f7243')
            b += circle(w * .05, h * .87, h * .1, '#d8b98a') + circle(w * .05, h * .87, h * .05, '#a07a4a')
            return b
        return world(name, 7, 2.4, f)
    if name == '障害_落石':
        def f(w, h):
            b = ''
            for cx, cy, rx, ry, col in [(.3, .7, .26, .3, '#7c7a76'), (.62, .62, .3, .38, '#8d8a84'), (.82, .8, .16, .2, '#6e6c68'),
                                        (.12, .85, .12, .15, '#77746f'), (.48, .86, .14, .14, '#9a968f')]:
                b += f'<ellipse cx="{w * cx:.0f}" cy="{h * cy:.0f}" rx="{w * rx:.0f}" ry="{h * ry:.0f}" fill="{col}" stroke="#4a4844" stroke-width="2"/>'
            return b
        return world(name, 5, 1.8, f)
    if name == '障害_シカ':
        def f(w, h):
            c = '#9a6a3c'
            b = f'<ellipse cx="{w * .45:.0f}" cy="{h * .45:.0f}" rx="{w * .3:.0f}" ry="{h * .14:.0f}" fill="{c}"/>'
            for x in (.22, .3, .58, .66):
                b += rect(w * x, h * .5, w * .045, h * .5, '#7a5230')
            b += poly([(w * .7, h * .42), (w * .78, h * .14), (w * .86, h * .16), (w * .8, h * .45)], c)
            b += f'<ellipse cx="{w * .86:.0f}" cy="{h * .16:.0f}" rx="{w * .09:.0f}" ry="{h * .06:.0f}" fill="{c}"/>'
            b += line(w * .82, h * .1, w * .76, 2, '#5a3d22', 3) + line(w * .86, h * .1, w * .92, 2, '#5a3d22', 3)
            b += circle(w * .9, h * .15, 2.5, '#111')
            for x, y in [(.3, .4), (.42, .38), (.54, .42), (.36, .48)]:
                b += circle(w * x, h * y, 3, '#f2e6d0')
            b += f'<ellipse cx="{w * .16:.0f}" cy="{h * .4:.0f}" rx="{w * .04:.0f}" ry="{h * .05:.0f}" fill="#f2e6d0"/>'
            return b
        return world(name, 2.2, 1.9, f)
    if name == '障害_車':
        def f(w, h):
            b = f'<path d="M {w * .02:.0f} {h * .82:.0f} V {h * .5:.0f} Q {w * .04:.0f} {h * .42:.0f} {w * .14:.0f} {h * .4:.0f} L {w * .3:.0f} {h * .08:.0f} H {w * .7:.0f} L {w * .84:.0f} {h * .4:.0f} Q {w * .97:.0f} {h * .44:.0f} {w * .98:.0f} {h * .55:.0f} V {h * .82:.0f} Z" fill="#d64545"/>'
            b += poly([(w * .33, h * .14), (w * .48, h * .14), (w * .48, h * .38), (w * .25, h * .38)], '#9fc4d8')
            b += poly([(w * .52, h * .14), (w * .67, h * .14), (w * .78, h * .38), (w * .52, h * .38)], '#9fc4d8')
            b += rect(w * .03, h * .55, w * .06, h * .08, '#ffe9a0') + rect(w * .91, h * .55, w * .06, h * .08, '#ff4a4a')
            for x in (.22, .78):
                b += circle(w * x, h * .82, h * .17, '#222') + circle(w * x, h * .82, h * .08, '#999')
            return b
        return world(name, 4.4, 1.6, f)
    if name.startswith('踏切_'):
        lit = name.endswith('1')

        def f(w, h):
            b = rect(w * .44, h * .1, w * .12, h * .9, '#eee')
            for i in range(6):
                b += rect(w * .44, h * (.55 + i * .07), w * .12, h * .035, '#222')
            b += line(w * .1, h * .02, w * .9, h * .2, '#f2c200', 9) + line(w * .1, h * .2, w * .9, h * .02, '#f2c200', 9)
            b += line(w * .1, h * .02, w * .9, h * .2, '#222', 3) + line(w * .1, h * .2, w * .9, h * .02, '#222', 3)
            b += rect(w * .08, h * .28, w * .84, h * .09, '#222', rx=4)
            b += circle(w * .25, h * .325, h * .035, '#ff3030' if lit else '#4a1010')
            b += circle(w * .75, h * .325, h * .035, '#4a1010' if lit else '#ff3030')
            b += text(w / 2, h * .47, '踏切', h * .045, '#222')
            return b
        return world(name, 1.6, 4.2, f)
    if name.startswith('特発_'):
        lit = name.endswith('点灯')

        def f(w, h):
            b = rect(w * .45, h * .25, w * .1, h * .75, '#9a9a9a')
            b += rect(0, h * .05, w, h * .22, '#1b1b1b', rx=4)
            for i in range(5):
                b += circle(w * (.12 + i * .19), h * .16, w * .075, '#ff2a2a' if lit else '#3a1010')
                if lit:
                    b += circle(w * (.12 + i * .19), h * .16, w * .13, '#ff2a2a', extra='opacity="0.35"')
            return b
        return world(name, 3.2, 4.8, f)
    if name.startswith('信号_'):
        aspect = name[3:]

        def f(w, h):
            b = rect(w * .44, h * .3, w * .12, h * .7, '#8a8a8a')
            b += rect(w * .12, 0, w * .76, h * .34, '#111', rx=6)
            for i, (col, on) in enumerate([('#ff2a2a', aspect == '赤'), ('#ffb020', False), ('#2ee06a', aspect == '青')]):
                cy = h * (.06 + i * .1)
                b += circle(w / 2, cy, w * .22, col if on else '#2a2a2a')
                if on:
                    b += circle(w / 2, cy, w * .34, col, extra='opacity="0.3"')
            return b
        return world(name, 1.2, 6, f)
    raise KeyError(name)


ACCIDENT_NAMES = ['障害_倒木', '障害_落石', '障害_シカ', '障害_車', '踏切_1', '踏切_2', '特発_点灯', '特発_消灯', '信号_赤', '信号_青']
AIRPORT_HALF_WIDTH = {'空港_ターミナル': 32, '空港_管制塔': 7, '空港_格納庫': 22, '空港_吹き流し': 1.5, '空港_看板': 6}
AIRPORT_HALF_WIDTH.update({f'駐機_{a[0]}': 28 for a in AIRLINES})
PLANE_NAMES = [f'飛行機_{a[0]}' for a in AIRLINES] + [f'飛行機前_{a[0]}' for a in AIRLINES]


SCENERY_NAMES = ['松', '杉', '広葉樹', '紅葉', '家', 'ビル1', 'ビル2', 'ビル3', '電柱', '鳥居', '灯籠'] + \
    [f'店_{sh[0]}' for sh in SHOPS] + AIRPORT_NAMES
SCENERY_HALF_WIDTH = {'松': 3, '杉': 2.3, '広葉樹': 3.5, '紅葉': 3, '家': 4.5, 'ビル1': 7, 'ビル2': 9, 'ビル3': 5,
                      '電柱': 0.8, '鳥居': 3.5, '灯籠': 0.6}
SCENERY_HALF_WIDTH.update({f'店_{sh[0]}': SHOP_SIZE[sh[1]][0] / 2 for sh in SHOPS})
SCENERY_HALF_WIDTH.update(AIRPORT_HALF_WIDTH)


def limit_sign(v):
    """速度制限標識（黄色の板に黒い数字）。v は数字または '解除'。"""
    def f(w, h):
        b = rect(w * .44, h * .4, w * .12, h * .6, '#8a8a8a')
        if v == '解除':
            b += rect(0, 0, w, h * .45, '#111', rx=1.5) + rect(w * .06, h * .03, w * .88, h * .39, '#fff', rx=1)
            b += line(w * .1, h * .4, w * .9, h * .05, '#111', 1.6)
            b += text(w / 2, h * .3, '解除', h * .17, '#111')
        else:
            b += rect(0, 0, w, h * .45, '#111', rx=1.5) + rect(w * .06, h * .03, w * .88, h * .39, '#ffd200', rx=1)
            b += text(w / 2, h * .33, str(v), h * (.26 if v < 100 else .21), '#111',
                      extra='letter-spacing="-0.5"')
        return b
    return world(f'制限{v}', 1.4, 3.2, f)


def stop_marker(n):
    def f(w, h):
        b = rect(w * .42, h * .45, w * .16, h * .55, '#9a9a9a')
        b += rect(0, 0, w, h * .5, '#111', rx=1) + rect(w * .07, h * .035, w * .86, h * .43, '#fff', rx=1)
        b += text(w / 2, h * .38, str(n), h * (.34 if len(str(n)) < 2 else .28), '#111')
        return b
    return world(f'停目{n}', 1.0, 2.0, f)


def station_board(name, transfer=None):
    """駅名標。駅名と同じ名前のコスチュームにしておくと 3D の中のホームに立つ。"""
    def f(w, h):
        b = rect(w * .08, h * .45, w * .05, h * .55, '#555') + rect(w * .87, h * .45, w * .05, h * .55, '#555')
        b += rect(0, 0, w, h * .5, '#333', rx=2) + rect(w * .015, h * .02, w * .97, h * .46, '#fdfdfb', rx=1.5)
        if name:
            n = len(name)
            size = min(h * .22, w * .82 / max(n, 1))
            b += text(w / 2, h * .25, name, f'{size:.1f}', '#111')
        b += rect(w * .015, h * .34, w * .97, h * .14, BLUE)
        if transfer:
            b += text(w / 2, h * .44, transfer, f'{h * .085:.1f}', '#fff')
        else:
            b += text(w / 2, h * .44, '信町高速鉄道', f'{h * .085:.1f}', '#fff')
        return b
    return world(name or '駅名標', 3.4, 2.8, f)


def pen_canvas():
    """ペンで描くスプライト用の大きな透明コスチューム。
    Scratch はスプライトを画面の外へ出しすぎないように位置を補正（フェンス）するが、
    コスチュームが大きいと画面外の点まで線を引ける。"""
    return svg(1600, 1200, rect(0, 0, 1600, 1200, '#000', extra='fill-opacity="0"')), 800, 600


# ---------------------------------------------------------------------------
# 運転台・計器
# ---------------------------------------------------------------------------
SPEEDO = (60, 306, 46)     # (中心x, 中心y, 半径) SVG 座標
BCGAUGE = (428, 306, 46)
GAUGE_SWEEP = 125     # 目盛りの角度（0 が −125°、最大が ＋125°）
SPEEDO_MAX = 400      # 速度計の最大 [km/h]


def _gauge(cx, cy, r, vmax, step_minor, step_label, unit, label_div=1, red_from=None):
    b = circle(cx, cy, r + 4, '#20252c') + circle(cx, cy, r, '#0c0f13')
    if red_from is not None:
        a0 = math.radians(-GAUGE_SWEEP + 2 * GAUGE_SWEEP * red_from / vmax)
        a1 = math.radians(GAUGE_SWEEP)
        rr = r - 4
        b += (f'<path d="M {cx + rr * math.sin(a0):.1f} {cy - rr * math.cos(a0):.1f} A {rr} {rr} 0 0 1 '
              f'{cx + rr * math.sin(a1):.1f} {cy - rr * math.cos(a1):.1f}" stroke="#d33" stroke-width="3" fill="none"/>')
    v = 0
    while v <= vmax + 1e-6:
        a = math.radians(-GAUGE_SWEEP + 2 * GAUGE_SWEEP * v / vmax)
        major = abs(v / step_label - round(v / step_label)) < 1e-6
        r0 = r - (9 if major else 5)
        b += line(cx + r0 * math.sin(a), cy - r0 * math.cos(a), cx + (r - 1.5) * math.sin(a),
                  cy - (r - 1.5) * math.cos(a), '#f2f2f2', 1.6 if major else 0.8)
        if major:
            rt = r - 17
            b += text(f'{cx + rt * math.sin(a):.1f}', f'{cy - rt * math.cos(a) + 3:.1f}', str(int(v / label_div)), 7.5,
                      '#f2f2f2')
        v += step_minor
    b += text(cx, cy - 12, unit, 6.5, '#9fb3c8', weight='normal')
    return b


def cab(name, body_col='#2f3a4a', face_col='#232a35'):
    b = ''
    # 上の枠と左右の柱
    b += rect(0, 0, 480, 24, '#22262d') + rect(0, 22, 480, 3, '#3a4049')
    b += poly([(0, 0), (30, 0), (24, 250), (0, 250)], '#2a2f37') + poly([(480, 0), (450, 0), (456, 250), (480, 250)],
                                                                         '#2a2f37')
    b += poly([(24, 24), (30, 24), (25, 246), (21, 246)], '#14171c') + poly([(456, 24), (450, 24), (455, 246),
                                                                            (459, 246)], '#14171c')
    b += text(172, 16, name, 10, '#c9d3df', extra='letter-spacing="2"')
    # ワイパー
    b += line(70, 242, 200, 232, '#15181c', 3) + line(70, 242, 76, 250, '#15181c', 5)
    # 計器盤
    b += poly([(0, 250), (14, 240), (466, 240), (480, 250), (480, 360), (0, 360)], body_col)
    b += rect(0, 240, 480, 3, ORANGE) + rect(0, 243, 480, 2, BLUE)
    b += rect(8, 250, 464, 106, face_col, rx=6)
    # 速度計・BC圧力計
    b += _gauge(*SPEEDO, SPEEDO_MAX, 10, 50, 'km/h', red_from=350)
    b += _gauge(*BCGAUGE, 600, 25, 100, 'BC kPa')
    b += rect(SPEEDO[0] - 21, SPEEDO[1] + 21, 42, 22, '#050608', rx=3)
    # ノッチ表示の枠
    b += rect(112, 254, 44, 100, '#0a0d12', rx=4) + rect(112, 254, 44, 100, 'none', rx=4,
                                                       extra='stroke="#4a5566" stroke-width="1"')
    # TIMS 画面
    b += rect(162, 254, 214, 100, '#0a1a33', rx=4, extra='stroke="#3fa9f5" stroke-width="1"')
    b += rect(162, 254, 214, 3, '#3fa9f5')
    b += text(372, 352, 'TIMS', 6, '#3fa9f5', anchor='end', weight='normal')
    return svg(480, 360, b)


def needle(color, length):
    b = poly([(46, 8.3), (50 + length, 10), (46, 11.7)], color) + line(38, 10, 50, 10, color, 3)
    b += circle(50, 10, 5, '#2b2f36') + circle(50, 10, 2.2, color)
    return svg(50 + length + 6, 20, b), 50, 10


NOTCHES = ['P5', 'P4', 'P3', 'P2', 'P1', 'N', 'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'EB']


def notch_costume(label):
    def col(l):
        if l.startswith('P'):
            return '#3fb6ff'
        if l == 'N':
            return '#4cd964'
        if l == 'EB':
            return '#ff2a2a'
        return '#ff9f1a' if l != 'B8' else '#ff5a1a'
    b = ''
    if label == 'EB':
        b += rect(2, 2, 40, 22, '#5a0a0a', rx=3)
    b += text(22, 20, label, 17, col(label))
    for i, l in enumerate(NOTCHES):
        y = 30 + i * 4.6
        lit = l == label
        b += rect(8, f'{y:.1f}', 28, 3.4, col(l) if lit else '#2a3038', rx=1)
        if lit:
            b += rect(4, f'{y:.1f}', 3, 3.4, '#fff')
    return svg(44, 100, b), 22, 50


SEG = {'0': 'abcdef', '1': 'bc', '2': 'abged', '3': 'abgcd', '4': 'fgbc', '5': 'afgcd', '6': 'afgedc', '7': 'abc',
       '8': 'abcdefg', '9': 'abcdfg', '空白': ''}


def digit(d):
    on, off = '#ffb43a', '#1a1208'
    w, h = 12, 20
    segs = {'a': (2.5, 1, 7, 2), 'g': (2.5, 9, 7, 2), 'd': (2.5, 17, 7, 2),
            'f': (1, 2.5, 2, 6.5), 'b': (9, 2.5, 2, 6.5), 'e': (1, 10.5, 2, 6.5), 'c': (9, 10.5, 2, 6.5)}
    b = ''
    for s, (x, y, sw, sh) in segs.items():
        b += rect(x, y, sw, sh, on if s in SEG[d] else off, rx=0.8)
    return svg(w, h, b), w / 2, h / 2


def lamp(label, lit, color):
    if lit:
        b = rect(0, 0, 34, 14, color, rx=3, extra='stroke="#fff" stroke-width="0.8"') + text(17, 10.5, label, 9,
                                                                                            '#fff' if label == 'ATS' else '#222')
    else:
        b = rect(0, 0, 34, 14, '#2a2224', rx=3) + text(17, 10.5, label, 9, '#6a5a5a')
    return svg(34, 14, b), 17, 7


# ---------------------------------------------------------------------------
# タイトル・メニュー
# ---------------------------------------------------------------------------

def title_screen():
    defs = ('<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0d1630"/>'
            '<stop offset="0.6" stop-color="#2b2a5c"/><stop offset="1" stop-color="#d9735c"/></linearGradient>'
            '<linearGradient id="body" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#aeb7c2"/>'
            '<stop offset="0.5" stop-color="#eef2f6"/><stop offset="1" stop-color="#aeb7c2"/></linearGradient>')
    b = rect(0, 0, 480, 360, 'url(#bg)')
    rnd = _random.Random(7)
    x = 0
    while x < 480:
        bw = rnd.randint(16, 40)
        bh = rnd.randint(20, 80)
        b += rect(x, 250 - bh, bw, bh + 10, '#1b1838')
        for wy in range(250 - bh + 5, 250, 8):
            for wx in range(x + 3, x + bw - 4, 7):
                if rnd.random() < 0.3:
                    b += rect(wx, wy, 3, 3, '#ffd98a', extra='opacity="0.8"')
        x += bw
    b += rect(0, 250, 480, 110, '#2a2530')
    for i in range(14):
        y = 252 + i * i * 0.55
        b += rect(0, y, 480, 1 + i * 0.25, '#3a3440')
    b += poly([(240, 250), (232, 360), (212, 360)], '#b8b8c0') + poly([(240, 250), (268, 360), (248, 360)], '#b8b8c0')
    # T25000系の正面（流線形の高速電車）
    cx = 240
    b += (f'<path d="M {cx - 92} 334 C {cx - 96} 268 {cx - 70} 196 {cx} 186 C {cx + 70} 196 {cx + 96} 268 {cx + 92} 334 Z" '
          f'fill="url(#body)"/>')
    b += (f'<path d="M {cx - 58} 236 C {cx - 50} 206 {cx - 26} 196 {cx} 195 C {cx + 26} 196 {cx + 50} 206 {cx + 58} 236 '
          f'C {cx + 30} 228 {cx - 30} 228 {cx - 58} 236 Z" fill="#101820"/>')
    b += (f'<path d="M {cx - 92} 300 C {cx - 60} 288 {cx + 60} 288 {cx + 92} 300 L {cx + 93} 310 '
          f'C {cx + 60} 298 {cx - 60} 298 {cx - 93} 310 Z" fill="{ORANGE}"/>')
    b += (f'<path d="M {cx - 93} 310 C {cx - 60} 298 {cx + 60} 298 {cx + 93} 310 L {cx + 93} 317 '
          f'C {cx + 60} 305 {cx - 60} 305 {cx - 93} 317 Z" fill="{BLUE}"/>')
    for sx in (-1, 1):
        b += f'<ellipse cx="{cx + sx * 58}" cy="276" rx="13" ry="6" fill="#fff7d6"/>'
        b += f'<ellipse cx="{cx + sx * 58}" cy="276" rx="24" ry="11" fill="#fff7d6" opacity="0.22"/>'
    b += rect(cx - 22, 250, 44, 14, '#2a3038', rx=2) + text(cx, 260.5, 'T25000', 8, '#e8eef5')
    b += rect(cx - 96, 332, 192, 10, '#1b1d22')
    # 文字
    b += text(240, 52, '信町高速鉄道', 18, '#cfe3ff', extra='letter-spacing="6"')
    b += text(240, 104, '3D運転士', 48, '#ffffff', extra='stroke="#1e5aa8" stroke-width="2" paint-order="stroke"')
    b += text(240, 132, '〜 最高350km/h の T25000系で３つの路線を走ろう 〜', 13, '#ffe2b0')
    b += text(240, 152, '発車メロディ: Clarinet_Express 様（信町高速鉄道のために制作、許可を得て使用）', 8.5, '#cfd8e3',
              weight='normal')
    b += rect(120, 318, 240, 22, '#000000', rx=11, extra='opacity="0.5"')
    b += text(240, 334, 'Enter キーかタップでスタート', 12, '#ffffff')
    b += text(240, 354, '※ 音が出ないときは、画面を一度クリックしてください', 9, '#cfd8e3', weight='normal')
    return svg(480, 360, b, defs)


def panel(title, hint, button=False):
    b = rect(0, 0, 480, 360, '#000', extra='opacity="0.55"')
    b += rect(20, 40, 440, 296, '#0e1a30', rx=12, extra='opacity="0.95" stroke="#3fa9f5" stroke-width="1.5"')
    b += f'<path d="M 32 40 H 448 Q 460 40 460 52 V 76 H 20 V 52 Q 20 40 32 40 Z" fill="{BLUE}"/>'
    b += rect(20, 76, 440, 3, ORANGE)
    b += text(240, 66, title, 18, '#ffffff', extra='letter-spacing="2"')
    if button:
        # タップしやすいように、ボタンの形にしておく（どこをタップしても進む）
        b += rect(110, 311, 260, 22, BLUE, rx=11, extra='stroke="#cfe3ff" stroke-width="1.5"')
        b += text(240, 326, hint, 11.5, '#ffffff')
    else:
        b += text(240, 326, hint, 11.5, '#cfe3ff', weight='normal')
    return svg(480, 360, b)


def icon(label, color):
    b = rect(1, 1, 46, 46, color, rx=9, extra='stroke="#fff" stroke-width="2"')
    b += text(24, 30, label, 13 if len(label) <= 2 else 10, '#fff')
    return svg(48, 48, b), 24, 24


# ---------------------------------------------------------------------------
# タップ操作のボタン（運転台の計器盤と同じ色づかい。運転の景色が少し透けて見える）
# ---------------------------------------------------------------------------
TAP_BUTTON = 52     # ボタンの大きさ（ステージのピクセル）
# 役割: (大きい記号, 小さい文字, 色)
TAP_BUTTONS = {
    '力行': ('▲', '力行', '#3fb6ff'),
    'ブレーキ': ('▼', 'ブレーキ', '#ff9f1a'),
    '非常': ('EB', '非常', '#ff3b30'),
    '警笛': ('♪', '警笛', '#ffd34d'),
}


def tap_button(role):
    big, small, col = TAP_BUTTONS[role]
    s = TAP_BUTTON
    b = rect(1, 1, s - 2, s - 2, '#14181e', rx=9, extra='opacity="0.78" stroke="#4a5566" stroke-width="1.5"')
    if role == '非常':
        # 非常ブレーキは赤いきのこ形のボタン
        b += circle(s / 2, s / 2 - 2, 19, '#5a0a0a') + circle(s / 2, s / 2 - 3, 16.5, col)
        b += f'<ellipse cx="{s / 2}" cy="{s / 2 - 9}" rx="10" ry="4.5" fill="#ffffff" opacity="0.28"/>'
        b += text(s / 2, s / 2 + 2, big, 13, '#ffffff')
        b += text(s / 2, s - 4, small, 8, '#ffd0cc')
    else:
        b += rect(6, 6, s - 12, s - 12, '#232a35', rx=6, extra=f'stroke="{col}" stroke-width="1.6"')
        b += rect(8, 8, s - 16, 4, '#ffffff', rx=2, extra='opacity="0.10"')
        b += text(s / 2, s / 2 + 3, big, 18, col)
        b += text(s / 2, s - 11, small, 8 if len(small) > 2 else 9, '#dfe7f1')
    return svg(s, s, b), s / 2, s / 2


def menu_button(n):
    """路線・車両を選ぶ画面の番号ボタン（リストの番号と同じ数字）。"""
    w, h = 56, 42
    b = rect(1, 1, w - 2, h - 2, BLUE, rx=9, extra='stroke="#cfe3ff" stroke-width="2"')
    b += rect(4, h - 9, w - 8, 3, ORANGE, rx=1.5)
    b += text(w / 2, h / 2 + 8, str(n), 22, '#ffffff')
    return svg(w, h, b), w / 2, h / 2


# ---------------------------------------------------------------------------
# 効果音（22050Hz・モノラル・16bit の WAV）
# ---------------------------------------------------------------------------
RATE = 22050


def _norm(x, peak):
    """いちばん大きいところが peak（0〜1）になるように音量をそろえる。"""
    m = float(np.abs(x).max())
    return x * (peak / m) if m > 0 else x


def _wav(x):
    x = np.clip(x, -1, 1)
    data = (x * 32000).astype('<i2').tobytes()
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data)
    return buf.getvalue(), RATE, len(x)


def _t(sec):
    return np.arange(int(RATE * sec)) / RATE


def _env(n, a, r, sus=1.0):
    e = np.ones(n) * sus
    na, nr = int(RATE * a), int(RATE * r)
    if na:
        e[:na] = np.linspace(0, sus, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def _lowpass(x, cutoff):
    a = math.exp(-2 * math.pi * cutoff / RATE)
    y = np.zeros_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def _noise(n, seed=1):
    return np.random.default_rng(seed).uniform(-1, 1, n)


def _bell(f, dur, decay=3.0):
    t = _t(dur)
    x = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.76 * t) + 0.2 * np.sin(2 * np.pi * f * 5.4 * t))
    return x * np.exp(-decay * t)


def _place(dst, src, at):
    i = int(RATE * at)
    j = min(len(dst), i + len(src))
    dst[i:j] += src[:j - i]


def snd_horn(volume=0.55, dur=1.3, far=False):
    t = _t(dur)
    x = np.zeros_like(t)
    for f in (311.1, 392.0):
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5 * t)
        ph = 2 * np.pi * f * np.cumsum(vib) / RATE
        x += sum(np.sin(k * ph) / k for k in range(1, 7))
    x = x / 4 * _env(len(t), 0.06, 0.35)
    if far:
        x = _lowpass(x, 900) * 0.5
        echo = np.zeros(len(x) + int(RATE * 0.25))
        echo[:len(x)] += x
        echo[int(RATE * 0.25):] += 0.35 * x
        x = echo
    return _wav(x * volume)


def snd_door_chime():
    out = np.zeros(int(RATE * 2.2))
    for k in range(3):
        _place(out, _bell(1318.5, 0.6, 5) * 0.45, k * 0.7)
        _place(out, _bell(1046.5, 0.8, 4) * 0.45, k * 0.7 + 0.3)
    return _wav(out)


def snd_ats_bell():
    t = _t(1.0)
    strike = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 24 * t))
    x = (np.sin(2 * np.pi * 2093 * t) + 0.6 * np.sin(2 * np.pi * 2793 * t)) * strike
    x += 0.15 * _noise(len(t), 3) * strike
    return _wav(x * 0.35)


def snd_joint():
    out = np.zeros(int(RATE * 0.45))
    for at, vol in ((0.0, 1.0), (0.12, 0.85)):
        t = _t(0.09)
        thump = np.sin(2 * np.pi * 85 * t) * np.exp(-40 * t)
        click = _lowpass(_noise(len(t), int(at * 100) + 5), 3500) * np.exp(-90 * t) * 1.5
        _place(out, (thump + click) * 0.55 * vol, at)
    return _wav(out)


def snd_motor():
    t = _t(1.0)
    x = 0.5 * np.sin(2 * np.pi * 220 * t) + 0.25 * np.sin(2 * np.pi * 440 * t) + 0.15 * np.sin(2 * np.pi * 660 * t)
    x += 0.18 * np.sin(2 * np.pi * 1100 * t) + 0.1 * np.sin(2 * np.pi * 1760 * t)
    x *= 1 + 0.1 * np.sin(2 * np.pi * 6 * t)
    return _wav(x * 0.28)


def snd_rumble():
    n = int(RATE * 2.0)
    x = _lowpass(_lowpass(_noise(n + 2000, 9), 300), 200)
    x = x[2000:]
    fade = int(RATE * 0.2)
    x[:fade] = x[:fade] * np.linspace(0, 1, fade) + x[-fade:] * np.linspace(1, 0, fade)
    x = x[:-fade]
    return _wav(x / max(1e-6, np.abs(x).max()) * 0.5)


def snd_passing():
    dur = 3.2
    n = int(RATE * dur)
    t = _t(dur)
    env = np.minimum(1, t / 0.25) * np.exp(-np.maximum(0, t - 0.4) * 1.0)
    x = _lowpass(_noise(n, 11), 900) * 1.6 * env
    for k in range(14):
        at = 0.15 + k * 0.19
        tt = _t(0.06)
        _place(x, np.sin(2 * np.pi * 120 * tt) * np.exp(-45 * tt) * 0.5 * np.exp(-at * 0.6), at)
    return _wav(x * 0.6)


def snd_air(dur=0.9, vol=0.4):
    t = _t(dur)
    x = _noise(len(t), 21) - _lowpass(_noise(len(t), 21), 2500)
    return _wav(x * np.exp(-2.5 * t) * vol)


def snd_door():
    out = np.zeros(int(RATE * 1.2))
    t = _t(0.5)
    _place(out, (_noise(len(t), 4) - _lowpass(_noise(len(t), 4), 2000)) * np.exp(-6 * t) * 0.35, 0)
    tt = _t(0.15)
    _place(out, np.sin(2 * np.pi * 70 * tt) * np.exp(-25 * tt) * 0.6, 0.85)
    return _wav(out)


def snd_arpeggio(freqs, step, tail=0.6, vol=0.35):
    out = np.zeros(int(RATE * (step * len(freqs) + tail + 0.6)))
    for i, f in enumerate(freqs):
        _place(out, _bell(f, tail + 0.6, 4) * vol, i * step)
    return _wav(out)


def snd_fanfare():
    out = np.zeros(int(RATE * 2.6))
    chords = [((523, 659, 784), 0, .35), ((587, 740, 880), .36, .35), ((659, 830, 988), .72, .3),
              ((784, 988, 1175), 1.04, 1.4)]
    for fs, at, d in chords:
        t = _t(d)
        c = sum(sum(np.sin(2 * np.pi * f * k * t) / k ** 1.4 for k in range(1, 5)) for f in fs)
        _place(out, c * _env(len(t), 0.02, min(0.2, d * 0.5)) * 0.12, at)
    return _wav(out)


def snd_select():
    t = _t(0.16)
    f = np.where(t < 0.07, 880, 1320)
    return _wav(np.sin(2 * np.pi * f * t) * _env(len(t), 0.005, 0.05) * 0.35)


def snd_alarm():
    """アクシデントの警報（運転台のブザー。2 つの高さを交互に）。"""
    out = np.zeros(int(RATE * 1.7))
    for k in range(6):
        f = 960 if k % 2 == 0 else 760
        t = _t(0.24)
        tone = np.sign(np.sin(2 * np.pi * f * t)) * 0.5 + np.sin(2 * np.pi * f * 2 * t) * 0.2
        _place(out, _lowpass(tone, 3500) * _env(len(t), 0.01, 0.04), k * 0.27)
    return _wav(out)


def snd_impact():
    """障害物に当たったときの「ゴトン」という鈍い音（こわくない程度）。"""
    out = np.zeros(int(RATE * 1.0))
    t = _t(0.5)
    _place(out, np.sin(2 * np.pi * 70 * t) * np.exp(-9 * t), 0)
    _place(out, _lowpass(_noise(len(t), 41), 600) * np.exp(-12 * t) * 1.5, 0)
    _place(out, np.sin(2 * np.pi * 55 * t) * np.exp(-10 * t) * 0.6, 0.18)
    return _wav(out)


def snd_squeal():
    """カーブで車輪がきしむ「キーー」という音（くり返して鳴らせるように、終わりと始めをなめらかにつないである）。"""
    dur = 2.15
    t = _t(dur)
    rnd = np.random.default_rng(31)
    x = np.zeros_like(t)
    for f, a in ((2850, 1.0), (3420, 0.5), (4180, 0.28), (5650, 0.15)):
        vib = 1 + 0.006 * np.sin(2 * np.pi * (5.5 + f / 2000) * t + rnd.uniform(0, 6))
        ph = 2 * np.pi * f * np.cumsum(vib) / RATE
        am = 0.6 + 0.4 * np.sin(2 * np.pi * (2.7 + f / 3000) * t + rnd.uniform(0, 6))
        x += a * np.sin(ph) * am
    x += 0.18 * (_noise(len(t), 33) - _lowpass(_noise(len(t), 33), 2200))
    fade = int(RATE * 0.15)
    x[:fade] = x[:fade] * np.linspace(0, 1, fade) + x[-fade:] * np.linspace(1, 0, fade)
    x = x[:-fade]
    return _wav(x / max(1e-6, np.abs(x).max()) * 0.5)


# 効果音（名前: 作る関数）。最大音量（peak）はそろえてある。
_PEAK = {'警笛': 0.95, '遠くの警笛': 0.6, 'ドアチャイム': 0.9, 'ATSベル': 0.8, 'ジョイント': 0.9,
         'モーター': 0.7, '走行音': 0.45, 'すれ違い': 0.95, 'ブレーキ緩め': 0.6, 'ドア': 0.8, '採点': 0.9, 'ピタ停車': 0.9,
         '結果': 0.9, '決定': 0.8, 'きしみ': 0.6, '警報': 0.75, '衝突': 0.9}


def _normalized(name, fn):
    def make():
        data, rate, count = fn()
        with wave.open(io.BytesIO(data)) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(float) / 32000
        return _wav(_norm(x, _PEAK[name]))
    return make


SOUNDS = {name: _normalized(name, fn) for name, fn in {
    '警笛': lambda: snd_horn(),
    '遠くの警笛': lambda: snd_horn(volume=0.45, dur=1.6, far=True),
    'ドアチャイム': snd_door_chime,
    'ATSベル': snd_ats_bell,
    'ジョイント': snd_joint,
    'モーター': snd_motor,
    '走行音': snd_rumble,
    'すれ違い': snd_passing,
    'ブレーキ緩め': lambda: snd_air(0.7, 0.3),
    'ドア': snd_door,
    '採点': lambda: snd_arpeggio([523, 659, 784, 1047], 0.09),
    'ピタ停車': lambda: snd_arpeggio([1047, 1319, 1568, 2093, 2637], 0.06, 0.9, 0.3),
    '結果': snd_fanfare,
    '決定': snd_select,
    'きしみ': snd_squeal,
    '警報': snd_alarm,
    '衝突': snd_impact,
}.items()}

# どのスプライトにどの音を入れるか（音量を別々に変えられるように分けている）
SOUND_SPRITES = {
    '効果音': ['警笛', '遠くの警笛', 'ドアチャイム', 'ATSベル', 'すれ違い', 'ブレーキ緩め', 'ドア', '採点', 'ピタ停車',
            '結果', '決定', '警報', '衝突'],
    'モーター音': ['モーター'],
    '走行音': ['走行音', 'ジョイント'],
    'きしみ音': ['きしみ'],
}


# ---------------------------------------------------------------------------
# 発車メロディ（Clarinet_Express 様の作曲。許可を得て使用している別扱いの音源）
#   元のファイルは generator/sounds/melodies/ にある（そこの README.md を読むこと）。
#   .sb3 に入れるときに、3 曲の大きさ（RMS）をそろえる。形式（44.1kHz ステレオ）はそのまま。
# ---------------------------------------------------------------------------
MELODY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sounds', 'melodies')
MELODY_NAMES = ['CLEX202', 'CLEX203', 'CLEX204']
MELODY_RMS_DB = -17.5     # そろえる大きさ [dBFS]。ドアチャイム（約 −13.5）より少し小さく、合成していた旧メロディ（約 −15）くらい
MELODY_PEAK = 0.95        # 音が割れないように、いちばん大きいところはこれ以下にする


def melody(name):
    with wave.open(os.path.join(MELODY_DIR, f'{name}.wav')) as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if width != 2:
            raise ValueError(f'{name}.wav は 16bit の WAV にしてください')
        x = np.frombuffer(w.readframes(n), dtype='<i2').astype(float) / 32768
    rms = float(np.sqrt((x ** 2).mean()))
    gain = 10 ** (MELODY_RMS_DB / 20) / max(rms, 1e-9)
    gain = min(gain, MELODY_PEAK / max(float(np.abs(x).max()), 1e-9))
    y = np.clip(np.round(x * gain * 32768), -32768, 32767).astype('<i2')
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(y.tobytes())
    return buf.getvalue(), rate, n
