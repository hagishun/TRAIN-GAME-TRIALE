"""コスチューム（SVG）と効果音（WAV）を作る。

発車メロディ（generator/sounds/CLEX*.wav）以外は、すべてプログラムで描いた・合成したオリジナル素材。
発車メロディは Clarinet_Express 様が信町高速鉄道のために制作した曲で、許可を得て使用している
（出典 https://scratch.mit.edu/projects/1440158623/ ）。このリポジトリのほかの素材とは権利が別なので、
ほかの作品に勝手に再利用しないこと。

3D の中に置く物（標識・駅名標・木・建物など）は「20ピクセル＝1メートル」で描き、
回転中心を根元（下の中央）にしてある。改造で絵を足すときも同じ決まりで描くと
3D の中で正しい大きさになる。
"""
import hashlib
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
    return airport_costume(name)


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
# 信町空港（田原海岸線）の建物と飛行機。航空会社は架空。
#   飛行機の絵は 20px = 1m、回転中心は車輪の下（地面）。「_右」「_左」は横から見た絵で、機首の向き。
#   「_前」は正面（遠くから向かってくる・遠ざかる機体）。
# ---------------------------------------------------------------------------
AIRLINES = {
    # 名前: (尾翼の色, 帯の色, 英語の名前)
    '信町エア': (BLUE, ORANGE, 'SHINMACHI AIR'),
    'うみかぜ航空': ('#1f8f8c', '#7fd3e0', 'UMIKAZE AIRLINES'),
}
PLANE_LEN, PLANE_SPAN, PLANE_H = 38, 36, 13


def plane_side(airline, facing):
    """横から見た旅客機（全長 38m）。facing は機首の向き '右' か '左'。"""
    tail, stripe, label = AIRLINES[airline]
    w, h = PLANE_LEN * PX_PER_M, PLANE_H * PX_PER_M
    flip = facing == '左'
    X = (lambda x: w - x) if flip else (lambda x: x)

    def P(pts, fill, extra=''):
        return poly([(X(x), y) for x, y in pts], fill, extra)

    cy, r = h - 68, 40          # 胴体の中心の高さ（地面から 3.4m）と半径 2m
    b = ''
    # 水平尾翼（奥側）・垂直尾翼
    b += P([(20, cy - 18), (95, cy - 26), (130, cy - 14), (40, cy - 8)], '#9aa3ad')
    b += P([(28, cy - 30), (70, 8), (118, 8), (150, cy - 34)], tail)
    b += P([(52, 60), (80, 22), (112, 22), (122, 60)], stripe, 'opacity="0.9"')
    # 胴体（機首は丸く、尾部は上に細くなる）
    body = [(16, cy - 28), (150, cy - r), (660, cy - r), (705, cy - 34), (735, cy - 14), (744, cy + 4), (735, cy + 22),
            (700, cy + 36), (640, cy + r), (170, cy + r), (60, cy + 4)]
    b += P(body, '#f4f6f8', 'stroke="#c4cad0" stroke-width="1.5"')
    b += P([(70, cy + 8), (170, cy + 18), (650, cy + 18), (700, cy + 24), (690, cy + 30), (640, cy + 32), (170, cy + 32)],
           stripe)
    b += P([(170, cy + 32), (640, cy + 32), (690, cy + 30), (640, cy + r), (170, cy + r)], '#d9dee3')
    # 客室の窓・操縦室の窓・ドア
    for i in range(34):
        wx = 175 + i * 14.5
        b += rect(f'{X(wx) - 3:.1f}', cy - 12, 6, 8, '#2a3644', rx=2.5)
    b += P([(694, cy - 18), (712, cy - 24), (730, cy - 12), (708, cy - 8)], '#1d2733')
    for dx in (160, 610):
        b += rect(f'{X(dx) - 7:.1f}', cy - 24, 14, 40, 'none', rx=3, extra='stroke="#aab2bb" stroke-width="1.5"')
    # 主翼（手前側）とエンジン
    b += P([(300, cy + 14), (450, cy + 6), (470, cy + 16), (330, cy + 28)], '#b8c0c8')
    b += f'<ellipse cx="{X(410):.1f}" cy="{cy + 38}" rx="50" ry="15" fill="#c9cfd5" stroke="#8d969f" stroke-width="2"/>'
    b += f'<ellipse cx="{X(456):.1f}" cy="{cy + 38}" rx="6" ry="12" fill="#3a4048"/>'
    # 主脚・前脚
    for gx in (350, 368):
        b += line(X(gx), cy + 30, X(gx), h - 10, '#555', 5) + circle(X(gx), h - 9, 9, '#222')
    b += line(X(650), cy + 30, X(650), h - 8, '#555', 4) + circle(X(650), h - 7, 7, '#222')
    # 会社名
    b += text(X(430), cy - 22, f'{airline}  {label}', 22, tail)
    return svg(w, h, b), w / 2, h


