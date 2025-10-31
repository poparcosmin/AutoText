// AutoText Content Script - Core text expansion logic
// Listens for Tab key, detects shortcuts, and replaces with expansions

let shortcuts = {};

// Load shortcuts from storage on initialization
async function loadShortcuts() {
  try {
    const result = await chrome.storage.local.get("shortcuts");
    shortcuts = result.shortcuts || {};
    console.log("AutoText: Loaded", Object.keys(shortcuts).length, "shortcuts");

    // If no shortcuts found, trigger auto-sync from background
    if (Object.keys(shortcuts).length === 0) {
      console.log("AutoText: No shortcuts found, triggering auto-sync...");
      chrome.runtime.sendMessage({ action: 'sync' }, (response) => {
        if (chrome.runtime.lastError) {
          console.error("AutoText: Failed to trigger sync:", chrome.runtime.lastError.message);
        } else {
          console.log("AutoText: Auto-sync triggered successfully");
        }
      });
    }
  } catch (error) {
    console.error("AutoText: Error loading shortcuts:", error);
  }
}

// Listen for storage changes (when background syncs new shortcuts)
chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && changes.shortcuts) {
    shortcuts = changes.shortcuts.newValue || {};
    console.log("AutoText: Shortcuts updated,", Object.keys(shortcuts).length, "available");
  }
});

// Get text before cursor in different element types
function getTextBeforeCursor(element) {
  // For input and textarea elements
  if (element.tagName === "INPUT" || element.tagName === "TEXTAREA") {
    const cursorPos = element.selectionStart;

    // Validate cursor position
    if (cursorPos === null || cursorPos === undefined || cursorPos < 0) {
      console.log("AutoText Debug: Invalid cursor position:", cursorPos);
      return "";
    }

    const fullValue = element.value;
    const textBefore = fullValue.substring(0, cursorPos);

    console.log("AutoText Debug: INPUT/TEXTAREA", {
      fullValue,
      cursorPos,
      textBefore,
      valueLength: fullValue.length
    });

    // Extract the last word (everything after last space/newline)
    const match = textBefore.match(/(\S+)$/);
    let lastWord = match ? match[1] : "";

    // Clean zero-width characters and invisible Unicode characters
    lastWord = lastWord.replace(/[\u200B-\u200D\uFEFF]/g, '');

    console.log("AutoText Debug: Extracted last word:", lastWord);
    return lastWord;
  }

  // For contenteditable elements (Gmail, rich text editors)
  if (element.isContentEditable) {
    try {
      const selection = window.getSelection();
      if (!selection.rangeCount) {
        console.log("AutoText Debug: No selection range in contenteditable");
        return "";
      }

      const range = selection.getRangeAt(0);

      // For Gmail and complex contenteditable, we need to find the actual editable ancestor
      let editableElement = element;
      let node = range.startContainer;

      // Walk up to find the contenteditable element
      while (node && node !== document.body) {
        if (node.isContentEditable && node.nodeType === 1) {
          editableElement = node;
          break;
        }
        node = node.parentNode;
      }

      const preCaretRange = range.cloneRange();
      preCaretRange.selectNodeContents(editableElement);
      preCaretRange.setEnd(range.endContainer, range.endOffset);

      const textBefore = preCaretRange.toString();

      console.log("AutoText Debug: contenteditable text before:", textBefore);

      // Extract the last word
      const match = textBefore.match(/(\S+)$/);
      let lastWord = match ? match[1] : "";

      // Clean zero-width characters and invisible Unicode characters
      lastWord = lastWord.replace(/[\u200B-\u200D\uFEFF]/g, '');

      console.log("AutoText Debug: Extracted last word from contenteditable:", lastWord);
      return lastWord;
    } catch (error) {
      console.error("AutoText: Error getting text in contenteditable:", error);
      return "";
    }
  }

  return "";
}

// Replace text in input/textarea
function replaceInTextInput(element, shortcutKey, expansion) {
  const cursorPos = element.selectionStart;
  const textBefore = element.value.substring(0, cursorPos);
  const textAfter = element.value.substring(cursorPos);

  // Remove the shortcut key and add expansion
  const newTextBefore = textBefore.slice(0, -shortcutKey.length) + expansion;

  element.value = newTextBefore + textAfter;

  // Set cursor position after the expansion
  const newCursorPos = newTextBefore.length;
  element.selectionStart = element.selectionEnd = newCursorPos;

  // Trigger input event for frameworks (React, Vue, etc.)
  element.dispatchEvent(new Event('input', { bubbles: true }));
}

