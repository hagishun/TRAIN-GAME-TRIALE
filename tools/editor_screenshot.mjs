// TurboWarp エディタ（Scratch エディタと同じ見た目）に .sb3 を読み込んで、
// コメント付きのブロックの画面をスクリーンショットする。
//
//   node tools/editor_screenshot.mjs
//
// エディタの「ファイル → コンピューターから読み込む」で読み込ませる（日本語表示）。
import path from 'path';
import {chromium} from 'playwright';

const ROOT = path.join(path.dirname(new URL(import.meta.url).pathname), '..');
const SB3 = path.join(ROOT, 'train-driver-3d.sb3');
const OUT = path.join(ROOT, 'docs', 'screenshots');

const browser = await chromium.launch();
try {
    const context = await browser.newContext({viewport: {width: 1600, height: 1000}, locale: 'ja-JP'});
    // TurboWarp は File System Access API を使うので、ふつうのファイル選択に戻す
    await context.addInitScript(() => { delete window.showOpenFilePicker; delete window.showSaveFilePicker; });
    const page = await context.newPage();
    page.on('dialog', d => d.accept().catch(() => {}));
    await page.goto('https://turbowarp.org/editor', {waitUntil: 'domcontentloaded', timeout: 90000});
    await page.waitForSelector('[class*="menu-bar_menu-bar-item"]', {timeout: 90000});
    await page.waitForTimeout(3000);
    await page.locator('[class*="menu-bar_menu-bar-item"]', {hasText: /^(ファイル|File)$/}).first().click();
    const chooserPromise = page.waitForEvent('filechooser', {timeout: 30000});
    await page.locator('[class*="menu_menu-item"]', {hasText: /コンピューターから読み込む|Load from your computer/}).first().click();
    const chooser = await chooserPromise;
    await chooser.setFiles(SB3);
    // 読み込みが終わり、スプライト一覧に「路線データ」が出るまで待つ
    await page.waitForSelector('text=路線データ', {timeout: 90000});
    await page.waitForTimeout(3000);
    // 小さいステージにして、コードを広く見せる
    await page.locator('[class*="stage-header_stage-button"]').first().click().catch(() => {});
    await page.waitForTimeout(1000);
    for (const [sprite, file] of [['路線データ', '20-editor-route-data.png'], ['設定', '21-editor-settings.png'],
        ['運転', '22-editor-drive.png']]) {
        await page.locator('[class*="sprite-selector-item_sprite-name"]', {hasText: new RegExp(`^${sprite}$`)}).first().click();
        await page.waitForTimeout(2500);
        await page.screenshot({path: path.join(OUT, file)});
        console.log('  saved', file);
        if (sprite === '路線データ') {
            // 下にスクロールして「路線1 信町本線」の駅のブロックを見せる
            await page.mouse.move(700, 600);
            await page.mouse.wheel(0, 760);
            await page.waitForTimeout(1500);
            await page.screenshot({path: path.join(OUT, '23-editor-route-stations.png')});
            console.log('  saved 23-editor-route-stations.png');
        }
    }
} catch (e) {
    console.error('エディタのスクリーンショットに失敗:', e.message);
    process.exitCode = 1;
} finally {
    await browser.close();
}
