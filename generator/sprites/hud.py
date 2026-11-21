"""運転台・計器・ランプ・画面（タイトル/メニュー）・サウンドのスプライト。"""
import assets
from routes_data import CARS, DEPARTURE_MELODIES, DEFAULT_MELODY
from sb3 import *


def _svg_to_stage(x, y):
    return x - 240, 180 - y


def _hud_sprite(p, name, overview):
    s = p.sprite(name)
    s.overview = overview
    s.script(when_recv('運転画面を隠す'), [hide()], comment='タイトルや結果の画面では隠す')
    return s


def build_hud(p):
    # 運転台
    s = _hud_sprite(p, '運転台', '【運転台スプライト】運転席から見た窓枠と計器盤の絵。ペンの絵より手前に出る。\n'
                               '車両名と同じ名前のコスチュームが使われる。新しい車両を足したら、ここにその車両名の\n'
                               'コスチュームを足す（無いときは「T25000系」の絵のまま）。')
    for c in CARS:
        s.costume_svg(c['name'], assets.cab(c['name']), 240, 180)
    s.script(when_recv('運転画面を表示'), [
        costume(CARS[0]['name']),
        costume(V('車両名')).c('車両名と同じ名前のコスチュームにする'),
        goto(0, 0), show(),
    ], comment='運転が始まったら表示')

    # 速度計の針
    sx, sy = _svg_to_stage(*assets.SPEEDO[:2])
    s = _hud_sprite(p, '速度計の針', f'【速度計の針】速度（km/h）に合わせて針を回す。0km/h が左下（−125°）、{assets.SPEEDO_MAX}km/h が右下（＋125°）。')
    s.costume_svg('針', *assets.needle('#ff3b30', 40))
    s.script(when_recv('運転画面を表示'), [goto(sx, sy), show()], comment='計器盤の速度計の中心に置く')
    s.script(when_recv('表示'), [point(-assets.GAUGE_SWEEP + 2 * assets.GAUGE_SWEEP * V('速度') / assets.SPEEDO_MAX)
                                      .c(f'速度 0〜{assets.SPEEDO_MAX} を −125°〜125° にする')],
             comment='毎フレーム')

    # BC 圧力計の針
    bx, by = _svg_to_stage(*assets.BCGAUGE[:2])
    s = _hud_sprite(p, 'BC圧計の針', '【BC圧計の針】ブレーキシリンダーの圧力（kPa）を示す。ブレーキの効き具合が目で見える。')
    s.costume_svg('針', *assets.needle('#ffe14d', 38))
    s.script(when_recv('運転画面を表示'), [goto(bx, by), show()], comment='計器盤の BC 圧力計の中心に置く')
    s.script(when_recv('表示'), [point(-assets.GAUGE_SWEEP + 2 * assets.GAUGE_SWEEP * V('BC圧') / 600)],
             comment='0〜600kPa を −125°〜125° にする')

    # ノッチ表示
    s = _hud_sprite(p, 'ノッチ表示', '【ノッチ表示】今のノッチ（P5〜N〜B8・EB）を表示する。コスチューム名がノッチ名。')
    for n in assets.NOTCHES:
        s.costume_svg(n, *assets.notch_costume(n))
    nx, ny = _svg_to_stage(134, 304)
    s.script(when_recv('運転画面を表示'), [goto(nx, ny), show()], comment='計器盤のノッチ表示の枠に置く')
    s.script(when_recv('表示'), [costume(V('ノッチ名'))], comment='ノッチ名と同じ名前のコスチュームにする')

    # 速度の数字（クローン 3 つ）
    s = _hud_sprite(p, '速度の数字', '【速度の数字】速度計の下のデジタル表示。百の位・十の位・一の位の 3 つのクローンで表示する。\n'
                                  '「桁」が 1=百の位、2=十の位、3=一の位。本体（桁 0）は表示しない。')
    for d in list('0123456789') + ['空白']:
        s.costume_svg(f'数字{d}', *assets.digit(d))
    s.var('桁', 0)
    s.var('_v', 0)
    dx, dy = _svg_to_stage(assets.SPEEDO[0], assets.SPEEDO[1] + 32)
    s.script(when_recv('運転画面を表示'), [
        if_(eq(V('桁'), 0), [
            set_('桁', 1), goto(dx - 13, dy), clone_myself(),
            set_('桁', 2), goto(dx, dy), clone_myself(),
            set_('桁', 3), goto(dx + 13, dy), clone_myself(),
            set_('桁', 0),
        ]),
    ], comment='本体が 3 つのクローンを作る（クローンは桁と位置を受け継ぐ）')
    s.script(when_clone(), [show()], comment='クローンだけ表示する')
    s.script(when_recv('運転画面を隠す'), [if_(V('桁') > 0, [delete_clone()])], comment='クローンを消す')
    s.script(when_recv('表示'), [
        if_(V('桁') > 0, [
            set_('_v', round_(V('速度'))),
            if_else(and_(V('桁') < 3, V('_v') < mathop('10 ^', 3 - V('桁'))), [costume('数字空白')], [
                costume(join('数字', floor(V('_v') / mathop('10 ^', 3 - V('桁'))) % 10)),
            ]).c('上の桁の 0 は表示しない（例: 045 → 45）'),
        ]),
    ], comment='自分の桁の数字のコスチュームにする')

    # ランプ
    for name, label, lit_col, cond, pos, desc in [
        ('ATS表示灯', 'ATS', '#ff2a2a', V('ATS状態') > 0, (42, 12), 'ATS が警報または非常ブレーキのときに赤く光る'),
        ('戸閉表示灯', '戸閉', '#ffb020', eq(V('ドア'), '閉'), (82, 12), 'ドアが全部閉まっているときに光る（発車してよい合図）'),
    ]:
        s = _hud_sprite(p, name, f'【{name}】{desc}')
        s.costume_svg('消灯', *assets.lamp(label, False, lit_col))
        s.costume_svg('点灯', *assets.lamp(label, True, lit_col))
        lx, ly = _svg_to_stage(*pos)
        s.script(when_recv('運転画面を表示'), [goto(lx, ly), show()], comment='運転台の上の枠に置く')
        s.script(when_recv('表示'), [if_else(cond, [costume('点灯')], [costume('消灯')])], comment='毎フレーム')

    # 画面（タイトル・メニュー・結果のパネル）
    s = p.sprite('画面')
    s.overview = ('【画面スプライト】タイトル・路線選択・車両選択・結果のパネルを出す。いちばん手前に表示される。\n'
                  'メニューの中身はリスト「路線一覧」「車両一覧」、結果はリスト「成績」と変数「総合評価」の表示。')
    s.costume_svg('タイトル', assets.title_screen(), 240, 180)
    s.costume_svg('路線パネル', assets.panel('路線をえらぶ', '番号のボタンをタップ（数字キーでも選べます）'), 240, 180)
    s.costume_svg('車両パネル', assets.panel('車両をえらぶ', '番号のボタンをタップ（数字キーでも選べます）'), 240, 180)
    s.costume_svg('結果パネル', assets.panel('運転成績', '▶ タイトルへ（Enter キーかタップ）', button=True), 240, 180)
    for msg, cos in [('タイトルを表示', 'タイトル'), ('路線メニューを表示', '路線パネル'), ('車両メニューを表示', '車両パネル'),
                     ('結果を表示', '結果パネル')]:
        s.script(when_recv(msg), [costume(cos), goto(0, 0), show()], comment=f'「{cos}」を出す')
    s.script(when_recv('画面を消す'), [hide()], comment='運転中は隠す')


