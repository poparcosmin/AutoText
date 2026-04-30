// Site-specific value extractors for system variables that need DOM context
// (e.g. [[recipient]] in Gmail compose). Each parser returns a string;
// gracious fallback to '' when the host page DOM doesn't match expected
// selectors — never throws, never blocks expansion.
//
// Architecture: this file is a content_script loaded BEFORE content.js so
// `siteParsers` is available in the same global scope. Adding a new site:
// 1. Add an entry to siteParsers keyed by location.host.
// 2. Add a per-site test fixture in tests/site-parsers.test.js.
//
// Failure visibility: parsers track consecutive empty results; after
// THRESHOLD failures we set chrome.storage.local.gmail_parser_warning so
// popup.js can surface a banner ("Gmail layout changed").

const SITE_PARSER_FAIL_THRESHOLD = 3;
let _gmailFailCount = 0;

function _firstNameFromAddressList(value) {
  // "Name Surname <email@x.com>, Other <other@y.com>" -> "Name Surname"
  // "email@x.com" -> "email"
  if (!value) return '';
  const first = value.split(',')[0].trim();
  const angled = first.match(/^([^<]+?)\s*<.*>$/);
  if (angled) return angled[1].trim();
  if (first.includes('@')) return first.split('@')[0];
  return first;
}

// Has the extension runtime been invalidated by a reload? Accessing
// chrome.runtime.id throws synchronously after the host extension is
// disabled or reloaded; we wrap the access so a stale content script
// can detect the situation without bringing down the whole expand
// pipeline.
function _runtimeAlive() {
  try {
    return typeof chrome !== 'undefined'
        && !!chrome.runtime
        && !!chrome.runtime.id;
  } catch (_e) {
    return false;
  }
}

function _gmailRecipient() {
  // Bail early on a stale content script — the parser cannot read storage
  // and the resolver in content.js will catch the empty string.
  if (!_runtimeAlive()) return '';

  // Try a series of selector strategies, broadest first. Gmail's class
  // names rotate; the [email] / [name] attributes have been stable for
  // years, which is why most fallbacks key on them rather than on a
  // specific class. Each strategy returns the *first* match, so we
  // walk an ordered list and stop at the first hit.
  const strategies = [
    // 1. Compose dialog "To" field (popup layout)
    () => {
      const el = document.querySelector('[role="dialog"] input[name="to"]')
              || document.querySelector('[role="dialog"] textarea[name="to"]');
      return el && el.value ? _firstNameFromAddressList(el.value) : '';
    },
    // 2. Compose dialog without role="dialog" (full-screen compose)
    () => {
      const el = document.querySelector('input[name="to"]')
              || document.querySelector('textarea[name="to"]');
      return el && el.value ? _firstNameFromAddressList(el.value) : '';
    },
    // 3. Compose chip — recipient already added (most common case in
    //    a real conversation). Gmail wraps the chip in a span with
    //    `email` and usually `name` attributes; class is unstable.
    () => {
      const chip = document.querySelector('[role="dialog"] [email][name]')
                || document.querySelector('[role="dialog"] [email]');
      if (!chip) return '';
      const name = chip.getAttribute('name');
      if (name) return name;
      const email = chip.getAttribute('email') || '';
      return email.split('@')[0];
    },
    // 4. Reading a thread (no compose open) — pull the last sender.
    //    Multiple Gmail variants put [email] on chips inside the open
    //    message header; the strict ".h7 .gD" selector misses
    //    redesigns, so try [email] anywhere first.
    () => {
      const candidates = document.querySelectorAll('[email]');
      // Prefer chips with both name and email (real recipient/sender),
      // skip stray hidden ones with empty values.
      for (const el of candidates) {
        const email = el.getAttribute('email');
        if (!email) continue;
        const name = el.getAttribute('name');
        if (name) return name;
        return email.split('@')[0];
      }
      return '';
    },
  ];

  for (const strategy of strategies) {
    try {
      const value = strategy();
      if (value) {
        _gmailFailCount = 0;
        return value;
      }
    } catch (_e) {
      // strategy threw — keep walking
    }
  }

  _gmailFailCount++;
  if (typeof console !== 'undefined' && !globalThis._SUPPRESS_AUTOTEXT_WARNINGS) {
    console.warn('AutoText: Gmail recipient parser empty (count:', _gmailFailCount, ')');
  }
  // Set the warning flag ONLY if the runtime is still alive. After a
  // browser-extension reload the previously-injected content script
  // outlives the extension context; calls to chrome.storage.* throw
  // "Extension context invalidated". Catching keeps the parser silent
  // until the page reloads and re-injects the new bundle.
  if (_gmailFailCount >= SITE_PARSER_FAIL_THRESHOLD && _runtimeAlive()
      && chrome.storage && chrome.storage.local) {
    try {
      const setPromise = chrome.storage.local.set({
        gmail_parser_warning: 'Gmail layout changed — recipient detection unreliable',
        gmail_parser_warning_at: new Date().toISOString(),
      });
      if (setPromise && typeof setPromise.catch === 'function') {
        setPromise.catch(() => {});
      }
    } catch (_e) {
      // Storage failed too — content script will be replaced on next page
      // reload, no further action needed.
    }
  }
  return '';
}

function _gmailRecipientEmail() {
  // Sister-parser to _gmailRecipient — returns the email address rather
  // than the display name. Used by [[recipient_email]] and consumed by
  // [[if:...]] conditions for language routing (e.g. .it/.de → English).
  if (!_runtimeAlive()) return '';

  const strategies = [
    // 1. Compose chip with [email] attribute (most reliable when present)
    () => {
      const chip = document.querySelector('[role="dialog"] [email]')
                || document.querySelector('[email]');
      return chip ? (chip.getAttribute('email') || '') : '';
    },
    // 2. Raw "To" field — first address in comma-separated list
    () => {
      const el = document.querySelector('[role="dialog"] input[name="to"]')
              || document.querySelector('input[name="to"]')
              || document.querySelector('textarea[name="to"]');
      if (!el || !el.value) return '';
      // Match "Name <email@domain>" or bare "email@domain"
      const first = el.value.split(',')[0].trim();
      const m = first.match(/<([^>]+)>/);
      if (m) return m[1].trim();
      // Bare email if no angle brackets
      return /@/.test(first) ? first : '';
    },
  ];

  for (const strategy of strategies) {
    try {
      const value = strategy();
      if (value) return value;
    } catch (_e) {
      // strategy threw — keep walking
    }
  }
  return '';
}

const siteParsers = {
  'mail.google.com': {
    recipient: _gmailRecipient,
    recipient_email: _gmailRecipientEmail,
  },
  // Future: outlook.live.com, mail.yahoo.com, web.whatsapp.com
};

function getSiteValue(name) {
  const host = (typeof location !== 'undefined' && location.host) || '';
  const parser = siteParsers[host] && siteParsers[host][name];
  return parser ? parser() : '';
}

// CommonJS export for tests; in browser, attach to globalThis so content.js
// can reference siteParsers / getSiteValue without a build step.
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    siteParsers,
    getSiteValue,
    _firstNameFromAddressList,
    _resetGmailFailCount: () => { _gmailFailCount = 0; },
  };
} else if (typeof globalThis !== 'undefined') {
  globalThis.siteParsers = siteParsers;
  globalThis.getSiteValue = getSiteValue;
}
