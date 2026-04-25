// AutoText Popup — Quick Actions and Overview
//
// Three-view popup layout: stat cards in the top grid double as tabs.
// State is persisted in chrome.storage.session so the chosen view
// survives popup re-open within the browser session and resets at
// browser restart (intentional — feels lighter than storage.local).

let activeView = 'shortcuts';
let activeSetFilter = null;  // when shortcuts view is filtered by a set

const TIME_WINDOWS = {
  '7d': 7 * 24 * 60 * 60 * 1000,
  '30d': 30 * 24 * 60 * 60 * 1000,
  'all': null,
};
let activeTimeWindow = '7d';

document.addEventListener('DOMContentLoaded', async () => {
  // Check for dark mode preference
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.body.classList.add('dark');
  }

  // Inject manifest version into the header so it stays in sync with builds
  // automatically — no more hardcoded `v1.0.0` lying after every release.
  try {
    const versionLabel = document.getElementById('version-label');
    if (versionLabel) {
      versionLabel.textContent = `v${chrome.runtime.getManifest().version}`;
    }
  } catch (_) { /* fallback to placeholder */ }

  // Initialize popup
  await initializePopup();

  // Attach event listeners
  attachEventListeners();
});

async function restoreActiveView() {
  try {
    if (!chrome.storage.session) return;
    const saved = await chrome.storage.session.get(['activeView', 'activeTimeWindow']);
    if (saved.activeView && ['shortcuts', 'expansions', 'sets'].includes(saved.activeView)) {
      activeView = saved.activeView;
    }
    if (saved.activeTimeWindow && TIME_WINDOWS[saved.activeTimeWindow] !== undefined) {
      activeTimeWindow = saved.activeTimeWindow;
    }
  } catch (_) { /* fall back to defaults */ }
}

async function initializePopup() {
  try {
    await restoreActiveView();
    await loadStats();
    syncTabUiToState();
    await renderActiveView();
    await updateSyncStatus();
    await showGmailParserWarningIfAny();

    const { auth_token } = await chrome.storage.local.get(['auth_token']);
    if (!auth_token) {
      updateStatus('offline', 'Not synced · open Options to login');
    }
  } catch (error) {
    console.error('Popup initialization error:', error);
    updateStatus('error', 'Error');
  }
}

// Surface the warning written by lib/site-parsers.js when the Gmail
// recipient selectors stop matching. Manual dismiss (X button) clears
// the storage flag — re-appears on the next failed parse.
async function showGmailParserWarningIfAny() {
  const { gmail_parser_warning } = await chrome.storage.local.get('gmail_parser_warning');
  if (!gmail_parser_warning) return;

  const banner = document.createElement('div');
  banner.className = 'parser-warning';
  banner.style.cssText =
    'background:#fff3cd;color:#664d03;border:1px solid #ffe69c;' +
    'padding:6px 10px;border-radius:4px;margin:6px 8px;font-size:12px;' +
    'display:flex;align-items:center;gap:8px;';
  const text = document.createElement('span');
  text.style.flex = '1';
  text.textContent = gmail_parser_warning;
  const close = document.createElement('button');
  close.textContent = '×';
  close.style.cssText = 'background:none;border:none;font-size:18px;cursor:pointer;color:#664d03;line-height:1;';
  close.addEventListener('click', async () => {
    await chrome.storage.local.remove('gmail_parser_warning');
    banner.remove();
  });
  banner.appendChild(text);
  banner.appendChild(close);
  document.body.insertBefore(banner, document.body.firstChild);
}

async function loadStats() {
  const { shortcuts, available_sets, shortcutStats } = await chrome.storage.local.get([
    'shortcuts',
    'available_sets',
    'shortcutStats'
  ]);

  const shortcutCount = shortcuts ? Object.keys(shortcuts).length : 0;
  document.getElementById('stat-shortcuts').textContent = shortcutCount;

  let totalExpansions = 0;
  if (shortcutStats) {
    Object.values(shortcutStats).forEach(stat => {
      totalExpansions += stat.count || 0;
    });
  }
  document.getElementById('stat-expansions').textContent = totalExpansions;

  // available_sets carries full objects; active_sets was just names — switch
  // to available_sets so the Sets view has owner/type/etc. metadata too.
  const setCount = available_sets ? available_sets.length : 0;
  document.getElementById('stat-sets').textContent = setCount;
}

