"""路線・車両の元データ（ジェネレータ用）。

ここで決めた値は .sb3 の「路線データ」「車両データ」スプライトにブロックとして書き出される。
Scratch 上で改造するときは、そのスプライトのブロックを直接書き換えればよい。

路線と駅は、ユーザーの路線図「信町高速鉄道仮路線図」に合わせている。
駅間距離は路線図上の駅の間隔をおおよその目安にして換算したもの（実際の縮尺ではない）。
"""

# 車両（同梱は T25000系 の 1 種類）
CARS = [
    {
        'name': 'T25000系',
        'desc': 'T25000系 高速電車（8両・最高350km/h）',
        'cars': 8,                 # 編成両数（1両 20m）
        'accel': 4.0,              # 起動加速度 [km/h/s]
        'const_power': 220,        # 定出力に入る速度 [km/h]（ここから加速が落ちる）
        'char_speed': 310,         # 特性域に入る速度 [km/h]（さらに加速が落ちる）
        'max_speed': 350,          # 最高速度 [km/h]
        'brake_max': 5.4,          # 常用最大(B8)の減速度 [km/h/s]
        'brake_eb': 6.6,           # 非常ブレーキの減速度 [km/h/s]
        'brake_lag': 0.6,          # ブレーキの遅れ（時定数）[秒]
        'power_lag': 0.4,          # 力行の遅れ（時定数）[秒]
        'low_speed_gain': 0.25,    # 止まる直前にブレーキがよく効く割合
        'res_a': 0.03,             # 走行抵抗（一定分）[km/h/s]
        'res_b': 0.0000026,        # 走行抵抗（速度の2乗に比例する分）[km/h/s ÷ (km/h)^2]
    },
]

# 乗り換え・直通の案内（駅名標の下の帯に小さく出す）
TRANSFER = {
    '信釜': '草河原鉄道 支線',
    '二間六草': '草河原鉄道 直通',
    '高田': '田原海岸線 のりかえ',
    '信早ヶ丘': '神社線・多山横断 直通',
}

# 駅ごとの発車メロディ（曲名は「発車メロディ」スプライトの音の名前）。
# 曲は Clarinet_Express 様の作曲（generator/sounds/melodies/README.md）。
# 同じ路線や運行（エアポート特快など）で、となりの停車駅が同じ曲にならないように並べている。
# 表にない駅では DEFAULT_MELODY が流れる。
DEPARTURE_MELODIES = [
    ('新信町', 'CLEX204'), ('信町', 'CLEX202'), ('二間六草', 'CLEX203'), ('高田', 'CLEX204'),
    ('旧信町城下町', 'CLEX202'), ('信早ヶ丘', 'CLEX203'), ('神社正門', 'CLEX202'), ('信町神社', 'CLEX204'),
    ('六町橋西詰', 'CLEX203'), ('新鎌京橋', 'CLEX202'), ('信町空港', 'CLEX203'), ('紅葉滝', 'CLEX204'),
    ('田原京', 'CLEX202'),
]
DEFAULT_MELODY = 'CLEX202'

