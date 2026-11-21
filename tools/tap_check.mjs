// キーボードを使わず、画面のタップ（タッチ）だけで遊べるかを Chromium で確かめる。
//
//   node tools/tap_check.mjs
//
// 1. タイトルをタップ → 番号ボタンで路線を選ぶ → 発車を待つ
// 2. 停車中に、ボタンの長押し（タッチしたまま）でノッチが何段動くかを測る。非常・警笛のボタンも押す
// 3. ▲力行・▼ブレーキのボタンだけで次の駅まで走り、停止位置に止めて採点されるまで
// 4. 終点の手前に移して（ここだけテレポート）、タップで止めて結果画面 → タップでタイトルへ戻る
// 判断のために VM の変数（速度・位置など）は読むが、操作はすべてタッチイベントで行う。
import fs from 'fs';
import path from 'path';
import {createRequire} from 'module';
import {chromium} from 'playwright';

const require = createRequire(import.meta.url);
const Packager = require('@turbowarp/packager');
const ROOT = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const SB3 = path.join(ROOT, 'train-driver-3d.sb3');
const BUILD = path.join(ROOT, 'build');
const ROUTE = Number(process.argv.includes('--route') ? process.argv[process.argv.indexOf('--route') + 1] : 3);
const SHOT = process.argv.includes('--shot') ? path.join(ROOT, 'docs', 'screenshots') : null;
fs.mkdirSync(BUILD, {recursive: true});

const project = await Packager.loadProject(fs.readFileSync(SB3));
const packager = new Packager.Packager();
packager.project = project;
packager.options.autoplay = true;
const file = path.join(BUILD, 'tap-check.html');
fs.writeFileSync(file, (await packager.package()).data);

const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width: 960, height: 720}, hasTouch: true, isMobile: false});
const page = await context.newPage();
const errors = [];
page.on('pageerror', e => errors.push(String(e)));
await page.goto('file://' + file);
await page.waitForFunction(() => window.scaffolding && scaffolding.vm.runtime.targets.length > 5, null, {timeout: 60000});
await page.evaluate(() => {
    const vm = scaffolding.vm;
    const stage = vm.runtime.getTargetForStage();
    const v = n => Object.values(stage.variables).find(x => x.name === n && x.type !== 'broadcast_msg');
    window.T = {
        get: n => v(n).value,
        set: (n, val) => { v(n).value = val; },
        clones: name => vm.runtime.targets.filter(t => !t.isOriginal && t.sprite.name === name && t.visible).length,
        heard: [],
    };
    const orig = vm.runtime.startHats.bind(vm.runtime);
    vm.runtime.startHats = (op, f, t) => {
        if (op === 'event_whenbroadcastreceived' && f && /^(タップ_|警笛$)/.test(f.BROADCAST_OPTION)) T.heard.push(f.BROADCAST_OPTION);
        return orig(op, f, t);
    };
});
const get = n => page.evaluate(n => T.get(n), n);
const num = async n => Number(await get(n));
const box = await page.locator('canvas').first().boundingBox();
// ステージの座標（中心が 0,0、右が＋x、上が＋y）→ ページの座標
const at = (x, y) => ({x: box.x + (x + 240) / 480 * box.width, y: box.y + (180 - y) / 360 * box.height});
const cdp = await context.newCDPSession(page);
const touch = async (type, p) => cdp.send('Input.dispatchTouchEvent', {type, touchPoints: type === 'touchEnd' ? [] : [{x: p.x, y: p.y}]});
async function tap(x, y, ms = 90) {
    const p = at(x, y);
    await touch('touchStart', p);
    await page.waitForTimeout(ms);
    await touch('touchEnd', p);
    await page.waitForTimeout(60);
}
async function hold(x, y, ms) {
    const p = at(x, y);
    await touch('touchStart', p);
    await page.waitForTimeout(ms);
    await touch('touchEnd', p);
    await page.waitForTimeout(150);
}
const BTN = {力行: [182, 32], ブレーキ: [182, -26], 警笛: [-182, 32], 非常: [-182, -26]};
const press = role => tap(...BTN[role]);
const report = {};
const check = (name, ok, detail = '') => {
    report[name] = ok;
    console.log(`${ok ? 'OK ' : 'NG '} ${name}${detail ? '  ' + detail : ''}`);
};

// ---- 1. タイトル → 路線選択 → 発車待ち
await page.waitForFunction(() => T.get('場面') === 'タイトル', null, {timeout: 30000});
await page.evaluate(() => T.set('アクシデント_起きやすさ', 0));   // 確かめる流れが毎回同じになるように
await page.waitForTimeout(800);
await tap(0, 0);
await page.waitForFunction(() => T.get('場面') === '路線選択', null, {timeout: 10000});
await page.waitForTimeout(500);
const menuButtons = await page.evaluate(() => T.clones('番号ボタン'));
check('路線選択に番号ボタンが出る', menuButtons === 3, `${menuButtons} 個`);
await tap((ROUTE - 2) * 66, -95);
await page.waitForFunction(() => T.get('場面') === '停車中', null, {timeout: 30000});
check('番号ボタンで路線を選べる', Number(await get('路線番号')) === ROUTE, String(await get('路線名')));
await page.waitForTimeout(500);
const tapButtons = await page.evaluate(() => T.clones('タップ操作'));
check('運転画面にタップ用ボタンが 4 つ出る', tapButtons === 4, `${tapButtons} 個`);

