// AutoText Options Page Logic with Authentication
// CONFIG is imported from config.js (loaded in options.html)

let availableSets = [];
let selectedSets = [];
let currentUser = null;
let authToken = null;
let allShortcuts = {};
// User role flags from /auth/login or /auth/check responses. Defaults
// false so unauthenticated UI hides curator-only controls. Updated on
// every successful login or token refresh.
let userPerms = { is_superuser: false, is_birou_curator: false };
let userSettings = {
  triggerKey: 'Tab',
  showToast: true,
  showHighlight: true,
  playSound: false,
  blacklistedSites: []
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
  console.log('AutoText Options: Initializing...');

  // Initialize theme
  initializeTheme();

  // Initialize tabs
  initializeTabs();

  try {
    // Check if user is authenticated
    await checkAuthentication();
  } catch (error) {
    showError(`Failed to load: ${error.message}`);
  }
});

// Theme Management
function initializeTheme() {
  const themeToggle = document.getElementById('theme-toggle');

  // Check saved theme or system preference
  chrome.storage.local.get('theme', (result) => {
    if (result.theme === 'dark' ||
        (!result.theme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.body.classList.add('dark');
      themeToggle.textContent = '☀️';
    }
  });

  themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark');
    const isDark = document.body.classList.contains('dark');
    themeToggle.textContent = isDark ? '☀️' : '🌙';
    chrome.storage.local.set({ theme: isDark ? 'dark' : 'light' });
  });
}

// Tab Navigation
function initializeTabs() {
  const tabs = document.querySelectorAll('.tab');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      // Remove active from all tabs and contents
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      // Add active to clicked tab
      tab.classList.add('active');

      // Show corresponding content
      const tabId = tab.dataset.tab;
      document.getElementById(`tab-${tabId}`).classList.add('active');

      // Load tab-specific data
      if (tabId === 'shortcuts') {
        loadShortcutsPreview();
      } else if (tabId === 'settings') {
        loadUserSettings();
      } else if (tabId === 'manage') {
        loadManageShortcuts();
      }
    });
  });
}

// Check if user has valid auth token
async function checkAuthentication() {
  const result = await chrome.storage.local.get(['auth_token', 'username', 'user_perms']);
  authToken = result.auth_token;
  currentUser = result.username;
  if (result.user_perms) {
    userPerms = { ...userPerms, ...result.user_perms };
  }

  if (!authToken) {
    // No token - show login form
    showLoginForm();
    return;
  }

  // Verify token is still valid
  try {
    const response = await fetch(`${CONFIG.API_URL}/auth/verify/`, {
      headers: {
        'Authorization': `Token ${authToken}`
      }
    });

    if (response.ok) {
      const data = await response.json();
      if (data.valid) {
        // Token is valid - proceed to show sets
        currentUser = data.user.username;
        userPerms = {
          is_superuser: !!data.user.is_superuser,
          is_birou_curator: !!data.user.is_birou_curator,
        };
        await chrome.storage.local.set({ user_perms: userPerms });
        await loadSetsView();
      } else {
        // Token expired
        console.log('Token expired');
        await chrome.storage.local.remove(['auth_token', 'username']);
        showLoginForm();
      }
    } else {
      // 401 or other error - show login
      await chrome.storage.local.remove(['auth_token', 'username']);
      showLoginForm();
    }
  } catch (error) {
    console.error('Failed to verify token:', error);
    showLoginForm();
  }
}

// Show login form
function showLoginForm() {
  document.getElementById('loading').style.display = 'none';
  document.getElementById('login-section').style.display = 'block';
  document.getElementById('sets-container').style.display = 'none';

  // Attach login form handler
  document.getElementById('login-form').addEventListener('submit', handleLogin);
}