# 路線
#  stations: (駅名, 停止位置[m])
#  passing:  通過する駅（ここにない駅は停車）
#  limits:   (開始m, 終了m, 制限km/h)
#  curves:   (開始m, 長さm, 半径m, '右' or '左')
#  grades:   (開始m, 長さm, 勾配‰)  ＋は上り、−は下り
#  viaducts: (開始m, 終了m, 高さm, 坂の長さm)  高架（高い所を走る線路）。開始から「坂の長さ」で上がり、
#            終了の「坂の長さ」手前から下りる。坂は勾配（＋上り・−下り）として自動で足される
#  scenery_until: (路線名, 位置m)  路線の始めからその位置までは、ほかの路線の景色（空はこの路線のまま）にする
#  scenery_left / scenery_right: 沿線に置く物（3D描画スプライトのコスチューム名）
#  accidents: この路線で起きるアクシデントの種類（倒木・落石・動物・踏切の車・強風・大雨・信号故障・モーター不調・非常通報・番線変更）
#  layout: 駅の配線のきまり（番線の数え方 '右' か '左', いつもの番線, 番線変更の番線）。ないときは LAYOUT_DEFAULT
#  layout_stations: {駅名: (数え方, いつも, 変更)}  その駅だけ配線のきまりを変える
#  roof_colors: (屋根の色, 柱の色)  駅の屋根（上屋）の、路線の雰囲気に合わせた色（設定の色と混ぜて使う）
#  roof_stations: {駅名: 長さ}  その駅だけ屋根の長さ（ホームの長さの何倍か）を変える
ROUTES = [
    {
        'name': '信町本線',
        'level': '上級',
        'desc': '信町本線（上級・夕方・速達 6駅停車/13駅・61km）新信町→信早ヶ丘',
        'note': '新信町から信早ヶ丘まで13駅・61km の速達運転。6駅に停車し、ほかの7駅は通過する。\n'
                '街なかは制限が多く、二間六草〜高田・旧信町城下町〜信早ヶ丘の長い区間では 350km/h まで出せる。\n'
                '高田で田原海岸線、信早ヶ丘で神社線と接続。',
        'max_speed': 350,
        'start_time': '17:30:00',
        'sky': '夕方',
        'far': '遠景_街',
        'colors': {
            '地面1': '#6b6259', '地面2': '#615950', '道床1': '#8f867c', '道床2': '#857c73',
            '左外側': '#3d3b42', '右外側': '#3d3b42', '霧': '#8e7f98',
        },
        'left_edge': 9, 'right_edge': 14, 'fog_dist': 900,
        'roof_colors': ('#3c4450', '#dcd5c3'),   # 街: 濃い鉄色の屋根と、クリーム色の柱
        'scenery_left': ['店_信町ストア', 'ビル1', '店_喫茶ひだまり', '店_信町書店', 'ビル2', '店_みどり薬局', '家',
                         '店_ラーメン信町軒', 'ビル3', '店_信町ベーカリー', '電柱', '店_花屋フローラ'],
        'scenery_right': ['ビル2', '店_信町銀行', 'ビル1', '店_ホテル信町', '店_信町デンキ', '家', '店_寿司 信', 'ビル3',
                          '店_信町歯科'],
        'scenery_interval': 36,
        'stations': [
            ('新信町', 500), ('信釜', 3100), ('信町', 7100), ('三間', 10900), ('二間六草', 13100),
            ('信六', 19000), ('際記ヶ野間', 20700), ('信町公園', 24600), ('高田', 31000), ('中ヶ野宮', 39500),
            ('旧信町城下町', 42300), ('坂ヶ野', 52400), ('信早ヶ丘', 61600),
        ],
        'passing': ['信釜', '三間', '信六', '際記ヶ野間', '信町公園', '中ヶ野宮', '坂ヶ野'],
        'limits': [
            (300, 1500, 120), (4900, 5900, 250), (6200, 7300, 160), (12200, 13300, 160), (15500, 16700, 280),
            (20900, 22300, 250), (29800, 31200, 160), (42400, 43800, 220), (60300, 61800, 160),
        ],
        'curves': [
            (1600, 700, 2500, '右'), (5000, 900, 2200, '左'), (8000, 1200, 4000, '右'), (15600, 1100, 3000, '左'),
            (21000, 1300, 2000, '右'), (26000, 1800, 5000, '左'), (34000, 2000, 6000, '右'), (42800, 1300, 1800, '右'),
            (47000, 2500, 5000, '左'), (56000, 2000, 4500, '右'),
        ],
        'grades': [
            (33000, 4000, -10), (44500, 5500, 18), (53000, 4000, -15),
        ],
        'margin': (1.04, 4),
        # この路線で起きるアクシデントの種類（街なか: 踏切・信号・大雨など）
        'accidents': ['踏切の車', '信号故障', '大雨', '非常通報', 'モーター不調', '番線変更'],
    },
    {
        'name': '神社線',
        'level': '中級',
        'desc': '神社線（中級・霧の山あい・3駅・13km・最高260km/h）信早ヶ丘→信町神社',
        'note': '信早ヶ丘から信町神社への参拝路線（13km）。33‰の急な上り坂とカーブが続き、霧で見通しが悪い。最高 260km/h。',
        'max_speed': 260,
        'start_time': '06:45:00',
        'sky': '霧',
        'far': '遠景_山',
        'colors': {
            '地面1': '#4f6b3a', '地面2': '#4a6536', '道床1': '#8c877d', '道床2': '#858077',
            '左外側': '#2e4a2b', '右外側': '#2e4a2b', '霧': '#c7cdd0',
        },
        'left_edge': 8, 'right_edge': 13, 'fog_dist': 320,
        'roof_colors': ('#3e4b40', '#b5452f'),   # 山あい・神社: 緑がかった銅板の屋根と、朱色の柱
        'scenery_left': ['杉', '杉', '灯籠', '店_門前そば', '杉', '鳥居', '杉', '店_みやげ 神社堂', '灯籠'],
        'scenery_right': ['杉', '広葉樹', '店_茶屋 杉の木', '杉', '杉', '店_旅館 信町荘'],
        'scenery_interval': 26,
        'stations': [('信早ヶ丘', 500), ('神社正門', 10400), ('信町神社', 13700)],
        'passing': [],
        'limits': [(300, 1500, 120), (3000, 3900, 200), (6400, 7400, 170), (9500, 10500, 160), (10900, 11900, 150),
                   (12900, 13800, 120)],
        'curves': [(3100, 800, 1200, '左'), (6500, 900, 900, '右'), (8200, 700, 1500, '左'), (11000, 900, 700, '右'),
                   (12500, 500, 1000, '左')],
        'grades': [(1500, 2500, 25), (4000, 4500, 33), (8500, 1800, 10), (10500, 600, -20), (11100, 2000, 33),
                   (13100, 800, 5)],
        'margin': (1.07, 6),
        # 山あい: 倒木・落石・シカ・大雨など
        'accidents': ['倒木', '落石', '動物', '大雨', 'モーター不調', '番線変更'],
    },
    {
        'name': '田原海岸線',
        'level': '初級',
        'desc': '田原海岸線（初級・昼の海沿い・6駅・30km）高田→田原京',
        'note': '高田から田原京まで海沿いを走る6駅・30km。見通しがよく、六町橋西詰〜新鎌京橋の長い直線では 300km/h 以上出せる。\n'
                '高田を出ると坂を上って街の上の高架を走り、坂を下りたところから海沿いになる。はじめての人におすすめ。',
        'max_speed': 350,
        'start_time': '10:20:00',
        'sky': '昼',
        'far': '遠景_海',
        'colors': {
            '地面1': '#c2b58a', '地面2': '#b9ac83', '道床1': '#a39d92', '道床2': '#9a948a',
            '左外側': '#6b8a45', '右外側': '#2e6fa8', '霧': '#d4e4ee',
        },
        'left_edge': 7, 'right_edge': 22, 'fog_dist': 1400,
        'roof_colors': ('#2f74a8', '#f1f1ea'),   # 海沿い: 海の色の屋根と、白い柱
        'roof_stations': {'信町空港': 1},         # 空港の駅は、ホームの端から端まで屋根がある
        'scenery_left': ['松', '店_海の家しおさい', '松', '家', '店_浜焼き 田原屋', '紅葉', '松', '店_民宿なぎさ', '電柱',
                         '店_釣具うみかぜ', '広葉樹', '店_田原みやげ'],
        'scenery_right': [],
        'scenery_interval': 34,
        'stations': [('高田', 500), ('六町橋西詰', 3900), ('新鎌京橋', 13500), ('信町空港', 21500), ('紅葉滝', 23400),
                     ('田原京', 30400)],
        'passing': [],
        'limits': [(300, 1300, 160), (4100, 5000, 230), (20600, 21600, 200), (23800, 24900, 230), (29600, 30500, 130)],
        'curves': [(1800, 800, 3000, '右'), (6500, 1300, 6000, '左'), (10500, 1300, 5000, '右'), (16000, 1800, 6000, '左'),
                   (23900, 900, 2000, '左'), (26500, 1300, 4000, '右')],
        'grades': [(23600, 1000, 12), (25500, 2600, -10)],
        # 高田を出てすぐ 25‰ の坂で高さ 15m の高架に上がり、街の上を走って、3300m で地上に降りる
        'viaducts': [(650, 3300, 15, 600)],
        # 高架を降りるまでは、高田のまわりの街（信町本線の景色）。降りたところから海沿いになる
        'scenery_until': ('信町本線', 3300),
        'margin': (1.10, 8),
        # 海沿い: 強風・シカ・踏切・非常通報など
        'accidents': ['強風', '動物', '踏切の車', '非常通報', 'モーター不調', '番線変更'],
        # 空港（開始m, 終了m, 側）。信町空港駅（21500m）の海側（右）にある埋め立ての空港
        'airports': [(19800, 23200, '右')],
    },
]

