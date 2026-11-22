// 分岐器（ポイント）の「ガタン」が、分岐器を通るときにだけ鳴り、ふつうのジョイント音より大きいかを Chromium で測る。
//
//   node tools/turnout_check.mjs
//
// HTML 化した版を開き、電車を分岐器の手前へ動かして、決まった速さで通らせる。
// 音を鳴らすたびに、音の名前・実際の音量（ゲイン）・位置を記録し、出力の直前で大きさ（ピーク）を測る。
//   1. 何もない直線を走る（ジョイントだけ鳴り、分岐器の音は鳴らない）
//   2. 通過駅の分岐器をまっすぐ通る（45・100・240km/h）。速いほど「ガタン」の間が短くなる
//   3. 停車駅の分岐器を曲がって 3番線に入る（45km/h）。まっすぐ（45km/h）より強い
// ほかの音と混ざらないように、効果音・モーター音・きしみ音の音量は 0 にする（走行音とジョイントはそのまま）。
import fs from 'fs';
import path from 'path';
import {createRequire} from 'module';
import {chromium} from 'playwright';

const require = createRequire(import.meta.url);
const Packager = require('@turbowarp/packager');
const ROOT = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const SB3 = path.join(ROOT, 'train-driver-3d.sb3');
const BUILD = path.join(ROOT, 'build');
fs.mkdirSync(BUILD, {recursive: true});

const project = await Packager.loadProject(fs.readFileSync(SB3));
const packager = new Packager.Packager();
packager.project = project;
packager.options.autoplay = true;
const file = path.join(BUILD, 'turnout-check.html');
fs.writeFileSync(file, (await packager.package()).data);

const browser = await chromium.launch({args: ['--autoplay-policy=no-user-gesture-required']});
const page = await browser.newPage({viewport: {width: 960, height: 720}});
const pageErrors = [];
page.on('pageerror', e => pageErrors.push(String(e)));
await page.goto('file://' + file);
await page.waitForFunction(() => window.scaffolding && scaffolding.vm.runtime.targets.length > 5, null, {timeout: 60000});

await page.evaluate(() => {
    const vm = scaffolding.vm;
    const engine = vm.runtime.audioEngine;
    const ctx = engine.audioContext;
    const stage = vm.runtime.getTargetForStage();
    const sv = n => Object.values(stage.variables).find(x => x.name === n).value;
    const set = (n, v) => { Object.values(stage.variables).find(x => x.name === n).value = v; };
    const local = (sprite, n) => {
        const t = vm.runtime.targets.find(x => x.isOriginal && x.sprite.name === sprite);
        return Object.values(t.variables).find(x => x.name === n).value;
    };
    window.A = {log: [], blocks: [], T: {get: sv, set, local}, frames: 0};
    vm.runtime.on('BEFORE_EXECUTE', () => { A.frames++; });
    // 出力の直前で、256 サンプル（約 5ms）ごとのピークを記録する（時刻は AudioContext の時計）
    const sp = ctx.createScriptProcessor(256, 1, 1);
    engine.inputNode.connect(sp);
    sp.connect(ctx.destination);
    sp.onaudioprocess = e => {
        const x = e.inputBuffer.getChannelData(0);
        let p = 0;
        for (const v of x) p = Math.max(p, Math.abs(v));
        A.blocks.push([e.playbackTime, p]);
        e.outputBuffer.getChannelData(0).fill(0);
    };
    const names = {};
    for (const t of vm.runtime.targets) if (t.sprite) for (const s of t.sprite.sounds) names[s.soundId] = s.name;
    for (const t of vm.runtime.targets) {
        const bank = t.sprite && t.sprite.soundBank;
        if (!bank || bank.__hooked) continue;
        bank.__hooked = true;
        const orig = bank.playSound.bind(bank);
        bank.playSound = (target, soundId) => {
            const r = orig(target, soundId);
            const chain = bank.soundEffects.get(soundId);
            const vol = chain && (chain._effects || chain.effects || []).find(e => e && e.name === 'volume');
            A.log.push({t: ctx.currentTime, sound: names[soundId], sprite: target.sprite.name,
                gain: vol ? vol.value / 100 : target.volume / 100, speed: Number(sv('速度')), pos: Number(sv('位置')),
                axles: Number(local('分岐器の音', 'ガタンの回数'))});
            return r;
        };
    }
});

