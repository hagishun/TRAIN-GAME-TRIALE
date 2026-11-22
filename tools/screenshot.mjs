// TurboWarp Packager で .sb3 を HTML にし、Chromium（Playwright）で開いてスクリーンショットを撮る。
// あわせて、素の Scratch と同じ「インタプリタ」動作と、TurboWarp の「コンパイラ」動作のフレームレートを測る。
//
//   node tools/screenshot.mjs            # docs/screenshots/*.png を作る
//   node tools/screenshot.mjs --fps-only # フレームレートだけ測る
//   node tools/screenshot.mjs --airport  # 路線選択とエアポート特快の写真（02・40〜45）だけ撮る
//   node tools/screenshot.mjs --viaduct  # 高田から先の高架の写真（50〜61）と、高架の上のフレームレートだけ
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
const airportOnly = process.argv.includes('--airport');
const viaductOnly = process.argv.includes('--viaduct');
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
    const v = n => Object.values(stage.variables).find(x => x.name === n);
    window.T = {
        vm,
        get: n => v(n).value,
        set: (n, val) => { v(n).value = val; },
        sprite: n => vm.runtime.targets.find(t => t.isOriginal && t.getName() === n),
        local: (s, n) => Object.values(window.T.sprite(s).variables).find(x => x.name === n),
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
    // でたらめなアクシデントは起こさない（撮りたい場面が変わらないように。アクシデントの写真は決めて起こす）
    await page.evaluate(() => T.set('アクシデント_起きやすさ', 0));
    return {page, errors};
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

async function measureFps(browser, compiler, viaduct = false) {
    const file = await pack(compiler);
    const {page, errors} = await openGame(browser, file);
    await startRoute(page, viaduct ? 3 : 1);
    await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 30000});
    await page.evaluate(() => { T.botOn = true; });
    await page.waitForTimeout(4000);
    if (viaduct) {
        // 田原海岸線の高架の上（カーブ・側壁・下に見える街）を走る場面
        await teleport(page, {pos: 1300, speed: 160, notch: 0, next: 2, early: 120});
    } else {
        // 駅の手前（ホームが見える）に移して、重い場面を測る
        await teleport(page, {pos: 31000 - 420, speed: 150, notch: -3, next: 9});
    }
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
    return {mode: (compiler ? 'コンパイラ（TurboWarp）' : 'インタプリタ（素の Scratch 相当）') + (viaduct ? '・高架の上' : ''), fps: r.steps / sec,
        msPerFrame: r.stepMs / Math.max(1, r.steps), gl, errors};
}

// エアポート特快（信町本線 → 高田 → 田原海岸線 → 田原京、10両）
async function shootAirportExpress(browser, file) {
    const {page, errors} = await openGame(browser, file);
    await page.waitForTimeout(800);
    await pressKey(page, 'Enter');
    await page.waitForFunction(() => T.get('場面') === '路線選択');
    await page.waitForTimeout(800);
    await shot(page, '02-route-select.png');
    await pressKey(page, '4');
    await page.waitForFunction(() => T.get('場面') === '停車中', null, {timeout: 30000});
    await page.waitForTimeout(2500);
    await shot(page, '40-airport-departure.png');
    const st = await page.evaluate(() => Object.fromEntries(T.get('駅名').map((n, i) => [n, [i + 1, Number(T.get('駅の位置')[i])]])));
    await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 30000});
    // 高田の手前（信町本線の夕方の街。10両用の長いホームと停止位置目標「10」）
    await teleport(page, {pos: st['高田'][1] - 170, speed: 45, notch: -3, next: st['高田'][0], early: 22});
    await page.waitForTimeout(1200);
    await shot(page, '41-airport-before-takata.png');
    // 高田から先（田原海岸線の昼の海沿いに切り替わる）
    await teleport(page, {pos: st['高田'][1] + 7500, speed: 320, notch: 0, next: st['信町空港'][0], early: 70});
    await page.waitForTimeout(1500);
    await shot(page, '42-airport-after-takata.png');
    // 信町空港の手前（空港のターミナル・管制塔・駐機中の飛行機）
    await teleport(page, {pos: st['信町空港'][1] - 120, speed: 36, notch: -2, next: st['信町空港'][0], early: 20});
    await page.waitForTimeout(1500);
    await shot(page, '43-airport-shinmachi-airport.png');
    // 信町空港駅に止まっているところへ、後ろから追い越して着陸してくる飛行機
    await teleport(page, {pos: st['信町空港'][1], speed: 0, notch: -8, next: st['信町空港'][0], early: 60});
    await page.evaluate(() => {
        T.local('景色', '飛行機の有無').value = 0;
        T.local('景色', '飛行機_最初の着陸済').value = 0;
    });
    await page.waitForFunction(() => Number(T.local('景色', '飛行機の有無').value) === 1 &&
        Number(T.local('景色', '飛行機の前後').value) - Number(T.get('位置')) > 380, null, {timeout: 30000});
    await shot(page, '44-airport-landing.png');
    // 終点の田原京 → 結果画面
    await teleport(page, {pos: st['田原京'][1] - 4.4, speed: 6.5, notch: -2, next: st['田原京'][0], early: 2});
    await page.waitForFunction(() => T.get('場面') === '結果', null, {timeout: 30000});
    await page.waitForTimeout(1500);
    await shot(page, '45-airport-result.png');
    console.log('  page errors:', errors.length ? errors : 'なし');
    await page.close();
}

