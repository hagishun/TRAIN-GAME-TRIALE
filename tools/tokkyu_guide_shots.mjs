// 「信町特急の作り方」ページ（docs/make-shinmachi-tokkyu.md）のスクリーンショットを撮る。
// 公式の Scratch エディター（@scratch/scratch-gui 15.3.0）を手元で動かし、ページの手順どおりに
// マウスとキーボードで操作しながら撮る。最後に、できあがった .sb3 を保存する。
//
//   npm pack @scratch/scratch-gui@15.3.0 && tar xzf scratch-scratch-gui-15.3.0.tgz   # package/dist ができる
//   node tools/tokkyu_guide_shots.mjs --gui package/dist --save /tmp/信町特急-完成見本.sb3
//
// 日本語の画面にするため、ブラウザーは ja-JP で開く（日本語フォント fonts-noto-cjk を入れておく）。
// 品質ゲートでは動かさない（エディターの見た目が変わったら撮り直すための道具）。
import fs from 'fs';
import http from 'http';
import path from 'path';
import {spawnSync} from 'child_process';
import {chromium} from 'playwright';

const args = process.argv.slice(2);
const opt = (name, def) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : def;
};
const ROOT = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const GUI_DIR = opt('--gui', null);
const SB3 = opt('--sb3', path.join(ROOT, 'train-driver-3d.sb3'));
const OUT = opt('--out', path.join(ROOT, 'docs', 'images', 'tokkyu'));
const SAVE = opt('--save', null);   // できあがった .sb3（完成見本）を保存する場所
const ONLY = opt('--only', null);   // 'main' / 'kid' / 'mistakes' だけ撮る
if (!GUI_DIR || !fs.existsSync(path.join(GUI_DIR, 'scratch-gui-standalone.js'))) {
    console.error('--gui に scratch-gui の dist フォルダー（scratch-gui-standalone.js があるところ）を指定してください');
    process.exit(1);
}
fs.mkdirSync(OUT, {recursive: true});

// ---- scratch-gui を出すだけの小さなサーバー --------------------------------------
const INDEX = `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Scratch 3.0 GUI</title>
<style>html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden}
#app{position:absolute;top:0;left:0;right:0;bottom:0;min-width:1024px;min-height:640px}</style></head>
<body><div id="app"></div><script src="scratch-gui-standalone.js"></script><script>
const target = document.getElementById('app');
GUI.setAppElement(target);
const root = GUI.createStandaloneRoot(new GUI.EditorState({}), target);
root.render({canEditTitle: true, backpackVisible: false, showComingSoon: false, canSave: false});
</script></body></html>`;
const TYPES = {'.js': 'text/javascript', '.svg': 'image/svg+xml', '.png': 'image/png', '.json': 'application/json',
    '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.css': 'text/css', '.html': 'text/html', '.hex': 'application/octet-stream'};
