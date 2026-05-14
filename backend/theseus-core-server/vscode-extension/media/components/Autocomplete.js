const SLASH_COMMANDS = [
  { value: '/tools', description: 'Refresh and open Custom Tools', scope: 'local' },
  { value: '/tools custom', description: 'Show custom tool list', scope: 'local' },
  { value: '/session', description: 'Open session list', scope: 'local' },
  { value: '/sessions', description: 'Open session list', scope: 'local' },
  { value: '/session list', description: 'Refresh local sessions', scope: 'local' },
  { value: '/session new', description: 'Create a new session', scope: 'local' },
  { value: '/session delete', description: 'Delete a session by name', scope: 'local' },
  { value: '/clear', description: 'Clear visible chat history', scope: 'local' },
  { value: '/help', description: 'Show command help', scope: 'local' },
  { value: '/?', description: 'Show command help', scope: 'local' },
  { value: '/quit', description: 'Stop the runner', scope: 'local' },
  { value: '/exit', description: 'Stop the runner', scope: 'local' },
  { value: '/cost', description: 'Show runner token/cost stats', scope: 'runner required' },
  { value: '/stats', description: 'Show runner session stats', scope: 'runner required' },
  { value: '/validate', description: 'Validate custom tools in runner', scope: 'runner required' },
  { value: '/plan approve', description: 'Approve a pending plan', scope: 'plan review only' },
  { value: '/plan reject', description: 'Reject a pending plan', scope: 'plan review only' },
  { value: '/plan cancel', description: 'Cancel the current session plan', scope: 'runner required' },
  { value: '/plan clear', description: 'Cancel the current session plan', scope: 'runner required' },
  { value: '/plan delete', description: 'Delete the current session plan', scope: 'runner required' },
  { value: '/plan remove', description: 'Delete the current session plan', scope: 'runner required' },
  { value: '/agent', description: 'Use the mode selector to switch modes', scope: 'mode selector' },
  { value: '/ask', description: 'Use the mode selector to switch modes', scope: 'mode selector' },
  { value: '/plan', description: 'Use the mode selector to switch modes', scope: 'mode selector' },
  { value: '/coordinator', description: 'Use the mode selector to switch modes', scope: 'mode selector' },
];

export function getWordBefore(text, pos) {
  const before = text.slice(0, pos);
  const match = before.match(/@"[^"]*$/) || before.match(/[/@]\S*$/);
  return match ? match[0] : '';
}

export function mentionValue(file) {
  return /\s/.test(file) ? `@"${file}"` : '@' + file;
}

export function createAutocompleteController({
  promptEl,
  listEl,
  resizeTextarea,
  onMentionSearch,
}) {
  let items = [];
  let index = -1;
  let mode = null;

  function itemValue(item) {
    return typeof item === 'string' ? item : item.value;
  }

  function show(nextItems) {
    if (!nextItems.length) {
      close();
      return;
    }
    items = nextItems;
    index = -1;
    listEl.innerHTML = '';
    nextItems.forEach(item => {
      const li = document.createElement('li');
      if (typeof item === 'string') {
        li.textContent = item;
      } else {
        li.className = 'command-item';
        const label = document.createElement('strong');
        label.textContent = item.value;
        const detail = document.createElement('span');
        detail.textContent = item.description || '';
        const scope = document.createElement('small');
        scope.textContent = item.scope || '';
        li.append(label, detail, scope);
      }
      li.addEventListener('mousedown', (e) => {
        e.preventDefault();
        apply(itemValue(item));
      });
      listEl.appendChild(li);
    });
    listEl.hidden = false;
  }

  function close() {
    items = [];
    index = -1;
    mode = null;
    listEl.hidden = true;
    listEl.innerHTML = '';
  }

  function move(dir) {
    const listItems = listEl.querySelectorAll('li');
    if (!listItems.length) return;
    if (index >= 0) listItems[index].classList.remove('active');
    index = Math.max(0, Math.min(items.length - 1, index + dir));
    listItems[index].classList.add('active');
    listItems[index].scrollIntoView({ block: 'nearest' });
  }

  function apply(value) {
    const val = promptEl.value;
    const pos = promptEl.selectionStart;
    const before = val.slice(0, pos);
    const after = val.slice(pos);
    const replaced = before.replace(/@"[^"]*$|[/@]\S*$/, value + ' ');
    promptEl.value = replaced + after;
    promptEl.selectionStart = promptEl.selectionEnd = replaced.length;
    close();
    promptEl.focus();
    resizeTextarea();
  }

  function handleInput() {
    resizeTextarea();
    const val = promptEl.value;
    const pos = promptEl.selectionStart;
    const word = getWordBefore(val, pos);

    if (word.startsWith('/') && word.length >= 1) {
      mode = 'slash';
      const q = word.slice(1).toLowerCase();
      show(SLASH_COMMANDS.filter(c => c.value.slice(1).includes(q) || c.description.toLowerCase().includes(q)));
      return;
    }
    if (word.startsWith('@') && word.length >= 1) {
      mode = 'at';
      onMentionSearch(word.slice(1));
      return;
    }
    close();
  }

  function handleKeydown(event) {
    if (!items.length) return false;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      move(1);
      return true;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      move(-1);
      return true;
    }
    if (event.key === 'Tab') {
      event.preventDefault();
      apply(itemValue(items[index >= 0 ? index : 0]));
      return true;
    }
    if (event.key === 'Enter' && index >= 0) {
      event.preventDefault();
      apply(itemValue(items[index]));
      return true;
    }
    if (event.key === 'Escape') {
      close();
      return true;
    }
    return false;
  }

  return {
    show,
    close,
    handleInput,
    handleKeydown,
    mentionValue,
    get mode() { return mode; },
    get items() { return [...items]; },
  };
}
