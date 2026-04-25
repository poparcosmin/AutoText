/**
 * @jest-environment jsdom
 */

const path = require('path');
const parsers = require(path.resolve(__dirname, '..', 'lib', 'site-parsers.js'));

function buildComposeWithInput(name, email) {
  const dialog = document.createElement('div');
  dialog.setAttribute('role', 'dialog');
  const input = document.createElement('input');
  input.setAttribute('name', 'to');
  input.value = email ? `${name} <${email}>` : name;
  dialog.appendChild(input);
  return dialog;
}

function buildComposeWithTextarea(value) {
  const dialog = document.createElement('div');
  dialog.setAttribute('role', 'dialog');
  const ta = document.createElement('textarea');
  ta.setAttribute('name', 'to');
  ta.value = value;
  dialog.appendChild(ta);
  return dialog;
}

function buildReplyChipDialog(email, name) {
  const dialog = document.createElement('div');
  dialog.setAttribute('role', 'dialog');
  const chip = document.createElement('span');
  chip.className = 'gD';
  chip.setAttribute('email', email);
  if (name) chip.setAttribute('name', name);
  dialog.appendChild(chip);
  return dialog;
}

function buildThreadHeader(email, name) {
  const wrapper = document.createElement('div');
  wrapper.className = 'h7';
  const chip = document.createElement('span');
  chip.className = 'gD';
  chip.setAttribute('email', email);
  if (name) chip.setAttribute('name', name);
  wrapper.appendChild(chip);
  return wrapper;
}

describe('site-parsers', () => {
  beforeEach(() => {
    document.body.textContent = '';
    parsers._resetGmailFailCount();
    global.chrome = {
      runtime: { id: 'test-extension-id' },
      storage: {
        local: {
          set: jest.fn().mockResolvedValue(undefined),
        },
      },
    };
  });

  describe('_firstNameFromAddressList', () => {
    it('extracts name from "Name <email>" syntax', () => {
      expect(parsers._firstNameFromAddressList('Cosmin Popa <c@x.com>')).toBe('Cosmin Popa');
    });

    it('takes first when multiple recipients', () => {
      const result = parsers._firstNameFromAddressList('Alice <a@x.com>, Bob <b@y.com>');
      expect(result).toBe('Alice');
    });

    it('strips domain when only email is provided', () => {
      expect(parsers._firstNameFromAddressList('alice@example.com')).toBe('alice');
    });

    it('returns empty string for empty input', () => {
      expect(parsers._firstNameFromAddressList('')).toBe('');
    });
  });

  describe('siteParsers["mail.google.com"].recipient', () => {
    const recipient = parsers.siteParsers['mail.google.com'].recipient;

    it('reads from compose dialog input[name="to"]', () => {
      document.body.appendChild(buildComposeWithInput('Alice', 'alice@example.com'));
      expect(recipient()).toBe('Alice');
    });

    it('reads from compose dialog textarea[name="to"]', () => {
      document.body.appendChild(buildComposeWithTextarea('Bob <bob@x.com>'));
      expect(recipient()).toBe('Bob');
    });

    it('falls back to reply chip name attribute', () => {
      document.body.appendChild(buildReplyChipDialog('alice@example.com', 'Alice'));
      expect(recipient()).toBe('Alice');
    });

    it('reads .h7 .gD[email] for read-only thread context', () => {
      document.body.appendChild(buildThreadHeader('sender@x.com', 'Sender Name'));
      expect(recipient()).toBe('Sender Name');
    });

    it('returns empty string when no selectors match', () => {
      expect(recipient()).toBe('');
    });

    it('sets gmail_parser_warning after threshold consecutive failures', () => {
      recipient();
      recipient();
      recipient();
      expect(global.chrome.storage.local.set).toHaveBeenCalledWith(
        expect.objectContaining({
          gmail_parser_warning: expect.any(String),
        })
      );
    });

    it('clears failure count on successful match', () => {
      recipient();
      recipient();
      document.body.appendChild(buildComposeWithInput('a@b.com', null));
      expect(recipient()).toBe('a');
      document.body.textContent = '';
      recipient();
      expect(global.chrome.storage.local.set).not.toHaveBeenCalled();
    });
  });

  describe('getSiteValue', () => {
    it('returns empty for unknown host (jsdom localhost)', () => {
      expect(parsers.getSiteValue('recipient')).toBe('');
    });

    it('returns empty for unknown variable name', () => {
      expect(parsers.siteParsers['mail.google.com'].subject).toBeUndefined();
    });
  });
});
