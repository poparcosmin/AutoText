// Import configuration
importScripts('config.js');

const DEBUG = false;
const debugLog = (...args) => {
  if (DEBUG) {
    console.log(...args);
  }
};

// Offline/Online status tracking
let isOnline = true;

// Keep-alive mechanism for Service Worker (Manifest V3)
// Service workers become inactive after ~30s, we need to keep them alive
let keepAliveInterval;

function startKeepAlive() {
  // Clear any existing interval
  if (keepAliveInterval) {
    clearInterval(keepAliveInterval);
  }

  // Send keepalive message every 20 seconds to prevent worker from sleeping
  keepAliveInterval = setInterval(() => {
    debugLog('AutoText: Service Worker keepalive ping');
  }, 20000);
}

// Start keepalive on worker activation
startKeepAlive();

/**
 * Update online/offline status and badge
 */
async function updateOnlineStatus(online) {
  isOnline = online;

  if (!online) {
    // Offline - show indicator
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });
    chrome.action.setTitle({ title: 'AutoText - Offline (using cached shortcuts)' });
    debugLog('AutoText: Now offline, using cached shortcuts');
  } else {
    // Online - clear offline indicator and sync
    await updateBadgeWithShortcutCount();
    chrome.action.setTitle({ title: 'AutoText' });
    debugLog('AutoText: Now online, attempting sync...');
    syncShortcuts();
  }
}

/**
 * Update badge with shortcut count
 */
async function updateBadgeWithShortcutCount() {
  try {
    const { shortcuts } = await chrome.storage.local.get('shortcuts');
    const count = shortcuts ? Object.keys(shortcuts).length : 0;

    if (count > 0) {
      chrome.action.setBadgeText({ text: count.toString() });
      chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
    } else {
      chrome.action.setBadgeText({ text: '' });
    }
  } catch (error) {
    console.error('AutoText: Error updating badge:', error);
  }
}

// Check and refresh token if needed (30 days before expiration)
async function checkAndRefreshToken() {
  try {
    const { auth_token, token_expires_at } = await chrome.storage.local.get([
      'auth_token',
      'token_expires_at'
    ]);

    if (!auth_token || !token_expires_at) return;

    const expiresAt = new Date(token_expires_at);
    const now = new Date();
    const daysUntilExpiry = (expiresAt - now) / (1000 * 60 * 60 * 24);

    // Refresh if within 30 days of expiration
    if (daysUntilExpiry <= 30 && daysUntilExpiry > 0) {
      debugLog(`AutoText: Token expires in ${Math.floor(daysUntilExpiry)} days, attempting refresh...`);

      const res = await fetch(`${CONFIG.API_URL}/auth/refresh/`, {
        method: 'POST',
        headers: {
          'Authorization': `Token ${auth_token}`,
          'Content-Type': 'application/json'
        }
      });

      if (res.ok) {
        const data = await res.json();
        await chrome.storage.local.set({
          auth_token: data.token,
          token_expires_at: data.expires_at
        });
        debugLog('AutoText: Token refreshed successfully');
      }
    }
  } catch (error) {
    console.error('AutoText: Token refresh failed:', error);
  }
}

