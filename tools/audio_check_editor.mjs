// Scratch 公式エディタ／TurboWarp エディタに .sb3 を読み込み、緑の旗で遊んだときに音が鳴るかを確かめる。
//
//   node tools/audio_check_editor.mjs scratch     # https://scratch.mit.edu/projects/editor/
//   node tools/audio_check_editor.mjs turbowarp   # https://turbowarp.org/editor
//
// ページの中で AudioBufferSourceNode.start（音の再生）を捕まえて長さから音の名前を当て、
// スピーカーに出る直前にアナライザーをつないで振幅を測る。
import path from 'path';
import {chromium} from 'playwright';

const site = process.argv[2] || 'scratch';
const ROOT = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const SB3 = path.join(ROOT, 'train-driver-3d.sb3');
const URL_ = site === 'scratch' ? 'https://scratch.mit.edu/projects/editor/' : 'https://turbowarp.org/editor';
const DUR = {1.3: '警笛', 1.85: '遠くの警笛', 2.2: 'ドアチャイム', 8.92: '発車メロディ CLEX202', 8.64: '発車メロディ CLEX203',
    10.57: '発車メロディ CLEX204', 0.45: 'ジョイント', 3.2: 'すれ違い',
    0.7: 'ブレーキ緩め', 1.2: 'ドア', 1.56: '採点', 2.6: '結果', 0.16: '決定', 1: 'モーター/ATSベル', 1.8: '走行音/ピタ停車',
    2: '走行音', 1.5: 'モーター'};

const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width: 1400, height: 900}, locale: 'ja-JP'});
await context.addInitScript(() => {
    delete window.showOpenFilePicker;
    delete window.showSaveFilePicker;
    window.__starts = [];
    window.__peaks = [];
    const origStart = AudioBufferSourceNode.prototype.start;
    AudioBufferSourceNode.prototype.start = function (...a) {
        window.__starts.push({t: performance.now(), dur: this.buffer ? Math.round(this.buffer.duration * 100) / 100 : 0,
            state: this.context.state});
        return origStart.apply(this, a);
    };
    const origConnect = AudioNode.prototype.connect;
    AudioNode.prototype.connect = function (dest, ...rest) {
        if (dest instanceof AudioDestinationNode) {
            const ctx = dest.context;
            if (!ctx.__an) {
                ctx.__an = ctx.createAnalyser();
                ctx.__an.fftSize = 2048;
                window.__ctx = ctx;
                const buf = new Float32Array(2048);
                setInterval(() => {
                    ctx.__an.getFloatTimeDomainData(buf);
                    let p = 0;
                    for (const v of buf) p = Math.max(p, Math.abs(v));
                    window.__peaks.push({t: performance.now(), p, state: ctx.state});
                }, 50);
            }
            origConnect.call(this, ctx.__an);
        }
        return origConnect.call(this, dest, ...rest);
    };
});
const page = await context.newPage();
page.on('dialog', d => d.accept().catch(() => {}));
const marks = [];
const mark = async label => marks.push({label, t: await page.evaluate(() => performance.now())});
try {
    await page.goto(URL_, {waitUntil: 'domcontentloaded', timeout: 120000});
    await page.waitForSelector('[class*="menu-bar_menu-bar-item"]', {timeout: 120000});
    await page.waitForTimeout(4000);
    await page.locator('[class*="menu-bar_menu-bar-item"]', {hasText: /^(ファイル|File)$/}).first().click();
    const chooserPromise = page.waitForEvent('filechooser', {timeout: 30000});
    await page.locator('[class*="menu_menu-item"]', {hasText: /コンピューターから読み込む|Load from your computer/}).first().click();
    await (await chooserPromise).setFiles(SB3);
    await page.waitForSelector('text=路線データ', {timeout: 120000});
    await page.waitForTimeout(3000);
    const flag = page.locator('[class*="green-flag"]').first();
    await mark('緑の旗をクリック');
    await flag.click();
    await page.waitForTimeout(2500);
    const stage = page.locator('canvas').first();
    await stage.click({position: {x: 100, y: 100}}).catch(() => {});
    const press = async k => { await page.keyboard.down(k); await page.waitForTimeout(150); await page.keyboard.up(k); };
    await mark('スペース（タイトルでは何も起きないはず）');
    await press('Space');
    await page.waitForTimeout(1200);
    await mark('Enter（タイトル→路線選択）');
    await press('Enter');
    await page.waitForTimeout(1500);
    await mark('3（田原海岸線）');
    await press('3');
    await page.waitForTimeout(20000);
    await mark('↑×13（B8 → P5 で力行）');
    for (let i = 0; i < 13; i++) await press('ArrowUp');
    await page.waitForTimeout(12000);
    await mark('H（警笛）');
    await press('h');
    await page.waitForTimeout(3000);
    await mark('終わり');
} catch (e) {
    console.error('失敗:', e.message);
    await page.screenshot({path: path.join(ROOT, 'build', `audio-${site}-error.png`)});
}
const starts = await page.evaluate(() => window.__starts);
const peaks = await page.evaluate(() => window.__peaks);
await browser.close();

console.log(`[${site}] ${URL_}`);
for (let i = 0; i < marks.length - 1; i++) {
    const a = marks[i].t, b = marks[i + 1].t;
    const ss = starts.filter(s => s.t >= a && s.t < b);
    const pk = peaks.filter(s => s.t >= a && s.t < b);
    const max = pk.length ? Math.max(...pk.map(x => x.p)) : 0;
    const states = [...new Set(pk.map(x => x.state))].join(',');
    const names = {};
    for (const s of ss) {
        const n = DUR[s.dur] || `${s.dur}秒`;
        names[n] = (names[n] || 0) + 1;
    }
    console.log(`  ${marks[i].label}: 最大振幅 ${max.toFixed(3)}  AudioContext=${states || '未作成'}  再生: ${Object.entries(names).map(([k, v]) => `${k}×${v}`).join(' ') || 'なし'}`);
}
