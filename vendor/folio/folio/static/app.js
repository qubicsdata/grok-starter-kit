// Clear the launch capability synchronously before routes or UI handlers run.
const launchCredential = location.hash.startsWith('#folio-launch=') ? location.hash.slice('#folio-launch='.length) : null;
if (launchCredential !== null) history.replaceState(null, '', location.pathname + location.search);
let sessionProof = sessionStorage.getItem('folio.sessionProof') || '';

const icons = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  tasks: '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="m8 9 1 1 2-2m3 1h3M8 15h3m3 0h3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9H3z"/>',
  people: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m1-16a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 5v2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  alert: '<path d="m12 3 10 18H2zM12 9v5m0 3v.1"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  leaf: '<path d="M20 4C8 2 2 8 6 16c8 5 15-1 14-12ZM4 21 15 10"/>',
  x: '<path d="m6 6 12 12M6 18 18 6"/>',
  board: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m6-16v16"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.1M3 12h.1M3 18h.1"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 6M4 12l2 6a7 7 0 0 0 12-1"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  note: '<path d="M5 3h10l4 4v14H5zM14 3v5h5M8 12h8m-8 4h6"/>',
  link: '<path d="m10 13 4-4m-5 7-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m0 10a4 4 0 0 0 6 0l4-4a4 4 0 0 0-6-6l-1 1"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
};
const icon = (name, cls = '') => `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.folder}</svg>`;
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
const colors = ['purple', 'blue', 'green', 'orange', 'pink', 'teal'];
const safeColor = value => colors.includes(value) ? value : 'purple';
const statusNames = { backlog: 'To do', in_progress: 'In progress', blocked: 'Blocked', done: 'Done' };
const projectStatusNames = { active: 'Active', on_hold: 'On hold', completed: 'Completed', archived: 'Archived' };
let state = null;
let scope = { type: 'portfolio', id: '' };
let tab = 'overview';
let layout = 'list';
let query = '';
let statusFilter = '';
let priorityFilter = '';
let streamFilter = '';
let showArchived = false;
let mobileOpen = false;
let notesDirty = false;
const noteDrafts = new Map();
let toastTimer;
let modalReturnFocus;
const app = document.querySelector('#app');
const modal = document.querySelector('#modal');

const initials = name => (name || '?').split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
const clientFor = project => state.clients.find(client => client.id === project.client_id);
const selectedProject = () => state.projects.find(project => project.id === scope.id);
const selectedClient = () => state.clients.find(client => client.id === scope.id);
const localToday = () => { const current = new Date(); return `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}-${String(current.getDate()).padStart(2, '0')}`; };
const overdue = task => task.status !== 'done' && task.due_date && task.due_date < localToday();
const attention = task => task.status !== 'done' && (task.status === 'blocked' || overdue(task));
const dateLabel = value => value ? new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : 'No date';
const dueLabel = task => task.due_date === localToday() ? 'Today' : dateLabel(task.due_date);
const progress = tasks => tasks.length ? Math.round(tasks.filter(task => task.status === 'done').length / tasks.length * 100) : 0;
const scopedProjects = () => state.projects.filter(project => (scope.type === 'project' ? project.id === scope.id : scope.type === 'client' ? project.client_id === scope.id : true) && (scope.type === 'project' || showArchived || project.status !== 'archived'));
const scopedTasks = () => scopedProjects().flatMap(project => project.tasks.map(task => ({ ...task, project_id: project.id })));
const priorityRank = { urgent: 0, high: 1, medium: 2, low: 3 };

async function api(path, method = 'GET', data) {
  const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json', 'X-Workspace-Token': state?.csrf_token || '', 'X-Folio-Session': sessionProof }, ...(data ? { body: JSON.stringify(data) } : {}) });
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.error || 'Something went wrong. Please try again.');
    error.code = result.code;
    error.status = response.status;
    throw error;
  }
  return result;
}

function toast(message, error = false) {
  const element = document.querySelector('#toast');
  element.textContent = message;
  element.className = `visible ${error ? 'error' : ''}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { element.className = ''; }, error ? 8000 : 3500);
}

async function refresh() {
  state = await api('/api/state');
  for (const [projectId, draft] of noteDrafts) {
    const project = state.projects.find(item => item.id === projectId);
    if (project && project.notes === draft.original) draft.revision = project.revision;
  }
  render();
}

function route() {
  const parts = location.hash.replace(/^#\/?/, '').split('/');
  scope = { type: ['client', 'project'].includes(parts[0]) ? parts[0] : 'portfolio', id: parts[1] || '' };
  tab = ['overview', 'tasks', 'notes', 'activity'].includes(parts[2]) ? parts[2] : 'overview';
  if (scope.type !== 'project' && ['notes', 'activity'].includes(tab)) tab = 'overview';
  query = ''; statusFilter = ''; priorityFilter = ''; streamFilter = ''; mobileOpen = false;
  notesDirty = noteDrafts.size > 0;
  if (state) render();
}

function navigate(type, id = '', view = 'overview') {
  const next = `#/${type}/${id}/${view}`;
  if (location.hash === next) { route(); return; }
  location.hash = next;
}

