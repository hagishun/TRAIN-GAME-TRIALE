"""train-driver-3d.sb3 を作る。

    python3 generator/build.py            # リポジトリ直下に train-driver-3d.sb3 を出力
    python3 generator/build.py out.sb3    # 出力先を指定
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sb3 import Project  # noqa: E402
from sprites import stage, data, logic, render, hud  # noqa: E402


def build(path):
    p = Project()
    stage.build(p)
    # スプライトは作った順に奥から手前へ重なる（ペンの絵はすべてのスプライトより奥）
    render.build_scenery(p)
    render.build_render(p)
    render.build_opposing(p)
    render.build_planes(p)
    data.build_settings(p)
    data.build_routes(p)
    data.build_cars(p)
    logic.build_drive(p)
    logic.build_scoring(p)
    hud.build_sound(p)
    logic.build_game(p)
    hud.build_hud(p)

    # 変数・リストの表示（モニター）。座標はステージ左上が (0,0)
    p.var_monitor('案内', 8, 28)
    p.var_monitor('時刻', 270, 2)
    p.var_monitor('定刻', 375, 2)
    p.var_monitor('次の駅', 166, 257)
    p.var_monitor('あと', 166, 281)
    p.var_monitor('勾配', 270, 281)
    p.var_monitor('制限', 166, 305)
    p.var_monitor('予告', 166, 329)
    p.var_monitor('総合評価', 40, 278)
    p.list_monitor('路線一覧', 40, 92, 400, 196)
    p.list_monitor('車両一覧', 40, 92, 400, 196)
    p.list_monitor('成績', 40, 86, 400, 186)
    p.list_monitor('採点', 90, 34, 300, 196)
    pj = p.save(path)
    nblocks = sum(len(t['blocks']) for t in pj['targets'])
    ncomments = sum(len(t['comments']) for t in pj['targets'])
    print(f'{path}: スプライト {len(pj["targets"]) - 1} 個, ブロック {nblocks} 個, コメント {ncomments} 個, '
          f'{os.path.getsize(path) // 1024} KB')
    return pj


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), 'train-driver-3d.sb3')
    build(out)