def build_sound(p):
    """音のスプライトを 3 つに分ける。Scratch の音量はスプライトごとなので、
    モーター音・走行音の音量を変えても効果音（警笛・チャイムなど）の音量は変わらない。"""
    def sounds_of(s, sprite_name):
        for name in assets.SOUND_SPRITES[sprite_name]:
            s.sound_wav(name, *assets.SOUNDS[name]())

    # 効果音（音量は「設定」の効果音の音量だけで決まる）
    s = p.sprite('効果音')
    s.costume_svg('効果音', *assets.icon('音', '#e04080'))
    sounds_of(s, '効果音')
    s.overview = ('【効果音スプライト】警笛・ドアチャイム・ATS ベルなどを鳴らす（音はすべて合成したオリジナル）。\n'
                  '■ 音量は「設定」スプライトの「効果音の音量」で決まり、走っている間も変わらない。\n'
                  '   （モーター音・走行音・発車メロディは別のスプライトなので、そちらの音量を変えても効果音には影響しない）\n'
                  '■ 音を差し替えたいときは、同じ名前の音を録音・読み込みして置き換える。\n'
                  '■ 発車メロディは「発車メロディ」スプライトにある。\n'
                  '■ ブラウザは、ページを一度クリック（またはキーを押す）するまで音を出さない決まりがある。\n'
                  '   Scratch ではクリックが必要なので、タイトル画面はクリックでも始められるようにしてある。')
    s.script(when_flag(), [hide(), set_volume(100)], comment='緑の旗で音量を戻す')
    s.script(when_recv('ATSベル'), [
        set_volume(V('効果音の音量')),
        repeat_until(eq(V('ATS状態'), 0), [play_wait('ATSベル')]),
    ], comment='ATS が元に戻るまでベルを鳴らし続ける')
    for msg, snd in [('警笛', '警笛'), ('遠くの警笛', '遠くの警笛'), ('ドアチャイム', 'ドアチャイム'),
                     ('すれ違い', 'すれ違い'), ('ブレーキ緩め', 'ブレーキ緩め'), ('ドア', 'ドア'), ('採点音', '採点'),
                     ('ピタ停車音', 'ピタ停車'), ('結果音', '結果'), ('決定音', '決定'), ('警報音', '警報'), ('衝突音', '衝突')]:
        s.script(when_recv(msg), [set_volume(V('効果音の音量')), play(snd)], comment=f'「{snd}」を鳴らす')

    # 発車メロディ（曲の音量を効果音と別に決められるように、スプライトを分けている）
    credit = ('発車メロディ: Clarinet_Express 様（信町高速鉄道のために制作、許可を得て使用）\n'
              '出典: Scratch「信町高速鉄道発車メロディー」https://scratch.mit.edu/projects/1440158623/')
    s = p.sprite('発車メロディ')
    s.costume_svg('発車メロディ', *assets.icon('メロ', '#1e5aa8'))
    for name in assets.MELODY_NAMES:
        s.sound_wav(name, *assets.melody(name))
    s.overview = ('【発車メロディスプライト】駅を発車する前に、駅ごとに決めた発車メロディを鳴らす。\n'
                  f'■ {credit}\n'
                  '   この 3 曲（CLEX202・CLEX203・CLEX204）は作曲者の許可を得て使っている別扱いの音源です。\n'
                  '   このゲーム以外の作品に流用したり、音だけを取り出して配ったりしないでください。\n'
                  '■ 駅ごとの曲は、下の「設定を読み込む」の『駅 ○○ の発車メロディは △△』で決める。ここを変えると駅ごとの発車メロディが変わる。\n'
                  '■ 大きさは「設定」スプライトの「効果音の音量」×「発車メロディの音量」%。\n'
                  '■ いつ鳴らすか（発車の何秒前か）は「設定」スプライトの「発車メロディの開始」、\n'
                  '   鳴らしたあとのドアチャイム・ドアの流れは「採点」スプライトの『発車する』。')
    s.var('曲', '')
    s.var('いつもの発車メロディ', DEFAULT_MELODY)
    s.var('_i', 0)
    s.lst('発車メロディの駅')
    s.lst('発車メロディの曲')
    table = [delete_all('発車メロディの駅'), delete_all('発車メロディの曲')]
    for k, (station, mel) in enumerate(DEPARTURE_MELODIES):
        b = call('駅 %s の発車メロディは %s', station, mel)
        if k == 0:
            b.c('━━ ここを変えると駅ごとの発車メロディが変わる ━━\n'
                '駅名は「路線データ」の『駅を追加』と同じ名前、曲名はこのスプライトの「音」タブにある音の名前\n'
                '（CLEX202・CLEX203・CLEX204）。2つの路線にある駅（高田・信早ヶ丘）は、どちらの路線でも同じ曲になる。\n'
                '自分で録音・読み込みした音の名前を書けば、その音を発車メロディにできる')
        table.append(b)
    table.append(set_('いつもの発車メロディ', DEFAULT_MELODY).c('上の表にない駅で流す曲'))
    s.script(when_recv('設定を読み込む'), table,
             comment='【駅ごとの発車メロディの表】ここを変えると駅ごとの発車メロディが変わる。\n' + credit)
    s.proc('駅 %s の発車メロディは %s', ['駅名', '曲名'], [
        add('発車メロディの駅', A('駅名')),
        add('発車メロディの曲', A('曲名')),
    ], comment='表に 1 行足す（同じ順番で「発車メロディの駅」「発車メロディの曲」のリストに入る）')
    s.script(when_flag(), [hide(), set_volume(100)], comment='緑の旗で音量を戻す')
    s.script(when_recv('発車メロディ'), [
        set_('_i', index_of('発車メロディの駅', V('発車する駅'))).c('発車する駅が表の何番目か（無ければ 0）'),
        if_else(V('_i') > 0, [set_('曲', item('発車メロディの曲', V('_i')))], [set_('曲', V('いつもの発車メロディ'))]),
        set_('案内', join('♪ 発車メロディ ', V('曲'))),
        set_volume(V('効果音の音量') * V('発車メロディの音量') / 100),
        play_wait(V('曲')).c('曲が終わるまで待つ'),
        set_('メロディ中', 0).c('採点スプライトの『発車する』が、これを見てドアチャイムに進む'),
    ], comment='「採点」スプライトから、発車時刻の「発車メロディの開始」秒前に届く。\n' + credit)

    # モーター音（速度に合わせて高さ、ノッチに合わせて大きさが変わる）
    s = p.sprite('モーター音')
    s.costume_svg('モーター音', *assets.icon('モータ', '#c05020'))
    sounds_of(s, 'モーター音')
    s.overview = ('【モーター音スプライト】走っている間ずっとモーター音を鳴らし、毎フレーム高さと大きさを変える。\n'
                  '■ 大きさの最大は「設定」の「モーター音の音量」。0 にするとモーター音が消える。\n'
                  '■ 速いほど高い音（ピッチ 10 で半音上がる）。力行中と電気ブレーキ中は大きくなる。')
    s.var('_音量', 0)
    s.script(when_flag(), [hide(), set_volume(0)], comment='最初は音を出さない')
    s.script(when_recv('運転画面を表示'), [
        set_volume(0),
        forever([play_wait('モーター')]).c('1 秒の音をくり返し鳴らす。大きさと高さは「表示」で変える'),
    ], comment='運転が始まったら鳴らし始める。\n'
               '（「運転の準備」は終わるまで待たれるメッセージなので、ずっと続くループは「運転画面を表示」で始める）')
    s.script(when_recv('運転画面を隠す'), [set_volume(0), stop('other scripts in sprite')],
             comment='運転が終わったら止める')
    s.script(when_recv('表示'), [
        set_('_音量', 0),
        if_(V('速度') > 0.5, [
            set_('_音量', 15 + V('力行率') * 85),
            if_(V('速度') > 8, [change('_音量', V('ブレーキ率') * 45)]).c('電気ブレーキ（回生）のときもモーターがうなる'),
            if_(V('_音量') > 100, [set_('_音量', 100)]),
        ]),
        set_volume(V('_音量') * V('モーター音の音量') / 100),
        sound_effect('PITCH', (V('速度') - 120) * 1.4).c('速いほど高い音（ピッチは −360〜360 まで）'),
    ], comment='毎フレーム、速度とノッチに合わせてモーター音を変える')

    # 走行音（ゴーという音と、レールのつなぎ目の「タタン」）
    s = p.sprite('走行音')
    s.costume_svg('走行音', *assets.icon('走行', '#806040'))
    sounds_of(s, '走行音')
    s.overview = ('【走行音スプライト】走っている間の「ゴー」という音と、レールのつなぎ目の「タタン」を鳴らす。\n'
                  '■ 大きさの最大は「設定」の「走行音の音量」。速いほど大きくなる。')
    s.var('_音量', 0)
    s.script(when_flag(), [hide(), set_volume(0)], comment='最初は音を出さない')
    s.script(when_recv('運転画面を表示'), [
        set_volume(0),
        forever([play_wait('走行音')]),
    ], comment='運転が始まったら鳴らし始める')
    s.script(when_recv('運転画面を隠す'), [set_volume(0), stop('other scripts in sprite')],
             comment='運転が終わったら止める')
    s.script(when_recv('表示'), [
        set_('_音量', 0),
        if_(V('速度') > 1, [set_('_音量', 30 + V('速度') * 0.25)]),
        if_(V('_音量') > 100, [set_('_音量', 100)]),
        set_volume(V('_音量') * V('走行音の音量') / 100),
        sound_effect('PITCH', V('速度') * 0.5 - 50),
    ], comment='毎フレーム、速度に合わせて走行音を変える（止まっているときは無音）')
    s.script(when_recv('ジョイント'), [if_(and_(V('速度') > 3, V('速度') < 160), [play('ジョイント')])],
             comment='25m ごとに「タタン」（運転スプライトから届く）。高速の区間は長いレールなので 160km/h 以上では鳴らさない')

    # きしみ音（カーブで車輪がきしむ。連続して鳴らし、大きさだけを毎フレーム変える）
    s = p.sprite('きしみ音')
    s.costume_svg('きしみ音', *assets.icon('きしみ', '#8a5a9a'))
    sounds_of(s, 'きしみ音')
    s.overview = ('【きしみ音スプライト】カーブを走るとき、車輪とレールがこすれる「キーー」という音を鳴らす。\n'
                  '■ 「設定」の「きしみが鳴る半径」より急なカーブで鳴る。半径が小さいほど、速いほど大きい。直線では鳴らない。\n'
                  '■ 大きさの最大は「設定」の「きしみ音の音量」（0 で消える）。ほかの効果音とは別のスプライトなので、\n'
                  '   ここで大きさを毎フレーム変えても、警笛やチャイムの音量は変わらない。\n'
                  '■ カーブの半径は、画面の見た目（見た目のカーブの強さ）ではなく、本物の半径（路線データの『カーブを追加』）で決まる。')
    for n in ('_音量', '_目標', '_k', 'ゆらぎ', 'ゆらぎの時間'):
        s.var(n, 0)
    s.script(when_flag(), [hide(), set_volume(0)], comment='最初は音を出さない')
    s.script(when_recv('運転画面を表示'), [
        set_volume(0), set_('_音量', 0), set_('ゆらぎ', 1),
        forever([play_wait('きしみ')]).c('2 秒の音をくり返し鳴らす。大きさは「表示」で変える'),
    ], comment='運転が始まったら鳴らし始める（音量 0 から）')
    s.script(when_recv('運転画面を隠す'), [set_volume(0), stop('other scripts in sprite')],
             comment='運転が終わったら止める')
    s.script(when_recv('表示'), [
        set_('_k', abs_(item('曲率表', floor(V('位置') / 10) + 1))).c('今いる所の曲率（1÷半径）'),
        set_('_目標', 0),
        if_(and_(V('速度') > 20, V('_k') > 1 / V('きしみが鳴る半径')), [
            set_('_目標', (V('_k') - 1 / V('きしみが鳴る半径')) / (1 / 700 - 1 / V('きしみが鳴る半径')))
            .c('鳴る半径で 0、半径 700m で 1'),
            if_(V('_目標') > 1, [set_('_目標', 1)]),
            set_('_目標', (0.4 + 0.6 * V('_目標')) * (0.4 + 0.6 * V('速度') / 250) * V('ゆらぎ'))
            .c('急なカーブほど、速いほど大きい。ときどき強くなったり弱くなったりする（ゆらぎ）'),
            if_(V('_目標') > 1, [set_('_目標', 1)]),
        ]),
        change('ゆらぎの時間', V('Δt')),
        if_(V('ゆらぎの時間') > 0.25, [set_('ゆらぎの時間', 0), set_('ゆらぎ', random(60, 100) / 100)]),
        change('_音量', (V('_目標') * 100 - V('_音量')) * V('Δt') * 4).c('急に変わらないように、少しずつ近づける'),
        if_(V('_音量') < 0.5, [set_('_音量', 0)]),
        set_volume(V('_音量') * V('きしみ音の音量') / 100),
        sound_effect('PITCH', (V('速度') - 120) * 0.25).c('速いと少し高い音'),
    ], comment='毎フレーム、カーブの急さと速度に合わせてきしみ音の大きさを変える（直線では 0）')