def plane_front(airline):
    """正面から見た旅客機（翼幅 36m）。向かってくる機体にも、遠ざかる機体にも使う。"""
    tail, stripe, _ = AIRLINES[airline]
    w, h = PLANE_SPAN * PX_PER_M, PLANE_H * PX_PER_M
    cx, cy, r = w / 2, h - 68, 40
    b = ''
    # 垂直尾翼・水平尾翼（奥）
    b += poly([(cx - 7, cy - r + 4), (cx - 5, 6), (cx + 5, 6), (cx + 7, cy - r + 4)], tail)
    b += poly([(cx - 125, cy - 40), (cx + 125, cy - 40), (cx + 125, cy - 33), (cx - 125, cy - 33)], '#9aa3ad')
    # 主翼（少し上に反っている）
    b += poly([(4, cy - 4), (cx - 30, cy + 14), (cx + 30, cy + 14), (w - 4, cy - 4), (w - 4, cy + 2), (cx + 30, cy + 24),
               (cx - 30, cy + 24), (4, cy + 2)], '#c3cad1')
    for sx in (-1, 1):
        b += rect(cx + sx * 352 - 3, cy - 14, 6, 12, stripe)        # 翼端
        ex = cx + sx * 130
        b += line(ex, cy + 16, ex, cy + 22, '#8d969f', 6)
        b += circle(ex, cy + 44, 27, '#c9cfd5', 'stroke="#8d969f" stroke-width="2"') + circle(ex, cy + 44, 18, '#2a3038')
        b += circle(ex, cy + 44, 5, '#9aa3ad')
        b += line(cx + sx * 34, cy + r - 6, cx + sx * 34, h - 10, '#555', 5) + rect(cx + sx * 34 - 9, h - 18, 18, 18, '#222',
                                                                                   rx=4)
    b += line(cx, cy + r - 4, cx, h - 8, '#555', 4) + rect(cx - 6, h - 15, 12, 15, '#222', rx=3)
    # 胴体（丸）と操縦室の窓・帯
    b += circle(cx, cy, r, '#f4f6f8', 'stroke="#c4cad0" stroke-width="1.5"')
    b += f'<path d="M {cx - r + 3} {cy + 12} Q {cx} {cy + 26} {cx + r - 3} {cy + 12} L {cx + r - 6} {cy + 20} Q {cx} {cy + 33} {cx - r + 6} {cy + 20} Z" fill="{stripe}"/>'
    b += poly([(cx - 26, cy - 12), (cx - 6, cy - 16), (cx - 6, cy - 4), (cx - 28, cy - 2)], '#1d2733')
    b += poly([(cx + 26, cy - 12), (cx + 6, cy - 16), (cx + 6, cy - 4), (cx + 28, cy - 2)], '#1d2733')
    b += circle(cx - 46, cy + 18, 5, '#fff7d6') + circle(cx + 46, cy + 18, 5, '#fff7d6')
    return svg(w, h, b), w / 2, h


