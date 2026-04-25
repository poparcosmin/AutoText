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

function _gmailRecipient() {
  // Compose dialog: input or textarea with name="to". Gmail uses both
  // depending on layout (popup vs full screen).
  const composeTo = document.querySelector('[role="dialog"] input[name="to"]')
                 || document.querySelector('[role="dialog"] textarea[name="to"]');
  if (composeTo && composeTo.value) {
    _gmailFailCount = 0;
    return _firstNameFromAddressList(composeTo.value);
  }

  // Reply chip — element with email attribute inside compose dialog
  const replyChip = document.querySelector(
    '[role="dialog"] .gD[email], [role="dialog"] .agP[email]'
  );
  if (replyChip) {
    _gmailFailCount = 0;
    const name = replyChip.getAttribute('name');
    if (name) return name;
    const email = replyChip.getAttribute('email') || '';
    return email.split('@')[0];
  }

  // Reading thread without an open compose: sender of the most recent message
  const lastSender = document.querySelector('.h7 .gD[email]');
  if (lastSender) {
    _gmailFailCount = 0;
    const name = lastSender.getAttribute('name');
    if (name) return name;
    const email = lastSender.getAttribute('email') || '';
    return email.split('@')[0];
  }

  // No selectors matched — increment counter, surface warning when persistent
  _gmailFailCount++;
  if (typeof console !== 'undefined') {
    console.warn('AutoText: Gmail recipient parser empty (count:', _gmailFailCount, ')');
  }
  if (_gmailFailCount >= SITE_PARSER_FAIL_THRESHOLD
      && typeof chrome !== 'undefined'
      && chrome.storage && chrome.storage.local) {
    chrome.storage.local.set({
      gmail_parser_warning: 'Gmail layout changed — recipient detection unreliable',
      gmail_parser_warning_at: new Date().toISOString(),
    }).catch(() => {});
  }
  return '';
}

const siteParsers = {
  'mail.google.com': {
    recipient: _gmailRecipient,
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
