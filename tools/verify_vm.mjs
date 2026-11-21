// scratch-vm（Scratch の実行エンジン）で .sb3 を読み込み、自動運転ボットで最後まで走らせて検証する。
//
//   node tools/verify_vm.mjs                       # 3 路線をすべて走る
//   node tools/verify_vm.mjs --route 2             # 路線 2 だけ
//   node tools/verify_vm.mjs --route 2 --reckless  # 制限を無視して走る（ATS の確認）
//   node tools/verify_vm.mjs --opp 100             # 対向列車の出現率を 100% にする
//   node tools/verify_vm.mjs --style careful       # 運転のうまさ: expert（上手）/ careful（丁寧）/ sloppy（雑）
//
// 時計（Date.now）を偽物にして 1 フレーム = 1/30 秒ずつ進めるので、実時間より速く検証できる。
import fs from 'fs';
import path from 'path';
import {createRequire} from 'module';

const require = createRequire(import.meta.url);
const args = process.argv.slice(2);
const opt = (name, def) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : def;
};
const sb3Path = opt('--file', path.join(path.dirname(new URL(import.meta.url).pathname), '..', 'train-driver-3d.sb3'));
const routes = opt('--route', null) ? [Number(opt('--route'))] : [1, 2, 3];
const reckless = args.includes('--reckless');
const oppRate = opt('--opp', null);
const quiet = args.includes('--quiet');
const trace = args.includes('--trace');
const style = opt('--style', 'expert');
// 運転のくせ（停止位置の狙いのずれ・止まる直前にブレーキを緩めるか・制限への余裕・ノッチ操作の間隔）
const STYLE = {
    expert: {aim: [0, 0], ease: 0.9, margin: -1.5, plan: 3.4, every: 1},
    careful: {aim: [-1.4, 1.0], ease: 1.3, margin: -8, plan: 3.0, every: 3},
    sloppy: {aim: [-3.5, 3.0], ease: 2.2, margin: 4, plan: 4.2, every: 5},
}[style];
let seed = Number(opt('--seed', 7));
const rand = () => {
    seed |= 0;
    seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
};

// ---- 偽の時計 --------------------------------------------------------------
let simNow = 1_700_000_000_000;
const realNow = Date.now.bind(Date);
Date.now = () => {
    simNow += 0.05;
    return simNow;
};

// ---- ログを集める ------------------------------------------------------------
const problems = [];
const origWarn = console.warn;
const origErr = console.error;
const origLog = console.log;
const noise = /Translation for|No storage module|Could not fetch|scratch-render|AudioContext/;
console.error = (...a) => {
    const s = a.join(' ');
    if (!noise.test(s)) problems.push('error: ' + s);
};
console.warn = (...a) => {
    const s = a.join(' ');
    if (!noise.test(s)) problems.push('warn: ' + s);
};
console.log = (...a) => {
    const s = a.join(' ');
    if (/vm (warn|error)/.test(s) && !noise.test(s)) problems.push('log: ' + s);
    else if (!noise.test(s)) origLog(...a);
};

const VM = require('scratch-vm');
const {ScratchStorage} = require('scratch-storage');

const FRAME = 1000 / 30;

async function newVM() {
    const vm = new VM();
    vm.attachStorage(new ScratchStorage());
    await vm.loadProject(fs.readFileSync(sb3Path));
    vm.runtime.currentStepTime = FRAME;
    vm.runtime.turboMode = false;
    return vm;
}

function helpers(vm) {
    const stage = vm.runtime.getTargetForStage();
    const byName = {};
    for (const v of Object.values(stage.variables)) byName[v.name] = v;
    const get = n => {
        const v = byName[n];
        if (!v) throw new Error('no var ' + n);
        return v.value;
    };
    const num = n => Number(get(n));
    const set = (n, val) => {
        byName[n].value = val;
    };
    const sprite = name => vm.runtime.targets.find(t => t.isOriginal && t.getName() === name);
    const local = (spriteName, n) => {
        const t = sprite(spriteName);
        return Object.values(t.variables).find(v => v.name === n).value;
    };
    return {stage, get, num, set, sprite, local};
}

let frame = 0;
function step(vm, n = 1) {
    for (let i = 0; i < n; i++) {
        frame++;
        simNow = Math.max(simNow, 1_700_000_000_000 + frame * FRAME);
        vm.runtime._step();
    }
}

const KEYMAP = {up: 'ArrowUp', down: 'ArrowDown', space: ' ', h: 'h', enter: 'Enter'};
function key(vm, k, down) {
    vm.postIOData('keyboard', {key: KEYMAP[k] || k, isDown: down});
}
function tap(vm, k, frames = 2) {
    key(vm, k, true);
    step(vm, frames);
    key(vm, k, false);
    step(vm, frames);
}