function syncTabUiToState() {
  document.querySelectorAll('.stat-card[data-view]').forEach(card => {
    const isActive = card.dataset.view === activeView;
    card.classList.toggle('active', isActive);
    card.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });
}

async function setActiveView(view) {
  if (view === activeView && !activeSetFilter) return;
  activeView = view;
  if (view !== 'shortcuts') activeSetFilter = null;
  try {
    await chrome.storage.session?.set({ activeView });
  } catch (_) { /* non-critical */ }
  syncTabUiToState();
  await renderActiveView();
}

async function renderActiveView() {
  const titleEl = document.getElementById('view-title');
  const controlsEl = document.getElementById('view-controls');
  const contentEl = document.getElementById('view-content');
  controlsEl.textContent = '';
  contentEl.textContent = '';

  if (activeView === 'shortcuts') {
    titleEl.textContent = activeSetFilter
      ? `Shortcuts în "${activeSetFilter}"`
      : 'Recent & Most Used';
    if (activeSetFilter) {
      const back = document.createElement('button');
      back.className = 'breadcrumb';
      back.textContent = '← Toate seturile';
      back.addEventListener('click', () => {
        activeSetFilter = null;
        renderActiveView();
      });
      controlsEl.appendChild(back);
    }
    await renderShortcutsView(contentEl);
  } else if (activeView === 'expansions') {
    titleEl.textContent = 'Activitate';
    controlsEl.appendChild(buildTimeFilterSelect());
    await renderExpansionsView(contentEl);
  } else if (activeView === 'sets') {
    titleEl.textContent = 'Sets';
    await renderSetsView(contentEl);
  }
}

function buildTimeFilterSelect() {
  const select = document.createElement('select');
  select.className = 'time-filter';
  [['7d', 'Ultimele 7 zile'], ['30d', 'Ultimele 30 zile'], ['all', 'Tot timpul']]
    .forEach(([val, label]) => {
      const opt = document.createElement('option');
      opt.value = val;
      opt.textContent = label;
      if (activeTimeWindow === val) opt.selected = true;
      select.appendChild(opt);
    });
  select.addEventListener('change', async () => {
    activeTimeWindow = select.value;
    try { await chrome.storage.session?.set({ activeTimeWindow }); } catch (_) {}
    renderActiveView();
  });
  return select;
}

async function renderShortcutsView(container) {
  const { shortcuts, shortcutStats } = await chrome.storage.local.get(['shortcuts', 'shortcutStats']);

  if (!shortcuts || Object.keys(shortcuts).length === 0) {
    container.appendChild(emptyState('📝', 'Niciun shortcut sincronizat. Apasă Sync Now.'));
    return;
  }

  // Combine shortcuts with both local + server-side usage stats. Local
  // stats are device-only; server `usage_count` is cross-device. Sorting
  // on combined count makes a heavily used shortcut on another device
  // still surface here.
  const rows = Object.entries(shortcuts).map(([key, data]) => {
    const localStats = (shortcutStats && shortcutStats[key]) || { count: 0, lastUsed: 0 };
    const serverCount = data.usage_count || 0;
    return {
      key,
      value: data.value || '',
      sets: data.sets || [],
      count: localStats.count + serverCount,
      lastUsed: Math.max(
        localStats.lastUsed || 0,
        data.last_used_at ? Date.parse(data.last_used_at) : 0
      ),
    };
  });

  const filtered = activeSetFilter
    ? rows.filter(r => Array.isArray(r.sets) && r.sets.includes(activeSetFilter))
    : rows;

  filtered.sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count;
    return (b.lastUsed || 0) - (a.lastUsed || 0);
  });

  if (filtered.length === 0) {
    container.appendChild(emptyState('🔍', 'Niciun shortcut în acest set.'));
    return;
  }

  filtered.slice(0, 10).forEach(row => container.appendChild(createShortcutItem(row)));
}