// Sync shortcuts from Django backend with multi-set support and authentication
// Uses bulk sync endpoint for better performance (single API call)
// Supports offline mode - uses cached shortcuts when network unavailable
async function syncShortcuts() {
  debugLog("AutoText Background: syncShortcuts() called");

  // Check if we're offline
  if (!navigator.onLine) {
    debugLog("AutoText: Device is offline, skipping sync");
    updateOnlineStatus(false);
    return;
  }

  try {
    // Check token refresh before sync
    await checkAndRefreshToken();

    let { auth_token, active_sets, last_sync, shortcuts } = await chrome.storage.local.get([
      "auth_token",
      "active_sets",
      "last_sync",
      "shortcuts"
    ]);

    // Log only non-sensitive info
    debugLog("AutoText: Storage retrieved:", {
      has_token: !!auth_token,
      sets_count: active_sets ? active_sets.length : 0,
      has_last_sync: !!last_sync
    });

    // Check if user is authenticated
    if (!auth_token) {
      debugLog("AutoText: No auth token found. User needs to login via Options page.");
      notifyUserToLogin();
      return;
    }

    // Force full sync if storage is empty (even if last_sync exists)
    const shortcutsCount = shortcuts ? Object.keys(shortcuts).length : 0;
    if (shortcutsCount === 0 && last_sync) {
      debugLog("AutoText: Storage is empty but last_sync exists, forcing full sync...");
      await chrome.storage.local.remove('last_sync');
      last_sync = null;
    }

    // Get active sets (default to 'birou' if none selected)
    const sets = active_sets || ['birou'];
    debugLog(`AutoText: Syncing shortcuts from ${sets.length} set(s)`);

    // Use bulk sync endpoint for better performance
    const bulkSyncUrl = `${CONFIG.API_URL}/sync/bulk/`;
    const isDeltaSync = !!last_sync;

    const requestBody = {
      sets: sets,
    };

    if (last_sync) {
      requestBody.updated_after = new Date(last_sync).toISOString();
    }

    debugLog(`AutoText: Syncing (${isDeltaSync ? 'delta' : 'full'}) via bulk endpoint`);

    const res = await fetch(bulkSyncUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${auth_token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    });

    // Handle authentication errors
    if (res.status === 401) {
      console.error("AutoText: Authentication failed - token expired or invalid");
      await handleAuthenticationFailure();
      return;
    }

    // Handle rate limiting
    if (res.status === 429) {
      console.warn("AutoText: Rate limited, will retry later");
      return;
    }

    if (!res.ok) {
      const errorText = await res.text();
      console.error("AutoText: Failed to sync shortcuts:", res.status, res.statusText);
      console.error("AutoText: Error details:", errorText);
      return;
    }

    const syncData = await res.json();
    debugLog(`AutoText: Received ${syncData.count.shortcuts} shortcuts, ${syncData.count.sets} sets from server`);

    // If delta sync and we have existing shortcuts, merge with them
    let shortcutsMap;
    if (last_sync && syncData.shortcuts.length > 0) {
      // Delta sync - merge with existing shortcuts
      const { shortcuts: existingShortcuts } = await chrome.storage.local.get('shortcuts');
      const existingMap = existingShortcuts || {};

      // Update existing map with new/changed shortcuts
      const newShortcutsMap = mergeShortcutsWithPriority(syncData.shortcuts);
      shortcutsMap = { ...existingMap, ...newShortcutsMap };

      debugLog(`AutoText: Delta sync - merged ${syncData.shortcuts.length} changes with existing shortcuts`);
    } else {
      // Full sync - replace all shortcuts
      shortcutsMap = mergeShortcutsWithPriority(syncData.shortcuts);
      debugLog(`AutoText: Full sync - loaded ${Object.keys(shortcutsMap).length} shortcuts`);
    }

    // Store indexed shortcuts, sets info, and sync timestamp
    await chrome.storage.local.set({
      shortcuts: shortcutsMap,
      available_sets: syncData.sets,
      last_sync: Date.now(),
      server_time: syncData.server_time,
      sync_status: 'success'
    });

    // Update badge with shortcut count
    await updateBadgeWithShortcutCount();

    debugLog(`AutoText: Sync complete. Total shortcuts: ${Object.keys(shortcutsMap).length}`);
  } catch (error) {
    console.error("AutoText: Error during sync:", error);

    // Check if it's a network error (offline)
    if (error.message && (error.message.includes('Failed to fetch') || error.message.includes('NetworkError'))) {
      updateOnlineStatus(false);
    }

    // Store sync failure status
    await chrome.storage.local.set({
      sync_status: 'error',
      sync_error: error.message,
      sync_error_time: Date.now()
    });
  }
}

/**
 * Handle authentication failure (401)
 * Clear auth token and notify user to login again
 */
async function handleAuthenticationFailure() {
  // Clear auth token
  await chrome.storage.local.remove(['auth_token', 'username']);

  // Notify user
  chrome.notifications.create('autotext-auth-error', {
    type: 'basic',
    iconUrl: 'icon48.png',
    title: 'AutoText - Session Expired',
    message: 'Your session has expired. Please open Options to login again.',
    priority: 2
  });

  debugLog("AutoText: Auth token cleared. User needs to re-login.");
}

/**
 * Notify user they need to login
 */
function notifyUserToLogin() {
  chrome.notifications.create('autotext-login-required', {
    type: 'basic',
    iconUrl: 'icon48.png',
    title: 'AutoText - Login Required',
    message: 'Please open AutoText Options to login.',
    priority: 1
  });
}

/**
 * Merge shortcuts with conflict resolution
 * Rule: Personal sets take priority over general sets
 *
 * Example:
 *   - shortcut1: key='b', sets=['birou'], set_types=['general']
 *   - shortcut2: key='b', sets=['cosmin'], set_types=['personal']
 *   Result: Use shortcut2 (personal > general)
 */