// Handle login form submission
async function handleLogin(e) {
  e.preventDefault();

  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const loginBtn = document.getElementById('login');

  if (!username || !password) {
    showError('Please enter username and password');
    return;
  }

  // Disable button during login
  loginBtn.disabled = true;
  loginBtn.textContent = 'Logging in...';

  try {
    const response = await fetch(`${CONFIG.API_URL}/auth/login/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ username, password })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Login failed');
    }

    // Save token, username, and expiration time
    authToken = data.token;
    currentUser = data.user.username;
    userPerms = {
      is_superuser: !!data.user.is_superuser,
      is_birou_curator: !!data.user.is_birou_curator,
    };

    await chrome.storage.local.set({
      auth_token: authToken,
      username: currentUser,
      user_perms: userPerms,
      token_expires_at: data.expires_at,
      api_url: CONFIG.API_URL  // Save API URL for content scripts
    });

    console.log('Login successful for user:', currentUser);

    // Hide login form, show sets
    document.getElementById('login-section').style.display = 'none';
    await loadSetsView();

    // Trigger initial sync
    await triggerBackgroundSync();

  } catch (error) {
    showError(error.message || 'Login failed');
    loginBtn.disabled = false;
    loginBtn.textContent = 'Login';
  }
}

// Load sets view after authentication
async function loadSetsView() {
  document.getElementById('loading').style.display = 'block';

  try {
    // Load available sets from API
    await loadAvailableSets();

    // Load user's selected sets from storage
    await loadSelectedSets();

    // Render UI
    renderSets();

    // Attach event listeners
    attachEventListeners();

    // Show user info
    document.getElementById('current-user').textContent = currentUser;

  } catch (error) {
    showError(`Failed to load sets: ${error.message}`);
  }
}

// Fetch available sets from Django API
async function loadAvailableSets() {
  console.log('Fetching available sets from API...');

  const response = await fetch(`${CONFIG.API_URL}/sets/`, {
    headers: {
      'Authorization': `Token ${authToken}`
    }
  });

  if (!response.ok) {
    if (response.status === 401) {
      // Token invalid - logout
      await handleLogout();
      throw new Error('Session expired. Please login again.');
    }
    throw new Error(`API returned ${response.status}: ${response.statusText}`);
  }

  availableSets = await response.json();
  console.log(`Loaded ${availableSets.length} sets:`, availableSets);
}

// Load selected sets from chrome.storage
async function loadSelectedSets() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['active_sets'], (result) => {
      selectedSets = result.active_sets || ['birou']; // Default to 'birou'
      console.log('Currently selected sets:', selectedSets);
      resolve();
    });
  });
}

// Render sets UI
function renderSets() {
  const generalList = document.getElementById('general-list');
  const personalList = document.getElementById('personal-list');
  const loading = document.getElementById('loading');
  const container = document.getElementById('sets-container');

  // Clear loading
  loading.style.display = 'none';
  container.style.display = 'block';

  // Group sets by type
  const generalSets = availableSets.filter(s => s.set_type === 'general');
  const personalSets = availableSets.filter(s => s.set_type === 'personal');

  // Render general sets
  generalSets.forEach(set => {
    generalList.appendChild(createSetOption(set));
  });

  // Render personal sets
  personalSets.forEach(set => {
    personalList.appendChild(createSetOption(set));
  });

  console.log('UI rendered successfully');
}

// Create HTML for a single set option
function createSetOption(set) {
  const div = document.createElement('div');
  div.className = 'set-option';
  div.dataset.setName = set.name;

  // Case-insensitive match since we normalize to lowercase on save
  const isSelected = selectedSets.some(s => s.toLowerCase() === set.name.toLowerCase());
  if (isSelected) {
    div.classList.add('selected');
  }

  div.innerHTML = `
    <input type="checkbox"
           id="set-${set.name}"
           value="${set.name}"
           ${isSelected ? 'checked' : ''}>
    <div class="set-info">
      <div class="set-name">${set.name}</div>
      <div class="set-description">${set.description || 'No description'}</div>
    </div>
    <span class="set-count">${set.shortcut_count} shortcuts</span>
  `;

  // Click on div also toggles checkbox
  div.addEventListener('click', (e) => {
    if (e.target.tagName !== 'INPUT') {
      const checkbox = div.querySelector('input');
      checkbox.checked = !checkbox.checked;
      checkbox.dispatchEvent(new Event('change'));
    }
  });

  // Handle checkbox change
  const checkbox = div.querySelector('input');
  checkbox.addEventListener('change', (e) => {
    e.stopPropagation();

    if (checkbox.checked) {
      div.classList.add('selected');
      // Case-insensitive check to avoid duplicates
      if (!selectedSets.some(s => s.toLowerCase() === set.name.toLowerCase())) {
        selectedSets.push(set.name);
      }
    } else {
      div.classList.remove('selected');
      // Case-insensitive removal
      selectedSets = selectedSets.filter(s => s.toLowerCase() !== set.name.toLowerCase());
    }

    console.log('Selected sets updated:', selectedSets);
  });

  return div;
}

// Attach event listeners to buttons
function attachEventListeners() {
  document.getElementById('save').addEventListener('click', saveAndSync);
  document.getElementById('logout').addEventListener('click', handleLogout);

  // Settings tab
  document.getElementById('save-settings').addEventListener('click', saveUserSettings);

  // Shortcuts search with autocomplete
  const searchInput = document.getElementById('shortcuts-search');
  searchInput.addEventListener('input', debounce(handleAutocompleteSearch, 300));
  searchInput.addEventListener('focus', () => {
    if (searchInput.value.length > 0) {
      handleAutocompleteSearch({ target: searchInput });
    }
  });
  searchInput.addEventListener('blur', () => {
    // Delay hiding to allow click on dropdown items
    setTimeout(() => hideAutocompleteDropdown(), 200);
  });

  // Manage tab search
  document.getElementById('manage-search').addEventListener('input', handleManageSearch);

  // CRUD modal
  document.getElementById('btn-add-shortcut').addEventListener('click', () => openShortcutModal());
  document.getElementById('modal-close').addEventListener('click', closeShortcutModal);
  document.getElementById('modal-cancel').addEventListener('click', closeShortcutModal);
  document.getElementById('modal-save').addEventListener('click', saveShortcut);
  document.getElementById('modal-test-expand')?.addEventListener('click', runTestExpand);
  document.getElementById('modal-test-close')?.addEventListener('click', () => {
    document.getElementById('modal-test-panel').classList.add('hidden');
  });

  // Content type toggle in modal
  document.querySelectorAll('.content-type-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.content-type-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const type = btn.dataset.type;
      document.getElementById('text-content-group').style.display = type === 'text' ? 'block' : 'none';
      document.getElementById('html-content-group').style.display = type === 'html' ? 'block' : 'none';

      // Initialize TinyMCE when switching to HTML mode (lazy init for proper rendering)
      if (type === 'html') {
        initTinyMCE();
      }
    });
  });

  // Close modal on overlay click
  document.getElementById('shortcut-modal').addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
      closeShortcutModal();
    }
  });

  // Backup tab
  document.getElementById('export-all').addEventListener('click', handleExportAll);
  document.getElementById('export-stats').addEventListener('click', handleExportStats);
  document.getElementById('import-data').addEventListener('click', () => {
    document.getElementById('import-file').click();
  });
  document.getElementById('import-file').addEventListener('change', handleImportData);
  document.getElementById('reset-data').addEventListener('click', handleResetData);
}

// ==========================================
// SHORTCUTS PREVIEW
// ==========================================

async function loadShortcutsPreview() {
  const result = await chrome.storage.local.get('shortcuts');
  allShortcuts = result.shortcuts || {};

  renderShortcutsPreview(allShortcuts);
}

function renderShortcutsPreview(shortcuts) {
  const container = document.getElementById('shortcuts-preview-list');
  const countEl = document.getElementById('shortcuts-count');
  container.textContent = ''; // Clear safely

  const entries = Object.entries(shortcuts);
  countEl.textContent = entries.length;

  if (entries.length === 0) {
    const emptyDiv = document.createElement('div');
    emptyDiv.style.cssText = 'padding: 30px; text-align: center; color: var(--text-secondary-light);';
    emptyDiv.textContent = 'No shortcuts loaded. Select sets and sync first.';
    container.appendChild(emptyDiv);
    return;
  }

  entries.forEach(([key, data]) => {
    const row = document.createElement('div');
    row.className = 'shortcut-row';

    const keyBadge = document.createElement('span');
    keyBadge.className = 'shortcut-key-badge';
    keyBadge.textContent = key;

    row.appendChild(keyBadge);

    // Add set badges if available (after key, before value)
    const setNames = data.sets || (data.set_name ? [data.set_name] : []);
    if (setNames.length > 0) {
      const setsDiv = document.createElement('div');
      setsDiv.className = 'shortcut-sets';

      setNames.forEach(setName => {
        const badge = document.createElement('span');
        badge.className = 'set-badge';
        badge.textContent = setName;
        // Special styling for Birou set
        if (setName === 'Birou') {
          badge.style.cssText = 'background: #6c757d; color: white;';
        }
        setsDiv.appendChild(badge);
      });

      row.appendChild(setsDiv);
    }

    const value = document.createElement('span');
    value.className = 'shortcut-value';
    value.textContent = data.value || (data.html_value ? '[Rich text]' : '');

    row.appendChild(value);
    container.appendChild(row);
  });
}

function handleShortcutsSearch(e) {
  const query = e.target.value.toLowerCase().trim();

  if (!query) {
    renderShortcutsPreview(allShortcuts);
    return;
  }

  const filtered = {};
  Object.entries(allShortcuts).forEach(([key, data]) => {
    if (key.toLowerCase().includes(query) ||
        (data.value && data.value.toLowerCase().includes(query))) {
      filtered[key] = data;
    }
  });

  renderShortcutsPreview(filtered);
}

// ==========================================
// USER SETTINGS
// ==========================================

async function loadUserSettings() {
  const result = await chrome.storage.local.get('settings');

  if (result.settings) {
    userSettings = { ...userSettings, ...result.settings };
  }

  // Populate UI
  document.getElementById('setting-trigger-key').value = userSettings.triggerKey || 'Tab';
  document.getElementById('setting-trigger-mode').value = userSettings.triggerMode || 'key';
  document.getElementById('setting-show-toast').checked = userSettings.showToast !== false;
  document.getElementById('setting-play-sound').checked = userSettings.playSound || false;
  document.getElementById('setting-blacklist').value =
    (userSettings.blacklistedSites || []).join('\n');
}

async function saveUserSettings() {
  const triggerKey = document.getElementById('setting-trigger-key').value;
  const triggerMode = document.getElementById('setting-trigger-mode').value;
  const showToast = document.getElementById('setting-show-toast').checked;
  const playSound = document.getElementById('setting-play-sound').checked;
  const blacklistText = document.getElementById('setting-blacklist').value;

  // Parse blacklist (one domain per line, trim whitespace)
  const blacklistedSites = blacklistText
    .split('\n')
    .map(s => s.trim())
    .filter(s => s.length > 0);

  userSettings = {
    triggerKey,
    triggerMode,
    showToast,
    showHighlight: true,
    playSound,
    blacklistedSites
  };

  await chrome.storage.local.set({ settings: userSettings });

  showStatus('Settings saved successfully!', 'success');
  console.log('Settings saved:', userSettings);
}

// ==========================================
// EXPORT / IMPORT
// ==========================================

async function handleExportAll() {
  try {
    const result = await chrome.storage.local.get([
      'shortcuts',
      'active_sets',
      'settings',
      'shortcutStats'
    ]);

    const exportData = {
      version: '1.1.0',
      exportedAt: new Date().toISOString(),
      data: result
    };

    downloadJson(exportData, 'autotext-backup.json');
    showStatus('Data exported successfully!', 'success');
  } catch (error) {
    showError('Failed to export data: ' + error.message);
  }
}

async function handleExportStats() {
  try {
    const result = await chrome.storage.local.get('shortcutStats');
    const stats = result.shortcutStats || {};

    const exportData = {
      version: '1.1.0',
      exportedAt: new Date().toISOString(),
      statistics: stats
    };

    downloadJson(exportData, 'autotext-stats.json');
    showStatus('Statistics exported successfully!', 'success');
  } catch (error) {
    showError('Failed to export statistics: ' + error.message);
  }
}

function downloadJson(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function handleImportData(e) {
  const file = e.target.files[0];
  if (!file) return;

  try {
    const text = await file.text();
    const importData = JSON.parse(text);

    if (!importData.data) {
      throw new Error('Invalid backup file format');
    }

    // Confirm import
    if (!confirm('This will replace your current settings and statistics. Continue?')) {
      return;
    }

    // Import data
    if (importData.data.settings) {
      await chrome.storage.local.set({ settings: importData.data.settings });
    }
    if (importData.data.active_sets) {
      await chrome.storage.local.set({ active_sets: importData.data.active_sets });
    }
    if (importData.data.shortcutStats) {
      await chrome.storage.local.set({ shortcutStats: importData.data.shortcutStats });
    }

    showStatus('Data imported successfully! Reloading...', 'success');

    // Reload to apply changes
    setTimeout(() => window.location.reload(), 1500);

  } catch (error) {
    showError('Failed to import data: ' + error.message);
  }

  // Reset file input
  e.target.value = '';
}

async function handleResetData() {
  if (!confirm('Are you sure you want to reset all local data? This cannot be undone.')) {
    return;
  }

  try {
    // Keep auth info but clear everything else
    const { auth_token, username } = await chrome.storage.local.get(['auth_token', 'username']);

    await chrome.storage.local.clear();

    // Restore auth
    if (auth_token && username) {
      await chrome.storage.local.set({ auth_token, username });
    }

    showStatus('Local data reset. Reloading...', 'success');

    setTimeout(() => window.location.reload(), 1500);
  } catch (error) {
    showError('Failed to reset data: ' + error.message);
  }
}

// Handle logout
async function handleLogout() {
  try {
    // Call logout endpoint
    await fetch(`${CONFIG.API_URL}/auth/logout/`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${authToken}`
      }
    });
  } catch (error) {
    console.error('Logout API call failed:', error);
    // Continue with local logout anyway
  }

  // Clear local storage
  await chrome.storage.local.remove(['auth_token', 'username']);

  // Reset state
  authToken = null;
  currentUser = null;
  availableSets = [];
  selectedSets = [];

  // Hide sets container
  document.getElementById('sets-container').style.display = 'none';

  // Show login form
  showLoginForm();

  console.log('Logged out successfully');
}

// Save selected sets and trigger sync
async function saveAndSync() {
  console.log('Saving selected sets:', selectedSets);

  if (selectedSets.length === 0) {
    showStatus('Please select at least one set!', 'info');
    return;
  }

  // Disable button during save
  const saveBtn = document.getElementById('save');
  saveBtn.disabled = true;
  saveBtn.textContent = '💾 Saving...';

  try {
    // Normalize: lowercase and remove duplicates
    const normalizedSets = [...new Set(selectedSets.map(s => s.toLowerCase()))];
    console.log('Normalized sets:', normalizedSets);

    // Save to storage
    await new Promise((resolve) => {
      chrome.storage.local.set({ active_sets: normalizedSets }, resolve);
    });

    console.log('Sets saved to storage');

    // Clear last_sync to force full sync (not delta)
    await chrome.storage.local.remove('last_sync');
    console.log('Cleared last_sync - forcing full sync');

    // Trigger sync
    await triggerBackgroundSync();

    // Show success message
    showStatus(`✅ Saved! All ${normalizedSets.join(', ')} shortcuts loaded.`, 'success');

    // Re-fetch sets to update shortcut counts
    await refreshShortcutCounts();

  } catch (error) {
    showError(`Failed to save: ${error.message}`);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = '💾 Save & Sync';
  }
}