const press = async k => { await page.keyboard.down(k); await page.waitForTimeout(120); await page.keyboard.up(k); };
await page.waitForFunction(() => A.T.get('場面') === 'タイトル');
await page.evaluate(() => {
    for (const [n, v] of [['アクシデント_起きやすさ', 0], ['番線変更_起きやすさ', 0], ['対向列車_出現率', 0], ['効果音の音量', 0],
                          ['モーター音の音量', 0], ['きしみ音の音量', 0], ['画面のボタン', 0]]) A.T.set(n, v);
});
await page.mouse.click(480, 360);   // 一度クリックすると音が出るようになる
await page.waitForTimeout(300);
if (await page.evaluate(() => A.T.get('場面')) === 'タイトル') await press('Enter');
await page.waitForFunction(() => A.T.get('場面') === '路線選択');
await press('1');
await page.waitForFunction(() => A.T.get('場面') === '運転中', null, {timeout: 180000});
for (let i = 0; i < 9; i++) await press('ArrowUp');   // ブレーキを緩めて N
await page.waitForTimeout(500);

const info = await page.evaluate(() => ({
    names: A.T.get('駅名'), kinds: A.T.get('駅の種別'), stops: A.T.get('駅の位置').map(Number),
    starts: A.T.get('駅の分岐の始め').map(Number), ends: A.T.get('駅の分岐の終わり').map(Number),
    siding: A.T.get('駅の副本線の番号').map(Number), len: Number(A.T.get('列車長')), cars: Number(A.T.get('編成両数')),
    turnoutLen: Number(A.T.get('分岐の長さ')), crossing: Number(A.T.get('クロッシングの位置')),
}));
const inTurnout = pos => info.starts.some((s, i) => s - 1 <= pos && pos - info.len <= info.ends[i] + 1);

// 電車を「位置」に置いて、「速さ」で決まった時間だけ走らせる（毎フレーム速さを戻して、同じ速さで走らせる）
async function run(label, pos, speed, seconds, setup = () => {}) {
    await page.evaluate(([pos, speed, setupSrc]) => {
        const stops = A.T.get('駅の位置').map(Number);
        A.T.set('ATS状態', 0);
        A.T.set('次の駅番号', stops.findIndex(p => p > pos + 50) + 1);
        A.T.set('位置', pos);
        A.T.set('速度', speed);
        A.T.set('ノッチ', 0);
        A.T.set('ブレーキ率', 0);
        A.T.set('力行率', 0);
        (0, eval)(setupSrc)();
        clearInterval(A.hold);
        A.hold = setInterval(() => { A.T.set('速度', speed); A.T.set('ATS状態', 0); }, 10);
    }, [pos, speed, `(${setup})`]);
    const now = () => page.evaluate(() => ({t: scaffolding.vm.runtime.audioEngine.audioContext.currentTime,
        axles: Number(A.T.local('分岐器の音', 'ガタンの回数')), frames: A.frames}));
    const a = await now();
    await page.waitForTimeout(seconds * 1000);
    await page.evaluate(() => clearInterval(A.hold));
    const b = await now();
    return {label, speed, t0: a.t, t1: b.t, axles: b.axles - a.axles, fps: (b.frames - a.frames) / (b.t - a.t)};
}

const passIdx = info.kinds.findIndex((k, i) => i > 0 && k === '通過');   // 通過駅（まっすぐ通る）
const stopIdx = info.kinds.findIndex((k, i) => i > passIdx && k === '停車');   // その次の停車駅（曲がって 3番線へ）
const span = info.turnoutLen * info.crossing + info.len + 25;   // 駅の手前の分岐器を、最後の車軸がクロッシングをこえるまで
const secs = v => (span + 20) / (v / 3.6) + 0.5;
const sections = [];
sections.push(await run('直線（分岐器なし）100km/h', info.starts[passIdx] - 1400, 100, 10));
for (const v of [45, 100, 240]) {
    sections.push(await run(`${info.names[passIdx]}・まっすぐ ${v}km/h`, info.starts[passIdx] - 20, v, secs(v)));
}
sections.push(await run(`${info.names[stopIdx]}・曲がって3番線 45km/h`, info.starts[stopIdx] - 20, 45, secs(45),
    new Function(`A.T.get('駅の着く番線')[${stopIdx}] = ${info.siding[stopIdx]};`)));

const log = await page.evaluate(() => A.log);
const blocks = await page.evaluate(() => A.blocks);
await browser.close();

