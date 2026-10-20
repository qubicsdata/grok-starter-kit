import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const temporary = await mkdtemp(join(tmpdir(), 'folio-browser-'));
const output = join(root, '.browser-tests');
await mkdir(output, { recursive: true });
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
let server;
let chrome;
let socket;
let nextId = 0;
const pending = new Map();
const errors = [];

const delay = milliseconds => new Promise(resolveDelay => setTimeout(resolveDelay, milliseconds));
async function until(callback, label, timeout = 15000) {
  const deadline = Date.now() + timeout;
  let lastError;
  while (Date.now() < deadline) {
    try { const result = await callback(); if (result) return result; } catch (error) { lastError = error; }
    await delay(80);
  }
  throw new Error(`Timed out: ${label}${lastError ? ` (${lastError.message})` : ''}`);
}

function command(method, params = {}) {
  return new Promise((resolveCommand, reject) => {
    const id = ++nextId;
    const timeout = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 15000);
    pending.set(id, { resolve: result => { clearTimeout(timeout); resolveCommand(result); }, reject: error => { clearTimeout(timeout); reject(error); } });
    socket.send(JSON.stringify({ id, method, params }));
  });
}

function waitForEvent(method, timeout = 15000) {
  return new Promise((resolveEvent, reject) => {
    const timer = setTimeout(() => { socket.removeEventListener('message', handler); reject(new Error(`Timed out waiting for ${method}`)); }, timeout);
    const handler = event => {
      const message = JSON.parse(event.data);
      if (message.method === method) { clearTimeout(timer); socket.removeEventListener('message', handler); resolveEvent(message.params); }
    };
    socket.addEventListener('message', handler);
  });
}

async function evaluate(expression) {
  const result = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true, userGesture: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
}
const click = selector => evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
const input = (selector, value) => evaluate(`(() => { const element = document.querySelector(${JSON.stringify(selector)}); element.value = ${JSON.stringify(value)}; element.dispatchEvent(new Event('input', {bubbles:true})); element.dispatchEvent(new Event('change', {bubbles:true})); })()`);
const visible = selector => until(() => evaluate(`Boolean(document.querySelector(${JSON.stringify(selector)}))`), selector);
const modalClosed = () => until(() => evaluate('!document.querySelector("#modal").open'), 'modal closes after save');
const saveModal = async () => { await evaluate('document.querySelector("#modal-form").requestSubmit()'); await modalClosed(); };
const screenshot = async name => {
  await evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))');
  await evaluate('Promise.all(document.getAnimations().map(animation => animation.finished.catch(() => {})))');
  const result = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  await writeFile(join(output, name), Buffer.from(result.data, 'base64'));
};