async function renderExpansionsView(container) {
  const { shortcuts, shortcutStats } = await chrome.storage.local.get(['shortcuts', 'shortcutStats']);
  const window = TIME_WINDOWS[activeTimeWindow];
  const cutoff = window ? Date.now() - window : 0;

  if (!shortcutStats || Object.keys(shortcutStats).length === 0) {
    container.appendChild(emptyState('📊', 'Nu ai folosit niciun shortcut încă.'));
    return;
  }

  const rows = Object.entries(shortcutStats).map(([key, stat]) => {
    const data = (shortcuts && shortcuts[key]) || {};
    return {
      key,
      value: data.value || '',
      count: countExpansionsInWindow(stat, cutoff),
      lastUsed: stat.lastUsed || 0,
    };
  }).filter(row => row.count > 0);

  rows.sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count;
    return (b.lastUsed || 0) - (a.lastUsed || 0);
  });

  if (rows.length === 0) {
    container.appendChild(emptyState('🕒', 'Nicio activitate în această fereastră.'));
    return;
  }

  rows.slice(0, 10).forEach(row => container.appendChild(createExpansionItem(row)));
}

// Counts timestamps in the window. cutoff=0 means "all time" → return scalar.
// Legacy rows without timestamps[] fall back to "1 if lastUsed within window".
function countExpansionsInWindow(stat, cutoff) {
  if (!cutoff) return stat.count || 0;
  if (!Array.isArray(stat.timestamps) || stat.timestamps.length === 0) {
    return stat.lastUsed && stat.lastUsed >= cutoff ? (stat.count || 1) : 0;
  }
  return stat.timestamps.filter(ts => ts >= cutoff).length;
}

async function renderSetsView(container) {
  const { shortcuts, available_sets, shortcutStats } = await chrome.storage.local.get([
    'shortcuts', 'available_sets', 'shortcutStats',
  ]);

  if (!available_sets || available_sets.length === 0) {
    container.appendChild(emptyState('📂', 'Niciun set disponibil.'));
    return;
  }

  const sorted = [...available_sets].sort((a, b) => {
    if (a.set_type !== b.set_type) return a.set_type === 'general' ? -1 : 1;
    return (a.name || '').localeCompare(b.name || '');
  });

  sorted.forEach(set => {
    const summary = summarizeSetData(set, shortcuts || {}, shortcutStats || {});
    container.appendChild(createSetCard(set, summary));
  });
}

// Aggregates per-set metrics over locally cached data.
// Returns: { shortcutCount, totalExpansions, lastUsedAt, owner }
function summarizeSetData(set, allShortcuts, allStats) {
  let shortcutCount = 0;
  let totalExpansions = 0;
  let lastUsedAt = 0;

  Object.entries(allShortcuts).forEach(([key, data]) => {
    const sets = data.sets || [];
    if (!sets.includes(set.name)) return;
    shortcutCount++;
    const localCount = (allStats[key] && allStats[key].count) || 0;
    const serverCount = data.usage_count || 0;
    totalExpansions += localCount + serverCount;
    const localLast = (allStats[key] && allStats[key].lastUsed) || 0;
    const serverLast = data.last_used_at ? Date.parse(data.last_used_at) : 0;
    lastUsedAt = Math.max(lastUsedAt, localLast, serverLast);
  });

  return {
    shortcutCount,
    totalExpansions,
    lastUsedAt,
    owner: set.set_type === 'personal' ? (set.owner_username || null) : null,
  };
}

function emptyState(icon, message) {
  const wrap = document.createElement('div');
  wrap.className = 'empty-state';
  const ic = document.createElement('div');
  ic.className = 'empty-state-icon';
  ic.textContent = icon;
  const text = document.createElement('p');
  text.textContent = message;
  wrap.appendChild(ic);
  wrap.appendChild(text);
  return wrap;
}