// Send message to background script to sync
function triggerBackgroundSync() {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ action: 'sync' }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        console.log('Sync response:', response);
        resolve(response);
      }
    });
  });
}

// Refresh shortcut counts after sync
async function refreshShortcutCounts() {
  try {
    console.log('Refreshing shortcut counts...');

    // Re-fetch sets from API to get updated counts
    await loadAvailableSets();

    // Clear existing UI
    const generalList = document.getElementById('general-list');
    const personalList = document.getElementById('personal-list');
    generalList.innerHTML = '';
    personalList.innerHTML = '';

    // Re-render with updated counts (preserves selection based on selectedSets array)
    const generalSets = availableSets.filter(s => s.set_type === 'general');
    const personalSets = availableSets.filter(s => s.set_type === 'personal');

    generalSets.forEach(set => {
      generalList.appendChild(createSetOption(set));
    });

    personalSets.forEach(set => {
      personalList.appendChild(createSetOption(set));
    });

    console.log('Shortcut counts refreshed successfully');
  } catch (error) {
    console.error('Failed to refresh counts:', error);
    // Don't show error to user - sync was successful, just counts didn't update
  }
}

// Show status message
function showStatus(message, type = 'info') {
  const statusEl = document.getElementById('status');
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
  statusEl.classList.remove('hidden');

  // Auto-hide after 5 seconds
  setTimeout(() => {
    statusEl.classList.add('hidden');
  }, 5000);
}

// Show error message
function showError(message) {
  const errorEl = document.getElementById('error');
  errorEl.textContent = message;
  errorEl.style.display = 'block';

  const loading = document.getElementById('loading');
  loading.style.display = 'none';

  console.error('AutoText Options Error:', message);
}

// ==========================================
// UTILITY: Debounce function
// ==========================================

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// ==========================================
// AUTOCOMPLETE SEARCH (AJAX)
// ==========================================

let autocompleteAbortController = null;

async function handleAutocompleteSearch(e) {
  const query = e.target.value.trim();

  if (query.length < 1) {
    hideAutocompleteDropdown();
    renderShortcutsPreview(allShortcuts);
    return;
  }

  // Cancel previous request
  if (autocompleteAbortController) {
    autocompleteAbortController.abort();
  }
  autocompleteAbortController = new AbortController();

  try {
    const response = await fetch(`${CONFIG.API_URL}/shortcuts/?search=${encodeURIComponent(query)}`, {
      headers: { 'Authorization': `Token ${authToken}` },
      signal: autocompleteAbortController.signal
    });

    if (!response.ok) throw new Error('Search failed');

    const results = await response.json();
    showAutocompleteDropdown(results);

    // Also filter local preview
    const filtered = {};
    Object.entries(allShortcuts).forEach(([key, data]) => {
      if (key.toLowerCase().includes(query.toLowerCase()) ||
          (data.value && data.value.toLowerCase().includes(query.toLowerCase()))) {
        filtered[key] = data;
      }
    });
    renderShortcutsPreview(filtered);

  } catch (error) {
    if (error.name === 'AbortError') return; // Cancelled, ignore
    console.error('Autocomplete search error:', error);
    // Fallback to local search
    handleShortcutsSearch(e);
  }
}

function showAutocompleteDropdown(results) {
  const dropdown = document.getElementById('autocomplete-dropdown');
  dropdown.textContent = ''; // Safe clear

  if (results.length === 0) {
    dropdown.style.display = 'none';
    return;
  }

  results.slice(0, 10).forEach(shortcut => {
    const item = document.createElement('div');
    item.className = 'autocomplete-item';

    const keySpan = document.createElement('span');
    keySpan.className = 'autocomplete-key';
    keySpan.textContent = shortcut.key;

    const valueSpan = document.createElement('span');
    valueSpan.className = 'autocomplete-value';
    valueSpan.textContent = (shortcut.value || shortcut.html_value || '').substring(0, 50);

    item.appendChild(keySpan);
    item.appendChild(valueSpan);

    item.addEventListener('click', () => {
      document.getElementById('shortcuts-search').value = shortcut.key;
      hideAutocompleteDropdown();
      // Show just this shortcut
      renderShortcutsPreview({ [shortcut.key]: shortcut });
    });
    dropdown.appendChild(item);
  });

  dropdown.style.display = 'block';
}

function hideAutocompleteDropdown() {
  document.getElementById('autocomplete-dropdown').style.display = 'none';
}

// ==========================================
// MANAGE SHORTCUTS (CRUD)
// ==========================================

let manageShortcuts = [];
let personalSetsForSelect = [];

// Make every <code> chip in the cheatsheet click-to-copy + wire the
// inline filter input. Idempotent — data-* flags prevent stacking
// listeners if loadManageShortcuts runs again on tab re-focus.
// =============================================================================
// CHEATSHEET — recipes, live results, hover tooltips
// =============================================================================

// Pre-built snippet "recipes" — click the title in the cheatsheet to copy
// the body. Each body is a working snippet you can paste into a new
// shortcut's Value field. Order: most generic first, most specific last.
//
// Tip when adding new recipes: keep them under ~10 lines, prefer [[var:...]]
// over hard-coded strings, and end with $|$ where the user will type next.
const CHEATSHEET_RECIPES = [
  {
    title: 'Email simplu',
    body: '[[greeting]] [[recipient]],\n\n$|$\n\nCu drag,\n[[var:nume_afisat]]',
  },
  {
    title: 'Confirmare comandă',
    body: '[[greeting]] [[recipient]],\n\nVă confirm comanda din [[date]].\nTermen livrare: [[date+7d:DD.MM.YYYY]].$|$\n\nMulțumesc,\n[[var:nume_afisat]]',
  },
  {
    title: 'Răspuns rapid',
    body: 'Mulțumesc, [[recipient]]! Revin cu detalii până [[date+1d:DD.MM]].$|$',
  },
  {
    title: 'Cerere ofertă — răspuns',
    body: '[[greeting]] [[recipient]],\n\nMulțumesc pentru cererea de ofertă. Vă transmit detaliile mai jos:\n\n• Preț: $|$\n• Termen livrare: [[date+{{zile:Cate zile?|7}}d:DD.MM.YYYY]]\n• Valabilitate ofertă: [[date+30d:DD.MM.YYYY]]\n\nCu drag,\n[[var:nume_afisat]]',
  },
  {
    title: 'Întrebare clarificare',
    body: '[[greeting]] [[recipient]],\n\nAm nevoie de o clarificare legată de $|$. Puteți să-mi confirmați?\n\nMulțumesc,\n[[var:nume_afisat]]',
  },
  {
    title: 'Reminder plată',
    body: '[[greeting]] [[recipient]],\n\nVă rugăm să verificați factura {{numar:Numărul facturii?}} cu scadența [[date-30d:DD.MM.YYYY]] — încă nu e marcată ca plătită.\n\nDacă plata e deja făcută, vă mulțumim, ignorați acest mesaj.$|$\n\nCu stimă,\n[[var:nume_afisat]]',
  },
  {
    title: 'Notificare expediere (AWB)',
    body: '[[greeting]] [[recipient]],\n\nComanda dvs. a fost expediată azi, [[date]], prin [[select:FAN Courier|Sameday|DPD]]. AWB-ul este {{awb:Număr AWB?}}.\n\nLivrare estimată: [[date+1d:DD.MM]] – [[date+2d:DD.MM]].$|$\n\nUn weekend frumos,\n[[var:nume_afisat]]',
  },
  {
    title: 'Programare întâlnire',
    body: '[[greeting]] [[recipient]],\n\nPropun întâlnirea pe [[date+{{zile:Peste cate zile?|3}}d:[[day]] DD.MM.YYYY]] la ora {{ora:La ce ora?|10:00}}, [[select:la sediul nostru|online (Google Meet)|telefonic]].\n\nConfirmati daca va convine?$|$\n\nCu drag,\n[[var:nume_afisat]]',
  },
  {
    title: 'Răspuns la reclamație',
    body: '[[greeting]] [[recipient]],\n\nÎmi pare rău pentru neplăcerea cauzată. Am preluat sesizarea — $|$\n\nVă voi reveni cu o soluție până [[date+1d:DD.MM]].\n\nCu stimă,\n[[var:nume_afisat]]',
  },
  {
    title: 'Welcome client nou',
    body: '[[greeting]] [[recipient]],\n\nBine ați venit! Mă bucur că am ocazia să colaborăm.\n\nÎn atașament găsiți $|$. Pentru orice întrebări, sunt la dispoziție.\n\nNumere utile:\n• Telefon: [[var:telefon]]\n• Website: [[var:website_paff]]\n\nCu drag,\n[[var:nume_afisat]]',
  },
  {
    title: 'Follow-up',
    body: '[[greeting]] [[recipient]],\n\nRevin asupra mesajului meu din [[date-{{zile:Acum cate zile a fost mesajul?|7}}d:DD.MM]] — am vrut să verific dacă $|$.\n\nO zi bună!\n[[var:nume_afisat]]',
  },
  {
    title: 'Cerere documente',
    body: '[[greeting]] [[recipient]],\n\nPentru a finaliza colaborarea, vă rog să-mi transmiteți următoarele:\n\n• $|$\n• \n• \n\nTermen: [[date+7d:DD.MM.YYYY]].\n\nMulțumesc,\n[[var:nume_afisat]]',
  },
  {
    title: 'Mulțumire formal',
    body: 'Cu stimă deosebită,\n\nVă mulțumesc pentru [[select:promptitudine|încredere|colaborare|flexibilitate]] — ne-a fost de mare ajutor.\n\nO [[day]] frumoasă!\n[[var:nume_afisat]]',
  },
  {
    title: 'Out-of-office (vacanță)',
    body: 'Bună ziua,\n\nÎn perioada [[date]] – [[date+{{zile:Cate zile?|7}}d:DD.MM.YYYY]] sunt în concediu și răspund cu întârziere.\n\nPentru urgențe, contactează: $|$\n\nMulțumesc pentru înțelegere,\n[[var:nume_afisat]]',
  },
  {
    title: 'Semnătură email',
    body: 'Cu stimă,\n[[var:nume_afisat]]\n[[var:companie]]\n📞 [[var:telefon]]\n🌐 [[var:website_paff]]',
  },
];

