// キーを一切使わず、画面のボタンのタップ（クリック）だけで遊べるかを Chromium で確かめる。
//
//   node tools/tap_check.mjs              # 田原海岸線で、タイトル → 路線選択 → 発車 → 次の駅に停車 → 採点 まで
//   node tools/tap_check.mjs --route 1    # 路線を選ぶ
//   node tools/tap_check.mjs --shots      # とちゅうの画面を docs/screenshots に保存する
//
// 1. タイトルの「クレジット」→ 画面をタップしてもどる →「スタート」
// 2. 路線のボタンをタップ
// 3. 発車したら、ボットが決めたノッチになるように「力行」「ブレーキ」ボタンをタップして、次の駅に止める
// 4. 押し続けたときのノッチの動き（動きすぎないか）、「警笛」「非常」ボタン
// 5. 終点の手前まで位置を移して止め、結果画面の「タイトルにもどる」ボタン
import fs from 'fs';
import path from 'path';
import {createRequire} from 'module';
import {chromium} from 'playwright';
import {makeBot} from './driver_bot.mjs';

const require = createRequire(import.meta.url);
const Packager = require('@turbowarp/packager');
const ROOT = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const SB3 = path.join(ROOT, 'train-driver-3d.sb3');
const BUILD = path.join(ROOT, 'build');
const OUT = path.join(ROOT, 'docs', 'screenshots');
const args = process.argv.slice(2);
const opt = (n, d) => (args.includes(n) ? args[args.indexOf(n) + 1] : d);
const routeNo = Number(opt('--route', 3));
const saveShots = args.includes('--shots');
fs.mkdirSync(BUILD, {recursive: true});

// ボタンの位置（ステージの座標。タッチボタンスプライトの『ボタンを作る』と同じ）
const BTN = {
    スタート: [0, -149], クレジット: [196, 162], もどる: [0, -140],
    力行: [204, 4], ブレーキ: [204, -38], 警笛: [-204, 4], 非常: [-204, -38],
    路線: n => [-142 + (n - 1) % 3 * 142, -86 - Math.floor((n - 1) / 3) * 46],
};

const project = await Packager.loadProject(fs.readFileSync(SB3));
const packager = new Packager.Packager();
packager.project = project;
packager.options.autoplay = true;
const file = path.join(BUILD, 'tap-check.html');
fs.writeFileSync(file, (await packager.package()).data);

const browser = await chromium.launch();
const page = await browser.newPage({viewport: {width: 960, height: 720}});
const pageErrors = [];
page.on('pageerror', e => pageErrors.push(String(e)));
await page.goto('file://' + file);
await page.waitForFunction(() => window.scaffolding && scaffolding.vm.runtime.targets.length > 5, null, {timeout: 60000});
await page.evaluate(() => {
    const vm = scaffolding.vm;
    const st = vm.runtime.getTargetForStage();
    const v = n => Object.values(st.variables).find(x => x.name === n && x.type !== 'broadcast_msg');
    window.T = {
        get: n => v(n).value,
        set: (n, x) => { v(n).value = x; },
        local: (s, n) => Object.values(vm.runtime.targets.find(t => t.isOriginal && t.getName() === s).variables).find(x => x.name === n && x.type !== 'broadcast_msg'),
        costume: s => { const t = vm.runtime.targets.find(x => x.isOriginal && x.getName() === s); return t.visible ? t.getCostumes()[t.currentCostume].name : '(隠れている)'; },
        keys: 0,
        broadcasts: {},
    };
    // キーが 1 回も押されていないことを確かめるため、キーの入力を数える
    const origPost = vm.postIOData.bind(vm);
    vm.postIOData = (dev, data) => {
        if (dev === 'keyboard') T.keys++;
        return origPost(dev, data);
    };
    // どのメッセージが送られたかを数える（警笛など）
    const origStart = vm.runtime.startHats.bind(vm.runtime);
    vm.runtime.startHats = (op, fields, target) => {
        if (op === 'event_whenbroadcastreceived' && fields) T.broadcasts[fields.BROADCAST_OPTION] = (T.broadcasts[fields.BROADCAST_OPTION] || 0) + 1;
        return origStart(op, fields, target);
    };
});

