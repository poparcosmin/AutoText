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

// Copy a shortcut to a personal set
async function copyToPersonalSet(shortcut) {
  // Check if we have personal sets available
  if (personalSetsForSelect.length === 0) {
    alert('No personal sets available. Create a personal set first.');
    return;
  }

  // If only one personal set, use it directly
  let targetSetId;
  if (personalSetsForSelect.length === 1) {
    targetSetId = personalSetsForSelect[0].id;
  } else {
    // Show selection if multiple personal sets
    const setNames = personalSetsForSelect.map(s => s.name).join(', ');
    const selectedName = prompt(`Enter the name of the personal set to copy to:\nAvailable: ${setNames}`);
    if (!selectedName) return;

    const targetSet = personalSetsForSelect.find(s => s.name.toLowerCase() === selectedName.toLowerCase());
    if (!targetSet) {
      alert('Set not found. Please enter an exact name.');
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
}

function closeShortcutModal() {
  document.getElementById('shortcut-modal').classList.add('hidden');
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
    const empty = document.createElement('div');
    empty.className = 'user-vars-empty';
    empty.textContent = 'Nicio variabilă încă. Adaugă una mai jos.';
    list.appendChild(empty);
    return;
  }

  for (const v of userVariables) {
    list.appendChild(renderUserVarRow(v));
  }
}

function renderUserVarRow(variable) {
  const row = document.createElement('div');
  row.className = 'user-var-row';
  row.dataset.id = variable.id;

  const nameInput = document.createElement('input');
  nameInput.type = 'text';
  nameInput.value = variable.name;
  nameInput.maxLength = 50;
  nameInput.title = 'Variable name';

  const valueInput = document.createElement('input');
  valueInput.type = 'text';
  valueInput.value = variable.value || '';
  valueInput.title = 'Variable value';

  const deleteBtn = makeActionButton('delete', '🗑️', 'Șterge', () =>
    deleteUserVariable(variable.id)
  );

  row.appendChild(nameInput);
  row.appendChild(valueInput);
  row.appendChild(deleteBtn);

  const syntax = document.createElement('span');
  syntax.className = 'var-syntax';
  syntax.textContent = `Folosește: [[var:${variable.name}]]`;
  row.appendChild(syntax);

  // Save on blur (no save button — feels lighter for short string edits).
  let saveTimer = null;
  const scheduleSave = () => {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      const newName = nameInput.value.trim();
      const newValue = valueInput.value;
      if (!newName) {
        nameInput.value = variable.name;
        return;
      }
      if (newName === variable.name && newValue === (variable.value || '')) return;
      try {
        const res = await fetch(`${CONFIG.API_URL}/user-variables/${variable.id}/`, {
          method: 'PATCH',
          headers: {
            'Authorization': `Token ${authToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ name: newName, value: newValue }),
        });
        if (!res.ok) {
          const err = await res.json();
          alert('Error: ' + (err.name || err.detail || 'save failed'));
          nameInput.value = variable.name;
          valueInput.value = variable.value || '';
          return;
        }
        variable.name = newName;
        variable.value = newValue;
        syntax.textContent = `Folosește: [[var:${newName}]]`;
        triggerBackgroundSync();
      } catch (err) {
        console.error('User variable save error:', err);
      }
    }, 600);
  };
  nameInput.addEventListener('blur', scheduleSave);
  valueInput.addEventListener('blur', scheduleSave);

  return row;
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