# タップ操作のボタンの置き場所（ステージの座標）。計器・TIMS・時刻の表示と重ならない、窓の下の左右の端
TAP_LAYOUT = [
    ('力行', 182, 32, 'タップ_力行'),
    ('ブレーキ', 182, -26, 'タップ_ブレーキ'),
    ('警笛', -182, 32, '警笛'),
    ('非常', -182, -26, 'タップ_非常'),
]


def build_tap(p):
    """キーボードがなくても遊べるように、画面のボタン（タップ・クリック）で操作するスプライト。"""
    # 運転中のボタン（力行・ブレーキ・非常・警笛）
    s = p.sprite('タップ操作')
    s.overview = ('【タップ操作スプライト】キーボードがなくても、スマホ・タブレットのタップ（パソコンではクリック）で運転できるボタン。\n'
                  '■ 右下: ▲力行（↑キーと同じ）・▼ブレーキ（↓キーと同じ）。左下: 警笛（H キー）・非常（スペースキー）。\n'
                  '■ 力行・ブレーキは押し続けると、「設定」の「ボタン_連続になるまで」秒たってから\n'
                  '   「ボタン_連続の間隔」秒ごとに 1 段ずつ動く（キーより少しゆっくりにして、動きすぎないようにしている）。\n'
                  '■ ボタンを出したくないときは、「設定」の「画面のボタン」を 0 にする。\n'
                  '■ 置き場所は下の「運転画面を表示」の『ボタンを作る』の x・y。計器や TIMS と重ならない所にする。\n'
                  '■ Scratch は指 1 本ぶん（マウス 1 つ）しか分からないので、2 つのボタンを同時には押せない。')
    for role in assets.TAP_BUTTONS:
        s.costume_svg(role, *assets.tap_button(role))
    s.var('役割', '')
    s.var('押した時刻', 0)
    s.script(when_flag(), [hide(), set_('役割', '')], comment='本体（役割なし）は隠しておき、クローンをボタンにする')
    s.proc('ボタンを作る %s x %s y %s', ['役割', 'x', 'y'], [
        set_('役割', A('役割')),
        costume(A('役割')).c('役割と同じ名前のコスチューム'),
        goto(A('x'), A('y')),
        clone_myself(),
    ], comment='役割のボタンを 1 つ作る（クローンは役割・コスチューム・位置を受け継ぐ）')
    make = []
    for role, x, y, _ in TAP_LAYOUT:
        make.append(call('ボタンを作る %s x %s y %s', role, x, y))
    make[0].c('右下: 力行（上）とブレーキ（下）。左下: 警笛（上）と非常（下）')
    s.script(when_recv('運転画面を表示'), [
        if_(and_(eq(V('役割'), ''), eq(V('画面のボタン'), 1)), make + [set_('役割', '')]),
    ], comment='運転が始まったらボタンを出す（「設定」の「画面のボタン」が 1 のとき）')
    s.script(when_clone(), [clear_effects(), show(), front()], comment='クローンだけ表示して、運転台より手前に出す')
    s.script(when_recv('運転画面を隠す'), [if_(not_(eq(V('役割'), '')), [delete_clone()])],
             comment='タイトルや結果の画面ではボタンを消す')

    def action(role):
        return [broadcast(msg) for r, _, _, msg in TAP_LAYOUT if r == role]

    held = lambda: and_(mouse_down(), touching_mouse())
    s.script(when_clicked(), [
        if_(eq(V('役割'), ''), [stop('this script')]),
        set_effect('BRIGHTNESS', 35).c('押しているあいだは明るくする'),
        if_else(or_(eq(V('役割'), '力行'), eq(V('役割'), 'ブレーキ')), [
            if_else(eq(V('役割'), '力行'), action('力行'), action('ブレーキ')).c('押した瞬間に 1 段動かす'),
            set_('押した時刻', timer()),
            wait_until(or_(not_(held()), timer() - V('押した時刻') > V('ボタン_連続になるまで'))),
            repeat_until(not_(held()), [
                if_else(eq(V('役割'), '力行'), action('力行'), action('ブレーキ')),
                set_('押した時刻', timer()),
                wait_until(or_(not_(held()), timer() - V('押した時刻') > V('ボタン_連続の間隔'))),
            ]).c('押し続けているあいだ、少しずつ動かす（指がボタンから外れたら止まる）'),
        ], [
            if_else(eq(V('役割'), '非常'), action('非常'), action('警笛')),
        ]),
        wait_until(not_(mouse_down())),
        clear_effects(),
    ], comment='ボタンが押されたら、運転スプライトに合図を送る（キーを押したときと同じ動きになる）')
    s.x, s.y = 182, 32

    # 路線・車両を選ぶ画面の番号ボタン
    s = p.sprite('番号ボタン')
    s.overview = ('【番号ボタンスプライト】路線・車両を選ぶ画面で、リストの番号と同じ数字のボタンを出す。\n'
                  'タップ（クリック）すると「タップで選んだ番号」に番号が入り、ゲーム進行スプライトがそれを見て選ぶ。\n'
                  'ボタンの数はリスト「路線一覧」「車両一覧」の長さで決まる（最大 9 個。数字キーと同じ）。')
    for n in range(1, 10):
        s.costume_svg(f'番号{n}', *assets.menu_button(n))
    s.var('番号', 0)
    s.var('ボタンの数', 0)
    s.script(when_flag(), [hide(), set_('番号', 0)], comment='本体（番号 0）は隠しておく')

    def make_menu(list_name):
        return [
            if_(eq(V('番号'), 0), [
                set_('タップで選んだ番号', 0),
                set_('ボタンの数', length(list_name)),
                if_(V('ボタンの数') > 9, [set_('ボタンの数', 9)]),
                repeat(V('ボタンの数'), [
                    change('番号', 1),
                    costume(join('番号', V('番号'))),
                    goto((V('番号') - (V('ボタンの数') + 1) / 2) * 66, -95).c('横に並べる（真ん中そろえ）'),
                    clone_myself(),
                ]),
                set_('番号', 0),
            ]),
        ]
    s.script(when_recv('路線メニューを表示'), make_menu('路線一覧'), comment='路線一覧の数だけ番号ボタンを出す')
    s.script(when_recv('車両メニューを表示'), make_menu('車両一覧'), comment='車両一覧の数だけ番号ボタンを出す')
    s.script(when_clone(), [clear_effects(), show(), front()], comment='クローンだけ表示する')
    s.script(when_clicked(), [
        if_(V('番号') > 0, [
            set_effect('BRIGHTNESS', 35),
            set_('タップで選んだ番号', V('番号')).c('ゲーム進行スプライトの『路線を選ぶ』『車両を選ぶ』がこれを見る'),
        ]),
    ], comment='タップされたら番号を知らせる')
    s.script(when_recv('メニューを閉じる'), [if_(V('番号') > 0, [delete_clone()])], comment='選び終わったら消す')
    s.x, s.y = 0, -95