const box = await page.locator('canvas').first().boundingBox();
const toPage = ([x, y]) => [box.x + (x + 240) * box.width / 480, box.y + (180 - y) * box.height / 360];
const G = n => page.evaluate(n => T.get(n), n);
const report = [];
const ok = (cond, msg) => {
    report.push(`${cond ? 'OK ' : 'NG '} ${msg}`);
    console.log(`${cond ? 'OK ' : 'NG '} ${msg}`);
    return cond;
};
async function tapAt(pos, ms = 70) {
    const [x, y] = toPage(pos);
    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.waitForTimeout(ms);
    await page.mouse.up();
}
const shot = async name => {
    if (saveShots) await page.locator('canvas').first().screenshot({path: path.join(OUT, name)});
};

// 1. タイトル → クレジット → スタート
await page.waitForFunction(() => T.get('場面') === 'タイトル');
await page.waitForTimeout(1200);
await shot('30-title-buttons.png');
await tapAt(BTN.クレジット);
await page.waitForTimeout(700);
ok(await page.evaluate(() => T.costume('画面')) === 'クレジット', '「クレジット」ボタンでクレジットの画面が出る');
await shot('33-credits.png');
await tapAt([0, 0]);
await page.waitForTimeout(700);
ok(await page.evaluate(() => T.costume('画面')) === 'タイトル' && await G('場面') === 'タイトル', '画面をタップするとタイトルにもどる');
await tapAt(BTN.スタート);
await page.waitForFunction(() => T.get('場面') === '路線選択', null, {timeout: 10000});
ok(true, '「スタート」ボタンで路線選択へ');
await page.waitForTimeout(800);
await shot('31-route-buttons.png');

// 2. 路線のボタン
await tapAt(BTN.路線(routeNo));
await page.waitForFunction(() => T.get('場面') === '停車中' || T.get('場面') === '運転中', null, {timeout: 30000});
const routeName = await G('路線名');
ok(Number(await G('路線番号')) === routeNo, `路線のボタンで「${routeName}」を選べる`);

// 3. ボタンのタップだけで運転して、次の駅に止める
const statics = await page.evaluate(() => ({
    駅の位置: T.get('駅の位置').slice(), 勾配表: T.get('勾配表').slice(), 停止位置の許容: T.get('停止位置の許容'),
    常用最大減速度: T.get('常用最大減速度'), 路線の最高速度: T.get('路線の最高速度'),
}));
const bot = makeBot({style: 'expert'});
const state = {creep: false};
await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 60000});
await shot('32-tap-driving.png');
const t0 = Date.now();
let taps = 0;
let maxSpeed = 0;
while (Date.now() - t0 < 300000) {
    const snap = await page.evaluate(() => ({
        場面: T.get('場面'), 速度: T.get('速度'), 位置: T.get('位置'), 現在の制限: T.get('現在の制限'), 次の駅番号: T.get('次の駅番号'),
        ノッチ: T.get('ノッチ'), 制限の開始: T.get('制限の開始').slice(), 制限の速度: T.get('制限の速度').slice(), 成績: T.get('成績').length,
        止まる位置: T.get('止まる位置'), アクシデントの段階: T.get('アクシデントの段階'), 非常停止中: T.get('非常停止中'),
    }));
    if (snap.場面 !== '運転中') break;
    maxSpeed = Math.max(maxSpeed, Number(snap.速度));
    const h = {num: n => Number(snap[n] ?? statics[n]), get: n => snap[n] ?? statics[n]};
    const want = bot.desiredNotch(h, state);
    const cur = Number(snap.ノッチ);
    if (want !== cur) {
        await tapAt(want > cur ? BTN.力行 : BTN.ブレーキ, 60);
        taps++;
        await page.waitForTimeout(40);
    } else {
        await page.waitForTimeout(80);
    }
}
const scene = await G('場面');
const results = await G('成績');
ok(scene === '停車中' && results.length === 1, `ボタン ${taps} 回のタップで発車から次の駅（${(await G('駅名'))[Number(await G('次の駅番号')) - 1]}）まで走り、停車して採点された` +
    `（最高 ${maxSpeed.toFixed(0)}km/h・${((Date.now() - t0) / 1000).toFixed(0)} 秒）: ${results[0]}`);
