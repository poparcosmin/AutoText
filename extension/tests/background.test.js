/**
 * Tests for background.js service worker functionality.
 */

const { mockStorage, mockRuntime, mockAlarms, mockNotifications, mockAction } = require('./setup');

// Import CONFIG for tests
const CONFIG = {
  API_URL: 'https://autotext.zua.ro/api'
};

// Make CONFIG available globally as it would be in the extension
global.CONFIG = CONFIG;

describe('Background Service Worker', () => {
  describe('Token Management', () => {
    it('should store token expiration on login', async () => {
      const expiresAt = new Date(Date.now() + 180 * 24 * 60 * 60 * 1000).toISOString();

      await chrome.storage.local.set({
        auth_token: 'test-token-123',
        token_expires_at: expiresAt
      });

      const { auth_token, token_expires_at } = await chrome.storage.local.get([
        'auth_token',
        'token_expires_at'
      ]);

      expect(auth_token).toBe('test-token-123');
      expect(token_expires_at).toBe(expiresAt);
    });

    it('should identify tokens needing refresh (< 30 days until expiry)', async () => {
      const now = new Date();
      const expiresIn20Days = new Date(now.getTime() + 20 * 24 * 60 * 60 * 1000);

      await chrome.storage.local.set({
        auth_token: 'test-token',
        token_expires_at: expiresIn20Days.toISOString()
      });

      const { token_expires_at } = await chrome.storage.local.get(['token_expires_at']);
      const expiresAt = new Date(token_expires_at);
      const daysUntilExpiry = (expiresAt - now) / (1000 * 60 * 60 * 24);

      expect(daysUntilExpiry).toBeLessThanOrEqual(30);
      expect(daysUntilExpiry).toBeGreaterThan(0);
    });

    it('should identify tokens NOT needing refresh (> 30 days until expiry)', async () => {
      const now = new Date();
      const expiresIn150Days = new Date(now.getTime() + 150 * 24 * 60 * 60 * 1000);

      await chrome.storage.local.set({
        auth_token: 'test-token',
        token_expires_at: expiresIn150Days.toISOString()
      });

      const { token_expires_at } = await chrome.storage.local.get(['token_expires_at']);
      const expiresAt = new Date(token_expires_at);
      const daysUntilExpiry = (expiresAt - now) / (1000 * 60 * 60 * 24);

      expect(daysUntilExpiry).toBeGreaterThan(30);
    });
  });

  describe('Shortcut Priority Merging', () => {
    // Function to test (same logic as in background.js)
    function mergeShortcutsWithPriority(shortcuts) {
      const map = {};

      shortcuts.forEach(shortcut => {
        const key = shortcut.key;
        const hasPersonal = shortcut.set_types && shortcut.set_types.includes('personal');

        if (!map[key]) {
          map[key] = {
            value: shortcut.value,
            html_value: shortcut.html_value,
            id: shortcut.id,
            sets: shortcut.set_names || [],
            is_personal: hasPersonal
          };
        } else {
          const existingIsPersonal = map[key].is_personal;

          if (hasPersonal && !existingIsPersonal) {
            map[key] = {
              value: shortcut.value,
              html_value: shortcut.html_value,
              id: shortcut.id,
              sets: shortcut.set_names || [],
              is_personal: hasPersonal
            };
          }
        }
      });

      return map;
    }

    it('should keep first shortcut when no conflict', () => {
      const shortcuts = [
        { key: 'hello', value: 'Hello!', id: 1, set_names: ['birou'], set_types: ['general'] }
      ];

      const result = mergeShortcutsWithPriority(shortcuts);

      expect(result['hello'].value).toBe('Hello!');
      expect(result['hello'].is_personal).toBe(false);
    });

    it('should prefer personal over general for same key', () => {
      const shortcuts = [
        { key: 'sig', value: 'General Signature', id: 1, set_names: ['birou'], set_types: ['general'] },
        { key: 'sig', value: 'My Personal Signature', id: 2, set_names: ['cosmin'], set_types: ['personal'] }
      ];

      const result = mergeShortcutsWithPriority(shortcuts);

      expect(result['sig'].value).toBe('My Personal Signature');
      expect(result['sig'].is_personal).toBe(true);
    });

    it('should keep first personal if both are personal', () => {
      const shortcuts = [
        { key: 'sig', value: 'First Personal', id: 1, set_names: ['set1'], set_types: ['personal'] },
        { key: 'sig', value: 'Second Personal', id: 2, set_names: ['set2'], set_types: ['personal'] }
      ];

      const result = mergeShortcutsWithPriority(shortcuts);

      expect(result['sig'].value).toBe('First Personal');
    });

    it('should keep first general if both are general', () => {
      const shortcuts = [
        { key: 'addr', value: 'Address 1', id: 1, set_names: ['birou'], set_types: ['general'] },
        { key: 'addr', value: 'Address 2', id: 2, set_names: ['other'], set_types: ['general'] }
      ];

      const result = mergeShortcutsWithPriority(shortcuts);

      expect(result['addr'].value).toBe('Address 1');
    });

    it('should handle mixed shortcuts correctly', () => {
      const shortcuts = [
        { key: 'a', value: 'General A', id: 1, set_names: ['birou'], set_types: ['general'] },
        { key: 'b', value: 'Personal B', id: 2, set_names: ['cosmin'], set_types: ['personal'] },
        { key: 'a', value: 'Personal A', id: 3, set_names: ['cosmin'], set_types: ['personal'] },
        { key: 'c', value: 'General C', id: 4, set_names: ['birou'], set_types: ['general'] }
      ];

      const result = mergeShortcutsWithPriority(shortcuts);

      expect(Object.keys(result).length).toBe(3);
      expect(result['a'].value).toBe('Personal A'); // Personal overrides general
      expect(result['b'].value).toBe('Personal B');
      expect(result['c'].value).toBe('General C');
    });
  });

  describe('Storage Operations', () => {
    it('should store shortcuts indexed by key', async () => {
      const shortcuts = {
        'hello': { value: 'Hello!', id: 1 },
        'bye': { value: 'Goodbye!', id: 2 }
      };

      await chrome.storage.local.set({ shortcuts });

      const { shortcuts: stored } = await chrome.storage.local.get(['shortcuts']);

      expect(stored['hello'].value).toBe('Hello!');
      expect(stored['bye'].value).toBe('Goodbye!');
    });

    it('should clear auth data on logout', async () => {
      await chrome.storage.local.set({
        auth_token: 'token123',
        username: 'testuser',
        shortcuts: { 'key': { value: 'value' } }
      });

      await chrome.storage.local.remove(['auth_token', 'username']);

      const { auth_token, username, shortcuts } = await chrome.storage.local.get([
        'auth_token',
        'username',
        'shortcuts'
      ]);

      expect(auth_token).toBeUndefined();
      expect(username).toBeUndefined();
      expect(shortcuts).toBeDefined(); // Shortcuts should remain
    });

    it('should track active sets', async () => {
      const activeSets = ['birou', 'cosmin'];

      await chrome.storage.local.set({ active_sets: activeSets });

      const { active_sets } = await chrome.storage.local.get(['active_sets']);

      expect(active_sets).toEqual(['birou', 'cosmin']);
    });
  });

  describe('API Interactions', () => {
    it('should handle successful bulk sync response', async () => {
      const mockResponse = {
        sets: [
          { id: 1, name: 'birou', set_type: 'general' }
        ],
        shortcuts: [
          { id: 1, key: 'hello', value: 'Hello!', set_names: ['birou'], set_types: ['general'] }
        ],
        server_time: new Date().toISOString(),
        count: { sets: 1, shortcuts: 1 }
      };

      global.fetch.mockResolvedValueOnce(mockFetchSuccess(mockResponse));

      const response = await fetch(`${CONFIG.API_URL}/sync/bulk/`, {
        method: 'POST',
        headers: {
          'Authorization': 'Token test-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ sets: ['birou'] })
      });

      expect(response.ok).toBe(true);
      const data = await response.json();
      expect(data.shortcuts.length).toBe(1);
      expect(data.sets.length).toBe(1);
    });

    it('should handle 401 authentication error', async () => {
      global.fetch.mockResolvedValueOnce(mockFetchError(401, 'Token expired'));

      const response = await fetch(`${CONFIG.API_URL}/sync/bulk/`, {
        method: 'POST',
        headers: { 'Authorization': 'Token expired-token' }
      });

      expect(response.ok).toBe(false);
      expect(response.status).toBe(401);
    });

    it('should handle 429 rate limit error', async () => {
      global.fetch.mockResolvedValueOnce(mockFetchError(429, 'Rate limited'));

      const response = await fetch(`${CONFIG.API_URL}/sync/bulk/`, {
        method: 'POST',
        headers: { 'Authorization': 'Token valid-token' }
      });

      expect(response.ok).toBe(false);
      expect(response.status).toBe(429);
    });

    it('should handle network failure gracefully', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(
        fetch(`${CONFIG.API_URL}/sync/bulk/`)
      ).rejects.toThrow('Network error');
    });
  });

  describe('Alarm Management', () => {
    it('should create sync alarm on initialization', () => {
      chrome.alarms.create('syncShortcuts', { periodInMinutes: 5 });

      expect(chrome.alarms.create).toHaveBeenCalledWith(
        'syncShortcuts',
        { periodInMinutes: 5 }
      );
    });
  });

  describe('Message sender validation', () => {
    // Reproduces the guard from background.js onMessage listener.
    // An external page with externally_connectable could otherwise send
    // arbitrary {action: 'sync'} messages to the extension.
    function guardedHandler(req, sender, sendResponse) {
      if (sender.id !== chrome.runtime.id) return false;
      sendResponse({ status: 'accepted', action: req.action });
      return true;
    }

    beforeEach(() => {
      chrome.runtime.id = 'autotext-extension-id';
    });

    it('accepts messages from our own extension', () => {
      const sendResponse = jest.fn();
      const result = guardedHandler(
        { action: 'sync' },
        { id: 'autotext-extension-id' },
        sendResponse
      );
      expect(result).toBe(true);
      expect(sendResponse).toHaveBeenCalledWith({
        status: 'accepted', action: 'sync'
      });
    });

    it('rejects messages from a different extension or web page', () => {
      const sendResponse = jest.fn();
      const result = guardedHandler(
        { action: 'sync' },
        { id: 'some-other-extension' },
        sendResponse
      );
      expect(result).toBe(false);
      expect(sendResponse).not.toHaveBeenCalled();
    });

    it('rejects messages with undefined sender.id (malformed)', () => {
      const sendResponse = jest.fn();
      const result = guardedHandler(
        { action: 'sync' },
        { id: undefined },
        sendResponse
      );
      expect(result).toBe(false);
    });
  });

  describe('Silent auth handling', () => {
    it('clears auth token without creating any OS notification', async () => {
      await chrome.storage.local.set({
        auth_token: 'to-be-cleared',
        username: 'u',
      });

      // Reproduce handleAuthenticationFailure behavior (inline — SW not requirable)
      await chrome.storage.local.remove(['auth_token', 'username']);

      const { auth_token, username } = await chrome.storage.local.get([
        'auth_token', 'username'
      ]);
      expect(auth_token).toBeUndefined();
      expect(username).toBeUndefined();

      // The key assertion: no user-facing popup was triggered
      expect(chrome.notifications.create).not.toHaveBeenCalledWith(
        'autotext-auth-error',
        expect.anything()
      );
      expect(chrome.notifications.create).not.toHaveBeenCalledWith(
        'autotext-login-required',
        expect.anything()
      );
    });
  });
});

