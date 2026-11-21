"""Scratch 3.0 (.sb3) を Python から組み立てるための小さな DSL。

ゲーム本体の改造は Scratch エディタ上で行う前提だが、ゲームを丸ごと作り直したいときは
このジェネレータを使う。ブロックは Python の式として書ける:

    set_("速度", V("速度") + V("加速度") * V("Δt"))
    if_(V("速度") > 0, [ ... ])

ブロックにコメントを付けるには .c("コメント") を付ける。
"""
import hashlib
import json
import zipfile

# ---------------------------------------------------------------------------
# 値・ブロックの表現
# ---------------------------------------------------------------------------


def _fmt(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return repr(round(v, 6))
    return str(v)


class Blk:
    """Scratch のブロック 1 個。"""
    shape = 'stack'

    def __init__(self, opcode, inputs=None, fields=None, mutation=None, shape=None):
        self.opcode = opcode
        self.inputs = inputs or {}
        self.fields = fields or {}
        self.mutation = mutation
        self.comment = None
        if shape:
            self.shape = shape

    def c(self, text):
        """ブロックにコメントを付ける。"""
        self.comment = text
        return self


class R(Blk):
    """値を返すブロック（レポーター / 真偽ブロック）。Python の演算子が使える。"""
    shape = 'reporter'

    def __bool__(self):
        raise TypeError('Scratch の式を Python の真偽値として使わないでください（and/or ではなく & | を使う）')

    def __add__(self, o):
        return R('operator_add', {'NUM1': (self, 'num'), 'NUM2': (o, 'num')})

    def __radd__(self, o):
        return R('operator_add', {'NUM1': (o, 'num'), 'NUM2': (self, 'num')})

    def __sub__(self, o):
        return R('operator_subtract', {'NUM1': (self, 'num'), 'NUM2': (o, 'num')})

    def __rsub__(self, o):
        return R('operator_subtract', {'NUM1': (o, 'num'), 'NUM2': (self, 'num')})

    def __mul__(self, o):
        return R('operator_multiply', {'NUM1': (self, 'num'), 'NUM2': (o, 'num')})

    def __rmul__(self, o):
        return R('operator_multiply', {'NUM1': (o, 'num'), 'NUM2': (self, 'num')})

    def __truediv__(self, o):
        return R('operator_divide', {'NUM1': (self, 'num'), 'NUM2': (o, 'num')})

    def __rtruediv__(self, o):
        return R('operator_divide', {'NUM1': (o, 'num'), 'NUM2': (self, 'num')})

    def __mod__(self, o):
        return R('operator_mod', {'NUM1': (self, 'num'), 'NUM2': (o, 'num')})

    def __rmod__(self, o):
        return R('operator_mod', {'NUM1': (o, 'num'), 'NUM2': (self, 'num')})

    def __neg__(self):
        return R('operator_subtract', {'NUM1': (0, 'num'), 'NUM2': (self, 'num')})

    def __lt__(self, o):
        return lt(self, o)

    def __gt__(self, o):
        return gt(self, o)

    def __and__(self, o):
        return R('operator_and', {'OPERAND1': (self, 'bool'), 'OPERAND2': (o, 'bool')}, shape='boolean')

    def __or__(self, o):
        return R('operator_or', {'OPERAND1': (self, 'bool'), 'OPERAND2': (o, 'bool')}, shape='boolean')

    def __invert__(self):
        return R('operator_not', {'OPERAND': (self, 'bool')}, shape='boolean')

    __hash__ = object.__hash__


class Var(R):
    """変数のレポーター。"""

    def __init__(self, name):
        super().__init__('data_variable')
        self.name = name


class Arg(R):
    """カスタムブロックの引数。"""

    def __init__(self, name):
        super().__init__('argument_reporter_string_number', fields={'VALUE': name})
        self.name = name


def V(name):
    return Var(name)


def A(name):
    return Arg(name)


class Hat(Blk):
    shape = 'hat'


class ProcDef:
    def __init__(self, proccode, argnames, body, warp, comment):
        self.proccode = proccode
        self.argnames = argnames
        self.body = body
        self.warp = warp
        self.comment = comment
        self.argids = []


# ---------------------------------------------------------------------------
# ブロックを作る関数（使うものだけ）
# ---------------------------------------------------------------------------

# 演算
def lt(a, b):
    return R('operator_lt', {'OPERAND1': (a, 'text'), 'OPERAND2': (b, 'text')}, shape='boolean')


def gt(a, b):
    return R('operator_gt', {'OPERAND1': (a, 'text'), 'OPERAND2': (b, 'text')}, shape='boolean')


def eq(a, b):
    return R('operator_equals', {'OPERAND1': (a, 'text'), 'OPERAND2': (b, 'text')}, shape='boolean')


def not_(a):
    return R('operator_not', {'OPERAND': (a, 'bool')}, shape='boolean')


def and_(*xs):
    r = xs[0]
    for x in xs[1:]:
        r = R('operator_and', {'OPERAND1': (r, 'bool'), 'OPERAND2': (x, 'bool')}, shape='boolean')
    return r


def or_(*xs):
    r = xs[0]
    for x in xs[1:]:
        r = R('operator_or', {'OPERAND1': (r, 'bool'), 'OPERAND2': (x, 'bool')}, shape='boolean')
    return r


def join(*xs):
    r = xs[-1]
    for x in reversed(xs[:-1]):
        r = R('operator_join', {'STRING1': (x, 'text'), 'STRING2': (r, 'text')})
    return r


def mathop(op, x):
    return R('operator_mathop', {'NUM': (x, 'num')}, {'OPERATOR': op})


def floor(x):
    return mathop('floor', x)


def ceil(x):
    return mathop('ceiling', x)


def abs_(x):
    return mathop('abs', x)


def sqrt(x):
    return mathop('sqrt', x)


def sin(x):
    return mathop('sin', x)


def cos(x):
    return mathop('cos', x)


def exp_(x):
    return mathop('e ^', x)


def round_(x):
    return R('operator_round', {'NUM': (x, 'num')})


def random(a, b):
    return R('operator_random', {'FROM': (a, 'num'), 'TO': (b, 'num')})


def letter_of(i, s):
    return R('operator_letter_of', {'LETTER': (i, 'whole'), 'STRING': (s, 'text')})


def length_of(s):
    return R('operator_length', {'STRING': (s, 'text')})


# データ
def set_(var, v):
    return Blk('data_setvariableto', {'VALUE': (v, 'text')}, {'VARIABLE': ('var', var)})


def change(var, v):
    return Blk('data_changevariableby', {'VALUE': (v, 'num')}, {'VARIABLE': ('var', var)})


def show_var(var):
    return Blk('data_showvariable', {}, {'VARIABLE': ('var', var)})


def hide_var(var):
    return Blk('data_hidevariable', {}, {'VARIABLE': ('var', var)})


def add(lst, v):
    return Blk('data_addtolist', {'ITEM': (v, 'text')}, {'LIST': ('list', lst)})


def delete_all(lst):
    return Blk('data_deletealloflist', {}, {'LIST': ('list', lst)})


def delete_at(lst, i):
    return Blk('data_deleteoflist', {'INDEX': (i, 'int')}, {'LIST': ('list', lst)})


def insert_at(lst, i, v):
    return Blk('data_insertatlist', {'ITEM': (v, 'text'), 'INDEX': (i, 'int')}, {'LIST': ('list', lst)})


def replace(lst, i, v):
    return Blk('data_replaceitemoflist', {'INDEX': (i, 'int'), 'ITEM': (v, 'text')}, {'LIST': ('list', lst)})


def item(lst, i):
    return R('data_itemoflist', {'INDEX': (i, 'int')}, {'LIST': ('list', lst)})


def length(lst):
    return R('data_lengthoflist', {}, {'LIST': ('list', lst)})


def index_of(lst, v):
    return R('data_itemnumoflist', {'ITEM': (v, 'text')}, {'LIST': ('list', lst)})


def list_has(lst, v):
    return R('data_listcontainsitem', {'ITEM': (v, 'text')}, {'LIST': ('list', lst)}, shape='boolean')


def show_list(lst):
    return Blk('data_showlist', {}, {'LIST': ('list', lst)})


def hide_list(lst):
    return Blk('data_hidelist', {}, {'LIST': ('list', lst)})


# イベント
def when_flag():
    return Hat('event_whenflagclicked')


def when_recv(name):
    return Hat('event_whenbroadcastreceived', {}, {'BROADCAST_OPTION': ('bcast', name)})


def when_clone():
    return Hat('control_start_as_clone')


def broadcast(name):
    return Blk('event_broadcast', {'BROADCAST_INPUT': (name, 'broadcast')})


def broadcast_wait(name):
    return Blk('event_broadcastandwait', {'BROADCAST_INPUT': (name, 'broadcast')})


# 制御
def wait(t):
    return Blk('control_wait', {'DURATION': (t, 'pos')})


def wait_until(c):
    return Blk('control_wait_until', {'CONDITION': (c, 'bool')})


def repeat(n, body):
    return Blk('control_repeat', {'TIMES': (n, 'whole'), 'SUBSTACK': (body, 'stack')}, shape='c')


def repeat_until(c, body):
    return Blk('control_repeat_until', {'CONDITION': (c, 'bool'), 'SUBSTACK': (body, 'stack')}, shape='c')


def forever(body):
    return Blk('control_forever', {'SUBSTACK': (body, 'stack')}, shape='cap_c')


def if_(c, body):
    return Blk('control_if', {'CONDITION': (c, 'bool'), 'SUBSTACK': (body, 'stack')}, shape='c')


def if_else(c, a, b):
    return Blk('control_if_else', {'CONDITION': (c, 'bool'), 'SUBSTACK': (a, 'stack'), 'SUBSTACK2': (b, 'stack')},
               shape='c2')


def stop(option='this script'):
    hasnext = 'true' if option == 'other scripts in sprite' else 'false'
    return Blk('control_stop', {}, {'STOP_OPTION': option},
               mutation={'tagName': 'mutation', 'children': [], 'hasnext': hasnext},
               shape='stack' if hasnext == 'true' else 'cap')


def clone_myself():
    return Blk('control_create_clone_of',
               {'CLONE_OPTION': ('_myself_', ('menu', 'control_create_clone_of_menu', 'CLONE_OPTION'))})


def delete_clone():
    return Blk('control_delete_this_clone', shape='cap')


# 調べる
def key(k):
    return R('sensing_keypressed', {'KEY_OPTION': (k, ('menu', 'sensing_keyoptions', 'KEY_OPTION'))},
             shape='boolean')


def timer():
    return R('sensing_timer')


def mouse_down():
    return R('sensing_mousedown', shape='boolean')


def reset_timer():
    return Blk('sensing_resettimer')


# 動き
def goto(x, y):
    return Blk('motion_gotoxy', {'X': (x, 'num'), 'Y': (y, 'num')})


def set_x(x):
    return Blk('motion_setx', {'X': (x, 'num')})


def set_y(y):
    return Blk('motion_sety', {'Y': (y, 'num')})


def point(d):
    return Blk('motion_pointindirection', {'DIRECTION': (d, 'angle')})


def rotation_style(style):
    return Blk('motion_setrotationstyle', {}, {'STYLE': style})


# 見た目
def costume(name):
    return Blk('looks_switchcostumeto', {'COSTUME': (name, ('menu', 'looks_costume', 'COSTUME'))})


def backdrop(name):
    return Blk('looks_switchbackdropto', {'BACKDROP': (name, ('menu', 'looks_backdrops', 'BACKDROP'))})


def set_size(v):
    return Blk('looks_setsizeto', {'SIZE': (v, 'num')})


def show():
    return Blk('looks_show')


def hide():
    return Blk('looks_hide')


def front():
    return Blk('looks_gotofrontback', {}, {'FRONT_BACK': 'front'})


def back():
    return Blk('looks_gotofrontback', {}, {'FRONT_BACK': 'back'})


def set_effect(effect, v):
    return Blk('looks_seteffectto', {'VALUE': (v, 'num')}, {'EFFECT': effect})


def clear_effects():
    return Blk('looks_cleargraphiceffects')


def costume_name():
    return R('looks_costumenumbername', {}, {'NUMBER_NAME': 'name'})


# 音
def play(name):
    return Blk('sound_play', {'SOUND_MENU': (name, ('menu', 'sound_sounds_menu', 'SOUND_MENU'))})


def play_wait(name):
    return Blk('sound_playuntildone', {'SOUND_MENU': (name, ('menu', 'sound_sounds_menu', 'SOUND_MENU'))})


def stop_sounds():
    return Blk('sound_stopallsounds')


def sound_effect(effect, v):
    return Blk('sound_seteffectto', {'VALUE': (v, 'num')}, {'EFFECT': effect})


def set_volume(v):
    return Blk('sound_setvolumeto', {'VOLUME': (v, 'num')})


# ペン
def pen_clear():
    return Blk('pen_clear')


def stamp():
    return Blk('pen_stamp')


def pen_down():
    return Blk('pen_penDown')


def pen_up():
    return Blk('pen_penUp')


def pen_color(c):
    return Blk('pen_setPenColorToColor', {'COLOR': (c, 'color')})


def pen_param(param, v):
    return Blk('pen_setPenColorParamTo', {'COLOR_PARAM': (param, ('menu', 'pen_menu_colorParam', 'colorParam')),
                                          'VALUE': (v, 'num')})


def pen_size(v):
    return Blk('pen_setPenSizeTo', {'SIZE': (v, 'num')})


# カスタムブロック呼び出し
def call(proccode, *args):
    b = Blk('procedures_call')
    b.call_proccode = proccode
    b.call_args = list(args)
    return b


# ---------------------------------------------------------------------------
# 幅・高さの見積もり（コメントをブロックの右に並べるため）
# ---------------------------------------------------------------------------

def _text_w(s):
    return sum(15 if ord(ch) > 0x2E80 else 8 for ch in str(s))


LABEL_W = {
    'data_setvariableto': 110, 'data_changevariableby': 110, 'data_addtolist': 110, 'data_itemoflist': 60,
    'data_replaceitemoflist': 160, 'data_deletealloflist': 120, 'data_lengthoflist': 60, 'data_insertatlist': 150,
    'data_itemnumoflist': 90, 'data_listcontainsitem': 80, 'data_deleteoflist': 120,
    'motion_gotoxy': 150, 'control_if': 60, 'control_if_else': 60, 'control_repeat': 70, 'control_forever': 70,
    'control_repeat_until': 90, 'control_wait': 70, 'control_wait_until': 90, 'operator_add': 20,
    'operator_subtract': 20, 'operator_multiply': 20, 'operator_divide': 20, 'operator_mod': 50,
    'operator_mathop': 60, 'operator_round': 60, 'operator_lt': 20, 'operator_gt': 20, 'operator_equals': 20,
    'operator_and': 40, 'operator_or': 40, 'operator_not': 50, 'operator_join': 20, 'operator_random': 110,
    'pen_setPenColorToColor': 120, 'pen_setPenSizeTo': 120, 'pen_penDown': 80, 'pen_penUp': 80, 'pen_clear': 70,
    'pen_stamp': 70, 'event_broadcast': 80, 'event_broadcastandwait': 120,
}


def _depth(v):
    if not isinstance(v, R):
        return 0
    d = 0
    for (iv, kind) in v.inputs.values():
        if kind != 'stack':
            d = max(d, _depth(iv))
    return d + 1


def _width(v):
    if isinstance(v, (Var, Arg)):
        return _text_w(v.name) + 24
    if isinstance(v, Blk):
        w = 16
        if v.opcode == 'procedures_call':
            return w + _text_w(v.call_proccode.replace('%s', '')) + sum(_width(a) for a in v.call_args) + 8
        w += LABEL_W.get(v.opcode, 90)
        for (iv, k) in v.inputs.values():
            if k != 'stack':
                w += _width(iv) + 6
        for fv in v.fields.values():
            w += (_text_w(fv[1]) + 24) if isinstance(fv, tuple) else (_text_w(fv) + 10)
        return w
    if v is None:
        return 40
    return max(40, _text_w(_fmt(v)) + 18)


# ---------------------------------------------------------------------------
# スプライト / ステージ
# ---------------------------------------------------------------------------

SHADOW_TYPES = {'num': 4, 'pos': 5, 'whole': 6, 'int': 7, 'angle': 8, 'color': 9, 'text': 10}


class Target:
    def __init__(self, project, name, is_stage=False):
        self.project = project
        self.name = name
        self.is_stage = is_stage
        self.vars = {}    # name -> [id, value]
        self.lists = {}   # name -> [id, items]
        self.items = []   # スクリプトとカスタムブロック定義（定義順）
        self.procs = {}
        self.costumes = []
        self.sounds = []
        self.overview = None   # スプライト冒頭の説明コメント
        self.notes = []        # 末尾のワークスペースコメント
        self.visible = False
        self.x = 0
        self.y = 0
        self.size = 100
        self.direction = 90
        self.rotation_style = 'all around'
        self.current_costume = 0
        self.layer = 0
        self.volume = 100

    # 定義 -------------------------------------------------------------
    def var(self, name, value=0):
        if name in self.vars:
            raise ValueError(f'変数が二重定義: {name} ({self.name})')
        self.vars[name] = [self.project.new_id('v'), value]
        return Var(name)

    def lst(self, name, items=None):
        if name in self.lists:
            raise ValueError(f'リストが二重定義: {name} ({self.name})')
        self.lists[name] = [self.project.new_id('l'), list(items or [])]
        return name

    def script(self, hat, body, comment=None):
        if comment:
            hat.c(comment)
        self.items.append((hat, body))

    def proc(self, proccode, argnames, body, warp=True, comment=None):
        if proccode.count('%s') != len(argnames):
            raise ValueError(f'引数の数が合いません: {proccode}')
        if proccode in self.procs:
            raise ValueError(f'カスタムブロックが二重定義: {proccode}')
        p = ProcDef(proccode, argnames, body, warp, comment)
        p.argids = [self.project.new_id('a') for _ in argnames]
        self.procs[proccode] = p
        self.items.append(p)

    def costume_svg(self, name, svg, cx, cy):
        self.costumes.append({'name': name, 'data': svg.encode('utf-8'), 'ext': 'svg', 'cx': cx, 'cy': cy})

    def sound_wav(self, name, data, rate, count):
        self.sounds.append({'name': name, 'data': data, 'rate': rate, 'count': count})

    # 変数解決 ---------------------------------------------------------
    def _var(self, name):
        if name in self.vars:
            return self.vars[name][0]
        st = self.project.stage
        if name in st.vars:
            return st.vars[name][0]
        raise KeyError(f'未定義の変数「{name}」（{self.name}）')

    def _list(self, name):
        if name in self.lists:
            return self.lists[name][0]
        st = self.project.stage
        if name in st.lists:
            return st.lists[name][0]
        raise KeyError(f'未定義のリスト「{name}」（{self.name}）')

    # シリアライズ -----------------------------------------------------
    def _field(self, fv):
        if isinstance(fv, tuple):
            kind, name = fv
            if kind == 'var':
                return [name, self._var(name)]
            if kind == 'list':
                return [name, self._list(name)]
            if kind == 'bcast':
                return [name, self.project.bcast_id(name)]
        return [fv, None]

    def _new_block(self, opcode, parent, shadow=False, top=False):
        bid = self.project.new_id('b')
        self.blocks[bid] = {'opcode': opcode, 'next': None, 'parent': parent, 'inputs': {}, 'fields': {},
                            'shadow': shadow, 'topLevel': top}
        return bid

    def _menu_shadow(self, opcode, field, value, parent):
        sid = self._new_block(opcode, parent, shadow=True)
        self.blocks[sid]['fields'][field] = [value, None]
        return sid

    def _reporter(self, r, parent):
        if isinstance(r, Var):
            return [12, r.name, self._var(r.name)]
        bid = self._new_block(r.opcode, parent)
        b = self.blocks[bid]
        for fname, fv in r.fields.items():
            b['fields'][fname] = self._field(fv)
        for iname, (iv, kind) in r.inputs.items():
            j = self._input(iv, kind, bid)
            if j is not None:
                b['inputs'][iname] = j
        if r.comment:
            self._pending.append((bid, r.comment, self._cur_y))
        return bid

    def _input(self, v, kind, parent):
        if kind == 'bool':
            if v is None:
                return None
            if not isinstance(v, R):
                raise TypeError(f'真偽ブロックが必要: {v!r}')
            return [2, self._reporter(v, parent)]
        if kind == 'broadcast':
            return [1, [11, v, self.project.bcast_id(v)]]
        if isinstance(kind, tuple) and kind[0] == 'menu':
            _, mop, mfield = kind
            if isinstance(v, R):
                sid = self._menu_shadow(mop, mfield, self._menu_default(mop), parent)
                return [3, self._reporter(v, parent), sid]
            return [1, self._menu_shadow(mop, mfield, v, parent)]
        st = SHADOW_TYPES[kind]
        if isinstance(v, R):
            return [3, self._reporter(v, parent), [st, '#000000' if kind == 'color' else '']]
        if isinstance(v, Blk):
            raise TypeError(f'文ブロックを値の場所に入れています: {v.opcode}')
        return [1, [st, _fmt(v)]]

    def _menu_default(self, mop):
        if mop == 'looks_costume':
            return self.costumes[0]['name'] if self.costumes else ''
        if mop == 'looks_backdrops':
            return self.project.stage.costumes[0]['name']
        if mop == 'sound_sounds_menu':
            return self.sounds[0]['name'] if self.sounds else ''
        if mop == 'sensing_keyoptions':
            return 'space'
        if mop == 'pen_menu_colorParam':
            return 'color'
        return ''

    def _stmt(self, s, parent, y, x):
        """文を登録して (id, 高さ, 幅) を返す。"""
        self._cur_y = y
        if isinstance(s, R):
            raise TypeError(f'値ブロックを文として置いています: {s.opcode}')
        bid = self._new_block(s.opcode, parent)
        b = self.blocks[bid]
        depth = 0
        if s.opcode == 'procedures_call':
            p = self.procs.get(s.call_proccode)
            if p is None:
                raise KeyError(f'未定義のカスタムブロック「{s.call_proccode}」（{self.name}）')
            if len(s.call_args) != len(p.argids):
                raise ValueError(f'引数の数が違います: {s.call_proccode}')
            b['mutation'] = {'tagName': 'mutation', 'children': [], 'proccode': p.proccode,
                             'argumentids': json.dumps(p.argids), 'warp': 'true' if p.warp else 'false'}
            for aid, av in zip(p.argids, s.call_args):
                b['inputs'][aid] = self._input(av, 'text', bid)
                depth = max(depth, _depth(av))
        else:
            for fname, fv in s.fields.items():
                b['fields'][fname] = self._field(fv)
            if s.mutation:
                b['mutation'] = s.mutation
            for iname, (iv, kind) in s.inputs.items():
                if kind == 'stack':
                    continue
                depth = max(depth, _depth(iv))
                j = self._input(iv, kind, bid)
                if j is not None:
                    b['inputs'][iname] = j
        width = _width(s)
        h = 48 + 8 * max(0, depth - 1)
        if s.comment:
            self._pending.append((bid, s.comment, y))
        if s.shape in ('c', 'cap_c', 'c2'):
            subs = ['SUBSTACK'] + (['SUBSTACK2'] if s.shape == 'c2' else [])
            for si, sname in enumerate(subs):
                body = s.inputs.get(sname, (None, 'stack'))[0]
                if si == 1:
                    h += 32
                if body:
                    first, bh, bw = self._stack(body, bid, y + h, x + 16)
                    b['inputs'][sname] = [2, first]
                    h += bh
                    width = max(width, bw + 16)
                else:
                    h += 24
            h += 24
        return bid, h, width

    def _stack(self, stmts, parent, y, x):
        first = prev = None
        total = 0
        width = 0
        for s in stmts:
            if s is None:
                continue
            if isinstance(s, list):
                raise TypeError('文のリストが入れ子になっています')
            bid, h, w = self._stmt(s, prev if prev else parent, y + total, x)
            if prev:
                self.blocks[prev]['next'] = bid
            else:
                first = bid
            prev = bid
            total += h
            width = max(width, w)
        return first, total, width

    def _place_comments(self, script_x, script_y, width, block_h):
        cx = script_x + int(max(width, 200) * 1.08) + 80
        bottom = script_y
        for (bid, text, y) in self._pending:
            cw = 460
            ch = self._comment_h(text, cw)
            cy = max(y, bottom + 8)
            cid = self.project.new_id('c')
            self.comments[cid] = {'blockId': bid, 'x': cx, 'y': cy, 'width': cw, 'height': ch,
                                  'minimized': False, 'text': text}
            self.blocks[bid]['comment'] = cid
            bottom = cy + ch
        self._pending = []
        return max(block_h, bottom - script_y)

    @staticmethod
    def _comment_h(text, w):
        # エディタでの実測: 日本語 1 文字 ≒ 16、1 行 ≒ 25、上の帯 ≒ 40（ワークスペースの座標）
        line_px = w - 36
        lines = 0
        for para in text.split('\n'):
            tw = sum(16 if ord(ch) > 0x2E80 else 8.5 for ch in para)
            lines += max(1, -(-int(tw) // line_px))
        return min(1400, 56 + lines * 25)

    def serialize(self):
        self.blocks = {}
        self.comments = {}
        self._pending = []
        self._cur_y = 0
        x0, y = 40, 40
        if self.overview:
            cw = 760
            ch = self._comment_h(self.overview, cw)
            cid = self.project.new_id('c')
            self.comments[cid] = {'blockId': None, 'x': x0, 'y': y, 'width': cw, 'height': ch,
                                  'minimized': False, 'text': self.overview}
            y += ch + 48
        for it in self.items:
            if isinstance(it, ProcDef):
                h = self._ser_proc(it, x0, y)
            else:
                h = self._ser_script(it[0], it[1], x0, y)
            y += h + 64
        for text in self.notes:
            cw = 560
            ch = self._comment_h(text, cw)
            cid = self.project.new_id('c')
            self.comments[cid] = {'blockId': None, 'x': x0, 'y': y, 'width': cw, 'height': ch,
                                  'minimized': False, 'text': text}
            y += ch + 40
        return self.blocks, self.comments

    def _ser_script(self, hat, body, x, y):
        hid = self._new_block(hat.opcode, None, top=True)
        hb = self.blocks[hid]
        hb['x'] = x
        hb['y'] = y
        for fname, fv in hat.fields.items():
            hb['fields'][fname] = self._field(fv)
        if hat.comment:
            self._pending.append((hid, hat.comment, y))
        hat_h = 72
        first, bh, bw = self._stack(body, hid, y + hat_h, x)
        hb['next'] = first
        width = max(bw, _width(hat) + 40)
        return self._place_comments(x, y, width, hat_h + bh)

    def _ser_proc(self, p, x, y):
        did = self._new_block('procedures_definition', None, top=True)
        pid = self._new_block('procedures_prototype', did, shadow=True)
        db = self.blocks[did]
        db['x'] = x
        db['y'] = y
        db['inputs']['custom_block'] = [1, pid]
        pb = self.blocks[pid]
        for aid, an in zip(p.argids, p.argnames):
            rid = self._new_block('argument_reporter_string_number', pid, shadow=True)
            self.blocks[rid]['fields']['VALUE'] = [an, None]
            pb['inputs'][aid] = [1, rid]
        pb['mutation'] = {'tagName': 'mutation', 'children': [], 'proccode': p.proccode,
                          'argumentids': json.dumps(p.argids),
                          'argumentnames': json.dumps(p.argnames, ensure_ascii=False),
                          'argumentdefaults': json.dumps(['' for _ in p.argnames]),
                          'warp': 'true' if p.warp else 'false'}
        if p.comment:
            self._pending.append((did, p.comment, y))
        hat_h = 96
        first, bh, bw = self._stack(p.body, did, y + hat_h, x)
        db['next'] = first
        width = max(bw, _text_w(p.proccode) + 140)
        return self._place_comments(x, y, width, hat_h + bh)

    def to_json(self, assets):
        blocks, comments = self.serialize()
        costumes = []
        for c in self.costumes:
            md5 = hashlib.md5(c['data']).hexdigest()
            assets[f"{md5}.{c['ext']}"] = c['data']
            costumes.append({'name': c['name'], 'bitmapResolution': 1, 'dataFormat': c['ext'], 'assetId': md5,
                             'md5ext': f"{md5}.{c['ext']}", 'rotationCenterX': c['cx'], 'rotationCenterY': c['cy']})
        sounds = []
        for s in self.sounds:
            md5 = hashlib.md5(s['data']).hexdigest()
            assets[f'{md5}.wav'] = s['data']
            sounds.append({'name': s['name'], 'assetId': md5, 'dataFormat': 'wav', 'format': '', 'rate': s['rate'],
                           'sampleCount': s['count'], 'md5ext': f'{md5}.wav'})
        j = {
            'isStage': self.is_stage,
            'name': self.name,
            'variables': {vid: [name, val] for name, (vid, val) in self.vars.items()},
            'lists': {lid: [name, items] for name, (lid, items) in self.lists.items()},
            'broadcasts': {},
            'blocks': blocks,
            'comments': comments,
            'currentCostume': self.current_costume,
            'costumes': costumes,
            'sounds': sounds,
            'volume': self.volume,
            'layerOrder': self.layer,
        }
        if self.is_stage:
            j.update({'tempo': 60, 'videoTransparency': 50, 'videoState': 'on', 'textToSpeechLanguage': None})
        else:
            j.update({'visible': self.visible, 'x': self.x, 'y': self.y, 'size': self.size,
                      'direction': self.direction, 'draggable': False, 'rotationStyle': self.rotation_style})
        return j


class Project:
    def __init__(self):
        self._n = 0
        self.broadcasts = {}
        self.stage = Target(self, 'Stage', is_stage=True)
        self.sprites = []
        self.monitors = []

    def new_id(self, prefix):
        self._n += 1
        return f'{prefix}{self._n:05d}'

    def bcast_id(self, name):
        if name not in self.broadcasts:
            self.broadcasts[name] = self.new_id('m')
        return self.broadcasts[name]

    def sprite(self, name):
        t = Target(self, name)
        t.layer = len(self.sprites) + 1
        self.sprites.append(t)
        return t

    def var_monitor(self, name, x, y, mode='default'):
        vid = self.stage.vars[name][0]
        self.monitors.append({'id': vid, 'mode': mode, 'opcode': 'data_variable', 'params': {'VARIABLE': name},
                              'spriteName': None, 'value': self.stage.vars[name][1], 'width': 0, 'height': 0,
                              'x': x, 'y': y, 'visible': False, 'sliderMin': 0, 'sliderMax': 100,
                              'isDiscrete': True})

    def list_monitor(self, name, x, y, w, h):
        lid = self.stage.lists[name][0]
        self.monitors.append({'id': lid, 'mode': 'list', 'opcode': 'data_listcontents', 'params': {'LIST': name},
                              'spriteName': None, 'value': [], 'width': w, 'height': h, 'x': x, 'y': y,
                              'visible': False})

    def save(self, path):
        assets = {}
        sprite_json = [s.to_json(assets) for s in self.sprites]
        stage_json = self.stage.to_json(assets)
        stage_json['broadcasts'] = {bid: name for name, bid in self.broadcasts.items()}
        pj = {'targets': [stage_json] + sprite_json, 'monitors': self.monitors, 'extensions': ['pen'],
              'meta': {'semver': '3.0.0', 'vm': '0.2.0', 'agent': 'train-driver-3d generator (Python)'}}
        data = json.dumps(pj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('project.json', data)
            for name, blob in sorted(assets.items()):
                z.writestr(name, blob)
        return pj
