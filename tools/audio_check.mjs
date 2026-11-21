// 効果音が本当に鳴っているかを Chromium で確かめる。
//
//   node tools/audio_check.mjs
//
// 1. 自動再生の制限（クリックやキーを押すまで音が出ない）で AudioContext がどうなるかを調べる
// 2. 効果音を鳴らすたびに、音の名前・鳴らしたスプライトの役割・音量・実際のゲイン（音量のかかり方）を記録する
// 3. 出力の直前にアナライザーをつなぎ、本当に音（振幅）が出ているかを測る
import fs from 'fs';
import path from 'path';
import {createRequire} from 'module';
import {chromium} from 'playwright';

const require = createRequire(import.meta.url);
const Packager = require('@turbowarp/packager');
const ROOT = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const SB3 = path.join(ROOT, process.argv.includes('--file') ? process.argv[process.argv.indexOf('--file') + 1] : 'train-driver-3d.sb3');
const BUILD = path.join(ROOT, 'build');
fs.mkdirSync(BUILD, {recursive: true});

const project = await Packager.loadProject(fs.readFileSync(SB3));
const packager = new Packager.Packager();
packager.project = project;
packager.options.autoplay = true;
const file = path.join(BUILD, 'audio-check.html');
fs.writeFileSync(file, (await packager.package()).data);

const browser = await chromium.launch();
const page = await browser.newPage({viewport: {width: 960, height: 720}});
const pageErrors = [];
page.on('pageerror', e => pageErrors.push(String(e)));
await page.goto('file://' + file);
await page.waitForFunction(() => window.scaffolding && scaffolding.vm.runtime.targets.length > 5, null, {timeout: 60000});

await page.evaluate(() => {
    const vm = scaffolding.vm;
    const engine = vm.runtime.audioEngine;
    window.A = {log: [], peaks: [], levels: [], engine};
    // 出力の手前で音の大きさを測る
    const an = engine.audioContext.createAnalyser();
    an.fftSize = 2048;
    an.smoothingTimeConstant = 0;
    engine.inputNode.connect(an);
    const buf = new Float32Array(an.fftSize);
    const spec = new Float32Array(an.frequencyBinCount);
    // きしみ音（約 3150Hz）のあたりの強さ [dB] を測る
    A.band = (lo, hi) => {
        an.getFloatFrequencyData(spec);
        const hz = engine.audioContext.sampleRate / an.fftSize;
        let m = -200;
        for (let i = Math.floor(lo / hz); i <= Math.ceil(hi / hz); i++) m = Math.max(m, spec[i]);
        return m;
    };
    setInterval(() => {
        an.getFloatTimeDomainData(buf);
        let p = 0, sq = 0;
        for (const v of buf) {
            p = Math.max(p, Math.abs(v));
            sq += v * v;
        }
        A.peaks.push(p);
        A.levels.push({t: performance.now(), p, rms: Math.sqrt(sq / buf.length)});
    }, 50);
    // 効果音を鳴らす呼び出しを捕まえる
    const names = {};
    for (const t of vm.runtime.targets) {
        if (t.sprite) for (const s of t.sprite.sounds) names[s.soundId] = s.name;
    }
    const stage = vm.runtime.getTargetForStage();
    const sv = n => Object.values(stage.variables).find(x => x.name === n).value;
    const hookBank = bank => {
        if (bank.__hooked) return;
        bank.__hooked = true;
        const orig = bank.playSound.bind(bank);
        bank.playSound = (target, soundId) => {
            const r = orig(target, soundId);
            // 実際にかかった音量（効果チェーンの volume の値 0〜100）。ビルドで名前が縮められても name は残る
            const chain = bank.soundEffects.get(soundId);
            const effects = chain ? (chain._effects || chain.effects || []) : [];
            const vol = effects.find(e => e && e.name === 'volume');
            A.log.push({t: performance.now(), sound: names[soundId], sprite: target.sprite.name, role: target.sprite.name,
                clone: !target.isOriginal, targetVolume: target.volume, gain: vol ? vol.value / 100 : target.volume / 100,
                ctx: engine.audioContext.state, speed: Number(sv('速度'))});
            return r;
        };
    };
    for (const t of vm.runtime.targets) if (t.sprite && t.sprite.soundBank) hookBank(t.sprite.soundBank);
    window.A.T = {
        get: sv,
        set: (n, v) => { Object.values(stage.variables).find(x => x.name === n).value = v; },
        targets: () => vm.runtime.targets.filter(t => t.sprite && ['効果音', '発車メロディ', 'モーター音', '走行音', 'きしみ音'].includes(t.sprite.name))
            .map(t => ({sprite: t.sprite.name, volume: Math.round(t.volume), pitch: t.soundEffects ? Math.round(t.soundEffects.pitch) : null})),
    };
});

