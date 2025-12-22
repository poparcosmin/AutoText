// AutoText Popup - Quick Actions and Overview

document.addEventListener('DOMContentLoaded', async () => {
  // Check for dark mode preference
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.body.classList.add('dark');
  }

  // Initialize popup
  await initializePopup();

  // Attach event listeners
  attachEventListeners();
});

async function initializePopup() {
  try {
    // Check authentication status
    const { auth_token, username } = await chrome.storage.local.get(['auth_token', 'username']);

    if (!auth_token) {
      showLoginPrompt();
      return;
    }

    // Load and display data
    await loadStats();
    await loadShortcuts();
    await updateSyncStatus();

  } catch (error) {
    console.error('Popup initialization error:', error);
    updateStatus('error', 'Error');
  }
}

function showLoginPrompt() {
  document.getElementById('login-prompt').classList.remove('hidden');
  document.getElementById('main-content').classList.add('hidden');
  updateStatus('offline', 'Not logged in');
}

async function loadStats() {
  const { shortcuts, active_sets, shortcutStats } = await chrome.storage.local.get([
    'shortcuts',
    'active_sets',
    'shortcutStats'
  ]);

  // Count shortcuts
  const shortcutCount = shortcuts ? Object.keys(shortcuts).length : 0;
  document.getElementById('stat-shortcuts').textContent = shortcutCount;

  // Count total expansions
  let totalExpansions = 0;
  if (shortcutStats) {
    Object.values(shortcutStats).forEach(stat => {
      totalExpansions += stat.count || 0;
    });
  }
  document.getElementById('stat-expansions').textContent = totalExpansions;

  // Count active sets
  const setCount = active_sets ? active_sets.length : 0;
  document.getElementById('stat-sets').textContent = setCount;
}

async function loadShortcuts() {
  const { shortcuts, shortcutStats } = await chrome.storage.local.get(['shortcuts', 'shortcutStats']);
  const listContainer = document.getElementById('shortcuts-list');
  listContainer.textContent = ''; // Clear existing content

  if (!shortcuts || Object.keys(shortcuts).length === 0) {
    const emptyState = document.createElement('div');
    emptyState.className = 'empty-state';

    const icon = document.createElement('div');
    icon.className = 'empty-state-icon';
    icon.textContent = '📝';

    const text = document.createElement('p');
    text.textContent = 'No shortcuts yet. Sync to get started!';

    emptyState.appendChild(icon);
    emptyState.appendChild(text);
    listContainer.appendChild(emptyState);
    return;
  }

  // Combine shortcuts with stats and sort by usage
  const shortcutsWithStats = Object.entries(shortcuts).map(([key, data]) => {
    const stats = shortcutStats && shortcutStats[key] ? shortcutStats[key] : { count: 0, lastUsed: 0 };
    return {
      key,
      value: data.value || '',
      count: stats.count,
      lastUsed: stats.lastUsed
    };
  });

  // Sort by count (most used first), then by last used
  shortcutsWithStats.sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count;
    return (b.lastUsed || 0) - (a.lastUsed || 0);
  });

  // Display top 3
  const topShortcuts = shortcutsWithStats.slice(0, 3);

  topShortcuts.forEach(shortcut => {
    const item = createShortcutItem(shortcut);
    listContainer.appendChild(item);
  });
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
  // Search functionality
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
  const { shortcuts, shortcutStats } = await chrome.storage.local.get(['shortcuts', 'shortcutStats']);

  if (!shortcuts) return;

  const listContainer = document.getElementById('shortcuts-list');
  listContainer.textContent = '';

  const filtered = Object.entries(shortcuts)
    .filter(([key, data]) => {
      return key.toLowerCase().includes(query) ||
             (data.value && data.value.toLowerCase().includes(query));
    })
    .map(([key, data]) => {
      const stats = shortcutStats && shortcutStats[key] ? shortcutStats[key] : { count: 0 };
      return { key, value: data.value || '', count: stats.count };
    })
    .slice(0, 10);

  if (filtered.length === 0) {
    const emptyState = document.createElement('div');
    emptyState.className = 'empty-state';
    emptyState.textContent = 'No shortcuts found';
    listContainer.appendChild(emptyState);
    return;
  }

  filtered.forEach(shortcut => {
    const item = createShortcutItem(shortcut);
    listContainer.appendChild(item);
  });
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

    // Reload stats and shortcuts
    await loadStats();
    await loadShortcuts();
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