function sidebar() {
  return `<aside class="sidebar ${mobileOpen ? 'mobile-open' : ''}" aria-label="Workspace navigation">
    <a class="brand" href="#/portfolio//overview" aria-label="Folio home" title="Folio"><svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3 28 10v12l-12 7-12-7V10z"/><path d="M4 10l12 7 12-7M16 17v12"/></svg><span>folio<span class="brand-dot">.</span></span></a>
    <div class="workspace-name"><span class="workspace-logo">F</span><div>My workspace<small>Personal workspace</small></div><span class="local-dot" title="Local workspace"></span></div>
    <div class="nav-label">WORKSPACE</div>
    <button class="nav-item ${scope.type === 'portfolio' && tab === 'overview' ? 'active' : ''}" data-action="nav" data-type="portfolio">${icon('grid')}<span>Portfolio overview</span></button>
    <button class="nav-item ${scope.type === 'portfolio' && tab === 'tasks' ? 'active' : ''}" data-action="nav" data-type="portfolio" data-tab="tasks">${icon('tasks')}<span>All tasks</span><span class="nav-count">${state.projects.filter(project => project.status !== 'archived').reduce((sum, project) => sum + project.tasks.filter(task => task.status !== 'done').length, 0)}</span></button>
    <div class="nav-label clients-label">CLIENTS <button class="icon-button" data-action="new-client" aria-label="Add client">${icon('plus')}</button></div>
    <nav class="clients-nav">${state.clients.map(client => {
      const projects = state.projects.filter(project => project.client_id === client.id && project.status !== 'archived');
      const selected = scope.type === 'client' && scope.id === client.id;
      const expanded = selected || (scope.type === 'project' && selectedProject()?.client_id === client.id);
      return `<button class="nav-item client-nav ${selected ? 'active' : ''}" data-action="nav" data-type="client" data-id="${client.id}"><span class="client-dot ${safeColor(client.color)}"></span><span>${escapeHTML(client.name)}</span><span class="nav-count">${projects.length}</span></button>${expanded ? `<div class="project-nav">${projects.map(project => `<button class="nav-item ${scope.id === project.id ? 'selected' : ''}" data-action="nav" data-type="project" data-id="${project.id}">${icon('folder')}<span>${escapeHTML(project.name)}</span></button>`).join('')}<button class="nav-item add-project-nav" data-action="new-project" data-client="${client.id}">${icon('plus')}<span>Add project</span></button></div>` : ''}`;
    }).join('') || '<p class="sidebar-empty">Your client accounts will appear here.</p>'}</nav>
    <button class="add-client" data-action="new-client">${icon('plus')} Add client</button>
    <div class="sidebar-bottom"><div class="local-card">${icon('folder')}<div>Your work, your folders<small>Saved locally. Always yours.</small></div><span class="local-dot"></span></div><div class="profile"><span class="avatar profile-avatar">ME</span><div>You<small>Local workspace</small></div><button class="icon-button" data-action="storage" aria-label="Workspace settings" title="Workspace settings">${icon('more')}</button></div></div>
  </aside>`;
}

function render() {
  const project = scope.type === 'project' ? selectedProject() : null;
  const client = scope.type === 'client' ? selectedClient() : project ? clientFor(project) : null;
  const missing = scope.type === 'project' && !project || scope.type === 'client' && !client;
  const title = project?.name || client?.name || 'Portfolio overview';
  const subtitle = project?.description || client?.description || 'A little clarity across every client, project, and moving part.';
  document.title = `${title} · Folio`;
  app.innerHTML = `${sidebar()}<div class="main-shell"><header class="topbar"><div class="breadcrumb"><button class="icon-button mobile-menu" data-action="menu" aria-label="Toggle navigation">${icon('menu')}</button><span class="crumb-root">Workspace</span>${icon('chevron')}${client && project ? `<button data-action="nav" data-type="client" data-id="${client.id}">${escapeHTML(client.name)}</button>${icon('chevron')}` : ''}<span>${escapeHTML(title)}</span></div><div class="topbar-right"><span class="today">${new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</span><button class="icon-button" data-action="refresh" aria-label="Refresh workspace" title="Refresh workspace">${icon('refresh')}</button><span class="avatar small-avatar">ME</span></div></header>
    <main><div class="page-heading"><div><div class="eyebrow">${project ? 'PROJECT WORKSPACE' : client ? 'CLIENT WORKSPACE' : 'THE BIG PICTURE'}</div><h1>${escapeHTML(title)}${client && !project ? `<span class="heading-dot ${safeColor(client.color)}"></span>` : ''}</h1><p>${escapeHTML(subtitle)}</p></div><div class="heading-actions">${project ? `<button class="button" data-action="edit-project" data-id="${project.id}">${icon('more')} Details</button><button class="button primary" data-action="new-task" data-project="${project.id}">${icon('plus')} New task</button>` : `${client ? `<button class="icon-button" data-action="edit-client" data-id="${client.id}" aria-label="Edit client">${icon('more')}</button>` : ''}<button class="button primary" data-action="new-project" ${client ? `data-client="${client.id}"` : ''}>${icon('plus')} New project</button>`}</div></div>
    ${state.storage_errors.length ? `<div class="storage-warning">${icon('alert')}<div><strong>${state.storage_errors.length} project folder${state.storage_errors.length === 1 ? '' : 's'} unavailable.</strong> Totals exclude unavailable data.<button class="text-button" data-action="storage">View details</button></div></div>` : ''}
    <div class="tabs"><div role="tablist" aria-label="Workspace views">${[['overview', 'Overview'], ['tasks', 'Tasks'], ...(project ? [['notes', 'Notes & decisions'], ['activity', 'Activity']] : [])].map(([key, label]) => `<button role="tab" aria-selected="${tab === key}" class="tab ${tab === key ? 'active' : ''}" data-action="tab" data-tab="${key}">${label}${key === 'tasks' ? `<span>${scopedTasks().length}</span>` : ''}</button>`).join('')}</div><span class="saved-label"><span class="local-dot"></span> Local workspace</span></div>
    ${missing ? `<div class="empty-state">${icon('folder')}<h2>This workspace is unavailable</h2><p>The project folder may have moved, or this link may be out of date.</p><button class="button" data-action="nav" data-type="portfolio">Back to portfolio</button></div>` : !state.clients.length ? welcome() : tab === 'overview' ? overview() : tab === 'tasks' ? tasksView() : tab === 'notes' ? notesView(project) : activityView(project)}
    <footer><span>Space to focus. Room to move forward.</span><span>Folio <span class="footer-dot">·</span> Your account workspace</span></footer></main></div>`;
}

function welcome() {
  return `<section class="welcome"><div class="welcome-art">${icon('folder')}${icon('leaf')}</div><div class="eyebrow">WELCOME TO FOLIO</div><h2>Every account.<br>One clear picture.</h2><p>Bring your clients, projects, and lines of work together.<br>Your project details stay in their own folders.</p><button class="button primary" data-action="new-client">${icon('plus')} Add your first client</button></section><div class="welcome-features"><div>${icon('people')}<h3>Start with the client</h3><p>See the whole relationship, across every project.</p></div><div>${icon('board')}<h3>Follow each line of work</h3><p>Turn parallel activities into clear workstreams.</p></div><div>${icon('folder')}<h3>Keep your context close</h3><p>Tasks, decisions, and notes travel with the project.</p></div></div>`;
}