const dB = v => 20 * Math.log10(Math.max(v, 1e-6));
const peakIn = (t0, t1) => blocks.filter(([t]) => t >= t0 && t < t1).reduce((a, [, p]) => Math.max(a, p), 0);
const median = a => {
    const s = [...a].sort((x, y) => x - y);
    return s.length ? s[Math.floor(s.length / 2)] : NaN;
};
const isTurnout = e => e.sprite === '分岐器の音';
const bad = [];
const rows = [];
for (const s of sections) {
    const ev = log.filter(e => e.t >= s.t0 && e.t < s.t1);
    const tu = ev.filter(isTurnout), jo = ev.filter(e => e.sound === 'ジョイント');
    // 鳴ってから 0.12 秒のあいだの出力のピーク（「ガタン」「タタン」ごと）の中央
    const tuPeaks = tu.map(e => peakIn(e.t - 0.01, e.t + 0.12));
    const joPeaks = jo.map(e => peakIn(e.t - 0.01, e.t + 0.12));
    // 鳴る間かく: 最初の「ガタン」から最後の「ガタン」までの時間 ÷（鳴った回数 − 1）。車軸 1 本あたりも出す
    const span = tu.length > 1 ? tu[tu.length - 1].t - tu[0].t : NaN;
    const r = {label: s.label, speed: s.speed, turnout: tu.length, axles: s.axles, fps: s.fps,
        joint: jo.length, gain: tu.length ? median(tu.map(e => e.gain)) : NaN, jointGain: jo.length ? median(jo.map(e => e.gain)) : NaN,
        tuPeak: tuPeaks.length ? dB(median(tuPeaks)) : NaN, joPeak: joPeaks.length ? dB(median(joPeaks)) : NaN,
        gapMed: span / (tu.length - 1), gapAxle: span / (s.axles - 1),
        sounds: [...new Set(tu.map(e => e.sound.replace(/\d$/, '')))].join('・'),
        outside: tu.filter(e => !inTurnout(e.pos)).length};
    rows.push(r);
    if (r.outside) bad.push(`${s.label}: 分岐器の外で「ガタン」が ${r.outside} 回鳴った`);
}
const f = (v, d = 1) => Number.isFinite(v) ? v.toFixed(d) : '-';
console.log(`分岐器の「ガタン」の測定（${info.cars}両・車軸 ${info.cars * 4} 本・分岐器 1 つにすき間 2 か所 → 車軸 ${info.cars * 8} 回）`);
for (const r of rows) {
    console.log(`  ${r.label}: ガタン ${r.turnout} 回（車軸 ${r.axles}）${r.sounds ? `「${r.sounds}」` : ''}  ゲイン ${f(r.gain, 2)}  ` +
        `出力ピーク ${f(r.tuPeak)} dB  ／ ジョイント ${r.joint} 回${r.turnout ? '' : ` ゲイン ${f(r.jointGain, 2)} 出力ピーク ${f(r.joPeak)} dB`}  ／ ` +
        `鳴る間かく 平均 ${f(r.gapMed, 3)} 秒（車軸 1 本あたり ${f(r.gapAxle, 3)} 秒）  ${f(r.fps, 0)}fps`);
}
const [plain, s45, s100, s240, bent] = rows;
if (plain.turnout) bad.push(`分岐器のない直線で「ガタン」が ${plain.turnout} 回鳴った`);
if (!(plain.joint > 0)) bad.push('直線でジョイント音が鳴らなかった');
for (const r of [s45, s100, s240, bent]) {
    if (r.axles !== info.cars * 8) bad.push(`${r.label}: 車軸 ${r.axles} 回（${info.cars * 8} 回のはず）`);
}
const joPeak = plain.joPeak;   // 分岐器のない直線のジョイント（100km/h）
if (!(s100.tuPeak > joPeak + 3)) bad.push(`100km/h のガタン（${f(s100.tuPeak)} dB）がジョイント（${f(joPeak)} dB）より 3dB 以上大きくない`);
if (!(bent.tuPeak > s45.tuPeak + 1 && bent.gain > s45.gain)) bad.push(`曲がるとき（${f(bent.tuPeak)} dB）が、まっすぐ（${f(s45.tuPeak)} dB）より強くない`);
if (!bent.sounds.includes('曲がる') || s45.sounds.includes('曲がる')) bad.push('曲がるとき・まっすぐのときの音の種類がちがう');
if (!(s45.gapMed > s100.gapMed && s100.gapMed > s240.gapMed && s45.gapAxle > s100.gapAxle && s100.gapAxle > s240.gapAxle)) bad.push('速くなっても「ガタン」の間が短くならない');
console.log(`  ガタン（100km/h）はジョイントより ${f(s100.tuPeak - joPeak)} dB 大きい。曲がるとき（45km/h）はまっすぐ（45km/h）より ${f(bent.tuPeak - s45.tuPeak)} dB 大きい`);
console.log(`  鳴る間かくの平均: 45km/h ${f(s45.gapMed, 3)} 秒 → 100km/h ${f(s100.gapMed, 3)} 秒 → 240km/h ${f(s240.gapMed, 3)} 秒` +
    `（車軸 1 本あたり ${f(s45.gapAxle, 3)} → ${f(s100.gapAxle, 3)} → ${f(s240.gapAxle, 3)} 秒）`);
console.log('ページのエラー:', pageErrors.length ? pageErrors : 'なし');
fs.writeFileSync(path.join(BUILD, 'turnout-check.json'), JSON.stringify({info, rows, log}, null, 1));
if (bad.length || pageErrors.length) {
    for (const b of bad) console.log('  ✗ ' + b);
    console.log('測定失敗');
    process.exit(1);
}
console.log('測定OK');
