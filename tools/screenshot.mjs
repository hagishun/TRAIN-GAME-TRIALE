// TurboWarp Packager で .sb3 を HTML にし、Chromium（Playwright）で開いてスクリーンショットを撮る。
// あわせて、素の Scratch と同じ「インタプリタ」動作と、TurboWarp の「コンパイラ」動作のフレームレートを測る。
//
//   node tools/screenshot.mjs            # docs/screenshots/*.png を作る
//   node tools/screenshot.mjs --fps-only # フレームレートだけ測る
//   node tools/screenshot.mjs --only airport,curves,accidents   # 一部の場面だけ撮る（main / airport / curves / accidents）
//   （タッチボタン・クレジットの画面は node tools/tap_check.mjs --shots で撮る）
import fs from 'fs';
import path from 'path';
import {createRequire} from 'module';
import {chromium} from 'playwright';

const require = createRequire(import.meta.url);
const Packager = require('@turbowarp/packager');
const ROOT = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const SB3 = path.join(ROOT, 'train-driver-3d.sb3');
const OUT = path.join(ROOT, 'docs', 'screenshots');
const BUILD = path.join(ROOT, 'build');
const fpsOnly = process.argv.includes('--fps-only');
const onlyArg = process.argv.includes('--only') ? process.argv[process.argv.indexOf('--only') + 1].split(',') : null;
const want = name => !onlyArg || onlyArg.includes(name);
fs.mkdirSync(OUT, {recursive: true});
fs.mkdirSync(BUILD, {recursive: true});

async function pack(compiler) {
    const project = await Packager.loadProject(fs.readFileSync(SB3));
    const p = new Packager.Packager();
    p.project = project;
    p.options.autoplay = true;
    p.options.compiler.enabled = compiler;
    p.options.app.windowTitle = '信町高速鉄道 3D運転士';
    const result = await p.package();
    const file = path.join(BUILD, compiler ? 'game.html' : 'game-interpreter.html');
    fs.writeFileSync(file, result.data);
    return file;
}

// ページの中で使う関数（VM の変数を読み書きする・ボットで運転する）
const PAGE_HELPERS = () => {
    const vm = window.scaffolding.vm;
    const stage = vm.runtime.getTargetForStage();
    const v = n => Object.values(stage.variables).find(x => x.name === n && x.type !== 'broadcast_msg');
    window.T = {
        vm,
        get: n => v(n).value,
        set: (n, val) => { v(n).value = val; },
        sprite: n => vm.runtime.targets.find(t => t.isOriginal && t.getName() === n),
        local: (s, n) => Object.values(window.T.sprite(s).variables).find(x => x.name === n && x.type !== 'broadcast_msg'),
        key: (k, down) => vm.postIOData('keyboard', {key: k, isDown: down}),
        steps: 0,
        stepMs: 0,
        botOn: false,
    };
    const orig = vm.runtime._step.bind(vm.runtime);
    vm.runtime._step = function () {
        const t0 = performance.now();
        orig();
        window.T.steps++;
        window.T.stepMs += performance.now() - t0;
    };
    // かんたんな自動運転（ノッチを目標に近づける）
    let held = null;
    setInterval(() => {
        if (!window.T.botOn) return;
        if (held) { window.T.key(held, false); held = null; return; }
        const T = window.T;
        if (T.get('場面') !== '運転中') return;
        const vel = Number(T.get('速度')), pos = Number(T.get('位置'));
        const stop = Number(T.get('駅の位置')[Number(T.get('次の駅番号')) - 1]);
        const d = stop - pos;
        let target = Number(T.get('現在の制限')) - 2;
        const starts = T.get('制限の開始'), sp = T.get('制限の速度');
        for (let i = 0; i < starts.length; i++) {
            const s = Number(starts[i]);
            if (s > pos) target = Math.min(target, Math.sqrt(Math.max(0, (sp[i] - 2) ** 2 + 18 * (s - pos))));
        }
        target = Math.min(target, Math.sqrt(Math.max(0, 18 * (d - 10))));
        let want = vel < target - 4 ? 5 : vel < target ? 1 : vel > target + 2 ? -4 : 0;
        if (d < 40) want = vel > 0 ? -2 : -8;
        const cur = Number(T.get('ノッチ'));
        if (want > cur) held = 'ArrowUp';
        else if (want < cur) held = 'ArrowDown';
        if (held) T.key(held, true);
    }, 40);
};

async function openGame(browser, file) {
    const page = await browser.newPage({viewport: {width: 960, height: 720}, deviceScaleFactor: 1});
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    page.on('console', m => {
        if (m.type() === 'error') errors.push(m.text());
    });
    await page.goto('file://' + file);
    await page.waitForFunction(() => window.scaffolding && window.scaffolding.vm && window.scaffolding.vm.runtime.targets.length > 5,
        null, {timeout: 60000});
    await page.evaluate(PAGE_HELPERS);
    await page.waitForFunction(() => T.get('場面') === 'タイトル', null, {timeout: 30000});
    // ふつうの場面ではアクシデントを起こさない（撮りたいときだけ injectAccident で起こす）
    await page.evaluate(() => T.set('アクシデント_起きやすさ', 0));
    return {page, errors};
}