# 空港の中の建物と駐機中の飛行機の並び（空港の始めからの距離 m, 線路の中心から空港の側への距離 m, 名前）。
# 名前は「景色」スプライトのコスチューム名。奥から順に描くので、距離の小さい順に並べる。
AIRPORT_LAYOUT = [
    (300, 108, '空港_吹き流し'),
    (1350, 17, '空港_看板'),
    (1500, 52, '空港_ターミナル'),
    (1850, 48, '駐機_そらいろ航空'),
    (2150, 50, '駐機_信町航空'),
    (2350, 100, '空港_管制塔'),
    (2600, 54, '駐機_信町航空'),
    (2900, 66, '空港_格納庫'),
]


# 種別（列車の種類）。名前と編成両数（1両 20m。列車の長さ・停止位置目標の数字になる）。
# 「路線データ」スプライトの「設定を読み込む」で『種別を追加』ブロックになる。
# ほかの種別（信町特急・信町特快・快速・通快・区快・準快速は 10両、普通は 6両）も同じ形で足せる。
TRAIN_TYPES = [
    {'name': 'エアポート特快', 'cars': 10},
]

# 運行（路線選択に出る、種別つきの列車）。路線一覧では ROUTES のあとに並ぶ。
#  type:       種別（TRAIN_TYPES の名前）
#  dest:       行き先（終点の駅名）
#  sections:   走る区間（路線名, 始めの駅, 終わりの駅）。前の区間の終わりの駅と、次の区間の始めの駅でつなぐ
#  stops:      停車駅（ここにない駅は通過）。始発駅と終点は停車にする
#  start_time: 始発駅の発車時刻
#  margin:     時刻表の余裕（理想の運転の所要時間 × 倍率 ＋ 秒）
SERVICES = [
    {
        'name': 'エアポート特快',
        'type': 'エアポート特快',
        'dest': '田原京',
        'level': '上級',
        'desc': 'エアポート特快 田原京行（上級・10両・信町本線→田原海岸線 直通 5駅停車/14駅・61km）',
        'note': '新信町から信町本線を走り、高田で田原海岸線に入って信町空港・田原京へ行く空港アクセスの速達列車（10両）。\n'
                '停車駅は 新信町・信町・高田・信町空港・田原京 だけで、ほかの 9 駅は通過する。\n'
                '高田までは夕方の街なか。高田を出ると高架に上がり、高架を降りたところから昼の海沿い（田原海岸線の景色）になる。',
        'sections': [('信町本線', '新信町', '高田'), ('田原海岸線', '高田', '田原京')],
        'stops': ['新信町', '信町', '高田', '信町空港', '田原京'],
        'start_time': '16:40:00',
        'margin': (1.04, 4),
    },
]