// ---- 2. 長押し・非常・警笛（停車中なので減点はない）
let n0 = await num('ノッチ');
await hold(...BTN['力行'], 1500);
let n1 = await num('ノッチ');
check('▲力行を 1.5 秒長押し → 少しずつ動く（動きすぎない）', n1 - n0 >= 4 && n1 - n0 <= 6, `${n0} → ${n1}（${n1 - n0} 段）`);
await press('ブレーキ');
const n2 = await num('ノッチ');
check('▼ブレーキを 1 回タップ → 1 段だけ動く', n2 === n1 - 1, `${n1} → ${n2}`);
await press('非常');
check('非常ボタン → EB', await get('ノッチ名') === 'EB', await get('ノッチ名'));
await press('警笛');
await page.waitForTimeout(200);
check('警笛ボタン → 警笛が鳴る', (await page.evaluate(() => T.heard)).includes('警笛'));
for (let i = 0; i < 1; i++) await press('力行');
check('EB から ▲力行で B8 に戻る', await get('ノッチ名') === 'B8', await get('ノッチ名'));

// ---- 3. タップだけで次の駅まで
await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 60000});
const stopIndex = await num('次の駅番号');
const stopPos = Number((await get('駅の位置'))[stopIndex - 1]);
const stationName = (await get('駅名'))[stopIndex - 1];
let taps = 0;
let shotTaken = false;
const t0 = Date.now();
async function driveToStop(maxMs) {
    const start = Date.now();
    while (Date.now() - start < maxMs) {
        const s = await page.evaluate(() => ({
            v: Number(T.get('速度')), pos: Number(T.get('位置')), lim: Number(T.get('現在の制限')), notch: Number(T.get('ノッチ')),
            scene: T.get('場面'), idx: Number(T.get('次の駅番号')), starts: T.get('制限の開始'), speeds: T.get('制限の速度'),
            stops: T.get('駅の位置'),
        }));
        if (s.scene !== '運転中') return s.scene;
        const d = Number(s.stops[s.idx - 1]) - s.pos;
        let target = s.lim - 6;
        for (let i = 0; i < s.starts.length; i++) {
            const st = Number(s.starts[i]);
            if (st > s.pos) target = Math.min(target, Math.sqrt(Math.max(0, (Number(s.speeds[i]) - 6) ** 2 + 2 * 2.6 * 3.6 * (st - s.pos - s.v))));
        }
        let want;
        const stopCurve = Math.sqrt(Math.max(0, 2 * 2.6 * 3.6 * (d - s.v / 3.6 * 1.5 - 1)));
        if (stopCurve < s.v + 3 || d < 60) {
            // 停止位置に向けてブレーキ（必要な減速度からノッチを選ぶ。止まる直前は緩める）
            if (s.v < 0.05) want = d > 1.5 ? 2 : -8;
            else {
                const req = s.v * s.v / (7.2 * Math.max(0.05, d - s.v / 3.6 * 0.6));
                want = -Math.min(8, Math.max(1, Math.round(req / 0.675 + 0.3)));
                if (s.v < 6 && req < 0.9) want = d > 2 ? 0 : -1;
                if (s.v < 3 && d > 4) want = 1;
            }
        } else {
            target = Math.min(target, stopCurve);
            want = s.v < target - 8 ? 5 : s.v < target - 1 ? 2 : s.v > target + 3 ? -3 : 0;
        }
        if (want > s.notch) { await press('力行'); taps++; }
        else if (want < s.notch) { await press('ブレーキ'); taps++; }
        else await page.waitForTimeout(80);
        if (SHOT && !shotTaken && s.v > 120) {
            shotTaken = true;
            await page.locator('canvas').first().screenshot({path: path.join(SHOT, '15-tap-buttons.png')});
        }
    }
    return 'timeout';
}
const scene = await driveToStop(8 * 60 * 1000);
const results = await get('成績');
check(`タップだけで発車から ${stationName} に停車・採点まで`, scene === '停車中' && results.length === 1,
    `${results[0] || '採点なし'}（タップ ${taps} 回、${((Date.now() - t0) / 1000).toFixed(0)} 秒）`);

// ---- 4. 終点 → 結果画面 → タイトル（終点の手前に移す）
await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 60000});
await page.evaluate(() => {
    const names = T.get('駅名');
    const kinds = T.get('駅の種別');
    let last = names.length;
    while (kinds[last - 1] !== '停車') last--;
    T.set('次の駅番号', last);
    const stop = Number(T.get('駅の位置')[last - 1]);
    T.set('位置', stop - 300);
    T.set('速度', 40);
    T.set('時刻の秒', Number(T.get('駅の時刻秒')[last - 1]) - 30);
});
const scene2 = await driveToStop(3 * 60 * 1000);
await page.waitForFunction(() => T.get('場面') === '結果', null, {timeout: 30000});
check('タップで終点に止めて結果画面へ', scene2 === '停車中' || scene2 === '結果', String(await get('総合評価')));
await page.waitForTimeout(1500);
await tap(0, -150);
await page.waitForFunction(() => T.get('場面') === 'タイトル', null, {timeout: 10000}).catch(() => {});
check('結果画面をタップしてタイトルへ戻る', await get('場面') === 'タイトル');
check('ページのエラーなし', errors.length === 0, errors.join(' / '));
await browser.close();
const ng = Object.entries(report).filter(([, ok]) => !ok);
console.log(ng.length ? `タップ操作の確認: 失敗 ${ng.length} 件` : 'タップ操作の確認: すべて OK');
process.exit(ng.length ? 1 : 0);