const state = () => page.evaluate(() => A.engine.audioContext.state);
const press = async k => { await page.keyboard.down(k); await page.waitForTimeout(150); await page.keyboard.up(k); };
const report = {};
report.ctxAtLoad = await state();
await page.waitForFunction(() => A.T.get('場面') === 'タイトル');
await press('Enter');
await page.waitForTimeout(500);
report.ctxAfterKeyOnly = await state();
// ステージをクリック（最初のクリックで音が出るようになるはず）
await page.mouse.click(480, 360);
await page.waitForTimeout(500);
report.ctxAfterClick = await state();
await page.waitForFunction(() => A.T.get('場面') === '路線選択');
await press('3');
await page.waitForFunction(() => A.T.get('場面') === '運転中', null, {timeout: 40000});
// 走る（P5 → 速度が出たらノッチを戻す）
for (let i = 0; i < 6; i++) await press('ArrowUp');
await page.waitForTimeout(500);
for (let i = 0; i < 6; i++) await press('ArrowUp');
await page.waitForTimeout(12000);
await press('h');
await page.waitForTimeout(1500);
// 対向列車を出してすれ違いの音
await page.evaluate(() => {
    const t = scaffolding.vm.runtime.targets.find(x => x.isOriginal && x.sprite.name === '対向列車');
    const v = n => Object.values(t.variables).find(x => x.name === n);
    A.T.set('対向列車_出現率', 100);
    v('有無').value = 0;
    v('抽選タイマー').value = 999;
});
await page.waitForTimeout(400);
await page.evaluate(() => {
    const t = scaffolding.vm.runtime.targets.find(x => x.isOriginal && x.sprite.name === '対向列車');
    Object.values(t.variables).find(x => x.name === '先頭位置').value = Number(A.T.get('位置')) + 1000;
});
await page.waitForTimeout(6000);
// 制限を大きく超えて ATS ベル
await page.evaluate(() => A.T.set('速度', Number(A.T.get('現在の制限')) + 6));
await page.waitForTimeout(2500);
report.soundTargetsWhileRunning = await page.evaluate(() => A.T.targets());
// 駅に止めて採点・ドア・発車メロディ・ドアチャイム
await page.evaluate(() => {
    const stop = Number(A.T.get('駅の位置')[Number(A.T.get('次の駅番号')) - 1]);
    A.T.set('ATS状態', 0);
    A.T.set('位置', stop - 4.4);
    A.T.set('速度', 6.5);
    A.T.set('ノッチ', -2);
    A.T.set('ブレーキ率', 0.25);
    A.T.set('力行率', 0);
});
await page.waitForFunction(() => A.T.get('場面') === '停車中', null, {timeout: 20000});
await page.waitForFunction(() => A.T.get('場面') === '運転中', null, {timeout: 40000});
await page.waitForTimeout(1000);
report.soundTargetsAfterStation = await page.evaluate(() => A.T.targets());
// カーブ（紅葉滝の先、半径 2000m の左カーブ）できしみ音が鳴るか。モーター音・走行音は 0 にして、きしみ音だけを測る
async function squealWindow(pos, label, ms) {
    await page.evaluate(p => {
        A.T.set('モーター音の音量', 0);
        A.T.set('走行音の音量', 0);
        A.T.set('ATS状態', 0);
        A.T.set('次の駅番号', A.T.get('駅名').length);
        A.T.set('位置', p);
        A.T.set('速度', 170);
        A.T.set('ノッチ', 0);
        A.T.set('場面', '運転中');
        A.T.set('ドア', '閉');
        A.T.set('現在の制限', 230);
    }, pos);
    await page.waitForTimeout(1000);   // 前の場所の音が消えるのを待つ
    const samples = [];
    const t0 = Date.now();
    while (Date.now() - t0 < ms) {
        await page.waitForTimeout(100);
        samples.push(await page.evaluate(() => {
            const t = scaffolding.vm.runtime.targets.find(x => x.isOriginal && x.sprite.name === 'きしみ音');
            return {vol: t.volume, band: A.band(2900, 3400), pos: Number(A.T.get('位置'))};
        }));
        await page.evaluate(() => A.T.set('速度', 170));
    }
    const on = samples.filter(x => x.vol > 1);
    const r = {label, maxVol: Math.max(...samples.map(x => x.vol)), onRatio: on.length / samples.length,
        bandOn: on.length ? Math.max(...on.map(x => x.band)) : null, bandMax: Math.max(...samples.map(x => x.band)),
        from: Math.round(samples[0].pos), to: Math.round(samples[samples.length - 1].pos)};
    console.log(`きしみ音 ${label}（${r.from}〜${r.to}m・170km/h）: 音量の最大 ${r.maxVol.toFixed(0)}、鳴っていた時間 ${(r.onRatio * 100).toFixed(0)}%、` +
        `3.15kHz 付近の強さ 最大 ${r.bandMax.toFixed(1)}dB`);
    return r;
}
report.squealCurve = await squealWindow(23920, 'カーブ（半径2000m）', 7000);
report.squealStraight = await squealWindow(26000, '直線', 3000);
const log = await page.evaluate(() => A.log);
const peaks = await page.evaluate(() => A.peaks);
const levels = await page.evaluate(() => A.levels);
await browser.close();