// Demo mode left with WP-6 (/api/demo is 404): the fixture workspace is seeded through the owner API
// with the same shape the demo used to give (3 clients, 4 projects, the first project with its 3
// default workstreams, one blocked and one overdue task = 2 attention items).
async function seedWorkspace(base, ownerToken) {
  const call = async (path, body) => {
    const response = await fetch(base + path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Workspace-Token': ownerToken }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok) throw new Error(`seed ${path}: ${JSON.stringify(data)}`);
    return data;
  };
  const revisionOf = async id => (await (await fetch(base + '/api/state', { headers: { 'X-Workspace-Token': ownerToken } })).json()).projects.find(project => project.id === id).revision;
  const withRevision = async (path, id, body) => call(path, { ...body, revision: await revisionOf(id) });
  const day = offset => new Date(Date.now() + offset * 86400000).toISOString().slice(0, 10);
  const clients = {};
  for (const [name, color] of [['Northstar Financial', 'purple'], ['Meridian Health', 'teal'], ['Orbit Retail', 'orange']]) clients[name] = await call('/api/clients', { name, color });
  const cloud = await call('/api/projects', { client_id: clients['Northstar Financial'].id, name: 'Cloud foundation', description: 'A secure, scalable landing zone.', target_date: day(30) });
  assert.equal(cloud.workstreams.length, 3, 'a new project starts with three default workstreams');
  const streams = cloud.workstreams.map(stream => stream.id);
  await withRevision(`/api/projects/${cloud.id}/tasks`, cloud.id, { title: 'Design the multi-account landing zone', status: 'in_progress', priority: 'high', due_date: day(3), workstream_id: streams[0] });
  await withRevision(`/api/projects/${cloud.id}/tasks`, cloud.id, { title: 'Validate network connectivity approach', status: 'blocked', priority: 'high', due_date: day(5), blocker: 'Waiting on address ranges.', workstream_id: streams[1] });
  await withRevision(`/api/projects/${cloud.id}/tasks`, cloud.id, { title: 'Align stakeholders on success criteria', status: 'done', priority: 'medium', due_date: day(-4), workstream_id: streams[2] });
  const data = await call('/api/projects', { client_id: clients['Northstar Financial'].id, name: 'Data platform modernization', target_date: day(30) });
  await withRevision(`/api/projects/${data.id}/tasks`, data.id, { title: 'Map source systems and data owners', status: 'backlog', priority: 'medium', due_date: day(-2), workstream_id: data.workstreams[0].id });
  await call('/api/projects', { client_id: clients['Meridian Health'].id, name: 'Patient experience platform', target_date: day(30) });
  await call('/api/projects', { client_id: clients['Orbit Retail'].id, name: 'Commerce replatforming', target_date: day(30) });
}

try {
  const serverCommand = process.env.FOLIO_SERVER_COMMAND ? JSON.parse(process.env.FOLIO_SERVER_COMMAND) : ['python3', 'server.py'];
  assert.ok(Array.isArray(serverCommand) && serverCommand.length && serverCommand.every(value => typeof value === 'string' && value), 'FOLIO_SERVER_COMMAND must be a JSON argument array');
  server = spawn(serverCommand[0], [...serverCommand.slice(1), '--data-dir', join(temporary, 'workspace'), '--port', '0'], { cwd: process.env.FOLIO_SERVER_COMMAND ? temporary : root, stdio: ['ignore', 'pipe', 'pipe'] });
  let serverOutput = '';
  server.stdout.on('data', chunk => { serverOutput += chunk; });
  server.stderr.on('data', () => {});
  const base = await until(() => serverOutput.match(/http:\/\/127\.0\.0\.1:\d+/)?.[0], 'local test server');
  const profile = join(temporary, 'chrome');
  // Hosted Linux runners restrict Chromium's user namespaces. This applies only
  // to the isolated CI profile visiting our temporary local fixture server.
  const ciLinux = process.platform === 'linux' && process.env.CI === 'true';
  chrome = spawn(chromePath, ['--headless=new', ...(ciLinux ? ['--no-sandbox'] : []), '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--disable-background-networking', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { stdio: ['ignore', 'ignore', 'pipe'] });
  let chromeOutput = '';
  chrome.stderr.on('data', chunk => { chromeOutput = (chromeOutput + chunk).slice(-8000); });
  chrome.on('error', error => { chromeOutput += `\n${error.message}`; });
  let port;
  try {
    port = await until(async () => (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0], 'headless Chrome');
  } catch (error) {
    throw new Error(`${error.message}\nChrome startup output:\n${chromeOutput || '(no stderr)'}`);
  }
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  socket = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolveOpen, reject) => { socket.addEventListener('open', resolveOpen, { once: true }); socket.addEventListener('error', reject, { once: true }); });
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const request = pending.get(message.id); pending.delete(message.id);
      if (message.error) request.reject(new Error(message.error.message)); else request.resolve(message.result);
    }
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    if (message.method === 'Log.entryAdded' && message.params.entry.level === 'error' && message.params.entry.source !== 'network') errors.push(message.params.entry.text);
  });
  await command('Page.enable');
  await command('Runtime.enable');
  await command('Log.enable');
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1060, deviceScaleFactor: 1, mobile: false });
  const discovery = JSON.parse(await readFile(join(temporary, 'workspace', '.server.json'), 'utf8'));
  await command('Page.navigate', { url: base + '/#folio-launch=' + discovery.browser_token });
  await visible('.welcome');
  assert.equal(await evaluate('document.querySelector("[data-action=demo]")'), null, 'the demo button is gone with demo mode');
  await screenshot('welcome.png');
  await seedWorkspace(base, discovery.owner_token);
  await click('[data-action="refresh"]');
  await visible('.project-card');
  assert.equal(await evaluate('document.querySelectorAll(".project-card").length'), 4);
  assert.equal(await evaluate('document.querySelectorAll(".client-row").length'), 3);
  assert.equal(await evaluate('document.querySelectorAll(".attention-item").length'), 2);
  await screenshot('portfolio.png');
  console.log('PASS empty workspace, API-seeded portfolio rollups, and attention items');

  await click('[data-action="storage"]');
  await visible('.workspace-about');
  assert.equal(await evaluate('document.querySelector("#appearance-theme")'), null, 'the appearance setting is gone with themes');
  assert.equal(await evaluate('document.querySelector("[data-action=download-backup]")'), null, 'the backup download is gone with /api/backup');
  assert.equal(await evaluate('document.querySelector("[data-action=doctor]")'), null, 'the health check is gone with /api/doctor');
  const expectedVersion = (await readFile(join(root, 'folio/__init__.py'), 'utf8')).match(/__version__ = "([^"]+)"/)[1];
  assert.equal(await evaluate('document.querySelector(".about-version").textContent'), `Folio ${expectedVersion}`);
  // No "about" object in the local config: the About panel shows no attribution, website or help link.
  for (const selector of ['.about-attribution', '.about-website', '.about-help']) {
    assert.equal(await evaluate(`document.querySelector(${JSON.stringify(selector)})`), null, `${selector} is hidden without an about config`);
  }
  for (const [selector, filename] of [['.about-license', 'LICENSE'], ['.about-notice', 'NOTICE']]) {
    const legal = await evaluate(`fetch(document.querySelector(${JSON.stringify(selector)}).href).then(r => ({status:r.status, type:r.headers.get('Content-Type'), body:r.text()})).then(async x=>({...x,body:await x.body}))`);
    assert.equal(legal.status, 200); assert.match(legal.type, /^text\/plain/);
    assert.equal(legal.body, await readFile(join(root, filename), 'utf8'));
    assert.equal(await evaluate(`document.querySelector(${JSON.stringify(selector)}).rel`), 'noopener noreferrer');
  }
  await evaluate('document.querySelector(".workspace-about").scrollIntoView({block:"end"})');
  await screenshot('about.png');
  await click('[data-action="close-modal"]');
  console.log('PASS About reports installed version, Apache-2.0, exact packaged LICENSE/NOTICE and public-facing attribution/help links');

  // Appearance follows the operating system only (the theme switch left with WP-6).
  const emulateAppearance = value => command('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value }] });
  const background = () => evaluate('getComputedStyle(document.body).backgroundColor');
  await emulateAppearance('dark');
  await until(async () => (await background()) === 'rgb(7, 13, 15)', 'dark follows the OS appearance');
  assert.equal(await evaluate('document.documentElement.getAttribute("data-theme")'), null);
  assert.equal(await evaluate('localStorage.getItem("folio.theme")'), null);
  await emulateAppearance('light');
  await until(async () => (await background()) === 'rgb(247, 250, 250)', 'light follows the OS appearance');
  console.log('PASS appearance follows the OS with no stored choice');

  await click('.client-row');
  await until(() => evaluate('document.querySelectorAll(".project-card").length === 2'), 'client projects');
  await click('.project-card');
  await visible('.workstream-card');
  assert.equal(await evaluate('document.querySelectorAll(".workstream-card").length'), 3);
  await click('[data-action="new-stream"]');
  await input('#modal [name="name"]', 'Security & compliance');
  await saveModal();
  await until(() => evaluate('document.querySelectorAll(".workstream-card").length === 4'), 'new workstream');
  console.log('PASS client/project navigation and workstream creation');

  await click('[data-action="new-task"]');
  await input('#modal [name="title"]', 'Browser test: architecture acceptance');
  await input('#modal [name="description"]', 'Verify the end-to-end editing flow.');
  await evaluate('document.querySelector("#modal [name=description]").focus(); window.__appearanceDraftNode = document.activeElement');
  await emulateAppearance('dark');
  await until(async () => (await background()) === 'rgb(7, 13, 15)', 'open form follows system dark appearance');
  assert.equal(await evaluate('document.activeElement === window.__appearanceDraftNode'), true, 'OS changes preserve the focused form element');
  assert.equal(await evaluate('document.querySelector("#modal [name=description]").value'), 'Verify the end-to-end editing flow.');
  assert.equal(await evaluate('document.querySelector("#modal [name=title]").value'), 'Browser test: architecture acceptance');
  await emulateAppearance('light');
  await input('#modal [name="owner"]', 'Test Architect');
  await input('#modal [name="priority"]', 'high');
  await input('#modal [name="status"]', 'blocked');
  await input('#modal [name="blocker"]', 'Awaiting stakeholder approval');
  await input('#modal [name="due_date"]', '2026-09-18');
  await saveModal();
  await click('[data-action="tab"][data-tab="tasks"]');
  await visible('#task-search');
  await input('#task-search', 'Browser test:');
  assert.equal(await evaluate('document.querySelectorAll(".task-table tbody tr").length'), 1);
  await click('.task-title-button');
  assert.equal(await evaluate('document.querySelector("#modal [name=owner]").value'), 'Test Architect');
  await input('#modal [name="status"]', 'done');
  await saveModal();
  await visible('.completed-task');
  await click('[data-action="clear-filters"]');
  await click('[data-layout="board"]');
  await visible('.kanban-card');
  await screenshot('project-board.png');
  await evaluate(`(() => { const card = [...document.querySelectorAll('.kanban-card')].find(element => element.textContent.includes('Browser test:')); const transfer = new DataTransfer(); card.dispatchEvent(new DragEvent('dragstart', {bubbles:true,dataTransfer:transfer})); document.querySelector('[data-drop-status="in_progress"]').dispatchEvent(new DragEvent('drop', {bubbles:true,dataTransfer:transfer})); })()`);
  await until(() => evaluate('document.querySelector("[data-drop-status=in_progress]").textContent.includes("Browser test:")'), 'board move persisted');
  console.log('PASS task creation, search, editing, completion, and drag-and-drop');

  await click('[data-action="tab"][data-tab="notes"]');
  await visible('#project-notes');
  await input('#project-notes', 'Decision: use managed infrastructure.\nNext: stakeholder review.');
  await click('[data-action="tab"][data-tab="overview"]');
  await visible('.workstream-card');
  await click('[data-action="tab"][data-tab="notes"]');
  await visible('#project-notes');
  assert.equal(await evaluate('document.querySelector("#project-notes").value'), 'Decision: use managed infrastructure.\nNext: stakeholder review.');
  await evaluate('document.querySelector("#notes-form").requestSubmit()');
  await until(() => evaluate('document.querySelector("#notes-status")?.textContent.includes("Saved")'), 'notes save');
  const reloaded = waitForEvent('Page.loadEventFired');
  await command('Page.reload');
  await reloaded;
  await until(() => evaluate('document.querySelector("#project-notes")?.value === ' + JSON.stringify('Decision: use managed infrastructure.\nNext: stakeholder review.')), 'notes reloaded');
  await input('#project-notes', 'Unsaved local draft');
  await evaluate(`(async () => {
    const snapshot = await (await fetch('/api/state', {headers: {'X-Folio-Session':sessionStorage.getItem('folio.sessionProof')}})).json();
    const project = snapshot.projects.find(item => item.name === 'Cloud foundation');
    const response = await fetch('/api/projects/' + project.id, {method:'PATCH', headers:{'Content-Type':'application/json','X-Folio-Session':sessionStorage.getItem('folio.sessionProof'),'X-Workspace-Token':snapshot.csrf_token},body:JSON.stringify({notes:'Saved by another window',revision:project.revision})});
    if (!response.ok) throw new Error('Concurrent note update failed');
  })()`);
  await evaluate('document.querySelector("#notes-form").requestSubmit()');
  await until(() => evaluate('document.querySelector("#toast").textContent.includes("changed in another window")'), 'notes conflict feedback');
  assert.equal(await evaluate('document.querySelector("#project-notes").value'), 'Unsaved local draft');
  await command('Page.handleJavaScriptDialog', { accept: true }).catch(() => {});
  const dialogHandler = event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Page.javascriptDialogOpening') command('Page.handleJavaScriptDialog', { accept: true });
  };
  socket.addEventListener('message', dialogHandler);
  await click('[data-action="discard-notes"]');
  await until(() => evaluate('document.querySelector("#project-notes").value === "Saved by another window"'), 'load saved notes after conflict');
  await input('#project-notes', 'Decision: use managed infrastructure.\nNext: stakeholder review.');
  await evaluate('document.querySelector("#notes-form").requestSubmit()');
  await until(() => evaluate('document.querySelector("#notes-status")?.textContent.includes("Saved")'), 'notes resave');
  await click('[data-action="tab"][data-tab="activity"]');
  await visible('.activity-item');
  assert.ok(await evaluate('document.querySelector(".activity-list").textContent.includes("Project notes updated")'));
  console.log('PASS note drafts, persistence, conflict protection, and activity');

  await click('[data-action="new-client"]');
  await input('#modal [name="name"]', 'Browser Test Client');
  await saveModal();
  await until(() => evaluate('document.querySelector("h1").textContent.includes("Browser Test Client")'), 'new client');
  await click('.heading-actions [data-action="new-project"]');
  // The native folder picker left with WP-6: the folder is typed (or pasted) into the project form.
  const chosenFolder = join(temporary, 'Chosen client project');
  await mkdir(chosenFolder);
  assert.equal(await evaluate('document.querySelector("[data-action=browse-folder]")'), null, 'the Browse button is gone with /api/folders/pick');
  await input('#project-folder', chosenFolder);
  await input('#modal [name="name"]', 'Browser Test Project');
  assert.equal(await evaluate('document.querySelector("#project-folder").value'), chosenFolder);
  assert.equal(await evaluate('document.querySelector("#modal button[type=submit]").disabled'), false);
  await screenshot('create-project-folder.png');
  await input('#modal [name="description"]', 'An independently stored project.');
  await saveModal();
  await until(() => evaluate('document.querySelector("h1").textContent === "Browser Test Project"'), 'new project');
  await click('[data-action="new-task"]');
  await input('#modal [name="title"]', 'A temporary task');
  await saveModal();
  await click('[data-action="tab"][data-tab="tasks"]');
  await visible('.task-title-button');
  await click('.task-title-button');
  await click('[data-action="delete-task"]');
  await modalClosed();
  await until(() => evaluate('document.querySelector(".empty-state")?.textContent.includes("Make room")'), 'task deleted');
  await click('[data-action="edit-project"]');
  assert.equal(await evaluate('document.querySelector("[data-action=download-project]")'), null, 'the project export is gone with /api/projects/<id>/export');
  await input('#modal [name="status"]', 'archived');
  await saveModal();
  await click('[data-action="nav"][data-type="portfolio"]');
  await visible('#show-archived');
  assert.equal(await evaluate('document.querySelectorAll(".project-card").length'), 4);
  await click('#show-archived');
  assert.equal(await evaluate('document.querySelectorAll(".project-card").length'), 5);
  await click('#show-archived');
  console.log('PASS client/project creation with a typed folder, task deletion, and archive filtering');

  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await screenshot('mobile-portfolio.png');
  assert.ok(await evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'mobile page should not overflow');
  await click('[data-action="menu"]');
  assert.ok(await evaluate('document.querySelector(".sidebar").classList.contains("mobile-open")'));
  await click('.client-nav');
  await visible('.project-card');
  assert.ok(await evaluate('!document.querySelector(".sidebar").classList.contains("mobile-open")'));
  await click('[data-action="storage"]');
  await visible('.workspace-about');
  await evaluate('document.querySelector(".workspace-about").scrollIntoView({block:"end"})');
  assert.ok(await evaluate('document.querySelector("#modal").scrollWidth <= document.querySelector("#modal").clientWidth'), 'mobile About must fit its modal');
  assert.equal(await evaluate('document.querySelector(".about-version").textContent'), `Folio ${expectedVersion}`);
  await screenshot('about-mobile.png');
  await click('#modal .primary');
  console.log('PASS mobile layout, About and navigation');

  assert.deepEqual(errors, [], 'Browser should have no uncaught exceptions or CSP violations');
  assert.equal(await evaluate('location.href.includes("folio-launch=")'), false, 'launch credential cleared from browser URL');

  const snapshot = await (await fetch(base + '/api/state', {headers: {'X-Workspace-Token':discovery.owner_token}})).json();
  assert.equal(snapshot.projects.find(project => project.name === 'Browser Test Project').folder, await realpath(chosenFolder));
  assert.equal(JSON.parse(await readFile(join(chosenFolder, '.task-manager', 'project.json'), 'utf8')).name, 'Browser Test Project');
  console.log('PASS typed folder selection and storage in the selected folder');
  const source = snapshot.projects.find(project => project.name === 'Cloud foundation');
  const stored = JSON.parse(await readFile(join(source.folder, '.task-manager', 'project.json'), 'utf8'));
  assert.equal(stored.tasks.find(task => task.title.startsWith('Browser test:')).status, 'in_progress');
  assert.equal(stored.notes, 'Decision: use managed infrastructure.\nNext: stakeholder review.');
  assert.ok(!await readFile(join(temporary, 'workspace', 'registry.json'), 'utf8').then(text => text.includes('Browser test:')));
  console.log('PASS browser edits persisted in the correct project folder');
  await evaluate(`location.hash = '#/project/${source.id}/overview'`);
  await visible(`[data-action="edit-project"][data-id="${source.id}"]`);
  await click(`[data-action="edit-project"][data-id="${source.id}"]`);
  await click(`[data-action="project-brief"][data-id="${source.id}"]`);
  await visible('#project-brief');
  assert.match(await evaluate('document.querySelector("#project-brief").value'), /Decision: use managed infrastructure/);
  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  assert.equal(await evaluate('document.querySelector("#modal").scrollWidth <= document.querySelector("#modal").clientWidth'), true);
  await screenshot('project-brief-mobile.png');
  await click('#modal [data-action="close-modal"]');
  // The cut routes are 404 for the authenticated browser session as well.
  for (const path of ['/api/backup', '/api/doctor', `/api/projects/${source.id}/export`]) {
    const status = await evaluate(`fetch(${JSON.stringify(path)}, {headers: {'X-Folio-Session':sessionStorage.getItem('folio.sessionProof')}}).then(r => r.status)`);
    assert.equal(status, 404, `${path} is cut`);
  }
  console.log('PASS bounded project brief; backup, export and doctor routes answer 404 to the browser session');
  const noteCheck = await evaluate(`(async () => {
    const state = await (await fetch('/api/state', {headers: {'X-Folio-Session':sessionStorage.getItem('folio.sessionProof')}})).json();
    const project = state.projects.find(item => item.name === 'Browser Test Project');
    const call = async (path, method, body) => {
      const response = await fetch('/api/projects/' + project.id + path, {method, headers:{'Content-Type':'application/json','X-Folio-Session':sessionStorage.getItem('folio.sessionProof'),'X-Workspace-Token':state.csrf_token}, body:JSON.stringify(body)});
      const data = await response.json();
      if (!response.ok) throw new Error(JSON.stringify(data));
      return data;
    };
    const added = await call('/notes/sections', 'POST', {revision:project.revision, title:'Browser source decision', kind:'decision', text:'Use SQLite WAL for source-verification. 🧭'});
    const corrected = await call('/notes/sections/' + added.id, 'PATCH', {revision:added.revision, hash:added.hash, text:'Use SQLite WAL for corrected-source-verification. 🧭'});
    const brief = await call('/brief', 'POST', {query:'corrected-source-verification', max_chars:500});
    let text = '', offset = 0;
    while (offset !== null) {
      const page = await call('/source', 'POST', {source_id:corrected.source, hash:corrected.hash, offset, max_chars:11});
      text += page.text;
      offset = page.next_offset;
    }
    const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)))].map(value=>value.toString(16).padStart(2,'0')).join('');
    return {project_id:project.id, original:project.notes, added, corrected, text, digest, found:brief.records.some(record=>record.source===corrected.source && record.text.includes('corrected-source-verification'))};
  })()`);
  assert.equal(noteCheck.added.source, noteCheck.corrected.source);
  assert.equal(noteCheck.digest, noteCheck.corrected.hash);
  assert.equal(noteCheck.found, true);
  // A new document reloads external API edits. Navigating only the hash and then
  // immediately reloading races Chromium's same-document navigation commit.
  const sourceReloaded = waitForEvent('Page.loadEventFired');
  await command('Page.navigate', {url:base + '/?source-check#/project/' + noteCheck.project_id + '/notes'});
  await sourceReloaded;
  await until(() => evaluate('document.querySelector("#project-notes")?.value.includes("corrected-source-verification")'), 'corrected source visible in authoritative notes');
  await screenshot('planning-source-notes-mobile.png');
  const forgotten = await evaluate(`(async () => {
    const state = await (await fetch('/api/state', {headers: {'X-Folio-Session':sessionStorage.getItem('folio.sessionProof')}})).json();
    const project = state.projects.find(item=>item.id===${JSON.stringify(noteCheck.project_id)});
    const response = await fetch('/api/projects/' + project.id + '/notes/sections/' + ${JSON.stringify(noteCheck.corrected.id)}, {method:'DELETE',headers:{'Content-Type':'application/json','X-Folio-Session':sessionStorage.getItem('folio.sessionProof'),'X-Workspace-Token':state.csrf_token},body:JSON.stringify({revision:project.revision,hash:${JSON.stringify(noteCheck.corrected.hash)}})});
    if (!response.ok) throw new Error(await response.text());
    return (await (await fetch('/api/state', {headers: {'X-Folio-Session':sessionStorage.getItem('folio.sessionProof')}})).json()).projects.find(item=>item.id===project.id).notes;
  })()`);
  assert.equal(forgotten, noteCheck.original);
  assert.deepEqual(errors, [], 'Source workflow should have no uncaught exceptions or CSP violations');
  console.log('PASS installed-capable browser note CRUD, query-aware brief, source paging/hash, and authoritative notes rendering');
  console.log(`Browser smoke checks complete. Screenshots: ${output}`);
} finally {
  socket?.close();
  chrome?.kill('SIGTERM');
  server?.kill('SIGTERM');
  await delay(500);
  await rm(temporary, { recursive: true, force: true });
}