function mergeShortcutsWithPriority(shortcuts) {
  const map = {};

  shortcuts.forEach(shortcut => {
    const key = shortcut.key;

    // Check if this shortcut belongs to a personal set
    const hasPersonal = shortcut.set_types && shortcut.set_types.includes('personal');

    // If key doesn't exist yet, add it
    if (!map[key]) {
      map[key] = {
        value: shortcut.value,
        html_value: shortcut.html_value,
        id: shortcut.id,
        sets: shortcut.set_names || [],
        is_personal: hasPersonal
      };
    } else {
      // Key already exists - check priority
      const existingIsPersonal = map[key].is_personal;

      // If current shortcut is personal and existing isn't, replace it
      if (hasPersonal && !existingIsPersonal) {
        debugLog(`AutoText: Replacing '${key}' with personal version`);
        map[key] = {
          value: shortcut.value,
          html_value: shortcut.html_value,
          id: shortcut.id,
          sets: shortcut.set_names || [],
          is_personal: hasPersonal
        };
      }
      // If both are personal or both are general, keep the first one
      // (API should not return duplicates at same priority level, but just in case)
    }
  });

  return map;
}

// Initialize event listeners (called on startup and when service worker wakes up)
function initializeListeners() {
  debugLog("AutoText: Initializing event listeners...");

  // Ensure keepalive is running
  startKeepAlive();

  // Periodic sync every 5 minutes (300000 ms)
  chrome.alarms.create("syncShortcuts", { periodInMinutes: 5 });
}

// Sync on extension startup
chrome.runtime.onStartup.addListener(() => {
  debugLog("AutoText: Extension started, syncing shortcuts...");
  initializeListeners();
  syncShortcuts();
});

// Sync on extension installation/update
chrome.runtime.onInstalled.addListener(() => {
  debugLog("AutoText: Extension installed/updated, syncing shortcuts...");
  initializeListeners();
  syncShortcuts();
});

// Alarm listener (must be at top level, not inside function)
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "syncShortcuts") {
    debugLog("AutoText: Periodic sync triggered");
    syncShortcuts();
  }
});

// Keyboard command listener
chrome.commands.onCommand.addListener(async (command) => {
  debugLog("AutoText: Command received:", command);

  switch (command) {
    case "sync-shortcuts":
      // Manual sync via keyboard shortcut
      debugLog("AutoText: Manual sync triggered via keyboard");
      await syncShortcuts();
      chrome.notifications.create('autotext-sync', {
        type: 'basic',
        iconUrl: 'icon48.png',
        title: 'AutoText - Sync Complete',
        message: 'Shortcuts have been synchronized.',
        priority: 0
      });
      break;

    case "toggle-autotext":
      // Toggle AutoText enabled/disabled
      const { autotext_enabled } = await chrome.storage.local.get('autotext_enabled');
      const newState = autotext_enabled === false ? true : false;
      await chrome.storage.local.set({ autotext_enabled: !autotext_enabled });

      // Update badge to show state
      if (newState) {
        await updateBadgeWithShortcutCount();
        chrome.action.setTitle({ title: 'AutoText - Active' });
      } else {
        chrome.action.setBadgeText({ text: 'OFF' });
        chrome.action.setBadgeBackgroundColor({ color: '#9E9E9E' });
        chrome.action.setTitle({ title: 'AutoText - Disabled' });
      }

      chrome.notifications.create('autotext-toggle', {
        type: 'basic',
        iconUrl: 'icon48.png',
        title: newState ? 'AutoText Enabled' : 'AutoText Disabled',
        message: newState ? 'Text expansion is now active.' : 'Text expansion is paused.',
        priority: 0
      });
      break;

    case "open-options":
      // Open options page
      chrome.runtime.openOptionsPage();
      break;
  }
});

// Manual sync trigger and status queries (must be at top level)
chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
  debugLog("AutoText Background: Received message:", req);

  if (req.action === "sync") {
    debugLog("AutoText Background: Starting manual sync...");
    syncShortcuts().then(() => {
      debugLog("AutoText Background: Sync completed, sending response");
      sendResponse({ status: "done" });
    }).catch(error => {
      console.error("AutoText Background: Sync failed:", error);
      sendResponse({ status: "error", message: error.message });
    });
    return true; // Keep message channel open for async response
  }

  if (req.action === "getStatus") {
    // Return current status for popup/options
    chrome.storage.local.get([
      'shortcuts', 'last_sync', 'sync_status', 'sync_error', 'active_sets'
    ]).then(data => {
      sendResponse({
        online: navigator.onLine,
        shortcutCount: data.shortcuts ? Object.keys(data.shortcuts).length : 0,
        lastSync: data.last_sync,
        syncStatus: data.sync_status,
        syncError: data.sync_error,
        activeSets: data.active_sets || []
      });
    });
    return true;
  }

  if (req.action === "updateBadge") {
    updateBadgeWithShortcutCount().then(() => {
      sendResponse({ status: "done" });
    });
    return true;
  }
});

// Initialize on service worker load
debugLog("AutoText Background: Service worker initialized");
initializeListeners();

// Initialize badge on load
updateBadgeWithShortcutCount();

// Check initial online status
if (!navigator.onLine) {
  updateOnlineStatus(false);
}