describe('Delta Sync Logic', () => {
  it('should merge delta sync with existing shortcuts', async () => {
    // Existing shortcuts
    const existingShortcuts = {
      'hello': { value: 'Hello!', id: 1 },
      'bye': { value: 'Goodbye!', id: 2 }
    };

    await chrome.storage.local.set({ shortcuts: existingShortcuts });

    // New/updated shortcut from delta sync
    const deltaShortcuts = {
      'hello': { value: 'Hello, Updated!', id: 1 },
      'new': { value: 'New shortcut', id: 3 }
    };

    const { shortcuts } = await chrome.storage.local.get(['shortcuts']);
    const merged = { ...shortcuts, ...deltaShortcuts };

    await chrome.storage.local.set({ shortcuts: merged });

    const { shortcuts: final } = await chrome.storage.local.get(['shortcuts']);

    expect(final['hello'].value).toBe('Hello, Updated!');
    expect(final['bye'].value).toBe('Goodbye!');
    expect(final['new'].value).toBe('New shortcut');
  });

  it('should track last sync timestamp', async () => {
    const syncTime = Date.now();

    await chrome.storage.local.set({ last_sync: syncTime });

    const { last_sync } = await chrome.storage.local.get(['last_sync']);

    expect(last_sync).toBe(syncTime);
  });

  it('should force full sync when storage is empty', async () => {
    await chrome.storage.local.set({
      last_sync: Date.now(),
      shortcuts: {}
    });

    const { shortcuts, last_sync } = await chrome.storage.local.get(['shortcuts', 'last_sync']);
    const shortcutsCount = shortcuts ? Object.keys(shortcuts).length : 0;

    // Logic from background.js — && short-circuits to the truthy operand (timestamp)
    const shouldForceFull = shortcutsCount === 0 && last_sync;

    expect(shouldForceFull).toBeTruthy();
  });
});