function stats() {
  const projects = scopedProjects();
  const tasks = scopedTasks();
  const active = tasks.filter(task => task.status === 'in_progress').length;
  const blocked = tasks.filter(task => task.status === 'blocked').length;
  const done = tasks.filter(task => task.status === 'done').length;
  const firstValue = scope.type === 'project' ? selectedProject().workstreams.length : projects.filter(project => project.status === 'active').length;
  const cards = [
    ['folder', 'purple', scope.type === 'project' ? 'Workstreams' : 'Active projects', firstValue, scope.type === 'project' ? 'Parallel lines of work' : `Across ${scope.type === 'client' ? 1 : new Set(projects.filter(project => project.status === 'active').map(project => project.client_id)).size} client accounts`, ''],
    ['clock', 'blue', 'Tasks in progress', active, `${tasks.filter(task => task.status === 'backlog').length} more ready to move forward`, 'in_progress'],
    ['alert', 'orange', 'Blocked tasks', blocked, blocked ? 'A little attention goes a long way' : 'Nothing standing in the way', 'blocked'],
    ['check', 'green', 'Completed tasks', done, `${progress(tasks)}% of all tasks complete`, 'done'],
  ];
  return `<div class="stats-grid">${cards.map(([symbol, color, label, value, note, filter]) => `<button class="stat-card" data-action="stat" data-filter="${filter}"><span class="stat-top"><span>${label}</span><span class="stat-icon ${color}">${icon(symbol)}</span></span><strong>${value.toString().padStart(2, '0')}</strong><span class="stat-note">${note}</span></button>`).join('')}</div>`;
}

function overview() {
  const tasks = scopedTasks();
  const urgent = tasks.filter(attention).sort((first, second) => priorityRank[first.priority] - priorityRank[second.priority]);
  const projects = scopedProjects();
  return `${stats()}<div class="overview-columns"><section class="projects-section"><div class="section-heading"><div><h2>${scope.type === 'project' ? 'Lines of work' : 'Your projects'} <span class="count-badge">${scope.type === 'project' ? selectedProject().workstreams.length : projects.length}</span></h2><p>${scope.type === 'project' ? 'Keep each activity moving in the right direction.' : 'Different moving parts. One place to keep them in view.'}</p></div>${scope.type === 'project' ? '<button class="text-button" data-action="new-stream">' + icon('plus') + ' Add workstream</button>' : `<label class="archive-toggle"><input type="checkbox" id="show-archived" ${showArchived ? 'checked' : ''}> Archived</label>`}</div>${scope.type === 'project' ? workstreams(selectedProject()) : `<div class="project-grid">${projects.map(projectCard).join('')}<button class="new-project-card" data-action="new-project" ${scope.type === 'client' ? `data-client="${scope.id}"` : ''}><span>${icon('plus')}</span><strong>A new line of possibility</strong><small>Create a project</small></button></div>`}
    ${scope.type === 'portfolio' ? clientRollup() : scope.type === 'project' ? projectContext(selectedProject()) : ''}</section>
    <aside class="attention-panel"><div class="section-heading"><h2>Needs attention <span class="attention-count">${urgent.length}</span></h2><span class="attention-dot"></span></div><p class="panel-subtitle">A few things to keep on your radar.</p>${urgent.length ? urgent.slice(0, 5).map(task => { const project = state.projects.find(item => item.id === task.project_id); return `<button class="attention-item" data-action="edit-task" data-project="${project.id}" data-id="${task.id}"><span class="attention-tag ${task.status === 'blocked' ? 'blocked' : 'overdue'}">${icon(task.status === 'blocked' ? 'alert' : 'clock')}${task.status === 'blocked' ? 'Blocked' : 'Overdue'}</span><strong>${escapeHTML(task.title)}</strong><span class="attention-context">${escapeHTML(clientFor(project)?.name)} <span> / </span> ${escapeHTML(project.name)}</span>${task.blocker && task.status === 'blocked' ? `<p>${escapeHTML(task.blocker)}</p>` : ''}<span class="attention-bottom">${escapeHTML(task.owner || 'Unassigned')}<span class="${overdue(task) ? 'late' : ''}">${dueLabel(task)}</span></span></button>`; }).join('') : `<div class="all-clear"><span>${icon('check')}</span><h3>A clear path ahead</h3><p>No blocked or overdue tasks.<br>Keep the momentum going.</p></div>`}${urgent.length ? '<button class="attention-link text-button" data-action="attention">View all attention items ' + icon('arrow') + '</button>' : ''}<div class="quiet-note">${icon('leaf')}<p>Progress isn’t doing everything.<br>It’s knowing what’s next.</p></div></aside></div>`;
}

function projectCard(project) {
  const client = clientFor(project);
  const done = project.tasks.filter(task => task.status === 'done').length;
  const blocked = project.tasks.filter(task => task.status === 'blocked').length;
  const percent = progress(project.tasks);
  const owners = [...new Set(project.tasks.map(task => task.owner).filter(Boolean))];
  const status = project.status === 'active' && blocked ? 'Needs attention' : projectStatusNames[project.status];
  return `<button class="project-card" data-action="nav" data-type="project" data-id="${project.id}"><div class="card-top"><span class="client-tag ${safeColor(client?.color)}"><span class="client-dot ${safeColor(client?.color)}"></span>${escapeHTML(client?.name)}</span>${icon('arrow', 'card-arrow')}</div><h3>${escapeHTML(project.name)}</h3><p class="project-description">${escapeHTML(project.description || 'A new project, ready to take shape.')}</p><div class="project-status"><span class="status-pill ${blocked && project.status === 'active' ? 'at-risk' : project.status}"><span></span>${status}</span><span>${project.workstreams.length} workstreams</span></div><div class="progress-caption"><span>Overall progress</span><strong>${percent}%</strong></div><div class="progress-track"><span class="${safeColor(client?.color)}" style="width:${percent}%"></span></div><div class="card-bottom"><span class="task-count">${icon('tasks')}${done}/${project.tasks.length} tasks</span><div class="card-people">${owners.slice(0, 3).map(owner => `<span class="avatar tiny-avatar" title="${escapeHTML(owner)}">${escapeHTML(initials(owner))}</span>`).join('')}${owners.length > 3 ? `<span class="avatar tiny-avatar">+${owners.length - 3}</span>` : ''}</div>${project.target_date ? `<span class="target-date">${icon('clock')}${dateLabel(project.target_date)}</span>` : ''}</div></button>`;
}