// 高田から先の高架（エアポート特快と田原海岸線）: 上り坂 → 高架の上 → 下り坂 → 景色の変わり目の前後 → 海沿い
async function shootViaduct(browser, file) {
    for (const [route, prefix, first, speeds] of [
        [4, 'airport', 50, {up: 70, top: 200, down: 200, sw: 170, sea: 220}],
        [3, 'tahara', 56, {up: 60, top: 160, down: 120, sw: 90, sea: 50}],
    ]) {
        const {page, errors} = await openGame(browser, file);
        await startRoute(page, route);
        await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 30000});
        const info = await page.evaluate(() => {
            const loc = n => T.local('路線データ', n).value;
            const zones = loc('景色の切り替え位置').map(Number);
            return {
                start: Number(T.get('高架の開始')[0]), end: Number(T.get('高架の終了')[0]), ramp: Number(T.get('高架の坂')[0]),
                boundary: zones[zones.length - 1] - Number(loc('景色を切り替える手前')),
                stations: T.get('駅の位置').map(Number), kinds: T.get('駅の種別'), times: T.get('駅の時刻秒').map(Number),
                dwell: Number(T.get('停車時間')),
            };
        });
        const stopIdx = info.stations.map((_, i) => i).filter(i => info.kinds[i] === '停車');
        // その位置まで走ってきたところを撮る（少し手前に移して、位置を過ぎるのを待つ）。
        // 時計は、前の停車駅を発車してから平均 120km/h で走ってきたくらいにする
        const at = async (pos, speed, notch, name) => {
            const next = stopIdx.find(i => info.stations[i] > pos + 30);
            const prev = [...stopIdx].reverse().find(i => info.stations[i] < pos);
            const dep = info.times[prev] + (prev === 0 ? 0 : info.dwell);
            const now = dep + 8 + (pos - info.stations[prev]) / (120 / 3.6);
            await teleport(page, {pos: pos - speed / 3.6 * 1.2, speed, notch, next: next + 1, early: info.times[next] - now});
            await page.evaluate(p => {
                T.local('採点', '通過を調べた駅').value = T.get('駅の位置').filter(x => Number(x) < p).length;
            }, pos);
            await page.waitForFunction(p => Number(T.get('位置')) >= p, pos, {timeout: 20000});
            await shot(page, name);
        };
        const n = k => `${first + k}-${prefix}-viaduct-${['up', 'top', 'down', 'before-switch', 'after-switch', 'seaside'][k]}.png`;
        await at(info.start - 60, speeds.up, 3, n(0));                   // 高田を出た直後: 前の線路が上り坂
        await at(info.start + info.ramp + 900, speeds.top, 0, n(1));     // 高架の上（カーブ）: 街が下に見え、側壁がある
        await at(info.end - info.ramp + 20, speeds.down, 0, n(2));       // 下り坂: 前の線路が下っている
        await at(info.boundary - 25, speeds.sw, 0, n(3));                // 景色の変わり目の手前
        await at(info.boundary + 25, speeds.sw, 0, n(4));                // 変わり目を過ぎたところ
        await at(info.boundary + (route === 3 ? 420 : 600), speeds.sea, route === 3 ? -2 : 0, n(5));   // 降りたあとの海沿い
        console.log('  page errors:', errors.length ? errors : 'なし');
        await page.close();
    }
}