// ============================================================================
// Retry policy tests — verify markSyncFailure / markSyncSuccess in isolation.
// We re-declare the helpers here because background.js is a service-worker
// script (importScripts + chrome.runtime.onStartup) and can't be required as
// a CommonJS module in Jest. If retry logic moves to a pure helper module,
// these should switch to direct imports.
// ============================================================================

describe('Sync Retry Policy', () => {
  const MAX_SYNC_RETRIES = 3;
  const RETRY_DELAY_MINUTES = 1;

  async function markSyncSuccess() {
    await chrome.storage.local.remove([
      'sync_retry_count', 'sync_error', 'sync_error_time'
    ]);
    try { await chrome.alarms.clear('syncRetry'); } catch (_) { /* noop */ }
    await chrome.storage.local.set({ sync_status: 'success' });
  }

  async function markSyncFailure(errorMessage) {
    const stored = await chrome.storage.local.get('sync_retry_count');
    const attempt = (stored.sync_retry_count || 0) + 1;
    await chrome.storage.local.set({
      sync_status: 'error',
      sync_error: errorMessage,
      sync_error_time: Date.now(),
      sync_retry_count: attempt,
    });
    if (attempt < MAX_SYNC_RETRIES) {
      chrome.alarms.create('syncRetry', { delayInMinutes: RETRY_DELAY_MINUTES });
    } else {
      chrome.action.setBadgeText({ text: '!' });
      chrome.action.setBadgeBackgroundColor({ color: '#F44336' });
      chrome.action.setTitle({
        title: `AutoText - Sync failed after ${MAX_SYNC_RETRIES} attempts. Click for options.`
      });
    }
  }

  it('schedules a retry alarm on first failure', async () => {
    await markSyncFailure('boom');

    expect(chrome.alarms.create).toHaveBeenCalledWith(
      'syncRetry',
      { delayInMinutes: 1 }
    );
    const { sync_retry_count } = await chrome.storage.local.get('sync_retry_count');
    expect(sync_retry_count).toBe(1);
  });

  it('increments retry count across successive failures', async () => {
    await markSyncFailure('err1');
    await markSyncFailure('err2');

    const { sync_retry_count } = await chrome.storage.local.get('sync_retry_count');
    expect(sync_retry_count).toBe(2);
  });

  it('shows red badge after MAX_SYNC_RETRIES and stops scheduling retries', async () => {
    await markSyncFailure('1');
    await markSyncFailure('2');
    await markSyncFailure('3');

    // Third failure should NOT schedule another retry
    const scheduleCalls = chrome.alarms.create.mock.calls.filter(
      ([name]) => name === 'syncRetry'
    );
    expect(scheduleCalls).toHaveLength(2); // calls 1 and 2 scheduled, call 3 gives up

    expect(chrome.action.setBadgeText).toHaveBeenCalledWith({ text: '!' });
    expect(chrome.action.setBadgeBackgroundColor).toHaveBeenCalledWith({ color: '#F44336' });
  });

  it('clears retry state on success (counter + alarm)', async () => {
    await markSyncFailure('bad');
    await markSyncSuccess();

    const data = await chrome.storage.local.get([
      'sync_retry_count', 'sync_error', 'sync_status'
    ]);
    expect(data.sync_retry_count).toBeUndefined();
    expect(data.sync_error).toBeUndefined();
    expect(data.sync_status).toBe('success');
    expect(chrome.alarms.clear).toHaveBeenCalledWith('syncRetry');
  });

  it('stores the error message so the options page can surface it', async () => {
    await markSyncFailure('HTTP 500: Internal Server Error');
    const { sync_error } = await chrome.storage.local.get('sync_error');
    expect(sync_error).toBe('HTTP 500: Internal Server Error');
  });
});