function clientRollup() {
  return `<section class="client-rollup"><div class="section-heading"><h2>Across your accounts</h2><span class="muted">${state.clients.length} clients</span></div>${state.clients.map(client => { const projects = state.projects.filter(project => project.client_id === client.id && project.status !== 'archived'); const tasks = projects.flatMap(project => project.tasks); return `<button class="client-row" data-action="nav" data-type="client" data-id="${client.id}"><span class="client-monogram ${safeColor(client.color)}">${escapeHTML(initials(client.name))}</span><span class="client-row-name"><strong>${escapeHTML(client.name)}</strong><small>${projects.length} projects · ${tasks.filter(task => task.status !== 'done').length} open tasks</small></span><span class="mini-progress"><span class="progress-track"><span class="${safeColor(client.color)}" style="width:${progress(tasks)}%"></span></span><span>${progress(tasks)}%</span></span>${icon('chevron')}</button>`; }).join('')}</section>`;
}

function workstreams(project) {
  const streams = [...project.workstreams, ...(project.tasks.some(task => !task.workstream_id) ? [{ id: '', name: 'Unassigned workstream', color: 'orange' }] : [])];
  return `<div class="workstreams">${streams.map(stream => { const tasks = project.tasks.filter(task => task.workstream_id === stream.id); const blocked = tasks.filter(task => task.status === 'blocked').length; return `<button class="workstream-card" data-action="stream-tasks" data-id="${stream.id}"><span class="stream-icon ${safeColor(stream.color)}">${icon('board')}</span><div class="workstream-main"><h3>${escapeHTML(stream.name)}</h3><p>${tasks.filter(task => task.status === 'done').length} of ${tasks.length} tasks complete${blocked ? ` <span class="late">· ${blocked} blocked</span>` : ''}</p><div class="progress-track"><span class="${safeColor(stream.color)}" style="width:${progress(tasks)}%"></span></div></div><strong>${progress(tasks)}%</strong>${icon('chevron')}</button>`; }).join('')}</div>`;
}

function projectContext(project) {
  return `<section class="context-card"><div class="section-heading"><h2>${icon('note')} Project context</h2><button class="text-button" data-action="tab" data-tab="notes">Edit notes ${icon('arrow')}</button></div><p class="context-preview">${escapeHTML(project.notes ? project.notes.slice(0, 280) + (project.notes.length > 280 ? '…' : '') : 'Keep meeting notes, project decisions, and next steps close to the work.')}</p><div class="folder-caption">${icon('folder')}<span>${escapeHTML(project.folder)}</span></div></section>`;
}

function filteredTasks() {
  return scopedTasks().filter(task => {
    const project = state.projects.find(item => item.id === task.project_id);
    const client = clientFor(project);
    const stream = project.workstreams.find(item => item.id === task.workstream_id);
    return (!statusFilter || (statusFilter === 'attention' ? attention(task) : task.status === statusFilter)) && (!priorityFilter || task.priority === priorityFilter) && (!streamFilter || (streamFilter === 'unassigned' ? !task.workstream_id : task.workstream_id === streamFilter)) && (!query || [task.title, task.description, task.owner, task.blocker, project.name, client?.name, stream?.name].join(' ').toLowerCase().includes(query.toLowerCase()));
  }).sort((first, second) => (first.status === 'done') - (second.status === 'done') || priorityRank[first.priority] - priorityRank[second.priority] || (first.due_date || '9999').localeCompare(second.due_date || '9999'));
}

function tasksView() {
  const project = scope.type === 'project' ? selectedProject() : null;
  return `<section class="tasks-section"><div class="task-toolbar"><label class="search-field">${icon('search')}<input id="task-search" placeholder="Search tasks, owners, projects…" aria-label="Search tasks" value="${escapeHTML(query)}"><kbd>/</kbd></label><div class="task-filters"><select id="status-filter" aria-label="Filter by status">${options({ '': 'All statuses', ...statusNames, attention: 'Needs attention' }, statusFilter)}</select><select id="priority-filter" aria-label="Filter by priority">${options({ '': 'All priorities', urgent: 'Urgent', high: 'High', medium: 'Medium', low: 'Low' }, priorityFilter)}</select>${project ? `<select id="stream-filter" aria-label="Filter by workstream"><option value="">All workstreams</option>${project.workstreams.map(stream => `<option value="${stream.id}" ${streamFilter === stream.id ? 'selected' : ''}>${escapeHTML(stream.name)}</option>`).join('')}<option value="unassigned" ${streamFilter === 'unassigned' ? 'selected' : ''}>Unassigned</option></select>` : ''}</div><div class="view-switch" aria-label="Task display"><button class="icon-button ${layout === 'list' ? 'selected' : ''}" data-action="layout" data-layout="list" aria-label="List view" aria-pressed="${layout === 'list'}">${icon('list')}</button><button class="icon-button ${layout === 'board' ? 'selected' : ''}" data-action="layout" data-layout="board" aria-label="Board view" aria-pressed="${layout === 'board'}">${icon('board')}</button></div><button class="button primary" data-action="new-task" ${project ? `data-project="${project.id}"` : ''}>${icon('plus')} Add task</button></div><div id="task-results">${taskResults()}</div></section>`;
}