// アクシデントを、いまの位置のすぐ先で起こす
async function injectAccident(page, kind) {
    await page.evaluate(kind => {
        const t = T.sprite('アクシデント');
        const L = n => Object.values(t.variables).find(v => v.name === n && v.type === 'list');
        L('予定の種類').value = [kind];
        L('予定の位置').value = [Number(T.get('位置')) + 30];
    }, kind);
    await page.waitForFunction(() => T.get('アクシデントの段階') === '知らせた', null, {timeout: 20000});
}

// 飛行機を置く（[位置, 高さ, 状態, 速さ, 会社] …）
async function placePlanes(page, planes) {
    await page.evaluate(planes => {
        const t = T.sprite('飛行機');
        const L = n => Object.values(t.variables).find(v => v.name === n && v.type === 'list');
        for (const n of ['飛行機の位置', '飛行機の横', '飛行機の高さ', '飛行機の向き', '飛行機の角度', '飛行機の会社']) T.get(n).length = 0;
        for (const n of ['飛行機の状態', '飛行機の速さ', '飛行機の音済']) L(n).value.length = 0;
        for (const [pos, h, st, v, company] of planes) {
            T.get('飛行機の位置').push(pos); T.get('飛行機の横').push(Number(T.get('滑走路の横'))); T.get('飛行機の高さ').push(h);
            T.get('飛行機の向き').push(-1); T.get('飛行機の角度').push(st === '上昇' ? 10 : st === '進入' ? 3 : 0);
            T.get('飛行機の会社').push(company);
            L('飛行機の状態').value.push(st); L('飛行機の速さ').value.push(v); L('飛行機の音済').value.push(1);
        }
        T.local('飛行機', '着陸を見せた').value = 1;
        T.set('飛行機_出現率', 0);
    }, planes);
}

// Scratch はキーをフレームごとに調べるので、少し長めに押す
async function pressKey(page, k) {
    await page.keyboard.down(k);
    await page.waitForTimeout(150);
    await page.keyboard.up(k);
}

async function startRoute(page, n) {
    await page.waitForTimeout(800);
    await pressKey(page, 'Enter');
    await page.waitForFunction(() => T.get('場面') === '路線選択');
    await page.waitForTimeout(500);
    await pressKey(page, String(n));
    await page.waitForFunction(() => T.get('場面') === '停車中' || T.get('場面') === '運転中', null, {timeout: 30000});
}

const shot = async (page, name) => {
    await page.locator('canvas').first().screenshot({path: path.join(OUT, name)}).catch(async () => {
        await page.screenshot({path: path.join(OUT, name)});
    });
    console.log('  saved', name);
};

// 位置を移して（テレポート）見せたい場面を作る
async function teleport(page, {pos, speed, notch, next, early = 30}) {
    await page.evaluate(({pos, speed, notch, next, early}) => {
        if (next !== undefined) T.set('次の駅番号', next);
        T.set('位置', pos);
        T.set('速度', speed);
        T.set('場面', '運転中');
        T.set('ドア', '閉');
        T.set('ノッチ', notch);
        T.set('ブレーキ率', notch < 0 ? -notch / 8 : 0);
        T.set('力行率', notch > 0 ? notch / 5 : 0);
        T.set('ノッチ名', T.get('ノッチの名前')[6 - notch - 1]);
        T.local('運転', 'ジョイント番号').value = Math.floor(pos / 25);
        // 時計も、次の駅の定刻の少し前に合わせる
        T.set('時刻の秒', Number(T.get('駅の時刻秒')[Number(T.get('次の駅番号')) - 1]) - early);
        for (const n of ['区間の減点', 'ATS警報回数', 'ATS非常回数', '非常ブレーキ回数', '再停車回数', 'ATS状態']) T.set(n, 0);
        T.set('案内', '');
    }, {pos, speed, notch, next, early});
}

