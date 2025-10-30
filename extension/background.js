// Import configuration
importScripts('config.js');

// Sync shortcuts from Django backend with multi-set support and authentication
async function syncShortcuts() {
  console.log("AutoText Background: syncShortcuts() called");

  try {
    let { auth_token, active_sets, api_url, last_sync } = await chrome.storage.local.get([
      "auth_token",
      "active_sets",
      "api_url",
      "last_sync"
    ]);

    console.log("AutoText: Storage retrieved:", {
      has_token: !!auth_token,
      active_sets,
      api_url,
      has_last_sync: !!last_sync
    });

    // Check if user is authenticated
    if (!auth_token) {
      console.log("AutoText: No auth token found. User needs to login via Options page.");
      notifyUserToLogin();
      return;
    }

    // Get active sets (default to 'birou' if none selected)
    const sets = active_sets || ['birou'];
    console.log(`AutoText: Syncing shortcuts from sets: ${sets.join(', ')}`);

    // Build API URL with sets query parameter
    const baseUrl = api_url || `${CONFIG.API_URL}/shortcuts/`;
    const setsParam = sets.join(',');

    // Delta sync: only fetch changes since last sync
    let url = `${baseUrl}?sets=${encodeURIComponent(setsParam)}`;
    if (last_sync) {
      const lastSyncDate = new Date(last_sync).toISOString();
      url += `&updated_after=${encodeURIComponent(lastSyncDate)}`;
      console.log(`AutoText: Delta sync since ${lastSyncDate}`);
    }

    console.log(`AutoText: Fetching from: ${url}`);

    const res = await fetch(url, {
      headers: { Authorization: `Token ${auth_token}` }
    });

    // Handle authentication errors
    if (res.status === 401) {
      console.error("AutoText: Authentication failed - token expired or invalid");
      await handleAuthenticationFailure();
      return;
    }

    if (!res.ok) {
      console.error("AutoText: Failed to sync shortcuts:", res.status, res.statusText);
      return;
    }

    const serverShortcuts = await res.json();
    console.log(`AutoText: Received ${serverShortcuts.length} shortcuts from server`);

    // If delta sync and we have existing shortcuts, merge with them
    let shortcutsMap;
    if (last_sync && serverShortcuts.length > 0) {
      // Delta sync - merge with existing shortcuts
      const { shortcuts: existingShortcuts } = await chrome.storage.local.get('shortcuts');
      const existingMap = existingShortcuts || {};

      // Update existing map with new/changed shortcuts
      const newShortcutsMap = mergeShortcutsWithPriority(serverShortcuts);
      shortcutsMap = { ...existingMap, ...newShortcutsMap };

      console.log(`AutoText: Delta sync - merged ${serverShortcuts.length} changes with existing shortcuts`);
    } else {
      // Full sync - replace all shortcuts
      shortcutsMap = mergeShortcutsWithPriority(serverShortcuts);
      console.log(`AutoText: Full sync - loaded ${Object.keys(shortcutsMap).length} shortcuts`);
    }

    // Store indexed shortcuts and sync timestamp
    await chrome.storage.local.set({
      shortcuts: shortcutsMap,
      last_sync: Date.now()
    });

    console.log(`AutoText: Sync complete. Total shortcuts: ${Object.keys(shortcutsMap).length}`);
  } catch (error) {
    console.error("AutoText: Error during sync:", error);
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

  console.log("AutoText: Auth token cleared. User needs to re-login.");
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
        console.log(`AutoText: Replacing '${key}' with personal version`);
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

// Sync on extension startup
chrome.runtime.onStartup.addListener(() => {
  console.log("AutoText: Extension started, syncing shortcuts...");
  syncShortcuts();
});

// Sync on extension installation/update
chrome.runtime.onInstalled.addListener(() => {
  console.log("AutoText: Extension installed/updated, syncing shortcuts...");
  syncShortcuts();
});

// Periodic sync every 5 minutes (300000 ms)
chrome.alarms.create("syncShortcuts", { periodInMinutes: 5 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "syncShortcuts") {
    console.log("AutoText: Periodic sync triggered");
    syncShortcuts();
  }
});

// Manual sync trigger (can be called from content script if needed)
chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
  console.log("AutoText Background: Received message:", req);

  if (req.action === "sync") {
    console.log("AutoText Background: Starting manual sync...");
    syncShortcuts().then(() => {
      console.log("AutoText Background: Sync completed, sending response");
      sendResponse({ status: "done" });
    }).catch(error => {
      console.error("AutoText Background: Sync failed:", error);
      sendResponse({ status: "error", message: error.message });
    });
    return true;
  }
});

console.log("AutoText Background: Service worker initialized");
