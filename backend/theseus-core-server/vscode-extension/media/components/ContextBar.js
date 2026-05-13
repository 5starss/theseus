const MENTION_RE = /@(?:"([^"]+)"|([^\s]+))/g;

export function parseMentionPills(text) {
  const pills = [];
  const seen = new Set();
  for (const match of text.matchAll(MENTION_RE)) {
    const value = match[1] || match[2] || '';
    if (!value || seen.has(value)) continue;
    seen.add(value);
    pills.push({ id: `mention:${value}`, type: 'mention', label: `@ ${value}`, value });
  }
  return pills;
}

export function removeMentionFromText(text, value) {
  if (!value) return text;
  const escaped = value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return text
    .replace(new RegExp(`@"${escaped}"\\s*`, 'g'), '')
    .replace(new RegExp(`@${escaped}\\s*`, 'g'), '')
    .trimStart();
}

export function renderContextBar({
  containerEl,
  session,
  activeFile,
  activeFileSuppressed,
  promptText,
  onRemoveActiveFile,
  onRemoveMention,
}) {
  if (!containerEl) return;
  containerEl.innerHTML = '';
  const pills = [];
  if (session) pills.push({ id: 'session', type: 'session', label: `session ${session}`, fixed: true });
  if (activeFile && !activeFileSuppressed) {
    const line = Number.isInteger(activeFile.line) ? `:${activeFile.line}` : '';
    pills.push({ id: 'active-file', type: 'active-file', label: `active ${activeFile.file}${line}` });
  }
  pills.push(...parseMentionPills(promptText || ''));

  containerEl.hidden = !pills.length;
  pills.forEach(pill => {
    const el = document.createElement('span');
    el.className = `context-pill ${pill.type}`;
    const label = document.createElement('span');
    label.textContent = pill.label;
    el.appendChild(label);
    if (!pill.fixed) {
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = '×';
      remove.title = `Remove ${pill.label}`;
      remove.addEventListener('click', () => {
        if (pill.type === 'active-file') onRemoveActiveFile?.();
        if (pill.type === 'mention') onRemoveMention?.(pill.value);
      });
      el.appendChild(remove);
    }
    containerEl.appendChild(el);
  });
}
