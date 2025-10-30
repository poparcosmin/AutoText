// AutoText Content Script - DEBUG VERSION
// This version has extensive logging to help diagnose issues

console.log('%c🚀 AutoText DEBUG: Starting...', 'color: green; font-weight: bold');

let shortcuts = {};

// Load shortcuts from storage
async function loadShortcuts() {
  try {
    console.log('📦 AutoText: Loading shortcuts from storage...');
    const result = await chrome.storage.local.get("shortcuts");
    shortcuts = result.shortcuts || {};
    console.log(`✅ AutoText: Loaded ${Object.keys(shortcuts).length} shortcuts:`, shortcuts);
  } catch (error) {
    console.error('❌ AutoText: Error loading shortcuts:', error);
  }
}

// Listen for storage changes
chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && changes.shortcuts) {
    shortcuts = changes.shortcuts.newValue || {};
    console.log(`🔄 AutoText: Shortcuts updated! Now have ${Object.keys(shortcuts).length} shortcuts`);
  }
});

// Get text before cursor
function getTextBeforeCursor(element) {
  console.log('🔍 AutoText: Getting text before cursor in', element.tagName);

  if (element.tagName === "INPUT" || element.tagName === "TEXTAREA") {
    const cursorPos = element.selectionStart;
    const textBefore = element.value.substring(0, cursorPos);
    const match = textBefore.match(/(\S+)$/);
    const result = match ? match[1] : "";
    console.log(`   📝 Text before cursor: "${textBefore}" → Last word: "${result}"`);
    return result;
  }

  if (element.isContentEditable) {
    try {
      const selection = window.getSelection();
      if (!selection.rangeCount) {
        console.log('   ⚠️  No selection range');
        return "";
      }

      const range = selection.getRangeAt(0);
      const preCaretRange = range.cloneRange();
      preCaretRange.selectNodeContents(element);
      preCaretRange.setEnd(range.endContainer, range.endOffset);

      const textBefore = preCaretRange.toString();
      const match = textBefore.match(/(\S+)$/);
      const result = match ? match[1] : "";
      console.log(`   📝 Text before cursor: "${textBefore}" → Last word: "${result}"`);
      return result;
    } catch (error) {
      console.error('   ❌ Error getting text:', error);
      return "";
    }
  }

  console.log('   ⚠️  Element not supported');
  return "";
}

// Replace in text input
function replaceInTextInput(element, shortcutKey, expansion) {
  console.log(`🔧 Replacing in INPUT/TEXTAREA: "${shortcutKey}" → "${expansion}"`);

  const cursorPos = element.selectionStart;
  const textBefore = element.value.substring(0, cursorPos);
  const textAfter = element.value.substring(cursorPos);

  const newTextBefore = textBefore.slice(0, -shortcutKey.length) + expansion;
  element.value = newTextBefore + textAfter;

  const newCursorPos = newTextBefore.length;
  element.selectionStart = element.selectionEnd = newCursorPos;

  element.dispatchEvent(new Event('input', { bubbles: true }));

  console.log('✅ Replacement complete!');
}

// Replace in contenteditable
function replaceInContentEditable(element, shortcutKey, expansion, htmlExpansion) {
  console.log(`🔧 Replacing in CONTENTEDITABLE: "${shortcutKey}" → "${expansion}"`);
  console.log(`   HTML version: ${htmlExpansion || 'none'}`);

  try {
    const selection = window.getSelection();
    if (!selection.rangeCount) {
      console.log('   ⚠️  No selection range');
      return;
    }

    const range = selection.getRangeAt(0);

    // Delete the shortcut key
    range.setStart(range.endContainer, range.endOffset - shortcutKey.length);
    range.deleteContents();

    if (htmlExpansion) {
      const template = document.createElement('template');
      template.innerHTML = htmlExpansion;
      const fragment = template.content;

      range.insertNode(fragment);
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
    } else {
      const textNode = document.createTextNode(expansion);
      range.insertNode(textNode);
      range.setStartAfter(textNode);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
    }

    element.dispatchEvent(new Event('input', { bubbles: true }));
    console.log('✅ Replacement complete!');
  } catch (error) {
    console.error('❌ Error replacing:', error);
  }
}

// Main handler
function handleTabKey(event) {
  console.log(`⌨️  Key pressed: "${event.key}" (code: ${event.code})`);

  // Only handle Tab key
  if (event.key !== 'Tab') {
    return;
  }

  console.log('✅ TAB KEY DETECTED!');

  const element = event.target;
  console.log(`   Target element: ${element.tagName}, contentEditable: ${element.isContentEditable}`);

  // Only process in text input elements
  if (
    element.tagName !== "INPUT" &&
    element.tagName !== "TEXTAREA" &&
    !element.isContentEditable
  ) {
    console.log('   ⏭️  Not a text input element, skipping');
    return;
  }

  console.log('   ✅ Valid text input element');

  // Get the text before cursor
  const textBefore = getTextBeforeCursor(element);

  if (!textBefore) {
    console.log('   ⏭️  No text before cursor, skipping');
    return;
  }

  console.log(`   🔍 Checking if "${textBefore}" is a shortcut...`);
  console.log(`   Available shortcuts:`, Object.keys(shortcuts));

  // Check if it matches a shortcut
  const shortcut = shortcuts[textBefore];

  if (!shortcut) {
    console.log(`   ⏭️  "${textBefore}" is not a shortcut`);
    return;
  }

  console.log(`   🎯 MATCH FOUND! "${textBefore}" → "${shortcut.value}"`);

  // Prevent default Tab behavior
  event.preventDefault();
  event.stopPropagation();
  console.log('   🚫 Default Tab behavior prevented');

  // Replace based on element type
  if (element.tagName === "INPUT" || element.tagName === "TEXTAREA") {
    replaceInTextInput(element, textBefore, shortcut.value);
  } else if (element.isContentEditable) {
    replaceInContentEditable(
      element,
      textBefore,
      shortcut.value,
      shortcut.html_value
    );
  }

  console.log('🎉 AutoText expansion complete!');
}

// Listen for ALL keydown events (debug)
document.addEventListener("keydown", handleTabKey, true);

// Initialize
loadShortcuts();

console.log('%c✅ AutoText DEBUG: Ready! Available shortcuts will be listed above.', 'color: green; font-weight: bold');
console.log('%c💡 Try typing "b" then Tab in any text field', 'color: blue; font-style: italic');