function formatTimeAgo(ts) {
  if (!ts) return 'niciodată';
  const diff = Date.now() - ts;
  if (diff < 60000) return 'acum';
  if (diff < 3600000) return `acum ${Math.floor(diff / 60000)}m`;
  if (diff < 86400000) return `acum ${Math.floor(diff / 3600000)}h`;
  if (diff < 7 * 86400000) return `acum ${Math.floor(diff / 86400000)}z`;
  return new Date(ts).toLocaleDateString('ro-RO');
}

function createShortcutItem(shortcut) {
  const item = document.createElement('div');
  item.className = 'shortcut-item';

  const keySpan = document.createElement('span');
  keySpan.className = 'shortcut-key';
  keySpan.textContent = shortcut.key;

  const previewSpan = document.createElement('span');
  previewSpan.className = 'shortcut-preview';
  previewSpan.textContent = shortcut.value.substring(0, 50) || 'Rich text';

  const countSpan = document.createElement('span');
  countSpan.className = 'shortcut-count';
  countSpan.textContent = shortcut.count > 0 ? `${shortcut.count}×` : 'new';

  item.appendChild(keySpan);
  item.appendChild(previewSpan);
  item.appendChild(countSpan);

  // Copy shortcut key on click
  item.addEventListener('click', () => {
    navigator.clipboard.writeText(shortcut.key).then(() => {
      keySpan.textContent = '✓';
      setTimeout(() => {
        keySpan.textContent = shortcut.key;
      }, 1000);
    });
  });

  return item;
}

function createExpansionItem(row) {
  const item = document.createElement('div');
  item.className = 'shortcut-item';

  const keySpan = document.createElement('span');
  keySpan.className = 'shortcut-key';
  keySpan.textContent = row.key;

  const previewSpan = document.createElement('span');
  previewSpan.className = 'shortcut-preview';
  previewSpan.textContent = (row.value || '').substring(0, 50) || 'Rich text';

  const countSpan = document.createElement('span');
  countSpan.className = 'shortcut-count';
  countSpan.textContent = `${row.count}×`;

  const ago = document.createElement('span');
  ago.className = 'shortcut-time-ago';
  ago.textContent = formatTimeAgo(row.lastUsed);

  item.appendChild(keySpan);
  item.appendChild(previewSpan);
  item.appendChild(countSpan);
  item.appendChild(ago);
  return item;
}

function createSetCard(set, summary) {
  const card = document.createElement('div');
  card.className = 'set-card';
  card.tabIndex = 0;

  const header = document.createElement('div');
  header.className = 'set-card-header';

  const name = document.createElement('span');
  name.className = 'set-name';
  name.textContent = set.name;

  const badge = document.createElement('span');
  const isGeneral = set.set_type === 'general';
  badge.className = `set-type-badge ${isGeneral ? 'general' : 'personal'}`;
  badge.textContent = isGeneral ? 'BIROU' : 'PERSONAL';

  header.appendChild(name);
  header.appendChild(badge);

  const meta = document.createElement('div');
  meta.className = 'set-meta';
  const parts = [
    `${summary.shortcutCount} shortcut${summary.shortcutCount === 1 ? '' : '-uri'}`,
    `${summary.totalExpansions} expand${summary.totalExpansions === 1 ? '' : '-uri'}`,
  ];
  if (summary.owner) parts.push(`owner: ${summary.owner}`);
  if (summary.lastUsedAt) parts.push(`ultima dată: ${formatTimeAgo(summary.lastUsedAt)}`);
  meta.textContent = parts.join(' · ');

  card.appendChild(header);
  card.appendChild(meta);

  const route = () => {
    activeSetFilter = set.name;
    setActiveView('shortcuts');
  };
  card.addEventListener('click', route);
  card.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      route();
    }
  });

  return card;
}

