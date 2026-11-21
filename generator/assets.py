"""コスチューム（SVG）と効果音（WAV）を作る。

すべてプログラムで描いた・合成したオリジナル素材。
3D の中に置く物（標識・駅名標・木・建物など）は「20ピクセル＝1メートル」で描き、
回転中心を根元（下の中央）にしてある。改造で絵を足すときも同じ決まりで描くと
3D の中で正しい大きさになる。
"""
import io
import math
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
                'ビル3': (10, 40, '#3f4c63', '#6c7f9c'), 'ビル4': (22, 12, '#b9b2a8', '#7d756b')}[name]
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
            if name == 'ビル4':
                b += rect(w * .1, h * .05, w * .8, h * .18, BLUE) + text(w / 2, h * .19, '信町ストア', h * .12, '#fff')
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
    raise KeyError(name)


SCENERY_NAMES = ['松', '杉', '広葉樹', '紅葉', '家', 'ビル1', 'ビル2', 'ビル3', 'ビル4', '電柱', '鳥居', '灯籠']
SCENERY_HALF_WIDTH = {'松': 3, '杉': 2.3, '広葉樹': 3.5, '紅葉': 3, '家': 4.5, 'ビル1': 7, 'ビル2': 9, 'ビル3': 5,
                      'ビル4': 11, '電柱': 0.8, '鳥居': 3.5, '灯籠': 0.6}


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
    b += _gauge(*SPEEDO, 160, 5, 20, 'km/h', red_from=130)
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
    # T25000系の正面
    cx = 240
    b += f'<path d="M {cx - 78} 330 L {cx - 72} 170 Q {cx} 150 {cx + 72} 170 L {cx + 78} 330 Z" fill="url(#body)"/>'
    b += f'<path d="M {cx - 66} 238 L {cx - 62} 182 Q {cx} 166 {cx + 62} 182 L {cx + 66} 238 Z" fill="#101820"/>'
    b += rect(cx - 30, 174, 60, 12, '#1a0d00', rx=2) + text(cx, 183.5, '信町高速鉄道', 8.5, ORANGE)
    b += rect(cx - 77, 250, 154, 9, ORANGE) + rect(cx - 77, 259, 154, 6, BLUE)
    for sx in (-1, 1):
        b += circle(cx + sx * 52, 285, 8, '#fff7d6') + circle(cx + sx * 52, 285, 14, '#fff7d6', extra='opacity="0.25"')
        b += rect(cx + sx * 52 - 7, 298, 14, 5, '#ff4040', rx=2)
    b += rect(cx - 20, 270, 40, 18, '#2a3038', rx=2) + text(cx, 283, 'T25000', 8, '#e8eef5')
    b += rect(cx - 80, 330, 160, 10, '#1b1d22')
    # 文字
    b += text(240, 52, '信町高速鉄道', 18, '#cfe3ff', extra='letter-spacing="6"')
    b += text(240, 104, '3D運転士', 48, '#ffffff', extra='stroke="#1e5aa8" stroke-width="2" paint-order="stroke"')
    b += text(240, 132, '〜 T25000系で３つの路線を走ろう 〜', 13, '#ffe2b0')
    b += rect(140, 334, 200, 20, '#000000', rx=10, extra='opacity="0.45"')
    b += text(240, 348, 'スペースキーでスタート', 12, '#ffffff')
    return svg(480, 360, b, defs)


def panel(title, hint):
    b = rect(0, 0, 480, 360, '#000', extra='opacity="0.55"')
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


def snd_departure_melody():
    notes = [(659, .25), (784, .25), (880, .25), (1047, .5), (880, .25), (784, .25), (659, .25), (587, .25),
             (659, .25), (784, .5), (0, .1), (1047, .25), (988, .25), (1047, .9)]
    out = np.zeros(int(RATE * 5.0))
    at = 0.0
    for f, d in notes:
        if f:
            tone = _bell(f, d + 0.6, 3.5) * 0.35 + _bell(f / 2, d + 0.6, 4) * 0.12
            _place(out, tone, at)
        at += d
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


SOUNDS = {
    '警笛': lambda: snd_horn(),
    '遠くの警笛': lambda: snd_horn(volume=0.45, dur=1.6, far=True),
    'ドアチャイム': snd_door_chime,
    '発車メロディ': snd_departure_melody,
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
}
