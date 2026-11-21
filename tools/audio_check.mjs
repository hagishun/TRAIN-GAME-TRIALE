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
    window.A = {log: [], peaks: [], engine};
    // 出力の手前で音の大きさを測る
    const an = engine.audioContext.createAnalyser();
    an.fftSize = 2048;
    engine.inputNode.connect(an);
    const buf = new Float32Array(an.fftSize);
    setInterval(() => {
        an.getFloatTimeDomainData(buf);
        let p = 0;
        for (const v of buf) p = Math.max(p, Math.abs(v));
        A.peaks.push(p);
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
        targets: () => vm.runtime.targets.filter(t => t.sprite && ['効果音', 'モーター音', '走行音'].includes(t.sprite.name))
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
const log = await page.evaluate(() => A.log);
const peaks = await page.evaluate(() => A.peaks);
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
console.log('ページのエラー:', pageErrors.length ? pageErrors : 'なし');
fs.writeFileSync(path.join(BUILD, 'audio-check.json'), JSON.stringify({report, byName: Object.fromEntries(Object.entries(byName).map(([k, b]) => [k, {...b, roles: [...b.roles], ctx: [...b.ctx]}])), log}, null, 1));