START_POS = 500     # 運行の始発駅の停止位置 [m]（路線と同じく、線路の始めから 500m）
SCENERY_SWITCH_BEFORE = 5   # 景色が変わる場所（つなぐ駅の停止位置・『始めの景色』の終わり）のこれ [m] 手前から次の景色
SCENERY_BLEND = 2500        # 景色が変わる場所のこれ [m] 手前から、空と遠景を少しずつ次の景色に混ぜる

# 駅の配線（どの駅も 3番線まで）。運転士から見て左から
#   3番線（副本線・待避線）／島式ホーム／2番線（自分の本線）／1番線（対向列車の本線）／ホーム
# の「2面3線」。番線は右（1番線）から数える。いつもは 2番線に着き、番線変更のときは分岐器で 3番線に入る。
#  island: 島式ホームの幅 [m]   len: 分岐器で線路が移る長さ [m]   gap: 分岐器の終わりからホームの端まで [m]
#  speed:  分岐の制限速度 [km/h]
TRACKS = {'island': 7, 'len': 120, 'gap': 15, 'speed': 45}
PLATFORM_FRONT = 8      # ホームの前の端は停止位置のこれ [m] 先
PLATFORM_LEN = 180      # 設定の「ホームの長さ」
# 『配線のきまり』の初期値（番線の数え方, いつもの番線, 番線変更の番線）。路線ごとに 'layout' で変えられる。
# 駅ごとに変えるときは 'layout_stations': {駅名: (数え方, いつも, 変更)}
LAYOUT_DEFAULT = ('右', 2, 3)


