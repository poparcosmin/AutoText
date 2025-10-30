// AutoText Options Page Logic
// CONFIG is imported from config.js (loaded in options.html)

let availableSets = [];
let selectedSets = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
  console.log('AutoText Options: Initializing...');

  try {
    // Load available sets from API
    await loadAvailableSets();

    // Load user's selected sets from storage
    await loadSelectedSets();

    // Render UI
    renderSets();

    // Attach event listeners
    attachEventListeners();

  } catch (error) {
    showError(`Failed to load: ${error.message}`);
  }
});

// Fetch available sets from Django API
async function loadAvailableSets() {
  console.log('Fetching available sets from API...');

  const response = await fetch(`${CONFIG.API_URL}/sets/`, {
    headers: {
      'Authorization': `Token ${CONFIG.DEV_TOKEN}`
    }
  });

  if (!response.ok) {
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

  const isSelected = selectedSets.includes(set.name);
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
      if (!selectedSets.includes(set.name)) {
        selectedSets.push(set.name);
      }
    } else {
      div.classList.remove('selected');
      selectedSets = selectedSets.filter(s => s !== set.name);
    }

    console.log('Selected sets updated:', selectedSets);
  });

  return div;
}

// Attach event listeners to buttons
function attachEventListeners() {
  document.getElementById('save').addEventListener('click', saveAndSync);
  document.getElementById('sync').addEventListener('click', syncNow);
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
    // Save to storage
    await new Promise((resolve) => {
      chrome.storage.local.set({ active_sets: selectedSets }, resolve);
    });

    console.log('Sets saved to storage');

    // Trigger sync
    await triggerBackgroundSync();

    // Show success
    showStatus(`✅ Saved! Active sets: ${selectedSets.join(', ')}`, 'success');

  } catch (error) {
    showError(`Failed to save: ${error.message}`);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = '💾 Save & Sync';
  }
}

// Trigger immediate sync via background script
async function syncNow() {
  console.log('Triggering manual sync...');

  const syncBtn = document.getElementById('sync');
  syncBtn.disabled = true;
  syncBtn.textContent = '🔄 Syncing...';

  try {
    await triggerBackgroundSync();
    showStatus('✅ Sync completed successfully!', 'success');
  } catch (error) {
    showError(`Sync failed: ${error.message}`);
  } finally {
    syncBtn.disabled = false;
    syncBtn.textContent = '🔄 Sync Now';
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
