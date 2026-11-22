"""時刻表（各駅の到着時刻）を計算する。

Scratch の「運転」スプライトと同じ物理（力行・走行抵抗・勾配・曲線抵抗）で、
「制限いっぱいまで加速 → 3.4km/h/s のブレーキでぴったり止まる」という理想の運転をしたときの
所要時間を出し、路線ごとの余裕（margin）を足して到着時刻にする。
"""
import math

from routes_data import all_grades, turnout_limits

DT = 0.02
PLAN_BRAKE = 3.4      # 計画ブレーキ [km/h/s]
DWELL = 25            # 停車時間 [秒]（設定スプライトの「停車時間」と同じ）。発車メロディ（約9〜11秒）が入る長さ


def hms_to_sec(s):
    h, m, sec = (int(x) for x in s.split(':'))
    return h * 3600 + m * 60 + sec


def sec_to_hms(t):
    t = int(round(t))
    return f'{t // 3600 % 24:02d}:{t // 60 % 60:02d}:{t % 60:02d}'


def _grade(route, pos):
    for start, length, g in all_grades(route):
        if start <= pos < start + length:
            return g
    return 0


def _curv(route, pos):
    for start, length, radius, _side in route['curves']:
        if start <= pos < start + length:
            return 1.0 / radius
    return 0.0


def traction(car, v):
    a = car['accel']
    if v < car['const_power']:
        acc = a
    elif v < car['char_speed']:
        acc = a * car['const_power'] / v
    else:
        acc = a * car['const_power'] * car['char_speed'] / (v * v)
    return 0.0 if v >= car['max_speed'] else acc


def effective_limit(route, car, pos):
    lim = route['max_speed']
    L = car['cars'] * 20
    for s, e, v in route['limits']:
        if s < pos and e > pos - L:
            lim = min(lim, v)
    return lim


def profile(route, car, pos, stop):
    v = min(effective_limit(route, car, pos), car['max_speed']) - 1.0
    for s, e, vl in route['limits']:
        if s > pos:
            v = min(v, math.sqrt((vl - 1.0) ** 2 + 2 * PLAN_BRAKE * 3.6 * (s - pos)))
    v = min(v, math.sqrt(max(0.0, 2 * PLAN_BRAKE * 3.6 * (stop - pos))))
    return v


def run_time(route, car, start, stop):
    pos, v, t = start, 0.0, 0.0
    while pos < stop - 0.02 and t < 3600:
        g = _grade(route, pos) * 0.0353
        res = car['res_a'] + car['res_b'] * v * v + 28.0 * _curv(route, pos)
        a = traction(car, v) - g - res
        v_new = max(0.0, v + a * DT)
        nxt = pos + (v + v_new) / 2 / 3.6 * DT
        cap = profile(route, car, nxt, stop)
        if v_new > cap:
            v_new = max(0.0, cap)
        if v_new <= 0.05 and pos > stop - 3:
            break
        if v_new <= 0.05 and v <= 0.05:
            v_new = 0.5     # 上り勾配の発車でも止まらないように
        pos += (v + v_new) / 2 / 3.6 * DT
        v = v_new
        t += DT
    return t


def timetable(route, car):
    """[(駅名, 位置, 'hh:mm:ss' または '通過', 種別), ...] を返す。始発駅の時刻は発車時刻。"""
    factor, extra = route['margin']
    # いつもは副本線（3番線）に着く駅では、分岐器の制限も入れる（ふだんの配線では無い）
    route = dict(route, limits=route['limits'] + turnout_limits(route, car['cars']))
    passing = set(route.get('passing', []))
    t = hms_to_sec(route['start_time'])
    st = route['stations']
    out = [(st[0][0], st[0][1], route['start_time'], '停車')]
    last_stop = st[0][1]
    for name, pos in st[1:]:
        if name in passing:
            out.append((name, pos, '通過', '通過'))
            continue
        rt = run_time(route, car, last_stop, pos)
        arr = math.ceil((t + rt * factor + extra) / 5) * 5
        out.append((name, pos, sec_to_hms(arr), '停車'))
        t = arr + DWELL
        last_stop = pos
    return out


def service_timetable(svc, car):
    """運行（種別つきの直通列車）の時刻表。両数は種別で決まる。"""
    from routes_data import service_route, train_type
    return timetable(service_route(svc), dict(car, cars=train_type(svc['type'])['cars']))


if __name__ == '__main__':
    from routes_data import ROUTES, CARS, SERVICES
    rows = [(r['name'], timetable(r, CARS[0])) for r in ROUTES]
    rows += [(f'{s["type"]} {s["dest"]}行', service_timetable(s, CARS[0])) for s in SERVICES]
    for name, tt in rows:
        total = hms_to_sec(tt[-1][2]) - hms_to_sec(tt[0][2])
        print(name, f'所要 {total // 60}分{total % 60}秒')
        for row in tt:
            print('  ', row)