def siding_number(count_from):
    """副本線（3本目の線路。いちばん左）の番線の番号。"""
    return 1 if count_from == '左' else 3


def station_layout(r, name):
    return r.get('layout_stations', {}).get(name, r.get('layout', LAYOUT_DEFAULT))


def turnout_limits(r, cars):
    """いつもは副本線に着く停車駅の、分岐器の制限（駅の手前と先）。Scratch の『配線の表を作る』と同じ計算。"""
    plat = max(PLATFORM_LEN, cars * 20 + 20)
    out = []
    for name, pos in r['stations']:
        if name in r.get('passing', []):
            continue
        cf, usual, _ = station_layout(r, name)
        if usual == siding_number(cf):
            a = pos - plat - TRACKS['gap'] - TRACKS['len']
            b = pos + PLATFORM_FRONT + TRACKS['gap']
            out += [(a, a + TRACKS['len'], TRACKS['speed']), (b, b + TRACKS['len'], TRACKS['speed'])]
    return out


def viaduct_grades(r):
    """高架の上り坂と下り坂（『高架を追加』が足す勾配と同じ。‰ は小数 1 けたに丸める）。"""
    out = []
    for s, e, h, ramp in r.get('viaducts', []):
        g = round(h / ramp * 1000, 1)
        out += [(s, ramp, g), (e - ramp, ramp, -g)]
    return out


def all_grades(r):
    """路線の坂: 『勾配を追加』の坂と、高架の坂。"""
    return r['grades'] + viaduct_grades(r)


def train_type(name):
    return next(t for t in TRAIN_TYPES if t['name'] == name)


def service_route(svc):
    """運行の区間をつないだ路線（ROUTES と同じ形）を作る。Scratch の『区間を足す』と同じ計算。"""
    by_name = {r['name']: r for r in ROUTES}
    out = {'name': f'{svc["type"]} {svc["dest"]}行', 'stations': [], 'limits': [], 'curves': [], 'grades': [],
           'airports': [], 'accidents': [], 'zones': [], 'layout_stations': {}, 'start_time': svc['start_time'], 'margin': svc['margin']}
    seg_speeds = []
    for k, (rname, a, b) in enumerate(svc['sections']):
        r = by_name[rname]
        pos = dict(r['stations'])
        pa, pb = pos[a], pos[b]
        first = not out['stations']
        shift = START_POS - pa if first else out['stations'][-1][1] - pa
        lo = -10 ** 9 if first else pa     # 最初の区間は、始発駅より手前のデータもそのまま使う

        def clip(s, e):
            s2, e2 = max(s, lo), min(e, pb)
            return (s2 + shift, e2 + shift) if e2 > s2 else None

        for n, p in r['stations']:
            if pa <= p <= pb and (first or p != pa):
                out['stations'].append((n, p + shift))
                out['layout_stations'][n] = station_layout(r, n)
        prev_limits = len(out['limits'])
        for s, e, v in r['limits']:
            if c := clip(s, e):
                # 前の区間の終わりにつながる同じ速さの制限は 1 つにまとめる
                j = next((j for j in range(prev_limits) if out['limits'][j][1] == c[0] and out['limits'][j][2] == v), None)
                if j is None:
                    out['limits'].append((c[0], c[1], v))
                else:
                    out['limits'][j] = (out['limits'][j][0], c[1], v)
        for s, ln, rad, side in r['curves']:
            if c := clip(s, s + ln):
                out['curves'].append((c[0], c[1] - c[0], rad, side))
        for s, ln, g in all_grades(r):
            if c := clip(s, s + ln):
                out['grades'].append((c[0], c[1] - c[0], g))
        for s, e, side in r.get('airports', []):
            if c := clip(s, e):
                out['airports'].append((c[0], c[1], side))
        for kind in r.get('accidents', []):
            if kind not in out['accidents']:
                out['accidents'].append(kind)
        out['zones'].append((None if first else pa + shift, rname))
        seg_speeds.append((0 if first else pa + shift, pb + shift, r['max_speed']))
    out['max_speed'] = max(v for _, _, v in seg_speeds)
    out['limits'] += [(s, e, v) for s, e, v in seg_speeds if v < out['max_speed']]
    out['passing'] = [n for n, _ in out['stations'] if n not in svc['stops']]
    return out


def all_station_names():
    names = []
    for r in ROUTES:
        for n, _ in r['stations']:
            if n not in names:
                names.append(n)
    return names