// 結果
const byName = {};
for (const e of log) {
    const k = e.sound;
    byName[k] = byName[k] || {count: 0, roles: new Set(), minGain: Infinity, maxGain: -Infinity, ctx: new Set()};
    const b = byName[k];
    b.count++;
    b.roles.add(`${e.role}${e.clone ? '(クローン)' : ''}`);
    b.minGain = Math.min(b.minGain, e.gain);
    b.maxGain = Math.max(b.maxGain, e.gain);
    b.ctx.add(e.ctx);
}
console.log('AudioContext: 読み込み直後=%s / キーだけ押した後=%s / クリック後=%s', report.ctxAtLoad, report.ctxAfterKeyOnly, report.ctxAfterClick);
console.log('鳴らした音（ゲイン＝実際にかかった音量 0〜1）:');
for (const [k, b] of Object.entries(byName)) {
    console.log(`  ${k.padEnd(8, '　')} ${String(b.count).padStart(4)}回  役割=${[...b.roles].join(',')}  ゲイン ${b.minGain.toFixed(2)}〜${b.maxGain.toFixed(2)}  context=${[...b.ctx].join(',')}`);
}
console.log('走行中のサウンドスプライト:', JSON.stringify(report.soundTargetsWhileRunning));
console.log('駅を出た後のサウンドスプライト:', JSON.stringify(report.soundTargetsAfterStation));
// 発車メロディ: 鳴らし始めてから 8 秒間の出力を測る（モーター音・走行音は停車中なので鳴っていない）
for (const e of log.filter(x => /^CLEX/.test(x.sound))) {
    const w = levels.filter(l => l.t >= e.t && l.t < e.t + 8000);
    const before = levels.filter(l => l.t >= e.t - 1500 && l.t < e.t - 200);
    const avg = a => a.length ? a.reduce((s, l) => s + l.rms, 0) / a.length : 0;
    const max = a => a.length ? Math.max(...a.map(l => l.p)) : 0;
    console.log(`発車メロディ ${e.sound}（${e.sprite}・音量 ${Math.round(e.targetVolume)}）: 鳴る前 RMS ${avg(before).toFixed(4)} → ` +
        `鳴っている 8 秒の RMS ${avg(w).toFixed(4)}・最大振幅 ${max(w).toFixed(3)}（${w.length} 回測定）`);
}
const loud = peaks.filter(p => p > 0.01).length;
console.log(`出力の振幅: 最大 ${Math.max(...peaks).toFixed(3)}、音が出ていた時間の割合 ${(100 * loud / peaks.length).toFixed(0)}%（${peaks.length} 回測定）`);
console.log('ページのエラー:', pageErrors.length ? pageErrors : 'なし');
fs.writeFileSync(path.join(BUILD, 'audio-check.json'), JSON.stringify({report, byName: Object.fromEntries(Object.entries(byName).map(([k, b]) => [k, {...b, roles: [...b.roles], ctx: [...b.ctx]}])), log}, null, 1));