async function updateSyncStatus() {
  const { last_sync } = await chrome.storage.local.get('last_sync');

  if (last_sync) {
    const date = new Date(last_sync);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);

    let timeAgo;
    if (diffMins < 1) {
      timeAgo = 'Just now';
    } else if (diffMins < 60) {
      timeAgo = `${diffMins}m ago`;
    } else if (diffHours < 24) {
      timeAgo = `${diffHours}h ago`;
    } else {
      timeAgo = date.toLocaleDateString();
    }

    document.getElementById('last-sync').textContent = timeAgo;
    updateStatus('online', 'Synced');
  } else {
    document.getElementById('last-sync').textContent = 'Never';
    updateStatus('offline', 'Not synced');
  }
}

function updateStatus(status, text) {
  const dot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');

  dot.className = 'status-dot';
  if (status === 'offline') {
    dot.classList.add('offline');
  } else if (status === 'error') {
    dot.classList.add('error');
  }

  statusText.textContent = text;
}

function attachEventListeners() {
  // Stat cards as tabs — click + keyboard for a11y.
  document.querySelectorAll('.stat-card[data-view]').forEach(card => {
    card.addEventListener('click', () => setActiveView(card.dataset.view));
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        setActiveView(card.dataset.view);
      }
    });
  });

  // Search functionality (semantic per view)
  const searchInput = document.getElementById('search-input');
  searchInput.addEventListener('input', handleSearch);

  // Sync button
  document.getElementById('btn-sync').addEventListener('click', handleSync);

  // Options button
  document.getElementById('btn-options').addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
  });

  // Login button
  document.getElementById('btn-login').addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
  });

  // Help link
  document.getElementById('help-link').addEventListener('click', (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: 'https://autotext.zua.ro/help' });
  });
}

async function handleSearch(e) {
  const query = e.target.value.toLowerCase().trim();
  const container = document.getElementById('view-content');
  container.textContent = '';

  if (!query) {
    await renderActiveView();
    return;
  }

  if (activeView === 'sets') {
    const { shortcuts, available_sets, shortcutStats } = await chrome.storage.local.get([
      'shortcuts', 'available_sets', 'shortcutStats',
    ]);
    const matches = (available_sets || []).filter(s =>
      (s.name || '').toLowerCase().includes(query));
    if (matches.length === 0) {
      container.appendChild(emptyState('🔍', 'Niciun set găsit.'));
      return;
    }
    matches.forEach(set => container.appendChild(
      createSetCard(set, summarizeSetData(set, shortcuts || {}, shortcutStats || {}))
    ));
    return;
  }

  const { shortcuts, shortcutStats } = await chrome.storage.local.get(['shortcuts', 'shortcutStats']);
  if (!shortcuts) return;

  const filtered = Object.entries(shortcuts)
    .filter(([key, data]) =>
      key.toLowerCase().includes(query) ||
      (data.value && data.value.toLowerCase().includes(query)))
    .map(([key, data]) => {
      const stats = (shortcutStats && shortcutStats[key]) || { count: 0 };
      return {
        key,
        value: data.value || '',
        count: (stats.count || 0) + (data.usage_count || 0),
        lastUsed: stats.lastUsed || 0,
      };
    })
    .slice(0, 10);

  if (filtered.length === 0) {
    container.appendChild(emptyState('🔍', 'Niciun shortcut găsit.'));
    return;
  }

  filtered.forEach(shortcut => container.appendChild(
    activeView === 'expansions' ? createExpansionItem(shortcut) : createShortcutItem(shortcut)
  ));
}

async function handleSync() {
  const syncBtn = document.getElementById('btn-sync');
  const syncIcon = document.getElementById('sync-icon');

  syncBtn.disabled = true;
  syncIcon.classList.add('syncing');

  try {
    await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ action: 'sync' }, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response);
        }
      });
    });

    // Reload stats and re-render current view
    await loadStats();
    await renderActiveView();
    await updateSyncStatus();

    updateStatus('online', 'Synced');

  } catch (error) {
    console.error('Sync error:', error);
    updateStatus('error', 'Sync failed');
  } finally {
    syncBtn.disabled = false;
    syncIcon.classList.remove('syncing');
  }
}