await page.waitForTimeout(1200);
await shot('34-tap-scored.png');

// 4. 押し続けたとき・警笛・非常
const n0 = Number(await G('ノッチ'));
let steps = 0, last = n0;
const [hx, hy] = toPage(BTN.力行);
await page.mouse.move(hx, hy);
await page.mouse.down();
const h0 = Date.now();
while (Date.now() - h0 < 2000) {
    const n = Number(await G('ノッチ'));
    if (n !== last) { steps += Math.abs(n - last); last = n; }
    await page.waitForTimeout(20);
}
await page.mouse.up();
await page.waitForTimeout(100);
const n1 = Number(await G('ノッチ'));
steps = n1 - n0;
ok(steps >= 4 && steps <= 7, `「力行」を 2 秒押し続けると ${steps} 段だけ動く（1 回で 1 段、0.6 秒後から 0.35 秒ごと。キーは同じ 2 秒で約 12 段）`);
for (let i = 0; i < 12 && Number(await G('ノッチ')) > -8; i++) {
    await tapAt(BTN.ブレーキ, 60);
    await page.waitForTimeout(60);
}
ok(Number(await G('ノッチ')) === -8, '「ブレーキ」を何回かタップして B8 にもどせる');
const horn0 = await page.evaluate(() => T.broadcasts['警笛'] || 0);
await tapAt(BTN.警笛);
await page.waitForTimeout(300);
ok(await page.evaluate(() => T.broadcasts['警笛'] || 0) === horn0 + 1, '「警笛」ボタンで警笛が 1 回鳴る');
await tapAt(BTN.非常);
await page.waitForTimeout(300);
ok(Number(await G('ノッチ')) === -9 && await G('ノッチ名') === 'EB', '「非常」ボタンで非常ブレーキ（EB）になる');
await tapAt(BTN.力行, 60);
await page.waitForTimeout(300);
ok(Number(await G('ノッチ')) === -8, 'EB から「力行」を 1 回タップで B8 にもどる');

// 5. 終点の手前に移して止め、結果画面の「タイトルにもどる」
await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 60000});
await page.evaluate(() => {
    const last = T.get('駅名').length;
    T.set('次の駅番号', last);
    const stop = Number(T.get('駅の位置')[last - 1]);
    T.set('位置', stop - 4.4);
    T.set('速度', 6.5);
    T.set('ノッチ', -2);
    T.set('ブレーキ率', 0.25);
    T.set('力行率', 0);
    T.set('時刻の秒', Number(T.get('駅の時刻秒')[last - 1]) - 3);
});
await page.waitForFunction(() => T.get('場面') === '結果', null, {timeout: 30000});
await page.waitForTimeout(1500);
await shot('35-result-buttons.png');
await tapAt(BTN.もどる);
await page.waitForFunction(() => T.get('場面') === 'タイトル', null, {timeout: 10000}).catch(() => {});
ok(await G('場面') === 'タイトル', '結果画面の「タイトルにもどる」ボタンでタイトルにもどる');
ok(await page.evaluate(() => T.keys) === 0, 'キーボードは 1 回も使っていない');
ok(pageErrors.length === 0, 'ページのエラーなし' + (pageErrors.length ? ': ' + pageErrors.join(' / ') : ''));
await browser.close();
const ng = report.filter(r => r.startsWith('NG'));
console.log(ng.length ? `\nタップ操作の確認: ${ng.length} 件 NG` : '\nタップ操作の確認: すべて OK');
process.exit(ng.length ? 1 : 0);