async function measureFps(browser, compiler) {
    const file = await pack(compiler);
    const {page, errors} = await openGame(browser, file);
    await startRoute(page, 1);
    await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 30000});
    await page.evaluate(() => { T.botOn = true; });
    await page.waitForTimeout(4000);
    // 駅の手前（ホームが見える）に移して、重い場面を測る
    await teleport(page, {pos: 31000 - 420, speed: 150, notch: -3, next: 9});
    await page.evaluate(() => { T.steps = 0; T.stepMs = 0; });
    const t0 = Date.now();
    await page.waitForTimeout(8000);
    const r = await page.evaluate(() => ({steps: T.steps, stepMs: T.stepMs}));
    const sec = (Date.now() - t0) / 1000;
    const gl = await page.evaluate(() => {
        const c = document.createElement('canvas').getContext('webgl');
        const ext = c && c.getExtension('WEBGL_debug_renderer_info');
        return ext ? c.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown';
    });
    await page.close();
    return {mode: compiler ? 'コンパイラ（TurboWarp）' : 'インタプリタ（素の Scratch 相当）', fps: r.steps / sec,
        msPerFrame: r.stepMs / Math.max(1, r.steps), gl, errors};
}

const browser = await chromium.launch({args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist']});
try {
    const file = fpsOnly ? null : await pack(true);
    if (!fpsOnly && want('main')) {
        // 信町本線（夕方の街）
        let {page, errors} = await openGame(browser, file);
        await page.waitForTimeout(1500);
        await shot(page, '01-title.png');
        await pressKey(page, 'Enter');
        await page.waitForFunction(() => T.get('場面') === '路線選択');
        await page.waitForTimeout(800);
        await shot(page, '02-route-select.png');
        await pressKey(page, '1');
        await page.waitForFunction(() => T.get('場面') === '停車中', null, {timeout: 30000});
        await page.waitForTimeout(2500);
        await shot(page, '03-shinmachi-departure.png');
        await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 30000});
        await page.evaluate(() => { T.botOn = true; });
        await page.waitForTimeout(6000);
        await teleport(page, {pos: 4650, speed: 245, notch: 0, next: 3});
        await page.waitForTimeout(1500);
        await shot(page, '04-shinmachi-curve.png');
        await teleport(page, {pos: 31000 - 150, speed: 42, notch: -3, next: 9, early: 22});
        await page.evaluate(() => { T.botOn = false; });
        await page.waitForTimeout(1200);
        await shot(page, '05-takata-approach.png');
        // 対向列車を出す
        // 通過駅（中ヶ野宮）を 300km/h で通過
        await teleport(page, {pos: 39500 - 230, speed: 300, notch: 0, next: 11, early: 60});
        await page.waitForTimeout(700);
        await shot(page, '14-passing-station.png');
        await teleport(page, {pos: 34500, speed: 300, notch: 0, next: 11, early: 120});
        await page.evaluate(() => {
            T.set('対向列車_出現率', 100);
            T.local('対向列車', '有無').value = 0;
            T.local('対向列車', '抽選タイマー').value = 999;
        });
        await page.waitForTimeout(300);
        await page.evaluate(() => {
            T.local('対向列車', '先頭位置').value = Number(T.get('位置')) + 900;
            T.local('対向列車', '列車の速さ').value = 70;
        });
        await page.waitForFunction(() => Number(T.local('対向列車', '先頭位置').value) - Number(T.get('位置')) < 260, null, {timeout: 20000});
        await shot(page, '06-opposing-train.png');
        await page.waitForFunction(() => Number(T.local('対向列車', '先頭位置').value) - Number(T.get('位置')) < -8, null, {timeout: 20000});
        await shot(page, '07-passing.png');
        // 停車して採点
        await teleport(page, {pos: 42300 - 4.4, speed: 6.5, notch: -2, next: 11, early: 3});
        await page.waitForFunction(() => T.get('場面') === '停車中', null, {timeout: 20000});
        await page.waitForTimeout(900);
        await shot(page, '08-station-score.png');
        // 終点 → 結果画面
        await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 30000});
        await teleport(page, {pos: 61600 - 4.4, speed: 6.5, notch: -2, next: 13, early: 2});
        await page.waitForFunction(() => T.get('場面') === '結果' || document.title === 'x', null, {timeout: 30000});
        await page.waitForTimeout(1500);
        await shot(page, '09-result.png');
        console.log('  page errors:', errors.length ? errors : 'なし');
        await page.close();

        // 神社線（霧の山あい）
        ({page, errors} = await openGame(browser, file));
        await startRoute(page, 2);
        await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 30000});
        await teleport(page, {pos: 2950, speed: 185, notch: 0, next: 2, early: 200});
        await page.waitForTimeout(1500);
        await shot(page, '10-jinja-fog-curve.png');
        await teleport(page, {pos: 10400 - 140, speed: 38, notch: -3, next: 2, early: 20});
        await page.waitForTimeout(1500);
        await shot(page, '11-jinja-seimon-approach.png');
        console.log('  page errors:', errors.length ? errors : 'なし');
        await page.close();

        // 田原海岸線（昼の海沿い）
        ({page, errors} = await openGame(browser, file));
        await startRoute(page, 3);
        await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 30000});
        await teleport(page, {pos: 8000, speed: 320, notch: 0, next: 3, early: 70});
        await page.waitForTimeout(1500);
        await shot(page, '12-tahara-seaside.png');
        await teleport(page, {pos: 21500 - 120, speed: 36, notch: -2, next: 4, early: 20});
        await page.waitForTimeout(1500);
        await shot(page, '13-tahara-airport-approach.png');
        console.log('  page errors:', errors.length ? errors : 'なし');
        await page.close();
    }
    if (!fpsOnly && want('airport')) {
        // 信町空港: 近づくと着陸してくる飛行機、駅から見たエプロン・駐機中の飛行機・滑走路
        const {page, errors} = await openGame(browser, file);
        await startRoute(page, 3);
        await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 30000});
        await teleport(page, {pos: 20480, speed: 110, notch: -2, next: 4, early: 40});
        await placePlanes(page, [[22150, 0, '着陸滑走', 55, '信町エア'], [23600, 60, '進入', 70, 'うみかぜ航空']]);
        await page.waitForTimeout(1200);
        await shot(page, '40-airport-approach.png');
        await teleport(page, {pos: 21497, speed: 0, notch: -8, next: 4, early: 0});
        await placePlanes(page, [[22350, 0, '離陸滑走', 45, 'うみかぜ航空'], [23300, 45, '進入', 70, '信町エア']]);
        await page.waitForTimeout(1500);
        await shot(page, '41-airport-station.png');
        console.log('  page errors:', errors.length ? errors : 'なし');
        await page.close();
    }
    if (!fpsOnly && want('curves')) {
        // カーブの入り口（奥の線路が曲がって見える）と途中（線路も景色も曲がる・流れる）
        for (const [route, entry, middle, next, label] of [[1, 4720, 5420, 3, 'shinmachi'], [2, 6330, 6900, 2, 'jinja'],
            [3, 23700, 24300, 6, 'tahara']]) {
            const {page, errors} = await openGame(browser, file);
            await startRoute(page, route);
            await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 30000});
            const n = {1: 50, 2: 52, 3: 54}[route];
            await teleport(page, {pos: entry, speed: route === 2 ? 160 : 230, notch: 0, next, early: 120});
            await page.waitForTimeout(1200);
            await shot(page, `${n}-curve-${label}-entry.png`);
            await teleport(page, {pos: middle, speed: route === 2 ? 160 : 230, notch: 0, next, early: 120});
            await page.waitForTimeout(1200);
            await shot(page, `${n + 1}-curve-${label}-middle.png`);
            console.log('  page errors:', errors.length ? errors : 'なし');
            await page.close();
        }
    }
    if (!fpsOnly && want('accidents')) {
        // 代表的なアクシデント
        const scenes = [
            [2, 2000, 2, '倒木', 40, '60-accident-fallen-tree.png'],
            [2, 2000, 2, '動物', 35, '61-accident-deer.png'],
            [1, 16000, 9, '踏切', 70, '62-accident-level-crossing.png'],
            [1, 46000, 13, '信号故障', 60, '63-accident-signal.png'],
            [1, 16000, 9, '踏切', 1100, '64-accident-warning-light.png'],
            [3, 8000, 3, '大雨', null, '65-accident-heavy-rain.png'],
            [3, 5000, 3, '強風', null, '66-accident-strong-wind.png'],
        ];
        for (const [route, pos, next, kind, dist, name] of scenes) {
            const {page, errors} = await openGame(browser, file);
            await startRoute(page, route);
            await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 30000});
            await teleport(page, {pos, speed: 180, notch: 0, next, early: 200});
            await page.waitForTimeout(300);
            await injectAccident(page, kind);
            if (dist !== null) {
                await page.evaluate(d => {
                    T.set('位置', Number(T.get('障害物の位置')) - d);
                    T.set('速度', d > 500 ? 150 : 0);
                    T.set('ノッチ', d > 500 ? 0 : -8);
                }, dist);
                await page.waitForTimeout(dist > 500 ? 600 : 1200);
            } else {
                await page.waitForTimeout(1500);
            }
            // 点滅している「異常」表示灯と障害物の赤い光が、どちらも点いている瞬間に撮る
            await page.waitForFunction(() => {
                const t = T.vm.runtime.ioDevices.clock.projectTimer() % 2;
                return t > 0.05 && t < 0.2;
            }, null, {timeout: 10000, polling: 10});
            await page.waitForTimeout(60);
            await shot(page, name);
            console.log('  page errors:', errors.length ? errors : 'なし');
            await page.close();
        }
    }
    for (const compiler of want('fps') || fpsOnly ? [true, false] : []) {
        const r = await measureFps(browser, compiler);
        console.log(`  ${r.mode}: ${r.fps.toFixed(1)} fps（1フレームの処理 ${r.msPerFrame.toFixed(1)}ms） GPU=${r.gl}  errors=${r.errors.length ? r.errors : 'なし'}`);
    }
} finally {
    await browser.close();
}