function populateRecipes() {
  const grid = document.getElementById('recipes-grid');
  if (!grid || grid.dataset.populated === '1') return;
  grid.dataset.populated = '1';
  grid.textContent = '';

  for (const recipe of CHEATSHEET_RECIPES) {
    const card = document.createElement('div');
    card.className = 'recipe';

    const title = document.createElement('div');
    title.className = 'recipe-title';
    title.textContent = '▸ ' + recipe.title;
    title.title = 'Click pentru a copia snippet-ul în clipboard';

    const body = document.createElement('pre');
    body.className = 'recipe-body';
    body.textContent = recipe.body;

    title.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(recipe.body);
        const original = title.textContent;
        title.classList.add('copied');
        title.textContent = '✓ Copiat — paste în câmpul Value al unui shortcut nou';
        setTimeout(() => {
          title.classList.remove('copied');
          title.textContent = original;
        }, 1800);
      } catch (err) {
        console.warn('Recipe copy failed:', err);
      }
    });

    card.appendChild(title);
    card.appendChild(body);
    grid.appendChild(card);
  }
}

// Compute the runtime value for inline "syntax → result" chips and the
// hover tooltips on every <code> in the cheatsheet. Re-run on every
// <details> open so dates stay current (no minute-by-minute polling).
function refreshCheatsheetResults() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const dayNames = ['Duminică', 'Luni', 'Marți', 'Miercuri', 'Joi', 'Vineri', 'Sâmbătă'];

  function formatDate(date, fmt) {
    if (!fmt) return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()}`;
    return fmt
      .replace(/YYYY/g, date.getFullYear())
      .replace(/MM/g, pad(date.getMonth() + 1))
      .replace(/DD/g, pad(date.getDate()))
      .replace(/HH/g, pad(date.getHours()))
      .replace(/mm/g, pad(date.getMinutes()));
  }

  function applyOffset(date, sign, n, unit) {
    const factor = sign === '-' ? -1 : 1;
    const d = new Date(date);
    if (unit === 'd') d.setDate(d.getDate() + factor * n);
    if (unit === 'w') d.setDate(d.getDate() + factor * 7 * n);
    if (unit === 'm') d.setMonth(d.getMonth() + factor * n);
    if (unit === 'y') d.setFullYear(d.getFullYear() + factor * n);
    return d;
  }

  function greeting(date) {
    const h = date.getHours();
    if (h < 11) return 'Bună dimineața';
    if (h < 18) return 'Bună ziua';
    return 'Bună seara';
  }

  function evaluateToken(token) {
    // token like "[[date]]" / "[[date+7d:DD.MM.YYYY]]" / "[[time:HH:mm]]"
    const inner = token.replace(/^\[\[/, '').replace(/\]\]$/, '');
    const m = inner.match(/^(date|time)(?:([+-])(\d+)([dwmy]))?(?::(.+))?$/);
    if (m) {
      const [, kind, sign, amount, unit, fmt] = m;
      let target = now;
      if (sign && amount && unit) {
        target = applyOffset(now, sign, parseInt(amount, 10), unit);
      }
      if (kind === 'time') {
        return formatDate(target, fmt || 'HH:mm');
      }
      return formatDate(target, fmt);
    }
    if (inner === 'day') return dayNames[now.getDay()];
    if (inner === 'greeting') return greeting(now);
    if (inner === 'user') {
      // currentUser may be null until login completes; fall back to placeholder
      return currentUser || 'cosmin';
    }
    return '';
  }

  // Inline arrows in vars-list: <span class="result" data-result-for="[[date]]">
  document.querySelectorAll('.cheatsheet [data-result-for]').forEach(span => {
    const token = span.dataset.resultFor;
    if (!token) return;
    const value = evaluateToken(token);
    if (value) span.textContent = value;
  });

  // Hover tooltips on every <code> chip — show what it would expand to
  // right now without forcing the user to scan the inline result column.
  document.querySelectorAll('.cheatsheet-section code, .cheatsheet-example code').forEach(code => {
    const text = code.textContent.trim();
    if (!text.startsWith('[[') || !text.endsWith(']]')) return;
    const value = evaluateToken(text);
    if (value) {
      code.title = `Acum: ${value}  ·  Click pentru copy`;
    }
  });

  // Highlight the current weekday in the [[day]] row so the user sees
  // at a glance which of the seven scenarios fires today.
  const todayName = dayNames[now.getDay()];
  document.querySelectorAll('#day-scenarios .result-scenario').forEach(scenario => {
    scenario.classList.toggle('is-current', scenario.dataset.dayName === todayName);
  });
}

function attachCheatsheetCopy() {
  document.querySelectorAll('.cheatsheet-section code, .cheatsheet-example code')
    .forEach(code => {
      if (code.dataset.copyBound === '1') return;
      code.dataset.copyBound = '1';
      code.style.cursor = 'pointer';
      code.title = 'Click pentru a copia';
      code.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(code.textContent);
          const originalBg = code.style.background;
          const originalColor = code.style.color;
          code.style.background = '#10b981';
          code.style.color = '#ffffff';
          setTimeout(() => {
            code.style.background = originalBg;
            code.style.color = originalColor;
          }, 800);
        } catch (err) {
          console.warn('Clipboard write failed:', err);
        }
      });
    });

  const filterInput = document.getElementById('cheatsheet-filter-input');
  if (filterInput && filterInput.dataset.filterBound !== '1') {
    filterInput.dataset.filterBound = '1';
    filterInput.addEventListener('input', () => {
      const q = filterInput.value.trim().toLowerCase();
      document.querySelectorAll('.cheatsheet-section').forEach(section => {
        let sectionMatchedAny = false;
        const sectionTitle = (section.querySelector('h4')?.textContent || '').toLowerCase();
        const titleMatches = q && sectionTitle.includes(q);

        section.querySelectorAll('li').forEach(li => {
          const liText = li.textContent.toLowerCase();
          const matches = !q || titleMatches || liText.includes(q);
          li.classList.toggle('hidden', !matches);
          if (matches) sectionMatchedAny = true;
        });

        // Example block (no <li>): hide whole section if it has no <ul>
        // and the query doesn't match its full text.
        if (!section.querySelector('li')) {
          const fullText = section.textContent.toLowerCase();
          sectionMatchedAny = !q || fullText.includes(q);
        }

        section.classList.toggle('hidden', !sectionMatchedAny);
      });
    });
  }

  // Populate recipes once + recompute live results / tooltips. Hook the
  // <details> open event so dates stay current next time the user opens it.
  populateRecipes();
  refreshCheatsheetResults();
  const cheatsheet = document.querySelector('details.cheatsheet:not(.user-vars-panel)');
  if (cheatsheet && cheatsheet.dataset.refreshBound !== '1') {
    cheatsheet.dataset.refreshBound = '1';
    cheatsheet.addEventListener('toggle', () => {
      if (cheatsheet.open) refreshCheatsheetResults();
    });
  }
}

async function loadManageShortcuts() {
  const container = document.getElementById('manage-shortcuts-list');
  container.textContent = '';
  const loadingDiv = document.createElement('div');
  loadingDiv.style.cssText = 'text-align: center; padding: 20px;';
  loadingDiv.textContent = 'Loading...';
  container.appendChild(loadingDiv);

  try {
    // Debug logging
    console.log('[Manage] Loading shortcuts, authToken:', authToken ? 'present' : 'missing');
    console.log('[Manage] API URL:', `${CONFIG.API_URL}/shortcuts/my/`);

    // Fetch user's shortcuts from API
    const response = await fetch(`${CONFIG.API_URL}/shortcuts/my/`, {
      headers: { 'Authorization': `Token ${authToken}` }
    });

    console.log('[Manage] Response status:', response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[Manage] Error response:', errorText);
      throw new Error(`Failed to load shortcuts (${response.status})`);
    }

    manageShortcuts = await response.json();
    console.log('[Manage] Loaded shortcuts:', manageShortcuts.length);

    // Also fetch personal sets for the dropdown
    await loadPersonalSetsForSelect();

    // Load custom variables — they live in the same Manage tab now
    // (used inside shortcuts as [[var:name]], so colocating editing
    // with the shortcuts list is the natural place).
    if (typeof loadUserVariables === 'function') {
      loadUserVariables();
    }

    // Wire click-to-copy on cheatsheet chips. Cheatsheet is static HTML
    // so we only need to attach once per Manage tab activation.
    attachCheatsheetCopy();

    // Apply current search filter if any, otherwise show all
    const searchInput = document.getElementById('manage-search');
    const query = searchInput ? searchInput.value.toLowerCase().trim() : '';

    if (query) {
      const filtered = manageShortcuts.filter(s =>
        s.key.toLowerCase().includes(query) ||
        (s.value && s.value.toLowerCase().includes(query))
      );
      renderManageShortcuts(filtered);
    } else {
      renderManageShortcuts(manageShortcuts);
    }
  } catch (error) {
    console.error('[Manage] Error:', error);
    container.textContent = '';
    const errorDiv = document.createElement('div');
    errorDiv.style.cssText = 'text-align: center; padding: 20px; color: var(--danger);';
    errorDiv.textContent = 'Error: ' + error.message;
    container.appendChild(errorDiv);
  }
}

async function loadPersonalSetsForSelect() {
  try {
    const response = await fetch(`${CONFIG.API_URL}/sets/`, {
      headers: { 'Authorization': `Token ${authToken}` }
    });
    if (response.ok) {
      const sets = await response.json();
      // Include general sets (Birou — team-shared, anyone can place into)
      // and personal sets the user owns. Backend gates with the same rule.
      personalSetsForSelect = sets.filter(s =>
        s.set_type === 'general' || s.set_type === 'personal'
      );
      // Sort: general (Birou) first, then personal alphabetically.
      personalSetsForSelect.sort((a, b) => {
        if (a.set_type !== b.set_type) {
          return a.set_type === 'general' ? -1 : 1;
        }
        return (a.name || '').localeCompare(b.name || '');
      });
    }
  } catch (error) {
    console.error('Failed to load personal sets:', error);
  }
}

// Build an action button with an icon and a label side-by-side. The
// previous design used colour-only pills which were harder to scan;
// the new buttons share a neutral surface and rely on the icon + label
// to convey intent. CSS class .btn-action carries the layout.
function makeActionButton(kind, icon, label, onClick) {
  const btn = document.createElement('button');
  btn.className = `btn-action btn-action-${kind}`;
  btn.title = label;
  const iconSpan = document.createElement('span');
  iconSpan.className = 'btn-action-icon';
  iconSpan.textContent = icon;
  const labelSpan = document.createElement('span');
  labelSpan.className = 'btn-action-label';
  labelSpan.textContent = label;
  btn.appendChild(iconSpan);
  btn.appendChild(labelSpan);
  btn.addEventListener('click', onClick);
  return btn;
}

function renderManageShortcuts(shortcuts) {
  const container = document.getElementById('manage-shortcuts-list');
  container.textContent = '';

  // Find keys that exist in personal sets (not Birou)
  const personalKeys = new Set();
  shortcuts.forEach(s => {
    const setNames = s.set_names || [];
    const isPersonal = setNames.some(name => name !== 'Birou');
    if (isPersonal) {
      personalKeys.add(s.key);
    }
  });

  // Filter out Birou shortcuts if the same key exists in a personal set
  const filteredShortcuts = shortcuts.filter(shortcut => {
    const setNames = shortcut.set_names || [];
    const isOnlyBirou = setNames.length === 1 && setNames[0] === 'Birou';
    // Hide if it's only in Birou AND the key exists in personal
    if (isOnlyBirou && personalKeys.has(shortcut.key)) {
      return false;
    }
    return true;
  });

  // Sort: personal first, then Birou. Within each group, alphabetic by key.
  // A shortcut is considered "personal" if any of its sets is not 'Birou'.
  filteredShortcuts.sort((a, b) => {
    const aPersonal = (a.set_names || []).some(name => name !== 'Birou') ? 0 : 1;
    const bPersonal = (b.set_names || []).some(name => name !== 'Birou') ? 0 : 1;
    if (aPersonal !== bPersonal) return aPersonal - bPersonal;
    return (a.key || '').localeCompare(b.key || '');
  });

  if (filteredShortcuts.length === 0) {
    const emptyDiv = document.createElement('div');
    emptyDiv.style.cssText = 'text-align: center; padding: 30px; color: var(--text-secondary-light);';
    emptyDiv.textContent = 'No shortcuts yet. Click "+ Add New" to create one.';
    container.appendChild(emptyDiv);
    return;
  }

  filteredShortcuts.forEach(shortcut => {
    const row = document.createElement('div');
    row.className = 'shortcut-row';

    const keyBadge = document.createElement('span');
    keyBadge.className = 'shortcut-key-badge';
    keyBadge.textContent = shortcut.key;

    // Add set badges
    const setsDiv = document.createElement('div');
    setsDiv.className = 'shortcut-sets';

    const setNames = shortcut.set_names || [];
    setNames.forEach(setName => {
      const badge = document.createElement('span');
      badge.className = 'set-badge';
      badge.textContent = setName;
      // Special styling for Birou set
      if (setName === 'Birou') {
        badge.style.cssText = 'background: #6c757d; color: white;';
      }
      setsDiv.appendChild(badge);
    });

    const value = document.createElement('span');
    value.className = 'shortcut-value';
    value.textContent = shortcut.value || (shortcut.html_value ? '[Rich text]' : '');

    const actions = document.createElement('div');
    actions.className = 'shortcut-actions';

    const isFromBirou = setNames.includes('Birou');
    // Birou edit is gated to superusers + birou-curators (matches API).
    // Birou delete is intentionally NOT exposed in the UI — even for
    // superusers — because the rule is "Birou shortcuts are deleted only
    // from Django admin." This keeps the destructive action behind one
    // extra deliberate step (open admin → confirm) and prevents a
    // misclick on a long row from removing a team-shared snippet.
    const canEditBirou = userPerms.is_superuser || userPerms.is_birou_curator;

    if (isFromBirou) {
      if (canEditBirou) {
        const editBtn = makeActionButton('edit', '✏️', 'Editează', () => openShortcutModal(shortcut));
        actions.appendChild(editBtn);
      }
      // Copy to Personal — always available for everyone (workflow when
      // they want a personal variant of a Birou shortcut without
      // touching the team's shared one).
      const copyBtn = makeActionButton('copy', '📋', 'Copiază personal', () => copyToPersonalSet(shortcut));
      actions.appendChild(copyBtn);
    } else {
      // Personal shortcut — owner can always edit + delete
      const editBtn = makeActionButton('edit', '✏️', 'Editează', () => openShortcutModal(shortcut));
      const deleteBtn = makeActionButton('delete', '🗑️', 'Șterge', () => deleteShortcut(shortcut.id));
      actions.appendChild(editBtn);
      actions.appendChild(deleteBtn);
    }

    row.appendChild(keyBadge);
    row.appendChild(setsDiv);
    row.appendChild(value);
    row.appendChild(actions);
    container.appendChild(row);
  });
}

// Copy a shortcut to a personal set. The set list now includes general
// (Birou) for the modal dropdown — but for "copy to personal" we must
// pick from personal-only, otherwise we'd silently copy back into Birou.
async function copyToPersonalSet(shortcut) {
  const personalOnly = personalSetsForSelect.filter(s => s.set_type === 'personal');

  if (personalOnly.length === 0) {
    alert('Nu ai niciun set personal. Creează unul mai întâi (din Django admin).');
    return;
  }

  let targetSetId;
  if (personalOnly.length === 1) {
    targetSetId = personalOnly[0].id;
  } else {
    const setNames = personalOnly.map(s => s.name).join(', ');
    const selectedName = prompt(
      `În ce set personal copiezi?\nDisponibile: ${setNames}`,
      personalOnly[0].name
    );
    if (!selectedName) return;

    const targetSet = personalOnly.find(s => s.name.toLowerCase() === selectedName.toLowerCase());
    if (!targetSet) {
      alert('Set inexistent. Introdu numele exact.');
      return;
    }
    targetSetId = targetSet.id;
  }

  try {
    const response = await fetch(`${CONFIG.API_URL}/shortcuts/`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        key: shortcut.key,
        content_type: shortcut.content_type,
        value: shortcut.value || '',
        html_value: shortcut.html_value || '',
        sets: [targetSetId]
      })
    });

    if (response.ok) {
      alert('Shortcut copied to personal set! You can now edit it.');
      await loadManageShortcuts();
    } else {
      const error = await response.json();
      alert(`Error: ${JSON.stringify(error)}`);
    }
  } catch (error) {
    console.error('Error copying shortcut:', error);
    alert('Failed to copy shortcut.');
  }
}

function handleManageSearch(e) {
  const query = e.target.value.toLowerCase().trim();

  if (!query) {
    renderManageShortcuts(manageShortcuts);
    return;
  }

  const filtered = manageShortcuts.filter(s =>
    s.key.toLowerCase().includes(query) ||
    (s.value && s.value.toLowerCase().includes(query))
  );
  renderManageShortcuts(filtered);
}

// ==========================================
// MODAL: Create/Edit Shortcut
// ==========================================

// TinyMCE editor instance
let tinyMCEEditor = null;

// Initialize TinyMCE rich text editor (called when switching to HTML mode)
let tinyMCEInitialized = false;

function initTinyMCE() {
  if (typeof tinymce === 'undefined') {
    console.warn('TinyMCE not loaded yet, retrying...');
    setTimeout(initTinyMCE, 500);
    return;
  }

  // If already initialized, just make sure the editor is visible
  if (tinyMCEInitialized && tinyMCEEditor) {
    return;
  }

  // Get the extension's base URL for TinyMCE resources
  const tinyMCEBaseUrl = chrome.runtime.getURL('lib/tinymce');

  tinymce.init({
    selector: '#tinymce-editor',
    height: 350,
    menubar: false,
    plugins: 'link lists autolink',
    toolbar: 'bold italic underline strikethrough | bullist numlist | alignleft aligncenter alignright | link unlink | removeformat',
    toolbar_mode: 'wrap',
    placeholder: 'Type your formatted text here...',
    content_style: 'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 14px; }',
    base_url: tinyMCEBaseUrl,
    suffix: '.min',
    link_default_target: '_blank',
    link_title: false,
    default_link_target: '_blank',
    setup: function(editor) {
      tinyMCEEditor = editor;
      tinyMCEInitialized = true;
    }
  });
}

// Insert text at the current caret position of whatever expansion field
// is active in the modal. Plain-text mode → manipulate the textarea
// directly; HTML mode → ask TinyMCE to insert content into its iframe.
function insertAtModalCursor(text) {
  const isHtml = document.querySelector('.content-type-btn.active')?.dataset?.type === 'html';
  if (isHtml && tinyMCEEditor) {
    tinyMCEEditor.focus();
    tinyMCEEditor.insertContent(text);
    return true;
  }
  const textarea = document.getElementById('shortcut-value');
  if (!textarea) return false;
  const before = textarea.value.slice(0, textarea.selectionStart);
  const after = textarea.value.slice(textarea.selectionEnd);
  textarea.value = before + text + after;
  const newPos = before.length + text.length;
  textarea.selectionStart = textarea.selectionEnd = newPos;
  textarea.focus();
  textarea.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
}

// Replace the whole expansion field with `text`. Used by recipe titles —
// recipes are full template bodies, not snippets to splice in.
function replaceModalValue(text) {
  const isHtml = document.querySelector('.content-type-btn.active')?.dataset?.type === 'html';
  if (isHtml && tinyMCEEditor) {
    tinyMCEEditor.setContent(text);
    tinyMCEEditor.focus();
    return;
  }
  const textarea = document.getElementById('shortcut-value');
  if (!textarea) return;
  textarea.value = text;
  textarea.selectionStart = textarea.selectionEnd = text.length;
  textarea.focus();
  textarea.dispatchEvent(new Event('input', { bubbles: true }));
}

// Build the in-modal cheatsheet by cloning the Manage-tab grid (deep
// cloneNode keeps the static markup safe — no innerHTML) and rebinding
// every click handler to insertAtModalCursor instead of clipboard copy.
// Idempotent via dataset flags.
function populateModalCheatsheet() {
  const sourceGrid = document.querySelector('#tab-manage .cheatsheet-grid');
  const targetGrid = document.getElementById('modal-cheatsheet-grid');
  if (!sourceGrid || !targetGrid) return;
  if (targetGrid.dataset.populated !== '1') {
    targetGrid.dataset.populated = '1';
    targetGrid.textContent = '';
    for (const child of sourceGrid.children) {
      targetGrid.appendChild(child.cloneNode(true));
    }
  }

  // Refresh live results inside the cloned grid the same way the
  // Manage-tab cheatsheet does (separate DOM tree, separate query).
  refreshCheatsheetResults();

  // Wire every <code> chip to insert-at-cursor instead of copy. We rebind
  // each render so chips picked up via cloneNode keep working after
  // user edits. data-modal-bound prevents stacking.
  targetGrid.querySelectorAll('code').forEach(code => {
    if (code.dataset.modalBound === '1') return;
    code.dataset.modalBound = '1';
    code.style.cursor = 'pointer';
    code.title = 'Click pentru a insera în text';
    code.addEventListener('click', (e) => {
      e.stopPropagation();
      const ok = insertAtModalCursor(code.textContent);
      if (ok) {
        code.classList.add('inserted');
        setTimeout(() => code.classList.remove('inserted'), 600);
      }
    });
  });

  // Recipes: render with replace-value handler.
  const recipesGrid = document.getElementById('modal-recipes-grid');
  if (recipesGrid && recipesGrid.dataset.populated !== '1') {
    recipesGrid.dataset.populated = '1';
    for (const recipe of CHEATSHEET_RECIPES) {
      const card = document.createElement('div');
      card.className = 'recipe';

      const title = document.createElement('div');
      title.className = 'recipe-title';
      title.textContent = '▸ ' + recipe.title;
      title.title = 'Click pentru a înlocui textul cu această rețetă';

      const body = document.createElement('pre');
      body.className = 'recipe-body';
      body.textContent = recipe.body;

      title.addEventListener('click', () => {
        replaceModalValue(recipe.body);
        const original = title.textContent;
        title.classList.add('copied');
        title.textContent = '✓ Inserat în câmpul Expansion';
        setTimeout(() => {
          title.classList.remove('copied');
          title.textContent = original;
        }, 1600);
      });

      card.appendChild(title);
      card.appendChild(body);
      recipesGrid.appendChild(card);
    }
  }

  // Filter input
  const filterInput = document.getElementById('modal-cheatsheet-filter-input');
  if (filterInput && filterInput.dataset.filterBound !== '1') {
    filterInput.dataset.filterBound = '1';
    filterInput.addEventListener('input', () => {
      const q = filterInput.value.trim().toLowerCase();
      targetGrid.querySelectorAll('.cheatsheet-section').forEach(section => {
        let any = false;
        const titleText = (section.querySelector('h4')?.textContent || '').toLowerCase();
        const titleMatch = q && titleText.includes(q);
        section.querySelectorAll('li').forEach(li => {
          const matched = !q || titleMatch || li.textContent.toLowerCase().includes(q);
          li.classList.toggle('hidden', !matched);
          if (matched) any = true;
        });
        if (!section.querySelector('li')) any = !q || section.textContent.toLowerCase().includes(q);
        section.classList.toggle('hidden', !any);
      });
    });
  }
}

// Test-expand: takes whatever is in the active expansion field, runs it
// through a synchronous demo evaluator (mirrors content.js but with
// hardcoded demo values for runtime-dependent vars), and prints the
// result in the test panel. Useful as a "did I typo?" check before save.
async function runTestExpand() {
  const isHtml = document.querySelector('.content-type-btn.active')?.dataset?.type === 'html';
  let raw;
  if (isHtml && tinyMCEEditor) {
    // Strip HTML to plain text for the test (browsing the rendered HTML
    // in the test panel adds no value — we want to see what the snippet
    // resolves to as text).
    const tmp = document.createElement('div');
    tmp.textContent = tinyMCEEditor.getContent({ format: 'text' });
    raw = tmp.textContent;
  } else {
    raw = document.getElementById('shortcut-value')?.value || '';
  }

  if (!raw.trim()) {
    document.getElementById('modal-test-output').textContent = '(câmpul Expansion e gol)';
    document.getElementById('modal-test-panel').classList.remove('hidden');
    return;
  }

  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const dayNames = ['Duminică', 'Luni', 'Marți', 'Miercuri', 'Joi', 'Vineri', 'Sâmbătă'];

  function formatDate(date, fmt) {
    if (!fmt) return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()}`;
    return fmt
      .replace(/YYYY/g, date.getFullYear())
      .replace(/MM/g, pad(date.getMonth() + 1))
      .replace(/DD/g, pad(date.getDate()))
      .replace(/HH/g, pad(date.getHours()))
      .replace(/mm/g, pad(date.getMinutes()));
  }
  function applyOffset(date, sign, n, unit) {
    const f = sign === '-' ? -1 : 1;
    const d = new Date(date);
    if (unit === 'd') d.setDate(d.getDate() + f * n);
    if (unit === 'w') d.setDate(d.getDate() + f * 7 * n);
    if (unit === 'm') d.setMonth(d.getMonth() + f * n);
    if (unit === 'y') d.setFullYear(d.getFullYear() + f * n);
    return d;
  }
  function greeting(date) {
    const h = date.getHours();
    if (h < 11) return 'Bună dimineața';
    if (h < 18) return 'Bună ziua';
    return 'Bună seara';
  }

  // Pull user variables from chrome storage so [[var:...]] resolves to
  // real values where possible.
  let userVars = {};
  try {
    const stored = await chrome.storage.local.get('userVariables');
    userVars = (stored && stored.userVariables) || {};
  } catch (_) {}

  let out = raw;

  // Date / time / day / greeting
  out = out.replace(/\[\[(date|time)(?:([+-])(\d+)([dwmy]))?(?::([^\]]+))?\]\]/g,
    (_, kind, sign, amount, unit, fmt) => {
      let target = now;
      if (sign && amount && unit) target = applyOffset(now, sign, parseInt(amount, 10), unit);
      if (kind === 'time') return formatDate(target, fmt || 'HH:mm');
      return formatDate(target, fmt);
    });
  out = out.replace(/\[\[day\]\]/g, dayNames[now.getDay()]);
  out = out.replace(/\[\[greeting\]\]/g, greeting(now));

  // User context
  out = out.replace(/\[\[user\]\]/g, currentUser || 'cosmin');
  out = out.replace(/\[\[recipient\]\]/g, '«Cosmin Popa»');

  // Custom variables
  out = out.replace(/\[\[var:([a-zA-Z_][a-zA-Z0-9_]*)\]\]/g, (_m, name) => {
    if (Object.prototype.hasOwnProperty.call(userVars, name)) return userVars[name];
    return `«[[var:${name}]] (nedefinit)»`;
  });

  // Random — just pick one option for demo
  out = out.replace(/\[\[random:([^\]]+)\]\]/g, (_, args) => {
    const opts = args.split('|').map(s => s.trim()).filter(Boolean);
    return opts.length ? `«${opts[0]}»` : '';
  });

  // Select — show first option as demo
  out = out.replace(/\[\[select:([^\]]+)\]\]/g, (_, args) => {
    const opts = args.split('|').map(s => s.trim()).filter(Boolean);
    return opts.length ? `«${opts[0]}»` : '';
  });

  // Form placeholders {{name}} / {{name:Label}} / {{name:Label|default}}
  out = out.replace(/\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([^|}]*))?(?:\|([^}]*))?\}\}/g,
    (_, name, label, def) => `«${(def || '').trim() || (label || '').trim() || name} (test)»`);

  // Snippet nesting [[%s(other)]] — show as inline tag
  out = out.replace(/\[\[%s\(([^)]+)\)\]\]/g, (_, name) => `«inserează shortcut: ${name.trim()}»`);

  // Cursor marker
  out = out.replace(/\$\|\$/g, '|');

  document.getElementById('modal-test-output').textContent = out;
  document.getElementById('modal-test-panel').classList.remove('hidden');
}