const browser = await chromium.launch({args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist']});
try {
    if (airportOnly) {
        await shootAirportExpress(browser, await pack(true));
    }
    if (viaductOnly) {
        await shootViaduct(browser, await pack(true));
    }
    if (!fpsOnly && !airportOnly && !viaductOnly) {
        const file = await pack(true);
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
        // カーブの入り口（左カーブ 5000m〜 半径2200m の手前）と、カーブの中
        await teleport(page, {pos: 4780, speed: 240, notch: 0, next: 3});
        await page.waitForTimeout(1200);
        await shot(page, '24-curve-shinmachi-entry.png');
        await teleport(page, {pos: 5350, speed: 240, notch: 0, next: 3});
        await page.waitForTimeout(1200);
        await shot(page, '25-curve-shinmachi-inside.png');
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
        await page.waitForFunction(() => T.get('場面') === '停車中', null, {timeout: 60000});
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
        // 右カーブ 6500m〜 半径900m の入り口と中
        await teleport(page, {pos: 6330, speed: 160, notch: 0, next: 2, early: 150});
        await page.waitForTimeout(1200);
        await shot(page, '26-curve-jinja-entry.png');
        await teleport(page, {pos: 6800, speed: 160, notch: 0, next: 2, early: 150});
        await page.waitForTimeout(1200);
        await shot(page, '27-curve-jinja-inside.png');
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
        // 右カーブ 1800m〜 半径3000m の入り口と中
        await teleport(page, {pos: 1600, speed: 150, notch: 0, next: 2, early: 90});
        await page.waitForTimeout(1200);
        await shot(page, '28-curve-tahara-entry.png');
        await teleport(page, {pos: 2150, speed: 150, notch: 0, next: 2, early: 80});
        await page.waitForTimeout(1200);
        await shot(page, '29-curve-tahara-inside.png');
        await teleport(page, {pos: 21500 - 120, speed: 36, notch: -2, next: 4, early: 20});
        await page.waitForTimeout(1500);
        await shot(page, '13-tahara-airport-approach.png');
        // 信町空港駅に止まっているところへ、後ろから追い越して着陸してくる飛行機
        await teleport(page, {pos: 21500, speed: 0, notch: -8, next: 4, early: 60});
        await page.evaluate(() => {
            T.local('景色', '飛行機の有無').value = 0;
            T.local('景色', '飛行機_最初の着陸済').value = 0;
        });
        await page.waitForFunction(() => Number(T.local('景色', '飛行機の有無').value) === 1 &&
            Number(T.local('景色', '飛行機の前後').value) - Number(T.get('位置')) > 380, null, {timeout: 30000});
        await shot(page, '16-airport-landing.png');
        console.log('  page errors:', errors.length ? errors : 'なし');
        await page.close();
    }
    if (!fpsOnly && !airportOnly && !viaductOnly) {
        await shootAirportExpress(browser, path.join(BUILD, 'game.html'));
        await shootViaduct(browser, path.join(BUILD, 'game.html'));
        const file = path.join(BUILD, 'game.html');
        // アクシデント（起きる場所と種類を決めて起こし、障害物などの近くへ移って撮る）
        for (const [route, shots] of [
            [1, [['踏切の車', 9000, '30-accident-crossing.png', -40, 20], ['信号故障', 20000, '33-accident-signal.png', -160, 60]]],
            [2, [['倒木', 3000, '31-accident-tree.png', -70, 35], ['大雨', 11000, '32-accident-rain.png', 400, 115]]],
            [3, [['強風', 5000, '34-accident-wind.png', 400, 150]]],
        ]) {
            const {page, errors} = await openGame(browser, file);
            await startRoute(page, route);
            await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 30000});
            for (const [kind, trigger, name, rel, speed] of shots) {
                await page.evaluate(([kind, trigger]) => {
                    T.local('アクシデント', '予定の位置').value = [trigger];
                    T.local('アクシデント', '予定の種類').value = [kind];
                }, [kind, trigger]);
                const next = await page.evaluate(p => T.get('駅の位置').map(Number).findIndex((x, i) => x > p + 50 && T.get('駅の種別')[i] === '停車') + 1, trigger);
                await teleport(page, {pos: trigger - 30, speed: 120, notch: 0, next, early: 300});
                await page.waitForFunction(() => T.local('アクシデント', '種類').value !== '', null, {timeout: 20000});
                const base = await page.evaluate(() => Number(T.local('アクシデント', '止まる所').value) > 0
                    ? Number(T.local('アクシデント', '止まる所').value) : Number(T.local('アクシデント', '規制の始め').value));
                await teleport(page, {pos: base + rel, speed, notch: 0, next, early: 300});
                await page.waitForTimeout(1300);
                await shot(page, name);
            }
            console.log('  page errors:', errors.length ? errors : 'なし');
            await page.close();
        }
    }
    for (const compiler of airportOnly ? [] : [true, false]) {
        for (const viaduct of viaductOnly ? [true] : [false, true]) {
            const r = await measureFps(browser, compiler, viaduct);
            console.log(`  ${r.mode}: ${r.fps.toFixed(1)} fps（1フレームの処理 ${r.msPerFrame.toFixed(1)}ms） GPU=${r.gl}  errors=${r.errors.length ? r.errors : 'なし'}`);
        }
    }
} finally {
    await browser.close();
}
