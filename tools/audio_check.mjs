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
    engine.inputNode.connect(an);
    const buf = new Float32Array(an.fftSize);
    const fbuf = new Float32Array(an.frequencyBinCount);
    const binHz = engine.audioContext.sampleRate / an.fftSize;
    setInterval(() => {
        an.getFloatTimeDomainData(buf);
        let p = 0, s = 0;
        for (const v of buf) {
            p = Math.max(p, Math.abs(v));
            s += v * v;
        }
        // きしみ音の高さ（2.6〜6kHz）だけの大きさ。走行音・モーター音はもっと低い
        an.getFloatFrequencyData(fbuf);
        let hf = 0;
        for (let i = Math.round(2600 / binHz); i <= Math.round(6000 / binHz); i++) hf += 10 ** (fbuf[i] / 10);
        A.peaks.push(p);
        A.levels.push([performance.now(), Math.sqrt(s / buf.length), hf]);
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
await page.evaluate(() => { A.T.set('アクシデント_起きやすさ', 0); A.T.set('番線変更_起きやすさ', 0); });   // 位置を移すので、アクシデントは起こさない
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
await page.waitForFunction(() => A.T.get('場面') === '運転中', null, {timeout: 60000});
await page.waitForTimeout(1000);
report.soundTargetsAfterStation = await page.evaluate(() => A.T.targets());
// カーブ（田原海岸線 23900m〜 半径2000m）ときしみ音。直線では鳴らないこと
const squeal = {};
for (const [name, pos, speed] of [['カーブ 半径2000m・180km/h', 24200, 180], ['直線・180km/h', 8000, 180], ['カーブ 半径2000m・60km/h', 24300, 60]]) {
    await page.evaluate(([pos, speed]) => {
        A.T.set('ATS状態', 0);
        const stops = A.T.get('駅の位置').map(Number);
        A.T.set('次の駅番号', stops.findIndex(p => p > pos + 100) + 1);
        A.T.set('位置', pos);
        A.T.set('速度', speed);
        A.T.set('ノッチ', 0);
        A.T.set('ブレーキ率', 0);
    }, [pos, speed]);
    await page.waitForTimeout(1800);
    const t1 = await page.evaluate(() => performance.now());
    await page.waitForTimeout(800);
    const r = await page.evaluate(() => A.T.targets().find(t => t.sprite === 'きしみ音'));
    squeal[name] = {volume: r.volume, t0: t1 - 800, t1};
}
// アクシデント（障害物）を起こして警報、そのまま走って当たったときの音
await page.evaluate(() => {
    const acc = scaffolding.vm.runtime.targets.find(t => t.isOriginal && t.sprite.name === 'アクシデント');
    const lv = n => Object.values(acc.variables).find(x => x.name === n);
    const stops = A.T.get('駅の位置').map(Number);
    const pos = 8000;
    A.T.set('次の駅番号', stops.findIndex(p => p > pos + 100) + 1);
    A.T.set('ATS状態', 0);
    A.T.set('位置', pos);
    A.T.set('速度', 120);
    lv('予定の位置').value = [pos + 30];
    lv('予定の種類').value = ['落石'];
});
await page.waitForTimeout(2500);
await page.evaluate(() => {
    const acc = scaffolding.vm.runtime.targets.find(t => t.isOriginal && t.sprite.name === 'アクシデント');
    const stop = Number(Object.values(acc.variables).find(x => x.name === '止まる所').value);
    A.T.set('位置', stop - 20);
    A.T.set('速度', 60);
});
await page.waitForTimeout(2500);
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
const loud = peaks.filter(p => p > 0.01).length;
console.log(`出力の振幅: 最大 ${Math.max(...peaks).toFixed(3)}、音が出ていた時間の割合 ${(100 * loud / peaks.length).toFixed(0)}%（${peaks.length} 回測定）`);
// 発車メロディ: 鳴らした曲・ドアチャイムまでの秒数・出力の大きさ（RMS を dB で。ほかの効果音と比べる）
const dB = v => (20 * Math.log10(Math.max(v, 1e-6))).toFixed(1);
const levelIn = (t0, t1) => {
    const w = levels.filter(([t]) => t >= t0 && t < t1).map(([, v]) => v);
    return w.length ? Math.sqrt(w.reduce((a, v) => a + v * v, 0) / w.length) : 0;
};
const melodies = log.filter(e => e.sprite === '発車メロディ');
for (const m of melodies) {
    const chime = log.find(e => e.sound === 'ドアチャイム' && e.t > m.t);
    const gap = chime ? (chime.t - m.t) / 1000 : NaN;
    console.log(`発車メロディ ${m.sound}: ゲイン ${m.gain.toFixed(2)}、鳴り始めから ${gap.toFixed(1)} 秒後にドアチャイム、` +
        `曲のあいだの出力 ${dB(levelIn(m.t + 300, m.t + Math.min(gap * 1000, 8000)))} dB`);
    if (chime) console.log(`  ドアチャイムの出力 ${dB(levelIn(chime.t + 50, chime.t + 2000))} dB`);
}
for (const n of ['警笛', 'すれ違い']) {
    const e = log.find(x => x.sound === n);
    if (e) console.log(`  ${n}の出力 ${dB(levelIn(e.t + 50, e.t + 1200))} dB（走行音・モーター音を含む）`);
}
console.log('きしみ音（スプライトの音量 0〜100、その間の出力の全体と 2.6〜6kHz の大きさ。走行音・モーター音を含む）:');
const hfIn = (t0, t1) => {
    const w = levels.filter(([t]) => t >= t0 && t < t1).map(([, , hf]) => hf);
    return w.length ? w.reduce((a, v) => a + v, 0) / w.length : 0;
};
for (const [name, s] of Object.entries(squeal)) {
    console.log(`  ${name}: 音量 ${s.volume}、出力 ${dB(levelIn(s.t0, s.t1))} dB、2.6〜6kHz ${(10 * Math.log10(Math.max(hfIn(s.t0, s.t1), 1e-12))).toFixed(1)} dB`);
}
console.log('  きしみ音を鳴らした回数:', log.filter(e => e.sound === 'きしみ').length);
console.log('アクシデントの音:', ['警報', '衝突'].map(n => `${n} ${log.filter(e => e.sound === n).length} 回`).join('・'));
console.log('ページのエラー:', pageErrors.length ? pageErrors : 'なし');
fs.writeFileSync(path.join(BUILD, 'audio-check.json'), JSON.stringify({report, byName: Object.fromEntries(Object.entries(byName).map(([k, b]) => [k, {...b, roles: [...b.roles], ctx: [...b.ctx]}])), log}, null, 1));