def airport_building(name):
    if name in ('ターミナル', 'ターミナル_看板'):
        def f(w, h):
            defs_id = 'g' + str(abs(hash(name)) % 1000)
            b = (f'<defs><linearGradient id="{defs_id}" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0" stop-color="#a9d0e8"/><stop offset="1" stop-color="#5e8fb4"/></linearGradient></defs>')
            b += rect(0, h - 20, w, 20, '#c9c4b8')
            b += rect(10, 60, w - 20, h - 80, f'url(#{defs_id})')
            for x in range(10, w - 9, 30):
                b += rect(x, 60, 3, h - 80, '#e8eef2')
            for y in (150, 240):
                b += rect(10, y, w - 20, 4, '#e8eef2')
            b += f'<path d="M -2 66 Q {w / 2} 18 {w + 2} 66 L {w + 2} 52 Q {w / 2} 2 -2 52 Z" fill="#f4f5f2" stroke="#c8ccd0"/>'
            b += rect(w * .35, h - 70, w * .3, 8, '#f4f5f2') + rect(w * .38, h - 62, w * .24, 42, '#3e5a70')
            if name == 'ターミナル_看板':
                b += rect(w * .12, 84, w * .76, 62, '#16324f', rx=4)
                b += text(w / 2, 124, '信町空港', 34, '#ffffff', extra='letter-spacing="6"')
                b += text(w / 2, 141, 'SHINMACHI AIRPORT', 13, '#ffd27a', extra='letter-spacing="2"')
            return b
        return world(name, 30, 16, f)
    if name == '管制塔':
        def f(w, h):
            b = poly([(60, h), (140, h), (128, h - 120), (72, h - 120)], '#d6d8d4')
            b += rect(76, 210, 48, h - 330, '#e2e4e0') + rect(96, 230, 8, h - 360, '#b9bcb8')
            b += poly([(30, 210), (170, 210), (190, 120), (10, 120)], '#2c4a58')
            for x in range(26, 180, 22):
                b += line(x, 124, x + (2 if x > 100 else -2), 206, '#cfd6da', 2)
            b += rect(4, 104, 192, 18, '#f2f3f0') + rect(40, 210, 120, 14, '#f2f3f0')
            b += rect(97, 40, 6, 64, '#9a9da0') + rect(70, 80, 60, 6, '#9a9da0') + circle(100, 36, 6, '#ff3b30')
            b += text(100, 260, 'TOWER', 18, '#5a6670')
            return b
        return world(name, 10, 46, f)
    if name == '格納庫':
        def f(w, h):
            b = rect(0, 120, w, h - 120, '#c4c8cc')
            b += f'<path d="M 0 130 Q {w / 2} -60 {w} 130 Z" fill="#9aa4ae"/>'
            b += rect(70, 170, w - 140, h - 170, '#dfe3e6')
            for x in range(70, w - 69, 86):
                b += rect(x, 170, 3, h - 170, '#aab2ba')
            b += text(w / 2, 155, 'SHINMACHI AIR  MAINTENANCE', 26, BLUE)
            return b
        return world(name, 50, 20, f)
    if name == '吹き流し':
        def f(w, h):
            b = rect(4, 0, 4, h, '#8d8a84')
            for i in range(5):
                x0 = 8 + i * 10
                b += poly([(x0, 4 + i * 1.6), (x0 + 10, 4 + (i + 1) * 1.6), (x0 + 10, 24 - (i + 1) * 1.6),
                           (x0, 24 - i * 1.6)], '#ff6a1a' if i % 2 == 0 else '#ffffff')
            return b
        return world(name, 3, 6.5, f)
    if name == '進入灯':
        def f(w, h):
            b = rect(w / 2 - 3, 12, 6, h - 12, '#8d8a84') + rect(4, 8, w - 8, 6, '#6d6a64')
            for i in range(7):
                b += circle(10 + i * (w - 20) / 6, 8, 5, '#fff3b0')
            return b
        return world(name, 8, 3, f)
    raise KeyError(name)