// Live conflict check on the shortcut-key field. Two cases:
//   1. Exact match  → another shortcut already uses this key
//   2. Prefix overlap → typing one will leave the other unreachable
//      (e.g. shortcut "ab" makes "abc" trigger first, never "ab")
// Warning is non-blocking — user can still Save and resolve later.
function checkShortcutKeyConflict(currentKey, currentId) {
  const warning = document.getElementById('shortcut-key-warning');
  if (!warning) return;

  const key = (currentKey || '').trim();
  if (!key || !manageShortcuts || manageShortcuts.length === 0) {
    warning.classList.add('hidden');
    return;
  }

  // Exact match (excluding the shortcut we're currently editing)
  const exact = manageShortcuts.find(s =>
    s.key === key && String(s.id) !== String(currentId || '')
  );
  if (exact) {
    warning.classList.remove('hidden');
    warning.classList.add('error');
    warning.innerHTML = '';
    const text = document.createElement('span');
    text.textContent = '⚠️ Există deja shortcut cu cheia ';
    const code = document.createElement('code');
    code.textContent = key;
    const after = document.createElement('span');
    after.textContent = ' (în setul ' + (exact.set_names || []).join(', ') + ')';
    warning.appendChild(text);
    warning.appendChild(code);
    warning.appendChild(after);
    return;
  }

  // Prefix overlap — find shortcuts whose key starts with our key, OR whose
  // key is a prefix of ours. Both directions cause "shorter wins" expand
  // race condition. Skip 1-char keys to avoid noise (everything starts with
  // 'a' if you have one shortcut starting with 'a').
  if (key.length < 2) {
    warning.classList.add('hidden');
    return;
  }
  const conflicts = manageShortcuts.filter(s => {
    if (String(s.id) === String(currentId || '')) return false;
    if (!s.key || s.key.length < 2) return false;
    return s.key.startsWith(key) || key.startsWith(s.key);
  });

  if (conflicts.length === 0) {
    warning.classList.add('hidden');
    return;
  }

  warning.classList.remove('hidden');
  warning.classList.remove('error');
  warning.innerHTML = '';
  const intro = document.createElement('span');
  intro.textContent = '⚠️ Atenție: ';
  warning.appendChild(intro);

  // Pick the most relevant conflict (shortest prefix wins on Tab)
  const c = conflicts[0];
  const shorter = c.key.length < key.length ? c : { key };
  const longer = c.key.length < key.length ? { key } : c;
  const fragMsg = document.createElement('span');
  fragMsg.textContent = ' e prefix pentru ';
  warning.appendChild(document.createElement('code')).textContent = shorter.key;
  warning.appendChild(fragMsg);
  warning.appendChild(document.createElement('code')).textContent = longer.key;
  const tail = document.createElement('span');
  tail.textContent = ' — Tab va declanșa primul, al doilea poate rămâne inaccesibil.';
  warning.appendChild(tail);
}