// ---- 自動運転ボット ----------------------------------------------------------
// 人間の運転士のように、制限速度と停止位置に向けてノッチを選ぶ。
function desiredNotch(h, state) {
    const v = h.num('速度');
    const pos = h.num('位置');
    const lim = h.num('現在の制限');
    const idx = h.num('次の駅番号');
    const stop = Number(h.get('駅の位置')[idx - 1]);
    if (state.station !== idx) {
        state.station = idx;
        state.creep = false;
        state.offset = STYLE.aim[0] + (STYLE.aim[1] - STYLE.aim[0]) * rand();
    }
    const dReal = stop - pos;
    const d = dReal + state.offset;
    state.dReal = dReal;
    state.tolerance = h.num('停止位置の許容');
    const per = h.num('常用最大減速度') / 8;
    const cell = Math.floor(pos / 10);
    const grade = Number(h.get('勾配表')[cell] || 0) * 0.0353;
    const plan = STYLE.plan;
    if (reckless) {
        const reckStop = Math.sqrt(Math.max(0, 2 * 2.5 * 3.6 * (d - v / 3.6 * 1.2)));
        if (reckStop < v + 2 || d < 40) return brakeToStop(h, v, d, per, grade, state);
        return v < h.num('路線の最高速度') + 15 ? 5 : 0;
    }
    let target = lim + STYLE.margin;
    const starts = h.get('制限の開始'), speeds = h.get('制限の速度');
    for (let i = 0; i < starts.length; i++) {
        const s = Number(starts[i]);
        if (s > pos) {
            const vl = Number(speeds[i]) + STYLE.margin;
            const allow = Math.sqrt(Math.max(0, vl * vl + 2 * plan * 3.6 * (s - pos - v / 3.6 * 1.5)));
            target = Math.min(target, allow);
        }
    }
    const stopCurve = Math.sqrt(Math.max(0, 2 * plan * 3.6 * (d - v / 3.6 * 1.2)));
    if (stopCurve < v + 2 || d < 40) return brakeToStop(h, v, d, per, grade, state);
    target = Math.min(target, stopCurve);
    const err = target - v;
    if (err > 0) return Math.min(5, Math.max(1, Math.round(err * 0.6 + grade * 2)));
    if (err > -1.5) return 0;
    return -Math.min(6, Math.max(1, Math.round(-err * 0.6 - grade)));
}

function brakeToStop(h, v, d, per, grade, state) {
    if (v < 0.05) {
        if (state.dReal > state.tolerance - 0.3) {
            state.offset = 0;   // 手前すぎて採点されなかったので、停止位置まで進め直す
            d = state.dReal;
        }
        if (d > 0.9) {
            state.creep = true;
            return grade > 0.3 ? 5 : 2;   // 上り坂では強めに力行しないと動かない
        }
        return -8;
    }
    if (state.creep && v < 30) {
        if (v < 4 && d > 3) return grade > 0.3 ? 5 : 2;
        if (d > 30) return v < 30 ? 4 : 0;
        if (d > 0.6 && v < 2.5) return 0;
        state.creep = false;
    }
    const dd = Math.max(0.02, d - v / 3.6 * 0.45);
    const req = v * v / (2 * 3.6 * dd);
    const gain = v < 15 ? 1 + 0.25 * (1 - v / 15) : 1;
    const res = 0.05 + grade;
    let n = (req - res) / (per * gain);
    if (v < 10) n *= STYLE.ease;
    if (n < 0.35) return d > 1 && v < 6 ? 0 : -1;
    return -Math.min(8, Math.max(1, Math.round(n)));
}

