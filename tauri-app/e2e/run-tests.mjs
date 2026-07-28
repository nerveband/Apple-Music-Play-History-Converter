// E2E Test Suite for Apple Music History Converter
// Runs against the real app via tauri-plugin-mcp socket
import MCPClient from './mcp-client.mjs';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

const SCREENSHOT_DIR = process.env.SCREENSHOT_DIR ||
  path.join(os.tmpdir(), 'apple-music-converter-e2e-screenshots');
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const results = [];
let client;

function log(msg) { console.log(`  ${msg}`); }

async function test(name, fn) {
  process.stdout.write(`TEST: ${name} ... `);
  try {
    await fn();
    console.log('PASS');
    results.push({ name, status: 'PASS' });
  } catch (e) {
    console.log(`FAIL: ${e.message}`);
    results.push({ name, status: 'FAIL', error: e.message });
  }
}

function assert(condition, msg) {
  if (!condition) throw new Error(msg || 'Assertion failed');
}

async function js(code) {
  return client.executeJs(code);
}

async function jsJson(code) {
  const result = await js(code);
  return JSON.parse(result);
}

// ============================================================
// TEST SUITE
// ============================================================

async function runTests() {
  client = new MCPClient();
  await client.connect();
  log('Connected to MCP socket\n');

  // ----------------------------------------------------------
  // 1. APP LIFECYCLE
  // ----------------------------------------------------------
  console.log('=== APP LIFECYCLE ===');

  await test('App has correct name', async () => {
    const info = await client.appInfo();
    assert(
      info.app.name === 'Apple Music History Converter' ||
      info.app.name === 'apple-music-history-converter',
      `Name: ${info.app.name}`
    );
  });

  await test('App version is 3.0.3', async () => {
    const info = await client.appInfo();
    assert(info.app.version === '3.0.3', `Version: ${info.app.version}`);
  });

  await test('Main window is visible', async () => {
    const info = await client.appInfo();
    const win = info.windows.find(w => w.label === 'main');
    assert(win, 'Main window not found');
    assert(win.visible, 'Window not visible');
  });

  await test('Window has reasonable dimensions', async () => {
    const info = await client.appInfo();
    const win = info.windows.find(w => w.label === 'main');
    assert(win.size.width >= 900, `Width too small: ${win.size.width}`);
    assert(win.size.height >= 600, `Height too small: ${win.size.height}`);
  });

  await test('App URL is localhost dev server', async () => {
    const url = await js('return window.location.href');
    assert(url.includes('localhost'), `URL: ${url}`);
  });

  // ----------------------------------------------------------
  // 2. HEADER
  // ----------------------------------------------------------
  console.log('\n=== HEADER ===');

  await test('App title/logo visible', async () => {
    const text = await js('return document.body.innerText');
    assert(
      text.includes('Apple Music') || text.includes('History Converter'),
      'App title not found'
    );
  });

  await test('Theme toggle button exists', async () => {
    const data = await jsJson(`
      var btns = document.querySelectorAll('button');
      var found = false;
      for (var i = 0; i < btns.length; i++) {
        var title = btns[i].getAttribute('title') || '';
        var aria = btns[i].getAttribute('aria-label') || '';
        var text = btns[i].textContent || '';
        if (title.toLowerCase().includes('theme') || aria.toLowerCase().includes('theme') ||
            title.toLowerCase().includes('dark') || title.toLowerCase().includes('light')) {
          found = true; break;
        }
      }
      return JSON.stringify({ found: found });
    `);
    assert(data.found, 'Theme toggle not found');
  });

  await test('Help button exists', async () => {
    const data = await jsJson(`
      var btns = document.querySelectorAll('button');
      var found = false;
      for (var i = 0; i < btns.length; i++) {
        var title = btns[i].getAttribute('title') || '';
        if (title.toLowerCase().includes('help') || title.toLowerCase().includes('about')) {
          found = true; break;
        }
      }
      return JSON.stringify({ found: found });
    `);
    assert(data.found, 'Help/About button not found');
  });

  // ----------------------------------------------------------
  // 3. FILE SELECTION
  // ----------------------------------------------------------
  console.log('\n=== FILE SELECTION ===');

  await test('File selection area visible', async () => {
    const text = await js('return document.body.innerText');
    assert(
      text.includes('Select') || text.includes('Choose') || text.includes('Drop') ||
      text.includes('CSV') || text.includes('file'),
      'File selection area not found'
    );
  });

  await test('Browse/Select file button exists', async () => {
    const data = await jsJson(`
      var btns = document.querySelectorAll('button');
      var found = false;
      for (var i = 0; i < btns.length; i++) {
        var text = btns[i].textContent.toLowerCase();
        if (text.includes('select') || text.includes('browse') || text.includes('choose') || text.includes('open')) {
          found = true; break;
        }
      }
      return JSON.stringify({ found: found });
    `);
    assert(data.found, 'File select button not found');
  });

  // Take initial screenshot
  const initialShot = await client.screenshot({ output_dir: SCREENSHOT_DIR });
  log(`Initial screenshot: ${initialShot.filePath}`);

  // ----------------------------------------------------------
  // 4. SETTINGS SIDEBAR
  // ----------------------------------------------------------
  console.log('\n=== SETTINGS SIDEBAR ===');

  await test('Settings sidebar toggle exists', async () => {
    const data = await jsJson(`
      var btns = document.querySelectorAll('button');
      var found = false;
      for (var i = 0; i < btns.length; i++) {
        var title = btns[i].getAttribute('title') || '';
        var aria = btns[i].getAttribute('aria-label') || '';
        if (title.toLowerCase().includes('settings') || title.toLowerCase().includes('sidebar') ||
            aria.toLowerCase().includes('settings')) {
          found = true; break;
        }
      }
      return JSON.stringify({ found: found });
    `);
    assert(data.found, 'Settings sidebar toggle not found');
  });

  await test('Search provider selector visible', async () => {
    const text = await js('return document.body.innerText');
    assert(
      text.includes('MusicBrainz') || text.includes('iTunes') || text.includes('Provider') ||
      text.includes('Apple Music') || text.includes('Search Service'),
      'Provider selector not found'
    );
  });

  await test('External app storage control is visible', async () => {
    const text = await js('return document.body.innerText');
    assert(text.toLowerCase().includes('app storage'), 'App Storage control not found');
    const data = await jsJson(`
      var input = document.querySelector('[aria-label="App storage location"]');
      return JSON.stringify({ found: !!input });
    `);
    assert(data.found, 'App storage path input not found');
  });

  await test('Export format selector visible', async () => {
    const text = await js('return document.body.innerText');
    assert(
      text.includes('Last.fm') || text.includes('ListenBrainz') || text.includes('Spotify') ||
      text.includes('Export') || text.includes('Format'),
      'Export format selector not found'
    );
  });

  await test('Database section visible', async () => {
    const text = await js('return document.body.innerText');
    assert(
      text.includes('Database') || text.includes('MusicBrainz') || text.includes('Download'),
      'Database section not found'
    );
  });

  // Take settings screenshot
  const settingsShot = await client.screenshot({ output_dir: SCREENSHOT_DIR });
  log(`Settings screenshot: ${settingsShot.filePath}`);

  // ----------------------------------------------------------
  // 5. LOG PANEL
  // ----------------------------------------------------------
  console.log('\n=== LOG PANEL ===');

  await test('Log panel or toggle exists', async () => {
    const data = await jsJson(`
      var found = false;
      var btns = document.querySelectorAll('button');
      for (var i = 0; i < btns.length; i++) {
        var text = btns[i].textContent.toLowerCase();
        var title = (btns[i].getAttribute('title') || '').toLowerCase();
        if (text.includes('log') || title.includes('log')) {
          found = true; break;
        }
      }
      if (!found) {
        var text = document.body.innerText;
        found = text.includes('Log') || text.includes('Console');
      }
      return JSON.stringify({ found: found });
    `);
    assert(data.found, 'Log panel/toggle not found');
  });

  // ----------------------------------------------------------
  // 6. BOTTOM TABS (Preview / Results)
  // ----------------------------------------------------------
  console.log('\n=== TABS ===');

  await test('Initial content state is valid before a CSV is loaded', async () => {
    const text = await js('return document.body.innerText');
    const normalized = text.toLowerCase();
    assert(
      normalized.includes('preview') || normalized.includes('results') ||
      normalized.includes('table') || normalized.includes('select or drop csv'),
      'Neither file-selection nor loaded-results state was found'
    );
  });

  // ----------------------------------------------------------
  // 7. DOM & MCP TOOLS VERIFICATION
  // ----------------------------------------------------------
  console.log('\n=== MCP TOOLS ===');

  await test('get_page_map returns element tree', async () => {
    const data = await client.send('get_page_map', { window_label: 'main', include_content: true });
    assert(data, 'No page map returned');
    const str = typeof data === 'string' ? data : JSON.stringify(data);
    assert(str.length > 100, `Page map too short: ${str.length} chars`);
  });

  await test('get_page_state returns page metadata', async () => {
    const data = await client.send('get_page_state', { window_label: 'main' });
    assert(data, 'No page state returned');
    const str = typeof data === 'string' ? data : JSON.stringify(data);
    assert(str.includes('localhost') || str.includes('Apple Music'), `Unexpected: ${str.substring(0, 200)}`);
  });

  await test('Screenshot saves to disk', async () => {
    const shot = await client.screenshot({ output_dir: SCREENSHOT_DIR });
    assert(shot.filePath, 'No file path in screenshot response');
    assert(fs.existsSync(shot.filePath), `Screenshot file not found: ${shot.filePath}`);
    const stat = fs.statSync(shot.filePath);
    assert(stat.size > 1000, `Screenshot too small: ${stat.size} bytes`);
    log(`  Screenshot: ${shot.filePath} (${Math.round(stat.size / 1024)}KB)`);
  });

  await test('execute_js can query React state', async () => {
    const result = await js('return typeof window.__TAURI__ !== "undefined" ? "tauri" : "web"');
    assert(result === 'tauri' || result === 'web', `Unexpected: ${result}`);
  });

  // ----------------------------------------------------------
  // 8. CROSS-PLATFORM CHECKS
  // ----------------------------------------------------------
  console.log('\n=== PLATFORM ===');

  await test('Platform detected correctly', async () => {
    const platform = await jsJson(`
      var ua = navigator.userAgent;
      var isWin = ua.includes('Windows');
      var isMac = ua.includes('Macintosh') || ua.includes('Mac OS');
      var isLinux = ua.includes('Linux');
      return JSON.stringify({ isWin: isWin, isMac: isMac, isLinux: isLinux, ua: ua.substring(0, 80) });
    `);
    assert(platform.isWin || platform.isMac || platform.isLinux, `Unknown platform: ${platform.ua}`);
    log(`  Platform: ${platform.isWin ? 'Windows' : platform.isMac ? 'macOS' : 'Linux'}`);
  });

  // ----------------------------------------------------------
  // RESULTS
  // ----------------------------------------------------------
  console.log('\n\n========================================');
  console.log('     E2E TEST RESULTS SUMMARY');
  console.log('========================================\n');

  const passed = results.filter(r => r.status === 'PASS').length;
  const failed = results.filter(r => r.status === 'FAIL').length;

  for (const r of results) {
    const icon = r.status === 'PASS' ? 'PASS' : 'FAIL';
    console.log(`  [${icon}] ${r.name}${r.error ? ` -- ${r.error}` : ''}`);
  }

  console.log(`\n  Total: ${results.length}  Passed: ${passed}  Failed: ${failed}`);

  // Save results to JSON
  const resultFile = path.join(SCREENSHOT_DIR, '..', 'test-results.json');
  fs.writeFileSync(resultFile, JSON.stringify({
    timestamp: new Date().toISOString(),
    platform: process.platform,
    total: results.length,
    passed,
    failed,
    results
  }, null, 2));
  console.log(`  Results: ${resultFile}\n`);

  client.close();
  process.exit(failed > 0 ? 1 : 0);
}

runTests().catch(e => {
  console.error('Test runner error:', e);
  if (client) client.close();
  process.exit(1);
});