const server = http.createServer((req, res) => {
    const url = decodeURIComponent(req.url.split('?')[0]);
    if (url === '/' || url === '/index.html') {
        res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'});
        return res.end(INDEX);
    }
    const file = path.join(GUI_DIR, path.normalize(url));
    if (!file.startsWith(path.resolve(GUI_DIR)) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
        res.writeHead(404);
        return res.end();
    }
    res.writeHead(200, {'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream'});
    fs.createReadStream(file).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const GUI_URL = `http://127.0.0.1:${server.address().port}/`;

// ---- エディターの操作 ---------------------------------------------------------------
const W = 1280, H = 800;
let page;
const wait = ms => page.waitForTimeout(ms);
let shotCount = 0;

async function openGui() {
    const browser = await chromium.launch();
    const ctx = await browser.newContext({viewport: {width: W, height: H}, locale: 'ja-JP', acceptDownloads: true});
    await ctx.addInitScript(() => {
        delete window.showOpenFilePicker;
        delete window.showSaveFilePicker;
    });
    page = await ctx.newPage();
    page.on('dialog', d => d.accept().catch(() => {}));
    page.on('pageerror', e => console.error('  pageerror:', e.message));
    await page.goto(GUI_URL, {waitUntil: 'load'});
    await page.waitForSelector('[class*="menu-bar_menu-bar-item"]', {timeout: 60000});
    await wait(1500);
    return browser;
}

const menuItem = name => page.locator('[class*="menu-bar_menu-bar-item"]', {hasText: new RegExp(`^${name}`)}).first();
const fileMenuEntry = name => page.locator('[class*="menu_menu-item"]', {hasText: name}).first();

// 開いたままの「ファイル」メニューを、メニューの外をクリックして閉じる
async function closeFileMenu() {
    for (let i = 0; i < 4; i++) {
        await wait(400);
        if (!await fileMenuEntry('コンピューターに保存する').isVisible()) return;
        if (i % 2 === 0) await page.mouse.click(1000, 70);
        else await menuItem('ファイル').click();
    }
    throw new Error('ファイルメニューが閉じない');
}

async function loadSb3(file) {
    await menuItem('ファイル').click();
    await wait(500);
    const chooser = page.waitForEvent('filechooser', {timeout: 30000});
    await fileMenuEntry(/コンピューターから読み込む|Load from your computer/).click();
    await (await chooser).setFiles(file);
    await page.waitForSelector('[class*="sprite-selector-item_sprite-name"] >> text=路線データ', {timeout: 120000});
    await wait(3000);
    // 読み込んだあとも開いたままのメニューを閉じる
    await closeFileMenu();
}

const spriteTile = name => page.locator('[class*="sprite-selector-item_sprite-selector-item"]', {
    has: page.locator('[class*="sprite-selector-item_sprite-name"]', {hasText: new RegExp(`^${name}$`)}),
}).first();

async function selectSprite(name) {
    await spriteTile(name).click();
    await wait(2500);
}

async function box(locator) {
    const b = await locator.boundingBox();
    return {x: b.x, y: b.y, w: b.width, h: b.height};
}

// コードエリア（メインのワークスペース）の、ブロックの一覧。
// sig は、ブロックの中の文字（ラベルと、あなの中身）を左から順につないだもの。
async function blocks() {
    return page.evaluate(() => {
        const canvas = [...document.querySelectorAll('g.blocklyBlockCanvas')]
            .find(c => !c.closest('.blocklyFlyout') && !c.closest('[class*="custom-procedures"]') && c.closest('.injectionDiv'));
        const out = [];
        for (const g of canvas.querySelectorAll('g.blocklyBlock[data-id]')) {
            if (g.classList.contains('blocklyShadow')) continue;
            const parts = [];
            const own = g.querySelectorAll(':scope > g.blocklyLabelField > text, :scope > g.blocklyEditableField > text, ' +
                ':scope > g.blocklyShadow text.blocklyText, :scope > g.blocklyBlock:not(.blocklyShadow) > g.blocklyLabelField > text');
            for (const t of own) {
                const r = t.getBoundingClientRect();
                // 中に入れたブロック（C の中・下につながったもの）の文字は入れない
                const holder = t.closest('g.blocklyBlock:not(.blocklyShadow)');
                if (holder !== g && holder.parentElement !== g) continue;
                if (holder !== g && !(holder.getAttribute('class') || '').match(/operator|argument|data_variable|data_itemoflist|data_lengthoflist/)) continue;
                parts.push([r.x, t.textContent.replace(/\u00a0/g, ' ').trim()]);
            }
            parts.sort((a, b) => a[0] - b[0]);
            if ((g.getAttribute('class') || '').startsWith('procedures_definition')) {
                const proto = g.querySelector(':scope > g.procedures_prototype');
                if (proto) parts.push([0, [...proto.querySelectorAll(':scope > g.blocklyLabelField > text, :scope > g.blocklyBlock > g.blocklyLabelField > text')]
                    .map(t => [t.getBoundingClientRect().x, t.textContent.replace(/\u00a0/g, ' ').trim()])
                    .sort((a, b) => a[0] - b[0]).map(x => x[1]).join(' ')]);
            }
            const p = g.querySelector(':scope > path.blocklyPath').getBoundingClientRect();
            const all = g.getBoundingClientRect();
            out.push({id: g.getAttribute('data-id'), cls: g.getAttribute('class'), sig: parts.map(x => x[1]).join(' '),
                x: p.x, y: p.y, w: p.width, h: p.height, ax: all.x, ay: all.y, aw: all.width, ah: all.height,
                top: !g.parentElement.closest('g.blocklyBlock')});
        }
        return out;
    });
}

async function findBlock(match, {all = false} = {}) {
    const list = await blocks();
    const f = typeof match === 'function' ? match : (b => (match instanceof RegExp ? match.test(b.sig) : b.sig.startsWith(match)));
    const hit = list.filter(f);
    if (all) return hit;
    if (!hit.length) throw new Error('ブロックが見つからない: ' + match);
    return hit[0];
}

async function idsNow() {
    return new Set((await blocks()).map(b => b.id));
}

async function newBlock(before, cls) {
    const hit = (await blocks()).filter(b => !before.has(b.id) && (!cls || b.cls.startsWith(cls)));
    if (!hit.length) throw new Error('新しいブロックが見つからない: ' + cls);
    return hit.sort((a, b) => a.y - b.y)[0];
}

async function blockById(id) {
    return (await blocks()).find(b => b.id === id);
}

async function workspaceBox() {
    return box(page.locator('.injectionDiv .blocklyMainBackground').first());
}

// ブロックの左上が画面の (x, y) に来るまでスクロールする（作者はホイールやスクロールバーで動かす）
async function scrollBlockTo(id, y = 150, x = 380) {
    for (let i = 0; i < 5; i++) {
        const b = await blockById(id);
        const dy = b.y - y, dx = b.x - x;
        if (Math.abs(dy) < 2 && Math.abs(dx) < 2) return b;
        await page.evaluate(([dx, dy]) => {
            // scratch-gui の Blocks コンポーネントが持っているワークスペース
            const host = document.querySelector('.injectionDiv').parentElement;
            let f = host[Object.keys(host).find(k => k.startsWith('__reactInternalInstance') || k.startsWith('__reactFiber'))];
            while (f && !(f.stateNode && f.stateNode.workspace)) f = f.return;
            const ws = f.stateNode.workspace;
            ws.scroll(ws.scrollX - dx, ws.scrollY - dy);
        }, [dx, dy]);
        await wait(300);
    }
    return blockById(id);
}

async function clickCategory(name) {
    await page.locator('.blocklyToolboxCategory', {hasText: name}).first().click();
    await wait(900);
}

// パレット（ブロックの一覧）のブロック。label はブロックのいちばん左の文字
async function paletteBlock(label) {
    return page.evaluate(label => {
        for (const g of document.querySelectorAll('.injectionDiv .blocklyFlyout .blocklyBlockCanvas > g.blocklyBlock')) {
            const t = [...g.querySelectorAll(':scope > g.blocklyLabelField > text, :scope > g.blocklyShadow text')]
                .map(t => [t.getBoundingClientRect().x, t.textContent.replace(/\u00a0/g, ' ').trim()]).sort((a, b) => a[0] - b[0]);
            if (t.length && t.map(x => x[1]).join(' ').startsWith(label)) {
                const r = g.querySelector(':scope > path.blocklyPath').getBoundingClientRect();
                return {x: r.x, y: r.y, w: r.width, h: r.height};
            }
        }
        return null;
    }, label);
}

async function paletteBox() {
    return box(page.locator('.injectionDiv .blocklyFlyout').first());
}

// パレットをホイールでスクロールして、ブロックを y の高さに出す
async function scrollPaletteTo(label, y = 300) {
    const pb = await paletteBox();
    for (let i = 0; i < 100; i++) {
        const r = await paletteBlock(label);
        if (!r) throw new Error('パレットにない: ' + label);
        const d = r.y - y;
        if (Math.abs(d) < 6) return r;
        await page.mouse.move(pb.x + pb.w / 2, pb.y + pb.h / 2);
        await page.mouse.wheel(0, Math.max(-300, Math.min(300, d)));
        await wait(150);
    }
    return paletteBlock(label);
}

// ブロックをつかんで動かす。grab はブロックの左上からのつかむ所。
// to はブロックの左上を置きたい所。mid があれば、はなす前に呼ぶ（灰色の影を撮る）
async function dragBlock(from, to, {grab = {x: 12, y: 14}, mid, via} = {}) {
    await page.mouse.move(from.x + grab.x, from.y + grab.y);
    await page.mouse.down();
    await page.mouse.move(from.x + grab.x + 8, from.y + grab.y + 6, {steps: 3});
    if (via) await page.mouse.move(via.x + grab.x, via.y + grab.y, {steps: 20});
    await page.mouse.move(to.x + grab.x, to.y + grab.y, {steps: 30});
    await wait(400);
    if (mid) await mid();
    await page.mouse.up();
    await wait(700);
}

// ブロックの文字のあな（左から n 番目、0 から）
async function fieldBoxes(id) {
    return page.evaluate(id => {
        const g = document.querySelector(`.injectionDiv g.blocklyBlock[data-id="${CSS.escape(id)}"]`);
        const out = [];
        for (const f of g.querySelectorAll(':scope > g.blocklyShadow, :scope > g.blocklyEditableField')) {
            const r = f.getBoundingClientRect();
            const t = f.querySelector('text');
            out.push({x: r.x, y: r.y, w: r.width, h: r.height, text: t ? t.textContent.replace(/\u00a0/g, ' ') : '',
                shadow: f.classList.contains('blocklyShadow')});
        }
        return out.sort((a, b) => a.x - b.x);
    }, id);
}

async function typeInField(id, n, text, {before} = {}) {
    const f = (await fieldBoxes(id))[n];
    await page.mouse.click(f.x + f.w / 2, f.y + f.h / 2);
    await wait(400);
    await page.keyboard.press('Control+A');
    await page.keyboard.type(text, {delay: 20});
    await wait(300);
    if (before) await before();
    await page.keyboard.press('Enter');
    await wait(500);
}

async function contextMenu(at, item, {before} = {}) {
    const entry = page.locator('.blocklyContextMenu .blocklyMenuItem', {hasText: item}).first();
    for (let i = 0; i < 3; i++) {
        await page.mouse.move(at.x, at.y);
        await wait(200);
        await page.mouse.click(at.x, at.y, {button: 'right'});
        await wait(700);
        if (await entry.isVisible()) break;
        await page.keyboard.press('Escape');
        await wait(500);
    }
    if (before) await before(await box(entry));
    await entry.click();
    await wait(600);
}

// ---- 書きこみ（赤い枠・番号・矢印） -------------------------------------------------
// marks: {box: {x,y,w,h}, n: 番号, label: 文字} / {arrow: [from, to]} / {text, at}
async function annotate(marks) {
    await page.evaluate(marks => {
        document.getElementById('guide-overlay')?.remove();
        const NS = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(NS, 'svg');
        svg.id = 'guide-overlay';
        svg.setAttribute('style', 'position:fixed;left:0;top:0;width:100vw;height:100vh;pointer-events:none;z-index:2147483647');
        svg.innerHTML = '<defs><marker id="ga" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">' +
            '<path d="M0,0 L10,5 L0,10 z" fill="#e8132b"/></marker></defs>';
        const el = (tag, attrs, text) => {
            const e = document.createElementNS(NS, tag);
            for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
            if (text !== undefined) e.textContent = text;
            svg.appendChild(e);
            return e;
        };
        const badge = (x, y, n) => {
            el('circle', {cx: x, cy: y, r: 15, fill: '#e8132b', stroke: '#fff', 'stroke-width': 2.5});
            el('text', {x, y: y + 6.5, 'text-anchor': 'middle', 'font-size': 19, 'font-weight': 'bold', fill: '#fff',
                'font-family': 'Noto Sans CJK JP, sans-serif'}, String(n));
        };
        const label = (x, y, s, anchor = 'start') => {
            const t = el('text', {x, y, 'text-anchor': anchor, 'font-size': 17, 'font-weight': 'bold', fill: '#e8132b',
                'font-family': 'Noto Sans CJK JP, sans-serif', stroke: '#fff', 'stroke-width': 5, 'paint-order': 'stroke'}, s);
            return t;
        };
        for (const m of marks) {
            if (m.box) {
                const p = m.pad ?? 4;
                const b = m.box;
                el('rect', {x: b.x - p, y: b.y - p, width: b.w + 2 * p, height: b.h + 2 * p, rx: 6, fill: 'none',
                    stroke: m.color || '#e8132b', 'stroke-width': 3.5, 'stroke-dasharray': m.dash ? '8 5' : ''});
                if (m.n !== undefined) {
                    const side = m.badge || 'left';
                    if (side === 'left') badge(Math.max(16, b.x - p - 16), b.y - p + 4, m.n);
                    else if (side === 'right') badge(b.x + b.w + p + 16, b.y - p + 4, m.n);
                    else badge(b.x - p + 4, b.y - p - 14, m.n);
                }
                if (m.label) {
                    const pos = m.labelAt || 'below';
                    if (pos === 'below') label(b.x - p, b.y + b.h + p + 20, m.label);
                    else if (pos === 'above') label(b.x - p, b.y - p - 8, m.label);
                    else if (pos === 'right') label(b.x + b.w + p + (m.n !== undefined && m.badge === 'right' ? 36 : 8), b.y + b.h / 2 + 6, m.label);
                    else if (pos === 'left') label(b.x - p - 8, b.y + b.h / 2 + 6, m.label, 'end');
                }
            }
            if (m.arrow) {
                const [a, b] = m.arrow;
                el('path', {d: `M${a.x},${a.y} L${b.x},${b.y}`, stroke: '#e8132b', 'stroke-width': 4.5, fill: 'none',
                    'marker-end': 'url(#ga)', 'stroke-dasharray': m.dash ? '10 6' : ''});
            }
            if (m.text) label(m.at.x, m.at.y, m.text, m.anchor || 'start');
            if (m.badgeAt) badge(m.badgeAt.x, m.badgeAt.y, m.n);
        }
        document.body.appendChild(svg);
    }, marks);
}

async function clearMarks() {
    await page.evaluate(() => document.getElementById('guide-overlay')?.remove());
}

async function shot(name, marks = [], {clip} = {}) {
    if (marks.length) await annotate(marks);
    await wait(250);
    const file = path.join(OUT, name + '.png');
    await page.screenshot({path: file, clip});
    shotCount++;
    console.log('  撮影', name);
    await clearMarks();
}

const grow = (b, dx, dy = dx) => ({x: b.x - dx, y: b.y - dy, w: b.w + 2 * dx, h: b.h + 2 * dy});
const union = (...bs) => {
    const x = Math.min(...bs.map(b => b.x)), y = Math.min(...bs.map(b => b.y));
    return {x, y, w: Math.max(...bs.map(b => b.x + b.w)) - x, h: Math.max(...bs.map(b => b.y + b.h)) - y};
};
// ブロックと、その下につながったブロック全部（C の中もふくむ）のかこみ
const stackBox = b => ({x: b.ax, y: b.ay, w: b.aw, h: b.ah});

// ---- 手順 -----------------------------------------------------------------------
const HOME = {
    type: '信町特急 ホームライナー', menu: '信町特急 ホームライナー 信早ヶ丘行（上級・10両・4駅停車）', def: '運行5 ホームライナー', no: '5',
    stops: [['新信町', '18:20:00'], ['二間六草', '18:25:00'], ['高田', '18:30:45'], ['信早ヶ丘', '18:39:10']],
};
const CITY = {
    type: '信町特急 シティライナー', menu: '信町特急 シティライナー 信早ヶ丘行（上級・10両・3駅停車）', def: '運行6 シティライナー', no: '6',
    stops: [['新信町', '18:50:00'], ['二間六草', '18:55:00'], ['信早ヶ丘', '19:07:30']],
};

async function partBackup() {
    // 0. 控えをとる
    await menuItem('ファイル').click();
    await wait(600);
    await shot('00-backup', [
        {box: await box(menuItem('ファイル')), n: 1, badge: 'left'},
        {box: await box(fileMenuEntry('コンピューターに保存する')), n: 2, badge: 'right', label: '「train-driver-3d-もと」などの名前で保存', labelAt: 'below'},
    ]);
    await closeFileMenu();
}

async function partOpenSprite() {
    const smallStage = page.locator('[class*="stage-header_stage-button"]').first();
    await shot('01-small-stage-and-sprite', [
        {box: await box(smallStage), n: 1, badge: 'left', label: 'ステージを小さくする', labelAt: 'left'},
        {box: await box(spriteTile('路線データ')), n: 2, badge: 'left'},
    ]);
    await smallStage.click();
    await selectSprite('路線データ');
    await shot('02-route-data-opened', [
        {box: await box(spriteTile('路線データ')), n: 1, badge: 'left'},
        {box: await workspaceBox(), pad: -6, label: 'コードエリア（路線データのプログラム）', labelAt: 'above', dash: true},
    ]);
    // 設定を読み込むを受け取ったとき
    const hat = await findBlock('設定を読み込む を受け取ったとき');
    const b = await scrollBlockTo(hat.id, 150);
    await shot('03-settings-script', [
        {box: stackBox(b), n: 1, badge: 'left'},
    ]);
    return hat.id;
}

async function addTrainType(t, prefix) {
    // 種別を追加: パレットから持ってきて、エアポート特快（か、前に足した種別）のすぐ下に入れる
    await clickCategory('ブロック定義');
    const types = await findBlock(b => b.cls.startsWith('procedures_call') && b.sig.startsWith('種別を追加'), {all: true});
    const last = types.sort((a, b) => a.y - b.y).at(-1);
    const pal = await scrollPaletteTo('種別を追加', 420);
    const target = {x: last.x, y: last.y + last.h};
    const marks = [
        {box: await box(page.locator('.blocklyToolboxCategory', {hasText: 'ブロック定義'}).first()), n: 1, badge: 'top'},
        {box: pal, n: 2, badge: 'left'},
        {arrow: [{x: pal.x + pal.w + 4, y: pal.y + pal.h / 2}, {x: target.x + 30, y: target.y + 18}]},
        {box: {x: target.x, y: target.y - 2, w: 230, h: 4}, pad: 3, label: 'ここに入れる', labelAt: 'right'},
    ];
    if (prefix) await shot(prefix + '-a', marks);
    await dragBlock(pal, {x: target.x, y: target.y}, {
        mid: prefix ? () => shot(prefix + '-b', [{text: '灰色の影が出たら、マウスをはなす', at: {x: target.x + 250, y: target.y + 30}}]) : null,
    });
    const added = await findBlock(b => b.cls.startsWith('procedures_call') && b.sig.startsWith('種別を追加') && !types.some(t => t.id === b.id));
    if (prefix) {
        await shot(prefix + '-c', [{box: {x: added.x, y: added.y, w: added.w, h: added.h}, n: 3, badge: 'left', label: '入った（あなはまだ空っぽ）', labelAt: 'right'}]);
    }
    let f = await fieldBoxes(added.id);
    await typeInField(added.id, 0, t.type, {
        before: prefix ? async () => shot(prefix + '-d', [{box: (await fieldBoxes(added.id))[0], n: 4, badge: 'top', label: 'クリックして書く', labelAt: 'below'}]) : null,
    });
    await typeInField(added.id, 1, t.cars || '10');
    const done = await blockById(added.id);
    if (prefix) {
        await shot(prefix + '-e', [{box: {x: done.x, y: done.y, w: done.w, h: done.h}, n: 5, badge: 'left', label: 'できた！', labelAt: 'right'}]);
    }
    return added.id;
}

async function addMenuLine(t, prefix) {
    await clickCategory('変数');
    const lines = (await findBlock(b => b.cls.startsWith('data_addtolist') && b.sig.includes('路線一覧'), {all: true}))
        .sort((a, b) => a.y - b.y);
    const last = lines.at(-1);
    const pal = await scrollPaletteTo('なにか を', 420);
    if (prefix) {
        await shot(prefix + '-a', [
            {box: await box(page.locator('.blocklyToolboxCategory', {hasText: '変数'}).first()), n: 1, badge: 'top'},
            {box: pal, n: 2, badge: 'left'},
            {arrow: [{x: pal.x + pal.w + 4, y: pal.y + pal.h / 2}, {x: last.x + 30, y: last.y + last.h + 16}]},
            {box: {x: last.x, y: last.y + last.h - 2, w: 230, h: 4}, pad: 3, label: 'ここに入れる', labelAt: 'right'},
        ]);
    }
    const before = await idsNow();
    await dragBlock(pal, {x: last.x, y: last.y + last.h});
    const added = await newBlock(before, 'data_addtolist');
    // ▼ でリストを「路線一覧」にする
    const fields = await fieldBoxes(added.id);
    const dd = fields.find(f => !f.shadow);
    await page.mouse.click(dd.x + dd.w - 10, dd.y + dd.h / 2);
    await wait(700);
    const item = page.locator('.blocklyDropDownDiv .blocklyMenuItem', {hasText: /^路線一覧$/}).first();
    await item.scrollIntoViewIfNeeded();
    await wait(300);
    if (prefix) {
        await shot(prefix + '-b', [
            {box: dd, n: 3, badge: 'left', label: '▼ をクリック', labelAt: 'below'},
            {box: await box(item), n: 4, badge: 'right'},
        ]);
    }
    await item.click();
    await wait(600);
    await typeInField(added.id, 0, t.menu, {
        before: prefix ? async () => shot(prefix + '-c', [{box: (await fieldBoxes(added.id))[0], n: 5, badge: 'top', label: '「なにか」をクリックして書く', labelAt: 'below'}]) : null,
    });
    const done = await blockById(added.id);
    if (prefix) await shot(prefix + '-d', [{box: done, n: 6, badge: 'left', label: 'できた！', labelAt: 'right'}]);
    return added.id;
}

async function makeDefinition(t, prefix, near = '運行4') {
    // 新しい定義は、今見ている所の左上に出る。先に、となりに置きたい定義（『運行4 エアポート特快』など）を出しておく
    const def4 = await findBlock(b => b.cls.startsWith('procedures_definition') && b.sig.includes(near));
    const d4 = await scrollBlockTo(def4.id, 130);
    if (prefix) await shot(prefix + '-a', [{box: stackBox(d4), n: 1, badge: 'left', label: '定義 運行4 エアポート特快', labelAt: 'right'}]);
    await clickCategory('ブロック定義');
    const make = page.locator('.blocklyFlyoutButton', {hasText: 'ブロックを作る'}).first();
    if (prefix) await shot(prefix + '-b', [{box: await box(make), n: 2, badge: 'left'}]);
    const before = await idsNow();
    await make.click();
    await wait(1500);
    await page.keyboard.type(t.def, {delay: 20});
    await wait(300);
    const warpRow = page.locator('[class*="custom-procedures_checkbox-row"]').first();
    const warp = warpRow.locator('input[type="checkbox"]');
    await warp.check();
    await wait(300);
    const ok = page.locator('[class*="custom-procedures_ok-button"]').first();
    if (prefix) {
        await shot(prefix + '-c', [
            {box: await box(page.locator('.blocklyHtmlInput, [class*="custom-procedures_workspace"] .blocklyEditableField').first()), n: 3, badge: 'left', label: '名前を書く', labelAt: 'below'},
            {box: await box(warpRow), n: 4, badge: 'left', label: 'チェックを入れる', labelAt: 'below'},
            {box: await box(ok), n: 5, badge: 'right'},
        ]);
    }
    await ok.click();
    await wait(1500);
    let def = await newBlock(before, 'procedures_definition');
    // 上のタブにかくれて、つかめないときは、少し下へずらして見る
    const ws = await workspaceBox();
    if (def.y < ws.y + 20) def = await scrollBlockTo(def.id, ws.y + 40, def.x);
    if (prefix) await shot(prefix + '-d', [{box: def, n: 6, badge: 'left', label: '新しい定義', labelAt: 'right'}]);
    return def.id;
}

// 新しい定義を、src の定義のかたまりの下の、何もない所へ動かす
async function moveDefinitionBelow(defId, srcDefId, prefix) {
    const src = await blockById(srcDefId);
    const def = await blockById(defId);
    const to = {x: src.x, y: src.ay + src.ah + 20};
    if (prefix) {
        await shot(prefix + '-a', [
            {box: def, n: 1, badge: 'left'},
            {arrow: [{x: def.x + 40, y: def.y + def.h}, {x: to.x + 40, y: to.y + 10}]},
            {text: '何もない所へ動かす', at: {x: to.x + 60, y: to.y + 40}},
        ]);
    }
    if (to.y + 60 > H) throw new Error('定義を置く所が画面の外');
    await dragBlock(def, to, {grab: {x: 14, y: 30}});
    const moved = await blockById(defId);
    if (Math.abs(moved.y - to.y) > 6 || Math.abs(moved.x - to.x) > 6) throw new Error('定義が思った所に動かなかった');
    if (prefix) await shot(prefix + '-b', [{box: moved, n: 2, badge: 'left', label: 'ここに置いた', labelAt: 'right'}]);
    return moved;
}

async function commentIds() {
    return page.evaluate(() => [...document.querySelectorAll('.injectionDiv image.blocklyDeleteIcon')].map(e => e.id));
}

async function deleteIconBox(id) {
    return page.evaluate(id => {
        const r = document.getElementById(id).getBoundingClientRect();
        return {x: r.x, y: r.y, w: r.width, h: r.height};
    }, id);
}

// srcDef のすぐ下のブロックを右クリック →「複製」して、newDef の下にくっつける。
// コピーについてくる黄色いメモ（コメント）は × で消す
async function copyBody(srcDefId, newDefId, prefix) {
    const src = await blockById(srcDefId);
    const first = (await blocks()).filter(b => !b.top && Math.abs(b.x - src.x) < 3 && b.y > src.y + 10 && b.y < src.y + src.h + 30)[0];
    const before = await idsNow();
    const comments = new Set(await commentIds());
    await contextMenu({x: first.x + 14, y: first.y + first.h / 2}, '複製', {
        before: prefix ? async item => shot(prefix + '-a', [
            {box: first, n: 1, badge: 'left', label: '右クリック', labelAt: 'right'},
            {box: item, n: 2, badge: 'right'},
        ]) : null,
    });
    await page.mouse.move(700, 760);
    await wait(500);
    const copyTop = await newBlock(before);
    const newComments = (await commentIds()).filter(id => !comments.has(id));
    const c = await blockById(copyTop.id);
    const nd = await blockById(newDefId);
    const target = {x: nd.x, y: nd.y + nd.h};
    if (prefix) {
        await shot(prefix + '-b', [
            {box: c, n: 3, badge: 'left', label: 'コピー。いちばん上をつかむ', labelAt: 'above'},
            {arrow: [{x: c.x + 20, y: c.y + c.h}, {x: target.x + 20, y: target.y + 14}]},
            {box: {x: target.x, y: target.y - 2, w: 160, h: 4}, pad: 3, label: 'ここにくっつける', labelAt: 'right'},
        ]);
    }
    await dragBlock(c, target, {
        grab: {x: 12, y: c.h / 2},
        mid: prefix ? () => shot(prefix + '-c', [{text: '「定義」の下に入りそうになったら、はなす', at: {x: target.x + 300, y: target.y - 20}}]) : null,
    });
    let d = await blockById(newDefId);
    if (!(await stackOf(newDefId)).length) throw new Error('コピーが定義にくっつかなかった');
    if (prefix) await shot(prefix + '-d', [{box: stackBox(d), n: 4, badge: 'left', label: 'くっついた！', labelAt: 'above'}]);
    // コピーについてきた黄色いメモ（コメント）を × で消す。少し下へスクロールしてから
    d = await scrollBlockTo(newDefId, 120);
    const clickable = async () => {
        const out = [];
        for (const id of (await commentIds()).filter(id => !comments.has(id))) {
            const ok = await page.evaluate(id => {
                const e = document.getElementById(id);
                const r = e.getBoundingClientRect();
                const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
                return hit === e ? {x: r.x, y: r.y, w: r.width, h: r.height} : null;
            }, id);
            if (ok) out.push(ok);
        }
        return out;
    };
    let firstShot = true;
    for (let i = 0; i < 20; i++) {
        const xs = await clickable();
        if (!xs.length) break;
        if (prefix && firstShot) {
            await shot(prefix + '-e', [{box: stackBox(d), n: 5, badge: 'left', label: 'コピーには黄色いメモもついてくる', labelAt: 'above'},
                ...xs.map((b, k) => ({box: b, pad: 3, ...(k === 0 ? {n: 6, badge: 'right'} : {})}))]);
        }
        firstShot = false;
        await page.mouse.click(xs[0].x + xs[0].w / 2, xs[0].y + xs[0].h / 2);
        await wait(400);
    }
    const left = (await commentIds()).filter(id => !comments.has(id));
    if (left.length) console.log('  消えなかったメモ', left.length);
    d = await blockById(newDefId);
    if (prefix) await shot(prefix + '-f', [{box: stackBox(d), n: 7, badge: 'left', label: 'メモを消した', labelAt: 'above'}]);
    return d;
}

// 定義の下につながったブロック（上から順）
async function stackOf(defId) {
    const d = await blockById(defId);
    return (await blocks()).filter(b => !b.top && Math.abs(b.x - d.x) < 3 && b.y > d.y + 10 && b.y < d.ay + d.ah)
        .sort((a, b) => a.y - b.y);
}

// edits: [[ブロックの sig の始め, あなの番号, 新しい文字], ...]
async function rewrite(defId, edits, prefix, {label} = {}) {
    const list = await stackOf(defId);
    const pick = start => list.find(b => b.sig.startsWith(start));
    if (prefix) {
        const marks = [];
        let n = 1;
        for (const [start, k, text] of edits) {
            const b = pick(start);
            const f = (await fieldBoxes(b.id))[k];
            marks.push({box: f, pad: 3, ...(edits.length <= 3 ? {n: n++, badge: 'top'} : {}), label: '→ ' + text, labelAt: 'right'});
        }
        // ラベルどうしが重ならないように、同じ行は右はしの枠にまとめて書く
        const rows = [];
        for (const m of marks) {
            const r = rows.find(r => Math.abs(r[0].box.y - m.box.y) < 5);
            if (r) r.push(m); else rows.push([m]);
        }
        for (const r of rows) {
            const text = '→ ' + r.map(m => m.label.slice(2)).join('  ');
            for (const m of r) delete m.label;
            r.sort((a, b) => a.box.x - b.box.x).at(-1).label = text;
        }
        await shot(prefix + '-a', marks);
    }
    const ids = edits.map(([start]) => pick(start).id);
    for (let i = 0; i < edits.length; i++) await typeInField(ids[i], edits[i][1], edits[i][2]);
    await page.mouse.click(700, 785);
    await wait(300);
    if (prefix) {
        const bs = [];
        for (const id of [...new Set(ids)]) bs.push(await blockById(id));
        const u = union(...bs);
        await shot(prefix + '-b', [{box: u, pad: 4, n: '✓', badge: 'left', label: label || '書きかえた', labelAt: 'right'}]);
    }
}

// 定義の中のブロックを右クリック →「ブロックを削除」
async function deleteInStack(defId, start, prefix) {
    const b = (await stackOf(defId)).find(x => x.sig.startsWith(start));
    await contextMenu({x: b.x + 12, y: b.y + b.h / 2}, 'ブロックを削除', {
        before: prefix ? async item => shot(prefix + '-a', [
            {box: b, n: 1, badge: 'left', label: '右クリック', labelAt: 'right', pad: 3},
            {box: item, n: 2, badge: 'right'},
        ]) : null,
    });
    await wait(400);
    if (prefix) {
        const d = await blockById(defId);
        await shot(prefix + '-b', [{box: stackBox(d), n: '✓', badge: 'left', label: '消えて、下のブロックが上につめた', labelAt: 'above'}]);
    }
}

// 『路線を読む』の、いちばん下の「もし (番号) = (□) なら」を複製して下につけ、番号と中のブロックを変える
async function addToReadRoute(t, prevCallLabel, prefix, hooks = {}) {
    const prevNo = String(Number(t.no) - 1);
    const def0 = await findBlock(b => b.cls.startsWith('procedures_definition') && b.sig.includes('路線を読む'));
    const def = await scrollBlockTo(def0.id, 130);
    const ifs = (await blocks()).filter(b => b.cls.startsWith('control_if') && b.y > def.y && b.y < def.ay + def.ah)
        .sort((a, b) => a.y - b.y);
    const last = ifs.at(-1);
    if (prefix) await shot(prefix + '-a', [{box: stackBox(await blockById(def.id)), n: 1, badge: 'left', label: '定義 路線を読む', labelAt: 'right'},
        {box: stackBox(last), pad: 3, n: 2, badge: 'right', label: 'いちばん下の「もし」', labelAt: 'right'}]);
    const before = await idsNow();
    const comments = new Set(await commentIds());
    await contextMenu({x: last.x + 10, y: last.y + 12}, '複製', {
        before: prefix ? async item => shot(prefix + '-b', [
            {box: {x: last.x, y: last.y, w: 40, h: 30}, n: 1, badge: 'left', label: '「もし」の左はしを右クリック', labelAt: 'above'},
            {box: item, n: 2, badge: 'right'},
        ]) : null,
    });
    await page.mouse.move(700, 785);
    await wait(400);
    const copy = (await blocks()).filter(b => !before.has(b.id) && b.cls.startsWith('control_if'))[0];
    const lastNow = await blockById(last.id);
    const target = {x: lastNow.x, y: lastNow.ay + lastNow.ah};
    // コピーの黄色いメモを消す
    for (const id of (await commentIds()).filter(id => !comments.has(id))) {
        const b = await deleteIconBox(id);
        if (b.w > 0) await page.mouse.click(b.x + b.w / 2, b.y + b.h / 2);
        await wait(300);
    }
    const c = await blockById(copy.id);
    if (prefix) {
        await shot(prefix + '-c', [
            {box: {x: c.x, y: c.y, w: 40, h: 30}, n: 3, badge: 'left', label: 'コピーの「もし」の左はしをつかむ', labelAt: 'above'},
            {arrow: [{x: c.x + 20, y: c.y + 30}, {x: target.x + 20, y: target.y + 12}]},
            {box: {x: target.x, y: target.y - 2, w: 160, h: 4}, pad: 3, label: 'ここにくっつける', labelAt: 'right'},
        ]);
    }
    // 上から近づけると「もし」の中に入りやすいので、右下から近づける
    await dragBlock(c, target, {grab: {x: 10, y: 12}, via: {x: target.x + 200, y: target.y + 90}});
    let placed = await blockById(copy.id);
    const lastAfter = await blockById(last.id);
    if (Math.abs(placed.x - lastAfter.x) > 2) throw new Error('「もし」が外側の下にくっつかなかった');
    if (prefix) await shot(prefix + '-d', [{box: stackBox(placed), pad: 3, n: '✓', badge: 'left', label: `くっついた（まだ ${prevNo} のまま）`, labelAt: 'right'}]);
    if (hooks.afterAttach) {
        await hooks.afterAttach();
        placed = await blockById(copy.id);
    }
    // 4 → 5
    const eq = (await blocks()).find(b => b.cls.startsWith('operator_equals') && b.y > placed.y - 2 && b.y < placed.y + 30 && b.x > placed.x);
    const eqf = await fieldBoxes(eq.id);
    await typeInField(eq.id, eqf.length - 1, t.no, {
        before: prefix ? async () => shot(prefix + '-e', [{box: (await fieldBoxes(eq.id)).at(-1), pad: 3, n: 4, badge: 'top', label: `${t.no} にする`, labelAt: 'right'}]) : null,
    });
    if (hooks.afterNumber) await hooks.afterNumber();
    // 中のブロックを入れかえる: 前のをパレットへすてて、新しいのを入れる
    const p2 = await blockById(copy.id);
    const inner = (await blocks()).find(b => b.cls.startsWith('procedures_call') && b.sig.startsWith(prevCallLabel) && b.y > p2.y + 10 && b.y < p2.ay + p2.ah);
    const rel = {x: inner.x - p2.x, y: inner.y - p2.y};
    const slotNow = async () => {
        const c = await blockById(copy.id);
        return {x: c.x + rel.x, y: c.y + rel.y};
    };
    const pal = await paletteBox();
    if (prefix) {
        await shot(prefix + '-f', [
            {box: inner, pad: 3, n: 5, badge: 'left'},
            {arrow: [{x: inner.x, y: inner.y + inner.h / 2}, {x: pal.x + pal.w / 2, y: inner.y + inner.h / 2}]},
            {text: 'パレットへすてる', at: {x: pal.x + 30, y: inner.y + inner.h / 2 - 16}},
        ]);
    }
    await dragBlock(inner, {x: pal.x + 60, y: inner.y}, {grab: {x: 20, y: inner.h / 2}});
    await clickCategory('ブロック定義');
    const pb = await scrollPaletteTo(t.def, 400);
    const slot = await slotNow();
    if (prefix) {
        await shot(prefix + '-g', [
            {box: pb, pad: 3, n: 6, badge: 'left'},
            {arrow: [{x: pb.x + pb.w + 4, y: pb.y + pb.h / 2}, {x: slot.x + 10, y: slot.y + 14}]},
            {box: {x: slot.x, y: slot.y, w: 120, h: 4}, pad: 3, label: '「もし」の中に入れる', labelAt: 'right'},
        ]);
    }
    // 上の『運行』の下に入らないように、口の少し下をねらう
    const sn = await slotNow();
    await dragBlock(pb, {x: sn.x + 6, y: sn.y + 18});
    const fin = await blockById(placed.id);
    const innerNow = (await blocks()).find(b => b.cls.startsWith('procedures_call') && b.sig.startsWith(t.def) && b.y > fin.y + 10 && b.y < fin.ay + fin.ah);
    if (!innerNow) throw new Error(t.def + ' が「もし」の中に入らなかった');
    if (prefix) await shot(prefix + '-h', [{box: stackBox(fin), pad: 3, n: '✓', badge: 'left', label: 'できた！', labelAt: 'right'}]);
    return fin;
}

// 「発車メロディ」スプライトで、曲をかえる。changes: [[駅, 曲], ...]
async function changeMelodies(changes, prefix) {
    await selectSprite('発車メロディ');
    const hat = await findBlock('設定を読み込む を受け取ったとき');
    await scrollBlockTo(hat.id, 130);
    const rows = [];
    for (const [st] of changes) rows.push(await findBlock(b => b.cls.startsWith('procedures_call') && b.sig.startsWith(`駅 ${st} の発車メロディは`)));
    if (prefix) {
        const marks = [{box: await box(spriteTile('発車メロディ')), n: 1, badge: 'left'}];
        let n = 2;
        for (let i = 0; i < rows.length; i++) {
            marks.push({box: (await fieldBoxes(rows[i].id))[1], pad: 3, n: n++, badge: 'right', label: '→ ' + changes[i][1], labelAt: 'right'});
        }
        await shot(prefix + '-a', marks);
    }
    for (let i = 0; i < rows.length; i++) await typeInField(rows[i].id, 1, changes[i][1]);
    await page.mouse.click(700, 785);
    if (prefix) {
        const bs = [];
        for (const r of rows) bs.push(await blockById(r.id));
        await shot(prefix + '-b', [{box: union(...bs), pad: 4, n: '✓', badge: 'left', label: '書きかえた', labelAt: 'right'}]);
    }
}

async function pressKey(k) {
    await page.keyboard.down(k);
    await wait(250);
    await page.keyboard.up(k);
}

// 全画面にして、緑の旗 → Enter → 番号 で走らせて撮る。steps: 撮る画面（'full' 全画面ボタン, 'menu' 路線をえらぶ画面, 'drive' 運転の画面）
async function tryRun(no, prefix, {steps = ['full', 'menu', 'drive'], driveLabel, menuLabel, wait: runWait = 14000, scrollMenu = false} = {}) {
    const full = page.locator('[class*="stage-header_stage-button"]').last();
    if (steps.includes('full')) await shot(prefix + '-a', [{box: await box(full), n: 1, badge: 'left', label: '全画面にする', labelAt: 'left'}]);
    await full.click();
    await wait(1500);
    const flag = page.locator('[class*="green-flag"]').first();
    await flag.click();
    await wait(5000);
    await page.mouse.click(W / 2, H / 2);
    await pressKey('Enter');
    await wait(2500);
    if (scrollMenu) {
        // 路線一覧のリストを下までスクロールして、5 と 6 を見せる
        await page.mouse.move(W / 2, 420);
        await page.mouse.wheel(0, 400);
        await wait(800);
    }
    if (steps.includes('menu')) {
        await shot(prefix + '-b', [{box: await box(flag), n: 2, badge: 'left'},
            {text: menuLabel || `緑の旗 → Enter キー → ${no} キー`, at: {x: 80, y: H - 22}}]);
    }
    await pressKey(no);
    await wait(runWait);
    if (steps.includes('drive')) await shot(prefix + '-c', driveLabel ? [{text: driveLabel, at: {x: 160, y: H - 18}}] : []);
    await page.locator('[class*="stop-all"]').first().click();
    await wait(800);
    // 全画面をやめる（ボタンは同じ場所）
    await page.locator('[class*="stage-header_stage-button"]').last().click();
    await wait(1500);
}

async function saveSb3(file) {
    await menuItem('ファイル').click();
    await wait(500);
    const dl = page.waitForEvent('download', {timeout: 120000});
    await fileMenuEntry(/コンピューターに保存する|Save to your computer/).click();
    const d = await dl;
    await d.saveAs(file);
    await closeFileMenu();
    console.log('  保存', file);
}

const defId = async label => (await findBlock(b => b.cls.startsWith('procedures_definition') && b.sig.includes(label))).id;

// ホームライナーの手順（ぜんぶ撮る）
async function partHome() {
    await addTrainType(HOME, '04-type');
    await addMenuLine(HOME, '05-menu');
    const def5 = await makeDefinition(HOME, '06-def');
    const def4 = await defId('運行4');
    await moveDefinitionBelow(def5, def4, '07-move');
    await copyBody(def4, def5, '08-copy');
    await rewrite(def5, [['運行を始める', 0, HOME.type], ['運行を始める', 1, '信早ヶ丘']], '09-start');
    await deleteInStack(def5, '区間を足す 路線 3', '10-del-section');
    await rewrite(def5, [['区間を足す', 2, '信早ヶ丘']], '11-section');
    await deleteInStack(def5, '停車 田原京', '12-del-stop');
    await rewrite(def5, [['停車 新信町', 1, HOME.stops[0][1]], ['停車 信町 ', 0, '二間六草'], ['停車 信町 ', 1, HOME.stops[1][1]],
        ['停車 高田', 1, HOME.stops[2][1]], ['停車 信町空港', 0, '信早ヶ丘'], ['停車 信町空港', 1, HOME.stops[3][1]]], '13-stops');
    await addToReadRoute(HOME, '運行4', '14-read', {
        // 失敗の例: 番号は 5 にしたが、中が『運行4』のまま → 5 でエアポート特快が走る
        afterNumber: async () => {
            await tryRun('5', '90-miss-inner', {steps: ['drive'], driveLabel: '5 を選んだのに、エアポート特快が走ってしまった'});
            await selectSprite('路線データ');
            await scrollBlockTo(await defId('路線を読む'), 130);
        },
    });
    await changeMelodies([['信町', 'CLEX203'], ['二間六草', 'CLEX202']], '15-melody');
    await tryRun('5', '16-run', {driveLabel: '「信町特急 ホームライナー 信早ヶ丘行」と出た！', scrollMenu: true});
}

// シティライナーの手順（ホームライナーとちがう所だけ撮る）
async function partCity({typeDone = false} = {}) {
    await selectSprite('路線データ');
    const hat = await findBlock('設定を読み込む を受け取ったとき');
    await scrollBlockTo(hat.id, 150);
    if (!typeDone) await addTrainType(CITY, null);
    await addMenuLine(CITY, null);
    const b = await blockById(hat.id);
    const rows = (await blocks()).filter(x => x.y > b.y && x.y < b.ay + b.ah &&
        (x.sig.startsWith(CITY.type) || x.sig.startsWith('種別を追加 ' + CITY.type)));
    await shot('20-city-settings', rows.map((r, i) => ({box: r, pad: 3, ...(i === 0 ? {n: 1, badge: 'left'} : {})})));
    const def6 = await makeDefinition(CITY, null, '運行5');
    const def5 = await defId('運行5');
    await moveDefinitionBelow(def6, def5, null);
    await copyBody(def5, def6, null);
    const d6 = await scrollBlockTo(def6, 300);
    const d5 = await blockById(def5);
    await shot('21-city-copied', [{box: stackBox(d5), pad: 3, label: 'ホームライナー（コピーのもと）', labelAt: 'above'},
        {box: stackBox(d6), pad: 3, n: 1, badge: 'left', label: '運行6 シティライナー（コピーしたところ）', labelAt: 'right'}]);
    await rewrite(def6, [['運行を始める', 0, CITY.type]], null);
    await deleteInStack(def6, '停車 高田', '22-city-del-takata');
    await rewrite(def6, [['停車 新信町', 1, CITY.stops[0][1]], ['停車 二間六草', 1, CITY.stops[1][1]], ['停車 信早ヶ丘', 1, CITY.stops[2][1]]], null);
    const fin = await blockById(def6);
    await shot('23-city-done', [{box: stackBox(fin), pad: 3, n: '✓', badge: 'left', label: 'シティライナーの中身', labelAt: 'right'}]);
    await addToReadRoute(CITY, '運行5', null, {
        // 失敗の例: 「もし」の番号が 5 のまま → 6 を選んでも列車のデータが読めない
        afterAttach: async () => {
            await tryRun('6', '91-miss-number', {steps: ['drive'], driveLabel: '6 を選んだのに、「列車」に種別が出ない'});
            await selectSprite('路線データ');
            await scrollBlockTo(await defId('路線を読む'), 130);
        },
    });
    const rr = await scrollBlockTo(await defId('路線を読む'), 130);
    await shot('24-city-read', [{box: stackBox(rr), pad: 3, n: '✓', badge: 'left', label: '5 と 6 の「もし」ができた', labelAt: 'right'}]);
    await tryRun('6', '25-city-run', {steps: ['menu', 'drive'], scrollMenu: true, menuLabel: '6 キーを押す', driveLabel: '「信町特急 シティライナー 信早ヶ丘行」と出た！'});
}

// 作者が ChatGPT と作った状態（種別を 9 こ足し、「なにか」を路線一覧に足した）から始める人のための写真
async function partKidState() {
    await partOpenSpriteQuiet();
    await clickCategory('ブロック定義');
    const names = [['信町特急', '10'], ['ホームライナー', '10'], ['シティライナー', '10'], ['信町特快', '10'], ['快速', '10'],
        ['通勤快速', '10'], ['区間快速', '10'], ['準快速', '10'], ['普通', '6']];
    for (const [n, c] of names) await addTrainType({type: n, cars: c}, null);
    // 「なにか を 路線一覧 に追加する」（文字はそのまま）
    await clickCategory('変数');
    const lines = (await findBlock(b => b.cls.startsWith('data_addtolist') && b.sig.includes('路線一覧'), {all: true})).sort((a, b) => a.y - b.y);
    const last = lines.at(-1);
    const pal = await scrollPaletteTo('なにか を', 420);
    const before = await idsNow();
    await dragBlock(pal, {x: last.x, y: last.y + last.h});
    const added = await newBlock(before, 'data_addtolist');
    const dd = (await fieldBoxes(added.id)).find(f => !f.shadow);
    await page.mouse.click(dd.x + dd.w - 10, dd.y + dd.h / 2);
    await wait(700);
    await page.locator('.blocklyDropDownDiv .blocklyMenuItem', {hasText: /^路線一覧$/}).first().click();
    await wait(600);
    const hat = await findBlock('設定を読み込む を受け取ったとき');
    await scrollBlockTo(hat.id, 110);
    const types = (await findBlock(b => b.cls.startsWith('procedures_call') && b.sig.startsWith('種別を追加'), {all: true}));
    const home = types.find(b => b.sig.startsWith('種別を追加 ホームライナー'));
    const city = types.find(b => b.sig.startsWith('種別を追加 シティライナー'));
    const nanika = await blockById(added.id);
    await shot('30-kid-before', [
        {box: (await fieldBoxes(nanika.id))[0], pad: 3, n: 1, badge: 'left', label: '→ ' + HOME.menu, labelAt: 'right'},
        {box: (await fieldBoxes(home.id))[0], pad: 3, n: 2, badge: 'left', label: '→ ' + HOME.type, labelAt: 'right'},
        {box: (await fieldBoxes(city.id))[0], pad: 3, n: 3, badge: 'left', label: '→ ' + CITY.type, labelAt: 'right'},
    ]);
    await typeInField(nanika.id, 0, HOME.menu);
    await typeInField(home.id, 0, HOME.type);
    await typeInField(city.id, 0, CITY.type);
    await page.mouse.click(700, 785);
    await wait(300);
    await shot('31-kid-after', [{box: await blockById(nanika.id), pad: 3, n: 1, badge: 'left'},
        {box: await blockById(home.id), pad: 3, n: 2, badge: 'left'}, {box: await blockById(city.id), pad: 3, n: 3, badge: 'left'}]);
}

async function partOpenSpriteQuiet() {
    await page.locator('[class*="stage-header_stage-button"]').first().click();
    await selectSprite('路線データ');
    const hat = await findBlock('設定を読み込む を受け取ったとき');
    await scrollBlockTo(hat.id, 150);
}

// 失敗の例: ブロックがくっつかずに浮いている
async function partFloating() {
    await partOpenSpriteQuiet();
    await clickCategory('ブロック定義');
    const types = await findBlock(b => b.cls.startsWith('procedures_call') && b.sig.startsWith('種別を追加'), {all: true});
    const last = types.at(-1);
    const pal = await scrollPaletteTo('種別を追加', 420);
    await dragBlock(pal, {x: last.x + 260, y: last.y + 60});
    await shot('92-miss-floating', [{text: 'すき間があいて、浮いている', at: {x: last.x + 260, y: last.y + 140}}]);
}

const browser = await openGui();
try {
    if (!ONLY || ONLY === 'main') {
        await loadSb3(SB3);
        await partBackup();
        await partOpenSprite();
        await partHome();
        await partCity();
        await selectSprite('路線データ');
        await tryRun('5', '17-final-menu', {steps: ['menu'], menuLabel: 'メニューに 5 と 6 が出た', wait: 1000, scrollMenu: true});
        if (SAVE) await saveSb3(SAVE);
    }
    if (!ONLY || ONLY === 'kid') {
        await loadSb3(SB3);
        await partKidState();
    }
    if (!ONLY || ONLY === 'mistakes') {
        await loadSb3(SB3);
        await partFloating();
    }
} finally {
    await browser.close();
    server.close();
}
// pngquant があれば、色数をへらしてファイルを小さくする（見た目はほぼ同じ）
if (spawnSync('pngquant', ['--version']).status === 0) {
    for (const f of fs.readdirSync(OUT).filter(f => f.endsWith('.png'))) {
        spawnSync('pngquant', ['--quality', '70-90', '--speed', '1', '--force', '--skip-if-larger', '--ext', '.png', path.join(OUT, f)]);
    }
}
console.log(`${shotCount} 枚撮った`);