function taskResults() {
  const tasks = filteredTasks();
  if (!tasks.length) return `<div class="empty-state">${icon('tasks')}<h2>${scopedTasks().length ? 'No matching tasks' : 'Make room for the next step'}</h2><p>${scopedTasks().length ? 'Try another search or clear your filters.' : 'Add a task and give your work a clear direction.'}</p><button class="button" data-action="${scopedTasks().length ? 'clear-filters' : 'new-task'}">${scopedTasks().length ? 'Clear filters' : 'Add a task'}</button></div>`;
  return `<div class="results-caption">${tasks.length} task${tasks.length === 1 ? '' : 's'}${statusFilter || priorityFilter || query || streamFilter ? ' match your filters <button class="text-button" data-action="clear-filters">Clear filters</button>' : ' in view'}${layout === 'board' ? '<span>Drag cards to update status, or open a task to edit.</span>' : ''}</div>${layout === 'list' ? `<div class="task-table-wrap"><table class="task-table"><thead><tr><th>Task & workstream</th><th>Project</th><th>Status</th><th>Priority</th><th>Owner</th><th>Due date</th><th><span class="sr-only">Edit</span></th></tr></thead><tbody>${tasks.map(task => taskRow(task)).join('')}</tbody></table></div>` : `<div class="kanban">${Object.entries(statusNames).map(([status, label]) => `<section class="kanban-column" data-drop-status="${status}"><h3><span class="status-dot ${status}"></span>${label}<span>${tasks.filter(task => task.status === status).length}</span></h3><div class="kanban-cards">${tasks.filter(task => task.status === status).map(task => taskCard(task)).join('')}<button class="board-add" data-action="new-task" data-status="${status}">${icon('plus')} Add task</button></div></section>`).join('')}</div>`}`;
}

function taskRow(task) {
  const project = state.projects.find(item => item.id === task.project_id);
  const stream = project.workstreams.find(item => item.id === task.workstream_id);
  return `<tr><td><button class="task-title-button ${task.status === 'done' ? 'completed-task' : ''}" data-action="edit-task" data-id="${task.id}" data-project="${project.id}"><span class="task-check ${task.status}">${task.status === 'done' ? icon('check') : task.status === 'blocked' ? icon('alert') : ''}</span><span><strong>${escapeHTML(task.title)}</strong><small><span class="client-dot ${safeColor(stream?.color)}"></span>${escapeHTML(stream?.name || 'Unassigned workstream')}</small></span></button></td><td><span class="table-project">${escapeHTML(project.name)}</span><small class="muted">${escapeHTML(clientFor(project)?.name)}</small></td><td><span class="task-status ${task.status}"><span class="status-dot ${task.status}"></span>${statusNames[task.status]}</span></td><td><span class="priority ${task.priority}"><span></span>${task.priority}</span></td><td><span class="owner-cell">${task.owner ? `<span class="avatar tiny-avatar">${escapeHTML(initials(task.owner))}</span>` : ''}${escapeHTML(task.owner || 'Unassigned')}</span></td><td><span class="task-date ${overdue(task) ? 'late' : ''}">${overdue(task) ? icon('alert') : ''}${dueLabel(task)}</span></td><td><button class="icon-button" data-action="edit-task" data-id="${task.id}" data-project="${project.id}" aria-label="Edit ${escapeHTML(task.title)}">${icon('more')}</button></td></tr>`;
}

function taskCard(task) {
  const project = state.projects.find(item => item.id === task.project_id);
  const stream = project.workstreams.find(item => item.id === task.workstream_id);
  return `<button class="kanban-card" draggable="true" data-drag-task="${task.id}" data-action="edit-task" data-id="${task.id}" data-project="${project.id}"><span class="kanban-client">${escapeHTML(clientFor(project)?.name)} / ${escapeHTML(project.name)}</span><strong>${escapeHTML(task.title)}</strong><span class="stream-tag ${safeColor(stream?.color)}">${escapeHTML(stream?.name || 'Unassigned')}</span>${task.status === 'blocked' && task.blocker ? `<p class="blocker-preview">${escapeHTML(task.blocker)}</p>` : ''}<span class="kanban-card-footer"><span class="priority ${task.priority}"><span></span>${task.priority}</span><span class="${overdue(task) ? 'late' : ''}">${task.due_date ? dueLabel(task) : ''}</span>${task.owner ? `<span class="avatar tiny-avatar" title="${escapeHTML(task.owner)}">${escapeHTML(initials(task.owner))}</span>` : ''}</span></button>`;
}

function notesView(project) {
  const draft = noteDrafts.get(project.id);
  return `<section class="notes-layout"><form id="notes-form" class="notes-editor"><div class="section-heading"><div><h2>Notes & decisions</h2><p>The context behind the work. Plain text and Markdown welcome.</p></div><button class="button primary" type="submit">Save notes</button></div><textarea name="notes" id="project-notes" aria-label="Project notes" placeholder="Meeting notes, project decisions, open questions, and next steps…">${escapeHTML(draft ? draft.value : project.notes)}</textarea><div class="notes-save-status" id="notes-status" role="status">${draft ? 'Unsaved draft — kept while you switch views in this window.' : 'Saved in this project’s folder.'}</div><button type="button" class="text-button" data-action="discard-notes">Discard draft and load saved notes</button></form><aside class="notes-help"><span class="stat-icon purple">${icon('note')}</span><h3>A home for the context</h3><p>Capture the things that don’t fit in a task.</p><ul><li>Meeting outcomes & next steps</li><li>Decisions & tradeoffs</li><li>Stakeholders & important links</li><li>Open questions & assumptions</li></ul><hr><h3>Travels with your project</h3><p>Notes live alongside tasks inside the project’s <code>.task-manager</code> folder.</p><button type="button" class="button" data-action="download-project" data-id="${project.id}">${icon('download')} Export project</button></aside></section>`;
}