AIRPORT_NAMES = ['ターミナル', 'ターミナル_看板', '管制塔', '格納庫', '吹き流し', '進入灯']
PLANE_NAMES = [f'飛行機_{a}_{v}' for a in AIRLINES for v in ('右', '左', '前')]
PARKED_NAMES = [f'駐機_{a}' for a in AIRLINES]


def airport_costume(name):
    if name.startswith('飛行機_'):
        _, airline, view = name.split('_')
        return plane_front(airline) if view == '前' else plane_side(airline, view)
    if name.startswith('駐機_'):
        return plane_side(name[3:], '右')
    return airport_building(name)


SCENERY_NAMES = ['松', '杉', '広葉樹', '紅葉', '家', 'ビル1', 'ビル2', 'ビル3', '電柱', '鳥居', '灯籠'] + \
    [f'店_{sh[0]}' for sh in SHOPS] + AIRPORT_NAMES + PARKED_NAMES + PLANE_NAMES
SCENERY_HALF_WIDTH = {'松': 3, '杉': 2.3, '広葉樹': 3.5, '紅葉': 3, '家': 4.5, 'ビル1': 7, 'ビル2': 9, 'ビル3': 5,
                      '電柱': 0.8, '鳥居': 3.5, '灯籠': 0.6, 'ターミナル': 15, 'ターミナル_看板': 15, '管制塔': 5,
                      '格納庫': 25, '吹き流し': 1.5, '進入灯': 4}
SCENERY_HALF_WIDTH.update({f'店_{sh[0]}': SHOP_SIZE[sh[1]][0] / 2 for sh in SHOPS})
SCENERY_HALF_WIDTH.update({n: PLANE_LEN / 2 for n in PARKED_NAMES + PLANE_NAMES})


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
    b += text(240, 152, '♪ 発車メロディ: Clarinet_Express 様（信町高速鉄道のために制作・許可を得て使用）', 9, '#cfe3ff',
              weight='normal')
    b += rect(120, 318, 240, 22, '#000000', rx=11, extra='opacity="0.5"')
    b += text(240, 334, 'Enter キーかクリックでスタート', 12, '#ffffff')
    b += text(240, 354, '※ 音が出ないときは、画面を一度クリックしてください', 9, '#cfd8e3', weight='normal')
    return svg(480, 360, b, defs)


def panel(title, hint, credit=None):
    b = rect(0, 0, 480, 360, '#000', extra='opacity="0.55"')
    if credit:
        b += text(240, 351, credit, 8.5, '#cfe3ff', weight='normal')
    b += rect(20, 40, 440, 296, '#0e1a30', rx=12, extra='opacity="0.95" stroke="#3fa9f5" stroke-width="1.5"')
    b += f'<path d="M 32 40 H 448 Q 460 40 460 52 V 76 H 20 V 52 Q 20 40 32 40 Z" fill="{BLUE}"/>'
    b += rect(20, 76, 440, 3, ORANGE)
    b += text(240, 66, title, 18, '#ffffff', extra='letter-spacing="2"')
    b += text(240, 326, hint, 11.5, '#cfe3ff', weight='normal')
    return svg(480, 360, b)


def icon(label, color):
    b = rect(1, 1, 46, 46, color, rx=9, extra='stroke="#fff" stroke-width="2"')
    b += text(24, 30, label, 13 if len(label) <= 2 else 10, '#fff')
    return svg(48, 48, b), 24, 24


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


def snd_jet():
    """遠くを通る旅客機の「ゴォー」という音（低いうなりと、高いキーンという音が少し下がる）。"""
    dur = 5.0
    t = _t(dur)
    env = np.minimum(1, t / 1.6) * np.minimum(1, (dur - t) / 2.2)
    roar = _lowpass(_lowpass(_noise(len(t), 31), 700), 500) * 3.0
    hiss = (_noise(len(t), 32) - _lowpass(_noise(len(t), 32), 1800)) * 0.25
    f = 2600 - 500 * t / dur
    whine = np.sin(2 * np.pi * np.cumsum(f) / RATE) * 0.12 * np.exp(-0.4 * t)
    return _wav((roar + hiss + whine) * env * 0.5)