async function runRoute(routeNo) {
    frame = 0;
    const vm = await newVM();
    const h = helpers(vm);
    vm.greenFlag();
    step(vm, 20);
    if (oppRate !== null) h.set('対向列車_出現率', Number(oppRate));
    if (h.get('場面') !== 'タイトル') throw new Error('タイトル画面にならない: ' + h.get('場面'));
    tap(vm, 'space', 3);
    step(vm, 5);
    if (h.get('場面') !== 'タイトル') throw new Error('スペースで始まってしまった（スペースは非常ブレーキ用）');
    tap(vm, 'enter', 3);
    step(vm, 5);
    if (h.get('場面') !== '路線選択') throw new Error('路線選択にならない: ' + h.get('場面'));
    tap(vm, String(routeNo), 3);
    step(vm, 30);
    if (oppRate !== null) h.set('対向列車_出現率', Number(oppRate));
    const routeName = h.get('路線名');
    const log = {route: routeName, events: [], opposing: 0, passes: 0, ats: 0, atsEB: 0, maxFrameMs: 0};
    let lastScene = '';
    let lastATS = 0;
    let oppWas = 0;
    let keyHeld = null;
    const state = {creep: false};
    const t0 = realNow();
    const maxFrames = 30 * 60 * 40;
    let nanFrames = 0;
    while (h.get('場面') !== '結果' && frame < maxFrames) {
        const scene = h.get('場面');
        if (scene !== lastScene) {
            log.events.push(`[${(frame / 30).toFixed(1)}s] 場面=${scene} 次の駅番号=${h.get('次の駅番号')} 案内=${h.get('案内')}`);
            lastScene = scene;
        }
        // キー操作（押す → 離す をくり返してノッチを動かす）
        if (keyHeld) {
            key(vm, keyHeld, false);
            keyHeld = null;
        } else if (frame % STYLE.every === 0) {
            let want = -8;
            if (scene === '運転中') want = desiredNotch(h, state);
            const cur = h.num('ノッチ');
            if (want > cur) keyHeld = 'up';
            else if (want < cur) keyHeld = 'down';
            if (keyHeld) key(vm, keyHeld, true);
        }
        if (trace && frame % 60 === 0 && scene === '運転中') {
            log.events.push(`  t=${(frame / 30).toFixed(0)} 位置=${h.num('位置').toFixed(0)} 速度=${h.num('速度').toFixed(1)} ノッチ=${h.get('ノッチ名')} 制限=${h.num('現在の制限')} 勾配=${h.get('勾配')} 力行率=${h.num('力行率').toFixed(2)} ブレーキ率=${h.num('ブレーキ率').toFixed(2)}`);
        }
        const fs0 = realNow();
        step(vm, 1);
        log.maxFrameMs = Math.max(log.maxFrameMs, realNow() - fs0);
        const ats = h.num('ATS状態');
        if (ats !== lastATS) {
            if (ats === 1) log.ats++;
            if (ats === 2) log.atsEB++;
            log.events.push(`[${(frame / 30).toFixed(1)}s] ATS状態=${ats} 速度=${h.num('速度').toFixed(1)} 制限=${h.num('現在の制限')}`);
            lastATS = ats;
        }
        const opp = Number(h.local('対向列車', '有無'));
        if (opp !== oppWas) {
            if (opp === 1) {
                log.opposing++;
                log.events.push(`[${(frame / 30).toFixed(1)}s] 対向列車 出現 両数=${h.local('対向列車', '両数')} 速さ=${(h.local('対向列車', '列車の速さ') * 3.6).toFixed(0)}km/h`);
            } else {
                log.passes++;
                log.events.push(`[${(frame / 30).toFixed(1)}s] 対向列車 すれ違い完了`);
            }
            oppWas = opp;
        }
        for (const n of ['位置', '速度', 'ブレーキ率', '力行率', '時刻の秒']) {
            if (!Number.isFinite(h.num(n))) nanFrames++;
        }
    }
    const elapsed = (realNow() - t0) / 1000;
    if (h.get('場面') === '結果') {
        step(vm, 40);
    }
    log.scene = h.get('場面');
    log.results = h.get('成績').slice();
    log.summary = h.get('総合評価');
    log.gameSeconds = frame / 30;
    log.realSeconds = elapsed;
    log.nanFrames = nanFrames;
    log.stations = h.get('駅名').length;
    log.stops = h.get('駅の種別').filter(k => k === '停車').length;
    log.blocks = 0;
    vm.stopAll();
    return log;
}

const all = [];
for (const r of routes) {
    const log = await runRoute(r);
    all.push(log);
    origLog(`\n=== 路線${r}: ${log.route}（${style}${reckless ? '・制限無視' : ''}） ===`);
    if (!quiet) for (const e of log.events) origLog('  ' + e);
    origLog('  成績:');
    for (const line of log.results) origLog('    ' + line);
    origLog(`  総合評価: ${log.summary}`);
    origLog(`  最後の場面=${log.scene}  ゲーム内 ${log.gameSeconds.toFixed(0)} 秒 / 実時間 ${log.realSeconds.toFixed(1)} 秒` +
        `  1フレーム最大 ${log.maxFrameMs.toFixed(1)}ms  ATS警報 ${log.ats} 回・ATS非常 ${log.atsEB} 回  対向列車 ${log.opposing} 本（すれ違い完了 ${log.passes}）  NaN ${log.nanFrames}`);
}
// 始発駅をのぞく停車駅の数だけ成績が並んでいれば OK（通過駅は採点しない）
const failed = all.filter(l => l.scene !== '結果' || l.results.length !== l.stops - 1 || l.nanFrames > 0);
origLog('\n問題（エラー・警告）: ' + (problems.length ? '\n  ' + [...new Set(problems)].slice(0, 30).join('\n  ') : 'なし'));
if (failed.length || problems.length) {
    origLog('検証失敗');
    process.exit(1);
}
origLog('検証OK');
process.exit(0);