function activityView(project) {
  return `<section class="activity-section"><div class="section-heading"><div><h2>Project activity</h2><p>A record of how the work moves forward.</p></div><span class="muted">${project.activity.length} updates</span></div><div class="activity-list">${project.activity.map(item => `<div class="activity-item"><span class="activity-mark">${icon('check')}</span><div><p>${escapeHTML(item.message)}</p><time datetime="${escapeHTML(item.at)}">${new Date(item.at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</time></div></div>`).join('') || '<p class="muted">No activity yet.</p>'}</div></section>`;
}

function options(entries, selected) {
  return Object.entries(entries).map(([value, label]) => `<option value="${value}" ${value === selected ? 'selected' : ''}>${escapeHTML(label)}</option>`).join('');
}

function field(label, name, value = '', extra = '') {
  return `<label class="field"><span>${label}</span><input name="${name}" value="${escapeHTML(value)}" ${extra}></label>`;
}

function colorField(value = 'purple') {
  return `<fieldset class="color-picker"><legend>Account color</legend>${colors.map(color => `<label class="color-option ${color}"><input type="radio" name="color" value="${color}" aria-label="${color}" ${value === color ? 'checked' : ''}><span>${icon('check')}</span></label>`).join('')}</fieldset>`;
}

function openModal(title, subtitle, body, submit, onSubmit, extra = '') {
  modalReturnFocus = document.activeElement;
  modal.innerHTML = `<form id="modal-form"><div class="modal-header"><div><span class="eyebrow">YOUR WORKSPACE</span><h2 id="modal-title">${escapeHTML(title)}</h2><p>${escapeHTML(subtitle)}</p></div><button type="button" class="icon-button" data-action="close-modal" aria-label="Close dialog">${icon('x')}</button></div><div class="modal-body">${body}<div class="form-error" role="alert"></div></div><div class="modal-footer">${extra}<span class="modal-spacer"></span><button type="button" class="button" data-action="close-modal">Cancel</button><button type="submit" class="button primary">${submit}</button></div></form>`;
  if (!modal.open) modal.showModal();
  modal.querySelector('input:not([type=radio]), textarea, select, button[type=submit]')?.focus();
  modal.querySelector('form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type=submit]');
    button.disabled = true;
    form.querySelector('.form-error').textContent = '';
    try {
      await onSubmit(Object.fromEntries(new FormData(form)));
      modal.close();
      await refresh();
    } catch (error) {
      form.querySelector('.form-error').textContent = error.message;
    } finally { button.disabled = false; }
  });
}

function clientModal(clientId) {
  const client = state.clients.find(item => item.id === clientId);
  openModal(client ? 'Edit client' : 'A new client relationship', 'Keep all of an account’s projects in one place.', `${field('Client name', 'name', client?.name, 'required maxlength="120" placeholder="e.g. Northstar Financial"')}<label class="field"><span>About this account</span><textarea name="description" rows="3" maxlength="10000" placeholder="Industry, relationship, or a little useful context">${escapeHTML(client?.description || '')}</textarea></label>${colorField(client?.color)}`, client ? 'Save changes' : 'Create client', async data => {
    const result = await api(`/api/clients${client ? '/' + client.id : ''}`, client ? 'PATCH' : 'POST', data);
    toast(client ? 'Client updated' : 'Your new client is ready');
    if (!client) navigate('client', result.id);
  });
}

function projectModal(projectId, clientId) {
  if (!state.clients.length) { clientModal(); return; }
  const project = state.projects.find(item => item.id === projectId);
  const client = clientId || (scope.type === 'client' ? scope.id : state.clients[0].id);
  const folderField = `<section class="folder-details" aria-label="Project folder"><label class="field" for="project-folder"><span>Project folder</span><input id="project-folder" name="folder" placeholder="Automatic workspace folder, or an existing folder path" maxlength="4096"></label><p>Paste the path of a folder on this computer, or leave blank to create one in your workspace.</p><small>Existing Folio projects reopen with their saved data.</small></section>`;
  const body = `${!project ? `<label class="field"><span>Client</span><select name="client_id">${state.clients.map(item => `<option value="${item.id}" ${item.id === client ? 'selected' : ''}>${escapeHTML(item.name)}</option>`).join('')}</select></label>` : ''}${field('Project name', 'name', project?.name, 'required maxlength="160" placeholder="e.g. Cloud foundation"')}<label class="field"><span>What are we working toward?</span><textarea name="description" rows="3" maxlength="10000" placeholder="A short description of the outcome">${escapeHTML(project?.description || '')}</textarea></label><div class="form-row">${field('Target date', 'target_date', project?.target_date, 'type="date"')}${project ? `<label class="field"><span>Project status</span><select name="status">${options(projectStatusNames, project.status)}</select></label>` : ''}</div>${!project ? folderField : `<div class="storage-info">${icon('folder')}<div><strong>Project folder</strong><code>${escapeHTML(project.folder)}</code><small>Tasks and notes are saved in .task-manager/project.json.</small></div></div><button type="button" class="text-button" data-action="relocate-project" data-id="${project.id}">Change project folder</button><button type="button" class="text-button" data-action="project-brief" data-id="${project.id}">Project brief</button>`}`;
  openModal(project ? 'Project details' : 'Start a new project', project ? 'Keep the goal, timeline, and status up to date.' : 'Give the work a home. Build clarity from there.', body, project ? 'Save changes' : 'Create project', async data => {
    const result = await api(`/api/projects${project ? '/' + project.id : ''}`, project ? 'PATCH' : 'POST', { ...data, ...(project ? { revision: project.revision } : {}) });
    toast(project ? 'Project updated' : 'Project ready — add your first task');
    if (!project) navigate('project', result.id);
  });
}