def snd_select():
    t = _t(0.16)
    f = np.where(t < 0.07, 880, 1320)
    return _wav(np.sin(2 * np.pi * f * t) * _env(len(t), 0.005, 0.05) * 0.35)


# 効果音（名前: 作る関数）。最大音量（peak）はそろえてある。
_PEAK = {'警笛': 0.95, '遠くの警笛': 0.6, 'ドアチャイム': 0.9, 'ATSベル': 0.8, 'ジョイント': 0.9,
         'モーター': 0.7, '走行音': 0.45, 'すれ違い': 0.95, 'ブレーキ緩め': 0.6, 'ドア': 0.8, '採点': 0.9, 'ピタ停車': 0.9,
         '結果': 0.9, '決定': 0.8, '飛行機': 0.7}


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
    '飛行機': snd_jet,
}.items()}

# どのスプライトにどの音を入れるか（音量を別々に変えられるように分けている）
SOUND_SPRITES = {
    '効果音': ['警笛', '遠くの警笛', 'ドアチャイム', 'ATSベル', 'すれ違い', 'ブレーキ緩め', 'ドア', '採点', 'ピタ停車',
            '結果', '決定', '飛行機'],
    'モーター音': ['モーター'],
    '走行音': ['走行音', 'ジョイント'],
}


# ---------------------------------------------------------------------------
# 発車メロディ（Clarinet_Express 様の作品。許可を得て使用）
# ---------------------------------------------------------------------------
MELODY_CREDIT = ('発車メロディ: Clarinet_Express 様（信町高速鉄道のために制作、許可を得て使用。'
                 '出典 https://scratch.mit.edu/projects/1440158623/）')
MELODY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sounds')
# 曲の名前（＝ Scratch の音の名前）と、受け取った原本ファイルの MD5。原本が変わっていないかをビルドのたびに確かめる
MELODIES = {
    'CLEX202': 'eae87d842b08f5192efb2cb1270e692b',
    'CLEX203': '851a24f1b48fa7832281fa7c8bd50469',
    'CLEX204': 'b978e0a237559bb66761d3088a11fe8f',
}
# 3 曲の大きさをそろえる目標（鳴っている部分の RMS）。合成した効果音（ドアチャイム −13dB 前後）より少し控えめにする
MELODY_TARGET_DB = -17.5
MELODY_MAX_PEAK = 0.95


def _active_rms(mono, rate):
    win = max(1, rate // 40)
    n = len(mono) // win
    r = np.sqrt(np.mean(mono[:n * win].reshape(n, win) ** 2, axis=1))
    act = r[r > r.max() * 0.1]
    return float(np.sqrt(np.mean(act ** 2)))


def melody(name):
    """発車メロディを読み込み、音の大きさだけそろえて WAV にする（ステレオ・44.1kHz のまま）。"""
    path = os.path.join(MELODY_DIR, f'{name}.wav')
    raw = open(path, 'rb').read()
    if hashlib.md5(raw).hexdigest() != MELODIES[name]:
        raise ValueError(f'{path} が受け取った原本と違います（MD5 が一致しない）')
    with wave.open(io.BytesIO(raw)) as w:
        ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if sw != 2:
            raise ValueError(f'{name}: 16bit PCM の WAV だけ読み込めます')
        x = np.frombuffer(w.readframes(n), dtype='<i2').astype(float).reshape(-1, ch) / 32768
    gain = 10 ** (MELODY_TARGET_DB / 20) / _active_rms(x.mean(axis=1), rate)
    gain = min(gain, MELODY_MAX_PEAK / float(np.abs(x).max()))
    y = np.clip(x * gain, -1, 1)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((y * 32767).astype('<i2').tobytes())
    return buf.getvalue(), rate, len(y)