function openShortcutModal(shortcut = null) {
  const modal = document.getElementById('shortcut-modal');
  const title = document.getElementById('modal-title');
  const idField = document.getElementById('shortcut-id');
  const keyField = document.getElementById('shortcut-key');
  const valueField = document.getElementById('shortcut-value');
  const setSelect = document.getElementById('shortcut-set');

  // Reset content type toggle
  document.querySelectorAll('.content-type-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('.content-type-btn[data-type="text"]').classList.add('active');
  document.getElementById('text-content-group').style.display = 'block';
  document.getElementById('html-content-group').style.display = 'none';

  // Wire conflict-check on every keystroke. Reset warning on open.
  const warning = document.getElementById('shortcut-key-warning');
  if (warning) warning.classList.add('hidden');
  if (keyField.dataset.conflictBound !== '1') {
    keyField.dataset.conflictBound = '1';
    keyField.addEventListener('input', () => {
      checkShortcutKeyConflict(keyField.value, idField.value);
    });
  }

  // Populate sets dropdown safely
  setSelect.textContent = '';
  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = '-- Select a set --';
  setSelect.appendChild(defaultOption);

  personalSetsForSelect.forEach(set => {
    const option = document.createElement('option');
    option.value = set.id;
    option.textContent = set.name;
    setSelect.appendChild(option);
  });

  // Add-new mode: pre-select the user's first personal set so they
  // don't accidentally save to Birou (which is at the top of the list
  // because of the dropdown's general-first sort). Edit mode handles
  // pre-selection further down based on the existing shortcut's sets.
  if (!shortcut) {
    const firstPersonal = personalSetsForSelect.find(s => s.set_type === 'personal');
    if (firstPersonal) {
      setSelect.value = firstPersonal.id;
    }
  }

  if (shortcut) {
    // Edit mode
    title.textContent = 'Edit Shortcut';
    idField.value = shortcut.id;
    keyField.value = shortcut.key;
    valueField.value = shortcut.value || '';

    // Set TinyMCE content
    if (tinyMCEEditor) {
      tinyMCEEditor.setContent(shortcut.html_value || '');
    }

    // Set content type
    if (shortcut.content_type === 'html') {
      document.querySelectorAll('.content-type-btn').forEach(b => b.classList.remove('active'));
      document.querySelector('.content-type-btn[data-type="html"]').classList.add('active');
      document.getElementById('text-content-group').style.display = 'none';
      document.getElementById('html-content-group').style.display = 'block';
      // Initialize TinyMCE when opening HTML shortcut
      initTinyMCE();
      // Set content after a short delay to ensure TinyMCE is ready
      setTimeout(() => {
        if (tinyMCEEditor) {
          tinyMCEEditor.setContent(shortcut.html_value || '');
        }
      }, 100);
    }

    // Select set if shortcut belongs to one. Prefer the first set whose
    // name is in the shortcut's set_names — covers both Birou (general)
    // and personal sets uniformly now that the dropdown lists both.
    if (shortcut.set_names && shortcut.set_names.length > 0) {
      const matchingSet = personalSetsForSelect.find(s =>
        shortcut.set_names.includes(s.name)
      );
      if (matchingSet) {
        setSelect.value = matchingSet.id;
      }
    }

    // Check if this shortcut key also exists in Birou (for "Download Original" button)
    const birouOriginal = manageShortcuts.find(s =>
      s.key === shortcut.key &&
      s.set_names &&
      s.set_names.includes('Birou') &&
      s.id !== shortcut.id
    );

    const downloadBtn = document.getElementById('modal-download-original');
    if (downloadBtn) {
      if (birouOriginal) {
        downloadBtn.classList.remove('hidden');
        downloadBtn.onclick = () => {
          // Restore content from Birou original
          valueField.value = birouOriginal.value || '';
          if (tinyMCEEditor) {
            tinyMCEEditor.setContent(birouOriginal.html_value || '');
          }
          // Also set content type if different
          if (birouOriginal.content_type === 'html') {
            document.querySelectorAll('.content-type-btn').forEach(b => b.classList.remove('active'));
            document.querySelector('.content-type-btn[data-type="html"]').classList.add('active');
            document.getElementById('text-content-group').style.display = 'none';
            document.getElementById('html-content-group').style.display = 'block';
          } else {
            document.querySelectorAll('.content-type-btn').forEach(b => b.classList.remove('active'));
            document.querySelector('.content-type-btn[data-type="text"]').classList.add('active');
            document.getElementById('text-content-group').style.display = 'block';
            document.getElementById('html-content-group').style.display = 'none';
          }
        };
      } else {
        downloadBtn.classList.add('hidden');
      }
    }
  } else {
    // Create mode
    title.textContent = 'Add New Shortcut';
    idField.value = '';
    keyField.value = '';
    valueField.value = '';

    // Clear TinyMCE content
    if (tinyMCEEditor) {
      tinyMCEEditor.setContent('');
    }

    setSelect.value = '';

    // Hide download original button in create mode
    const downloadBtn = document.getElementById('modal-download-original');
    if (downloadBtn) {
      downloadBtn.classList.add('hidden');
    }
  }

  modal.classList.remove('hidden');

  // Build the in-modal cheatsheet on first open (idempotent). Recipes
  // and chip handlers are wired here so user can immediately click any
  // [[var]] / recipe to insert it into the active expansion field.
  populateModalCheatsheet();

  // Run conflict check once for the prefilled key (edit mode), so the
  // warning is correct without waiting for the user to type.
  checkShortcutKeyConflict(keyField.value, idField.value);
}

function closeShortcutModal() {
  document.getElementById('shortcut-modal').classList.add('hidden');
  // Reset transient panels so the next open is clean.
  document.getElementById('modal-test-panel')?.classList.add('hidden');
  document.getElementById('shortcut-key-warning')?.classList.add('hidden');
}

async function saveShortcut() {
  const id = document.getElementById('shortcut-id').value;
  const key = document.getElementById('shortcut-key').value.trim();
  const value = document.getElementById('shortcut-value').value;
  // Read HTML from TinyMCE editor
  const htmlValue = tinyMCEEditor ? tinyMCEEditor.getContent() : '';
  const setId = document.getElementById('shortcut-set').value;

  const isHtml = document.querySelector('.content-type-btn.active').dataset.type === 'html';

  if (!key) {
    alert('Shortcut key is required!');
    return;
  }

  if (!setId) {
    alert('Please select a set!');
    return;
  }

  const payload = {
    key,
    content_type: isHtml ? 'html' : 'text',
    value: isHtml ? '' : value,
    html_value: isHtml ? htmlValue : '',
    sets: [parseInt(setId)]
  };

  try {
    const url = id
      ? `${CONFIG.API_URL}/shortcuts/${id}/`
      : `${CONFIG.API_URL}/shortcuts/`;

    const response = await fetch(url, {
      method: id ? 'PUT' : 'POST',
      headers: {
        'Authorization': `Token ${authToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to save');
    }

    closeShortcutModal();
    showStatus(id ? 'Shortcut updated!' : 'Shortcut created!', 'success');
    loadManageShortcuts();

    // Trigger sync to update local cache
    triggerBackgroundSync();

  } catch (error) {
    alert('Error: ' + error.message);
  }
}

async function deleteShortcut(id) {
  if (!confirm('Are you sure you want to delete this shortcut?')) {
    return;
  }

  try {
    const response = await fetch(`${CONFIG.API_URL}/shortcuts/${id}/`, {
      method: 'DELETE',
      headers: { 'Authorization': `Token ${authToken}` }
    });

    if (!response.ok && response.status !== 204) {
      throw new Error('Failed to delete');
    }

    showStatus('Shortcut deleted!', 'success');
    loadManageShortcuts();

    // Trigger sync to update local cache
    triggerBackgroundSync();

  } catch (error) {
    alert('Error: ' + error.message);
  }
}

// ==========================================
// USER VARIABLES (Settings tab)
// ==========================================

let userVariables = [];

async function loadUserVariables() {
  const list = document.getElementById('user-vars-list');
  if (!list) return;
  list.textContent = '';

  try {
    const res = await fetch(`${CONFIG.API_URL}/user-variables/`, {
      headers: { 'Authorization': `Token ${authToken}` }
    });
    if (!res.ok) {
      list.innerHTML = '';
      const empty = document.createElement('div');
      empty.className = 'user-vars-empty';
      empty.textContent = 'Could not load variables.';
      list.appendChild(empty);
      return;
    }
    userVariables = await res.json();
  } catch (err) {
    console.error('User variables fetch error:', err);
    return;
  }

  if (userVariables.length === 0) {
    list.appendChild(renderEmptyVarsCTA());
    renderCheatsheetUserVars();
    return;
  }

  for (const v of userVariables) {
    list.appendChild(renderUserVarRow(v));
  }

  renderCheatsheetUserVars();
}

// PAFF-flavoured starter pack — first-run users see concrete one-click
// CTAs instead of a generic "no variables yet" line. Each suggestion is
// a real workflow value the team uses (company name, signature email,
// IBAN). Picking one creates the variable + reloads the panel.
const STARTER_VARIABLES = [
  { name: 'companie', value: 'PAFF SRL & BOXPACK SRL', label: 'companie' },
  { name: 'adresa_paff', value: 'Ion Ghica 129 · Răcari · Dâmbovița · România', label: 'adresa_paff' },
  { name: 'telefon', value: '+40 0756.119.876', label: 'telefon' },
  { name: 'website_paff', value: 'www.paff.ro', label: 'website_paff' },
  { name: 'semnatura_email', value: 'Cu stimă,\nEchipa PAFF', label: 'semnatura_email' },
];

function renderEmptyVarsCTA() {
  const wrap = document.createElement('div');
  wrap.className = 'user-vars-empty-cta';

  const headline = document.createElement('div');
  headline.className = 'user-vars-empty-headline';
  headline.textContent = '🎨 Începe cu una din valorile uzuale PAFF:';
  wrap.appendChild(headline);

  const buttons = document.createElement('div');
  buttons.className = 'user-vars-empty-buttons';
  for (const starter of STARTER_VARIABLES) {
    const btn = document.createElement('button');
    btn.className = 'btn-action btn-action-copy user-vars-starter-btn';
    btn.textContent = `+ ${starter.label}`;
    btn.title = `Va crea: ${starter.name} = ${starter.value.slice(0, 50)}…`;
    btn.addEventListener('click', () => createStarterVariable(starter));
    buttons.appendChild(btn);
  }
  wrap.appendChild(buttons);

  const hint = document.createElement('div');
  hint.className = 'user-vars-empty-hint';
  hint.textContent = 'Sau scrie-ți propriile variabile mai jos.';
  wrap.appendChild(hint);

  return wrap;
}

async function createStarterVariable(starter) {
  try {
    const res = await fetch(`${CONFIG.API_URL}/user-variables/`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${authToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name: starter.name, value: starter.value }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert('Error: ' + (err.name || err.detail || JSON.stringify(err)));
      return;
    }
    loadUserVariables();
    triggerBackgroundSync();
  } catch (err) {
    alert('Error: ' + err.message);
  }
}

// Mirror the user's variables into the cheatsheet's "Variabilele tale"
// section as click-to-copy chips. Keeps the discoverability tight: user
// scans the cheatsheet, sees their own var inline, copies the [[var:x]]
// token without scrolling away to the editor below.
function renderCheatsheetUserVars() {
  const ul = document.getElementById('cheatsheet-user-vars-list');
  if (!ul) return;
  ul.textContent = '';

  if (!userVariables || userVariables.length === 0) {
    const li = document.createElement('li');
    li.className = 'cheatsheet-user-vars-empty';
    li.textContent = 'Adaugă variabile mai jos — vor apărea aici ca chip-uri click-to-copy.';
    ul.appendChild(li);
    return;
  }

  for (const v of userVariables) {
    const li = document.createElement('li');
    const code = document.createElement('code');
    code.textContent = `[[var:${v.name}]]`;
    li.appendChild(code);
    const desc = document.createTextNode(` — ${v.value || '(gol)'}`);
    li.appendChild(desc);
    ul.appendChild(li);
  }

  // Wire click-to-copy on the new chips (idempotent via data-copy-bound).
  attachCheatsheetCopy();
}

// Notion-style inline edit: each cell renders as static text by default;
// click swaps to <input>; Enter or blur saves; Esc reverts. Keeps the
// list scannable when you have 10+ variables and reduces noise from
// always-visible inputs.
function renderUserVarRow(variable) {
  const row = document.createElement('div');
  row.className = 'user-var-row';
  row.dataset.id = variable.id;

  const nameCell = makeEditableCell({
    initial: variable.name,
    placeholder: 'nume',
    title: 'Click pentru a edita numele',
    onSave: async (newName) => {
      if (!newName) return false;
      if (newName === variable.name) return true;
      const ok = await patchVariable(variable.id, { name: newName });
      if (ok) {
        variable.name = newName;
        syntax.textContent = `Folosește: [[var:${newName}]]`;
      }
      return ok;
    },
  });
  nameCell.classList.add('user-var-cell-name');

  const valueCell = makeEditableCell({
    initial: variable.value || '',
    placeholder: '(gol)',
    title: 'Click pentru a edita valoarea',
    onSave: async (newValue) => {
      if (newValue === (variable.value || '')) return true;
      const ok = await patchVariable(variable.id, { value: newValue });
      if (ok) variable.value = newValue;
      return ok;
    },
  });
  valueCell.classList.add('user-var-cell-value');

  const deleteBtn = makeActionButton('delete', '🗑️', 'Șterge', () =>
    deleteUserVariable(variable.id)
  );

  row.appendChild(nameCell);
  row.appendChild(valueCell);
  row.appendChild(deleteBtn);

  const syntax = document.createElement('span');
  syntax.className = 'var-syntax';
  syntax.textContent = `Folosește: [[var:${variable.name}]]`;
  row.appendChild(syntax);

  return row;
}

// Build a cell that toggles between static text and an editable <input>.
// onSave returns true on success, false to revert. Saving happens on
// Enter or blur; Esc cancels and restores the previous text.
function makeEditableCell({ initial, placeholder, title, onSave }) {
  const cell = document.createElement('div');
  cell.className = 'editable-cell';
  cell.title = title;
  cell.tabIndex = 0;

  const text = document.createElement('span');
  text.className = 'editable-cell-text';
  text.textContent = initial || '';
  if (!initial) {
    text.classList.add('editable-cell-placeholder');
    text.textContent = placeholder;
  }
  cell.appendChild(text);

  let editing = false;
  let currentValue = initial || '';

  const enterEdit = () => {
    if (editing) return;
    editing = true;
    cell.classList.add('editing');
    cell.textContent = '';
    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentValue;
    input.placeholder = placeholder;
    cell.appendChild(input);
    input.focus();
    input.select();

    let cancelled = false;
    const exit = async (commit) => {
      if (!editing) return;
      editing = false;
      cell.classList.remove('editing');
      const newVal = input.value;
      if (commit && !cancelled) {
        const ok = await onSave(newVal);
        currentValue = ok ? newVal : currentValue;
      }
      cell.textContent = '';
      const span = document.createElement('span');
      span.className = 'editable-cell-text';
      if (currentValue) {
        span.textContent = currentValue;
      } else {
        span.classList.add('editable-cell-placeholder');
        span.textContent = placeholder;
      }
      cell.appendChild(span);
    };

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); exit(true); }
      else if (e.key === 'Escape') { cancelled = true; exit(false); }
    });
    input.addEventListener('blur', () => exit(true));
  };

  cell.addEventListener('click', enterEdit);
  cell.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !editing) { e.preventDefault(); enterEdit(); }
  });

  return cell;
}

async function patchVariable(id, payload) {
  try {
    const res = await fetch(`${CONFIG.API_URL}/user-variables/${id}/`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Token ${authToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      alert('Error: ' + (err.name || err.detail || 'save failed'));
      return false;
    }
    triggerBackgroundSync();
    return true;
  } catch (err) {
    console.error('User variable save error:', err);
    return false;
  }
}

async function deleteUserVariable(id) {
  if (!confirm('Șterge această variabilă?')) return;
  try {
    const res = await fetch(`${CONFIG.API_URL}/user-variables/${id}/`, {
      method: 'DELETE',
      headers: { 'Authorization': `Token ${authToken}` },
    });
    if (!res.ok && res.status !== 204) {
      throw new Error('Delete failed');
    }
    loadUserVariables();
    triggerBackgroundSync();
  } catch (err) {
    alert('Error: ' + err.message);
  }
}

async function addUserVariable() {
  const nameEl = document.getElementById('new-var-name');
  const valueEl = document.getElementById('new-var-value');
  const name = nameEl.value.trim();
  const value = valueEl.value;
  if (!name) {
    alert('Numele variabilei nu poate fi gol.');
    return;
  }
  try {
    const res = await fetch(`${CONFIG.API_URL}/user-variables/`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${authToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name, value }),
    });
    if (!res.ok) {
      const err = await res.json();
      alert('Error: ' + (err.name || err.detail || JSON.stringify(err)));
      return;
    }
    nameEl.value = '';
    valueEl.value = '';
    loadUserVariables();
    triggerBackgroundSync();
  } catch (err) {
    alert('Error: ' + err.message);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const addBtn = document.getElementById('btn-add-var');
  if (addBtn) addBtn.addEventListener('click', addUserVariable);
});