function taskModal(projectId, taskId, initialStatus = 'backlog') {
  if (!state.projects.length) { projectModal(); return; }
  const available = state.projects.filter(project => project.status !== 'archived' || project.id === projectId);
  if (!available.length) { toast('Create a project or reopen an archived project first.'); return; }
  const project = state.projects.find(item => item.id === projectId) || (scope.type === 'project' ? selectedProject() : null) || available.find(item => scope.type === 'client' && item.client_id === scope.id) || available[0];
  const task = project.tasks.find(item => item.id === taskId);
  const streamOptions = selected => `<option value="">Unassigned</option>${project.workstreams.map(stream => `<option value="${stream.id}" ${stream.id === selected ? 'selected' : ''}>${escapeHTML(stream.name)}</option>`).join('')}`;
  const body = `${!task ? `<label class="field"><span>Project</span><select name="project_id" id="task-project">${available.map(item => `<option value="${item.id}" ${item.id === project.id ? 'selected' : ''}>${escapeHTML(clientFor(item)?.name)} / ${escapeHTML(item.name)}</option>`).join('')}</select></label>` : `<div class="task-project-caption">${escapeHTML(clientFor(project)?.name)} ${icon('chevron')} ${escapeHTML(project.name)}</div>`}${field('Task title', 'title', task?.title, 'required maxlength="300" placeholder="What’s the next step?"')}<label class="field"><span>Details & acceptance criteria</span><textarea name="description" rows="3" maxlength="50000" placeholder="What needs to happen? What does done look like?">${escapeHTML(task?.description || '')}</textarea></label><div class="form-row"><label class="field"><span>Status</span><select name="status">${options(statusNames, task?.status || initialStatus)}</select></label><label class="field"><span>Priority</span><select name="priority">${options({ low: 'Low', medium: 'Medium', high: 'High', urgent: 'Urgent' }, task?.priority || 'medium')}</select></label></div><div class="form-row"><label class="field"><span>Workstream</span><select name="workstream_id">${streamOptions(task?.workstream_id || streamFilter)}</select></label>${field('Owner', 'owner', task?.owner, 'maxlength="120" placeholder="Who’s taking the lead?"')}</div><div class="form-row">${field('Due date', 'due_date', task?.due_date, 'type="date"')}</div><label class="field"><span>Blocker / dependency</span><textarea name="blocker" rows="2" maxlength="10000" placeholder="Waiting on a decision, a person, or another team?">${escapeHTML(task?.blocker || '')}</textarea></label>`;
  openModal(task ? 'Task details' : 'A step forward', task ? 'Keep the details clear and the work moving.' : 'Small, clear steps make big projects manageable.', body, task ? 'Save changes' : 'Create task', async data => {
    const target = task ? project : state.projects.find(item => item.id === data.project_id);
    const payload = { ...data, revision: target.revision };
    await api(`/api/projects/${target.id}/tasks${task ? '/' + task.id : ''}`, task ? 'PATCH' : 'POST', payload);
    toast(task ? 'Task updated' : 'Task created');
  }, task ? `<button type="button" class="text-button danger" data-action="delete-task" data-project="${project.id}" data-id="${task.id}" data-revision="${project.revision}">Delete task</button>` : '');
  modal.querySelector('#task-project')?.addEventListener('change', event => {
    const target = state.projects.find(item => item.id === event.target.value);
    modal.querySelector('[name=workstream_id]').innerHTML = '<option value="">Unassigned</option>' + target.workstreams.map(stream => `<option value="${stream.id}">${escapeHTML(stream.name)}</option>`).join('');
  });
}

function streamModal() {
  const project = selectedProject();
  openModal('A new line of work', 'Group related activities into a workstream.', field('Workstream name', 'name', '', 'required maxlength="100" placeholder="e.g. Security & compliance"') + colorField(), 'Add workstream', async data => {
    await api(`/api/projects/${project.id}/workstreams`, 'POST', { ...data, revision: project.revision });
    toast('Workstream added');
  });
}

async function briefModal(projectId) {
  const brief = await api(`/api/projects/${projectId}/brief`);
  const text = brief.records.map(record => `[${record.source}]\n${record.text}${record.truncated ? '\n[Excerpt truncated]' : ''}`).join('\n\n');
  openModal('Project brief', `Revision ${brief.revision} · ${brief.total_tasks} tasks · ${brief.returned_chars.toLocaleString()} characters${brief.truncated ? ' · bounded excerpt' : ''}`, `<p class="storage-explanation">Planning context for your next conversation or handoff. Unsaved note drafts are not included.</p><label class="field"><span>Select and copy the brief</span><textarea id="project-brief" rows="18" readonly>${escapeHTML(text)}</textarea></label>`, 'Done', async () => {});
}

function relocateModal(projectId) {
  const project = state.projects.find(p => p.id === projectId);
  openModal('Change project folder', 'Move the planning registration; your source files stay where they are.', `${field('Existing destination folder', 'folder', '', 'required maxlength="4096" placeholder="/absolute/path/to/project"')}<p class="storage-explanation">Use an empty planning folder or a folder containing the same saved project.</p>`, 'Use this folder', async data => {
    await api(`/api/projects/${projectId}/relocate`, 'POST', { folder: data.folder });
    toast(`${project?.name || 'Project'} folder updated`);
  });
}

