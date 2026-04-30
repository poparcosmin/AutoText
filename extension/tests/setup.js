/**
 * Jest setup file for AutoText extension tests.
 *
 * Mocks Chrome Extension APIs and provides test utilities.
 */

global.DOMPurify = { sanitize: (html) => html };
// =============================================================================
// CHROME API MOCKS
// =============================================================================

const mockStorage = {
  onChanged: {
    addListener: jest.fn(),
    removeListener: jest.fn(),
  },

  local: {
    _data: {},

    get: jest.fn((keys) => {
      return new Promise((resolve) => {
        if (typeof keys === 'string') {
          resolve({ [keys]: mockStorage.local._data[keys] });
        } else if (Array.isArray(keys)) {
          const result = {};
          keys.forEach(key => {
            result[key] = mockStorage.local._data[key];
          });
          resolve(result);
        } else if (keys === null || keys === undefined) {
          resolve({ ...mockStorage.local._data });
        } else {
          const result = {};
          Object.keys(keys).forEach(key => {
            result[key] = mockStorage.local._data[key] ?? keys[key];
          });
          resolve(result);
        }
      });
    }),

    set: jest.fn((items) => {
      return new Promise((resolve) => {
        Object.assign(mockStorage.local._data, items);
        resolve();
      });
    }),

    remove: jest.fn((keys) => {
      return new Promise((resolve) => {
        const keysArray = Array.isArray(keys) ? keys : [keys];
        keysArray.forEach(key => {
          delete mockStorage.local._data[key];
        });
        resolve();
      });
    }),

    clear: jest.fn(() => {
      return new Promise((resolve) => {
        mockStorage.local._data = {};
        resolve();
      });
    })
  }
};

const mockRuntime = {
  sendMessage: jest.fn((message) => {
    return new Promise((resolve) => {
      resolve({ status: 'done' });
    });
  }),

  onMessage: {
    addListener: jest.fn(),
    removeListener: jest.fn()
  },

  onStartup: {
    addListener: jest.fn()
  },

  onInstalled: {
    addListener: jest.fn()
  },

  getURL: jest.fn((path) => `chrome-extension://mock-extension-id/${path}`)
};

const mockAlarms = {
  create: jest.fn(),
  clear: jest.fn(),
  get: jest.fn(),
  getAll: jest.fn(() => Promise.resolve([])),

  onAlarm: {
    addListener: jest.fn()
  }
};

const mockNotifications = {
  create: jest.fn((id, options) => {
    return new Promise((resolve) => resolve(id));
  }),
  clear: jest.fn()
};

const mockAction = {
  setBadgeText: jest.fn(),
  setBadgeBackgroundColor: jest.fn(),
  setTitle: jest.fn()
};

const mockCommands = {
  onCommand: {
    addListener: jest.fn()
  }
};

// Global chrome object mock
global.chrome = {
  storage: mockStorage,
  runtime: mockRuntime,
  alarms: mockAlarms,
  notifications: mockNotifications,
  action: mockAction,
  commands: mockCommands
};

// =============================================================================
// FETCH MOCK
// =============================================================================

global.fetch = jest.fn();

// Helper to create mock fetch responses
global.mockFetchSuccess = (data, status = 200) => {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data))
  });
};

global.mockFetchError = (status, message = 'Error') => {
  return Promise.resolve({
    ok: false,
    status,
    json: () => Promise.resolve({ error: message }),
    text: () => Promise.resolve(message)
  });
};

// =============================================================================
// DOM HELPERS
// =============================================================================

// Create a mock DOM element with common methods
global.createMockElement = (tagName, attributes = {}) => {
  const element = document.createElement(tagName);
  Object.entries(attributes).forEach(([key, value]) => {
    if (key === 'className') {
      element.className = value;
    } else if (key === 'textContent') {
      element.textContent = value;
    } else {
      element.setAttribute(key, value);
    }
  });
  return element;
};

// =============================================================================
// TEST UTILITIES
// =============================================================================

global._SUPPRESS_AUTOTEXT_WARNINGS = true;

// Reset all mocks between tests
beforeEach(() => {
  jest.clearAllMocks();
  mockStorage.local._data = {};
  global.fetch.mockReset();
});

// Clean up after each test - use safe DOM clearing
afterEach(() => {
  while (document.body.firstChild) {
    document.body.removeChild(document.body.firstChild);
  }
});

// =============================================================================
// CONSOLE SUPPRESSION (optional)
// =============================================================================

// Suppress console.log in tests (comment out to debug)
// global.console = {
//   ...console,
//   log: jest.fn(),
//   debug: jest.fn(),
//   info: jest.fn(),
// };

// Export mocks for direct access in tests
module.exports = {
  mockStorage,
  mockRuntime,
  mockAlarms,
  mockNotifications,
  mockAction,
  mockCommands
};
