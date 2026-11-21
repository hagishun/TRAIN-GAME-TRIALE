"""運転台・計器・ランプ・画面（タイトル/メニュー）・サウンドのスプライト。"""
import assets
from routes_data import CARS
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
    s.costume_svg('路線パネル', assets.panel('路線をえらぶ', '数字キーで路線を選んでください'), 240, 180)
    s.costume_svg('車両パネル', assets.panel('車両をえらぶ', '数字キーで車両を選んでください'), 240, 180)
    s.costume_svg('結果パネル', assets.panel('運転成績', 'Enter キーかクリックでタイトルにもどる',
                                         '♪ 発車メロディ: Clarinet_Express 様（信町高速鉄道のために制作・許可を得て使用）'), 240, 180)
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
    s.overview = ('【効果音スプライト】警笛・ドアチャイム・ATS ベルなどを鳴らす（ここの音はすべて合成したオリジナル）。\n'
                  '   発車メロディは「発車メロディ」スプライトで鳴らす。\n'
                  '■ 音量は「設定」スプライトの「効果音の音量」で決まり、走っている間も変わらない。\n'
                  '   （モーター音と走行音は別のスプライトなので、そちらの音量を変えても効果音には影響しない）\n'
                  '■ 音を差し替えたいときは、同じ名前の音を録音・読み込みして置き換える。\n'
                  '■ ブラウザは、ページを一度クリック（またはキーを押す）するまで音を出さない決まりがある。\n'
                  '   Scratch ではクリックが必要なので、タイトル画面はクリックでも始められるようにしてある。')
    s.script(when_flag(), [hide(), set_volume(100)], comment='緑の旗で音量を戻す')
    s.script(when_recv('ATSベル'), [
        set_volume(V('効果音の音量')),
        repeat_until(eq(V('ATS状態'), 0), [play_wait('ATSベル')]),
    ], comment='ATS が元に戻るまでベルを鳴らし続ける')
    for msg, snd in [('警笛', '警笛'), ('遠くの警笛', '遠くの警笛'), ('ドアチャイム', 'ドアチャイム'),
                     ('すれ違い', 'すれ違い'), ('ブレーキ緩め', 'ブレーキ緩め'), ('ドア', 'ドア'), ('採点音', '採点'),
                     ('ピタ停車音', 'ピタ停車'), ('結果音', '結果'), ('決定音', '決定'), ('飛行機の音', '飛行機')]:
        s.script(when_recv(msg), [set_volume(V('効果音の音量')), play(snd)], comment=f'「{snd}」を鳴らす')

    # 発車メロディ（Clarinet_Express 様の曲。専用のスプライトなので、音量を変えてもほかの効果音に影響しない）
    s = p.sprite('発車メロディ')
    s.costume_svg('発車メロディ', *assets.icon('♪', '#2a8fbf'))
    for name in assets.MELODIES:
        s.sound_wav(name, *assets.melody(name))
    s.overview = ('【発車メロディスプライト】駅を発車するときの発車メロディを鳴らす。\n'
                  '■ ' + assets.MELODY_CREDIT + '\n'
                  '   曲の権利は Clarinet_Express 様にあります。このゲームの中で使う・改造するのは OK ですが、\n'
                  '   曲だけを取り出してほかの作品に使わないでください。\n'
                  '■ どの駅でどの曲が鳴るか: 「路線データ」スプライトの『駅を追加』の最後の欄（発車メロディ）。\n'
                  '   ここを変えると駅ごとの発車メロディが変わる。名前はこのスプライトの音の名前（CLEX202 / CLEX203 / CLEX204）。\n'
                  '   「なし」と書いた駅では鳴らさない。新しい曲を足すときは、このスプライトに音を読み込んで、その名前を書く。\n'
                  '■ 音量は「設定」スプライトの「発車メロディの音量」。曲を鳴らし始める時刻は「発車メロディの前の秒」。\n'
                  '■ 3 曲は、ほかの効果音とつり合うように音の大きさだけそろえてある（ステレオ・44.1kHz のまま）。')
    s.var('曲', '')
    s.script(when_flag(), [hide(), set_volume(100)], comment='緑の旗で音量を戻す')
    s.script(when_recv('発車メロディ'), [
        set_('曲', item('駅の発車メロディ', V('発車する駅'))).c('発車する駅の曲の名前（路線データの『駅を追加』で決めたもの）'),
        set_volume(V('発車メロディの音量')),
        if_(not_(eq(V('曲'), 'なし')), [
            play_wait(V('曲')).c('曲が終わるまで待つ。名前の音が無いときはすぐ終わる'),
        ]),
        set_('メロディ中', 0).c('採点スプライトの『発車する』に「曲が終わった」と知らせる → ドアチャイムへ'),
    ], comment='発車メロディを最後まで鳴らす。' + assets.MELODY_CREDIT)

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