function aboutFolio() {
  const product = state.product;
  return `<section class="workspace-about" aria-labelledby="about-folio-title"><h3 id="about-folio-title">About Folio</h3><p><span class="about-version">Folio ${escapeHTML(product.version)}</span> · <a class="about-license" href="${escapeHTML(product.license_url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(product.license)}</a> · <a class="about-notice" href="${escapeHTML(product.notice_url)}" target="_blank" rel="noopener noreferrer">Notices</a></p>${product.attribution ? `<p class="about-attribution">${escapeHTML(product.attribution)}</p>` : ''}${product.website ? `<a class="about-website" href="${escapeHTML(product.website)}" target="_blank" rel="noopener noreferrer">${escapeHTML(product.website.replace(/^https?:\/\//, '').replace(/\/$/, ''))}</a>` : ''}${product.help_url ? `<p><a class="about-help" href="${escapeHTML(product.help_url)}" target="_blank" rel="noopener noreferrer">Installation and support</a></p>` : ''}</section>`;
}

function storageModal() {
  openModal('Your workspace', 'Local storage.', `<div class="storage-info">${icon('folder')}<div><strong>Workspace registry</strong><code>${escapeHTML(state.workspace)}/registry.json</code><small>Contains client accounts and project folder registrations.</small></div></div><p class="storage-explanation">Each project keeps its tasks, workstreams, notes, and activity in <code>.task-manager/project.json</code> inside its own folder. Source files need their own backup. Run <code>folio doctor</code> to check the workspace and project storage.</p>${state.storage_errors.map(item => `<div class="storage-error"><code>${escapeHTML(item.path)}</code><p>${escapeHTML(item.error)}</p><button type="button" class="button" data-action="relocate-project" data-id="${escapeHTML(item.id)}">Locate project folder</button></div>`).join('')}${aboutFolio()}`, 'Done', async () => {});
}

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-action]');
  if (!button || button.disabled) return;
  const data = button.dataset;
  try {
    switch (data.action) {
      case 'nav': navigate(data.type, data.id || '', data.tab || 'overview'); break;
      case 'tab': navigate(scope.type, scope.id, data.tab); break;
      case 'new-client': clientModal(); break;
      case 'edit-client': clientModal(data.id); break;
      case 'new-project': projectModal(null, data.client); break;
      case 'edit-project': projectModal(data.id); break;
      case 'new-task': taskModal(data.project, null, data.status); break;
      case 'edit-task': taskModal(data.project, data.id); break;
      case 'new-stream': streamModal(); break;
      case 'storage': storageModal(); break;
      case 'project-brief': await briefModal(data.id); break;
      case 'relocate-project': relocateModal(data.id); break;
      case 'close-modal': modal.close(); break;
      case 'layout': layout = data.layout; render(); break;
      case 'menu': mobileOpen = !mobileOpen; render(); break;
      case 'refresh': await refresh(); toast('Workspace refreshed'); break;
      case 'discard-notes':
        if (noteDrafts.has(scope.id) && !confirm('Discard this unsaved draft and load the latest saved notes?')) return;
        noteDrafts.delete(scope.id); notesDirty = noteDrafts.size > 0; await refresh(); break;
      case 'clear-filters': query = ''; statusFilter = ''; priorityFilter = ''; streamFilter = ''; render(); break;
      case 'stat': if (!data.filter) { document.querySelector('.projects-section')?.scrollIntoView({ behavior: 'smooth' }); break; } tab = 'tasks'; statusFilter = data.filter; render(); break;
      case 'attention': tab = 'tasks'; statusFilter = 'attention'; render(); break;
      case 'stream-tasks': tab = 'tasks'; streamFilter = data.id || 'unassigned'; render(); break;
      case 'delete-task':
        if (!confirm('Delete this task? This cannot be undone.')) return;
        await api(`/api/projects/${data.project}/tasks/${data.id}`, 'DELETE', { revision: Number(data.revision) });
        modal.close(); await refresh(); toast('Task deleted'); break;
    }
  } catch (error) { toast(error.message, true); button.disabled = false; }
});

document.addEventListener('input', event => {
  if (event.target.id === 'task-search') { query = event.target.value; document.querySelector('#task-results').innerHTML = taskResults(); }
  if (event.target.id === 'project-notes') {
    const project = selectedProject();
    const draft = noteDrafts.get(project.id) || { original: project.notes, revision: project.revision };
    draft.value = event.target.value;
    noteDrafts.set(project.id, draft);
    notesDirty = true;
    document.querySelector('#notes-status').textContent = 'Unsaved draft — kept while you switch views in this window.';
  }
});

document.addEventListener('change', event => {
  if (event.target.id === 'status-filter') statusFilter = event.target.value;
  else if (event.target.id === 'priority-filter') priorityFilter = event.target.value;
  else if (event.target.id === 'stream-filter') streamFilter = event.target.value;
  else if (event.target.id === 'show-archived') { showArchived = event.target.checked; render(); return; }
  else return;
  document.querySelector('#task-results').innerHTML = taskResults();
});

document.addEventListener('submit', async event => {
  if (event.target.id !== 'notes-form') return;
  event.preventDefault();
  const button = event.target.querySelector('button[type=submit]');
  button.disabled = true;
  const project = selectedProject();
  try {
    await api(`/api/projects/${project.id}`, 'PATCH', { notes: event.target.elements.notes.value, revision: noteDrafts.get(project.id)?.revision ?? project.revision });
    noteDrafts.delete(project.id);
    notesDirty = noteDrafts.size > 0;
    await refresh();
    toast('Project notes saved');
  } catch (error) { toast(error.message, true); button.disabled = false; }
});

document.addEventListener('dragstart', event => {
  const card = event.target.closest('[data-drag-task]');
  if (!card) return;
  event.dataTransfer.setData('text/plain', JSON.stringify({ task: card.dataset.id, project: card.dataset.project }));
  event.dataTransfer.effectAllowed = 'move';
});
document.addEventListener('dragover', event => { const column = event.target.closest('[data-drop-status]'); if (column) { event.preventDefault(); event.dataTransfer.dropEffect = 'move'; } });
document.addEventListener('drop', async event => {
  const column = event.target.closest('[data-drop-status]');
  if (!column) return;
  event.preventDefault();
  try {
    const data = JSON.parse(event.dataTransfer.getData('text/plain'));
    const project = state.projects.find(item => item.id === data.project);
    const task = project?.tasks.find(item => item.id === data.task);
    if (!project || !task) return;
    const status = column.dataset.dropStatus;
    await api(`/api/projects/${project.id}/tasks/${task.id}`, 'PATCH', { status, revision: project.revision });
    await refresh(); toast('Task moved');
  } catch (error) { toast(error.message, true); }
});

document.addEventListener('keydown', event => {
  if (event.ctrlKey || event.metaKey || event.altKey || ['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName) || modal.open) return;
  if (event.key === '/') { event.preventDefault(); tab = 'tasks'; render(); document.querySelector('#task-search')?.focus(); }
  if (event.key === 'n' && state) { event.preventDefault(); taskModal(); }
});
modal.addEventListener('close', () => modalReturnFocus?.isConnected && modalReturnFocus.focus());
window.addEventListener('hashchange', route);
window.addEventListener('beforeunload', event => { if (notesDirty) { event.preventDefault(); event.returnValue = ''; } });
route();
async function connectBrowser() {
  if (launchCredential !== null) {
    const exchange = await api('/api/session', 'POST', { credential: launchCredential });
    sessionProof = exchange.session_proof;
    sessionStorage.setItem('folio.sessionProof', sessionProof);
  }
  await refresh();
}

connectBrowser().catch(error => { app.innerHTML = `<div class="startup-error">${icon('alert')}<h1>Couldn’t open the workspace</h1><p>${escapeHTML(error.message)}</p><p>Run folio ui for this workspace to open an authenticated browser session.</p><button class="button" data-action="refresh">Try again</button></div>`; });
