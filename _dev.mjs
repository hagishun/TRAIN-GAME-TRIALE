// 一時的な確認用（あとで消す）
import fs from 'fs';
import path from 'path';
import {createRequire} from 'module';
import {chromium} from 'playwright';
const require = createRequire(import.meta.url);
const Packager = require('@turbowarp/packager');
const OUT = '/tmp/dev'; fs.mkdirSync(OUT, {recursive: true});
const project = await Packager.loadProject(fs.readFileSync('train-driver-3d.sb3'));
const pk = new Packager.Packager(); pk.project = project; pk.options.autoplay = true; pk.options.compiler.enabled = process.env.COMPILER !== '0';
fs.writeFileSync('/tmp/dev/game.html', (await pk.package()).data);
const browser = await chromium.launch();
const page = await browser.newPage({viewport: {width: 960, height: 720}});
const errors = []; page.on('pageerror', e => errors.push(String(e)));
await page.goto('file:///tmp/dev/game.html');
await page.waitForFunction(() => window.scaffolding && scaffolding.vm.runtime.targets.length > 5, null, {timeout: 60000});
await page.evaluate(() => {
  const vm = scaffolding.vm, st = vm.runtime.getTargetForStage();
  const v = n => Object.values(st.variables).find(x => x.name === n);
  const orig = vm.runtime._step.bind(vm.runtime); window.STEP = {n: 0, ms: 0, max: 0};
  vm.runtime._step = function () { const t0 = performance.now(); orig(); const d = performance.now() - t0; STEP.n++; STEP.ms += d; STEP.max = Math.max(STEP.max, d); };
  window.T = {vm, get: n => v(n).value, set: (n, x) => { v(n).value = x; },
    local: (s, n) => Object.values(vm.runtime.targets.find(t => t.isOriginal && t.getName() === s).variables).find(x => x.name === n)};
});
await page.waitForFunction(() => T.get('場面') === 'タイトル');
const route = Number(process.argv[2] || 3);
await page.keyboard.down('Enter'); await page.waitForTimeout(150); await page.keyboard.up('Enter');
await page.waitForFunction(() => T.get('場面') === '路線選択');
await page.waitForTimeout(300);
await page.keyboard.down(String(route)); await page.waitForTimeout(150); await page.keyboard.up(String(route));
await page.waitForFunction(() => T.get('場面') === '運転中', null, {timeout: 60000});
const steps = JSON.parse(process.argv[3] || '[]');
for (const st of steps) {
  if (st.eval) await page.evaluate('(' + st.eval + ')()');
  if (st.tp) await page.evaluate(({pos, speed, notch}) => {
    T.set('位置', pos); T.set('速度', speed); T.set('ノッチ', notch); T.set('場面', '運転中'); T.set('ドア', '閉');
    T.set('ブレーキ率', notch < 0 ? -notch / 8 : 0); T.set('力行率', notch > 0 ? notch / 5 : 0);
    T.local('運転', 'ジョイント番号').value = Math.floor(pos / 25);
    for (const n of ['ATS状態']) T.set(n, 0);
  }, st.tp);
  if (st.reset) await page.evaluate(() => { STEP.n = 0; STEP.ms = 0; STEP.max = 0; });
  if (st.wait) await page.waitForTimeout(st.wait);
  if (st.perf) console.log('perf', await page.evaluate(() => JSON.stringify({frames: STEP.n, avgMs: (STEP.ms / STEP.n).toFixed(2), maxMs: STEP.max.toFixed(1)})));
  if (st.shot) { await page.locator('canvas').first().screenshot({path: path.join(OUT, st.shot)}); console.log('shot', st.shot, await page.evaluate(() => JSON.stringify({pos: Math.round(T.get('位置')), v: Math.round(T.get('速度')), planes: T.get('飛行機の位置').map(Math.round), h: T.get('飛行機の高さ').map(Math.round)}))); }
}
console.log('errors', errors);
await browser.close();
