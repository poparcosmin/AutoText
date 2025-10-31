// AutoText Options Page Logic with Authentication
// CONFIG is imported from config.js (loaded in options.html)

let availableSets = [];
let selectedSets = [];
let currentUser = null;
let authToken = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
  console.log('AutoText Options: Initializing...');

  try {
    // Check if user is authenticated
    await checkAuthentication();
  } catch (error) {
    showError(`Failed to load: ${error.message}`);
  }
});

// Check if user has valid auth token
async function checkAuthentication() {
  const result = await chrome.storage.local.get(['auth_token', 'username']);
  authToken = result.auth_token;
  currentUser = result.username;

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

    // Save token and username
    authToken = data.token;
    currentUser = data.user.username;

    await chrome.storage.local.set({
      auth_token: authToken,
      username: currentUser
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

    // Show success
    showStatus(`✅ Saved! All ${normalizedSets.join(', ')} shortcuts loaded.`, 'success');

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
