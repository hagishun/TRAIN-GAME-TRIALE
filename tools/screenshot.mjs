// TurboWarp Packager で .sb3 を HTML にし、Chromium（Playwright）で開いてスクリーンショットを撮る。
// あわせて、素の Scratch と同じ「インタプリタ」動作と、TurboWarp の「コンパイラ」動作のフレームレートを測る。
//
//   node tools/screenshot.mjs            # docs/screenshots/*.png を作る
//   node tools/screenshot.mjs --fps-only # フレームレートだけ測る
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
    if (!fpsOnly) {
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
    for (const compiler of [true, false]) {
        const r = await measureFps(browser, compiler);
        console.log(`  ${r.mode}: ${r.fps.toFixed(1)} fps（1フレームの処理 ${r.msPerFrame.toFixed(1)}ms） GPU=${r.gl}  errors=${r.errors.length ? r.errors : 'なし'}`);
    }
} finally {
    await browser.close();
}