// Replace text in contenteditable (Gmail, rich text editors)
function replaceInContentEditable(element, shortcutKey, expansion, htmlExpansion) {
  try {
    const selection = window.getSelection();
    if (!selection.rangeCount) return;

    const range = selection.getRangeAt(0);

    // Delete the shortcut key
    range.setStart(range.endContainer, range.endOffset - shortcutKey.length);
    range.deleteContents();

    // Insert the expansion (HTML if available, otherwise plain text)
    if (htmlExpansion) {
      // Create a document fragment from HTML
      const template = document.createElement('template');
      template.innerHTML = htmlExpansion;
      const fragment = template.content;

      range.insertNode(fragment);

      // Move cursor to end of inserted content
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
    } else {
      // Insert plain text
      const textNode = document.createTextNode(expansion);
      range.insertNode(textNode);

      // Move cursor after inserted text
      range.setStartAfter(textNode);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
    }

    // Trigger input event for the editor
    element.dispatchEvent(new Event('input', { bubbles: true }));
  } catch (error) {
    console.error("AutoText: Error replacing in contenteditable:", error);
  }
}

// Main handler for Tab key press
function handleTabKey(event) {
  // Only handle Tab key
  if (event.key !== 'Tab') {
    return;
  }

  let element = event.target;

  // Check if element is inside a contenteditable (for Gmail and complex editors)
  let isInContentEditable = false;
  let contentEditableParent = null;
  let node = element;

  while (node && node !== document.body) {
    if (node.isContentEditable && node.nodeType === 1) {
      isInContentEditable = true;
      contentEditableParent = node;
      break;
    }
    node = node.parentNode;
  }

  // Only process in text input elements or contenteditable
  if (
    element.tagName !== "INPUT" &&
    element.tagName !== "TEXTAREA" &&
    !isInContentEditable
  ) {
    return;
  }

  // If inside contenteditable, use the contenteditable parent as the element
  if (isInContentEditable && contentEditableParent) {
    element = contentEditableParent;
  }

  // Debug logging
  console.log("AutoText Debug: Tab pressed", {
    elementType: element.tagName || 'contenteditable',
    isContentEditable: element.isContentEditable,
    cursorPos: element.selectionStart,
  });

  // Get the text before cursor
  const textBefore = getTextBeforeCursor(element);

  console.log("AutoText Debug: Text before cursor:", {
    textBefore,
    length: textBefore.length,
    hasShortcut: !!shortcuts[textBefore]
  });

  if (!textBefore) {
    console.log("AutoText Debug: No text before cursor, skipping");
    return;
  }

  // Check if it matches a shortcut
  const shortcut = shortcuts[textBefore];

  if (!shortcut) {
    console.log("AutoText Debug: No shortcut found for:", textBefore);
    return;
  }

  console.log("AutoText Debug: Shortcut match found!", textBefore);

  // We found a match! Prevent default Tab behavior
  event.preventDefault();
  event.stopPropagation();

  // Determine what content to use
  let textContent = shortcut.value;
  let htmlContent = shortcut.html_value;

  // If text is empty but HTML exists, extract text from HTML
  if (!textContent && htmlContent) {
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = htmlContent;
    textContent = tempDiv.textContent || tempDiv.innerText || '';
  }

  console.log(`AutoText: Expanding "${textBefore}" -> "${textContent || htmlContent}"`);

  // Replace based on element type
  if (element.tagName === "INPUT" || element.tagName === "TEXTAREA") {
    // For input/textarea, use plain text (extracted from HTML if needed)
    replaceInTextInput(element, textBefore, textContent);
  } else if (element.isContentEditable) {
    // For contenteditable, use HTML if available
    replaceInContentEditable(
      element,
      textBefore,
      textContent,
      htmlContent
    );
  }
}

// Listen for Tab key press
document.addEventListener("keydown", handleTabKey, true);

// Initialize: load shortcuts
loadShortcuts();

console.log("AutoText: Content script loaded and ready");
