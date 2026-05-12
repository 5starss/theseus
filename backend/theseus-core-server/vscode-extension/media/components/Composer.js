export function insertAtCursor(promptEl, text, resizeTextarea) {
  const pos = promptEl.selectionStart || 0;
  const val = promptEl.value || '';
  promptEl.value = val.slice(0, pos) + text + val.slice(pos);
  promptEl.selectionStart = promptEl.selectionEnd = pos + text.length;
  resizeTextarea();
  promptEl.focus();
}

export function insertMentionPath(promptEl, path, resizeTextarea) {
  insertAtCursor(
    promptEl,
    (promptEl.value && !/\s$/.test(promptEl.value) ? ' ' : '') + `@${path} `,
    resizeTextarea,
  );
}

export function bindImageAttachments({ promptEl, resizeTextarea, onSaveImage, onInsertMention }) {
  promptEl.addEventListener('paste', (event) => {
    const items = Array.from(event.clipboardData?.items || []);
    const image = items.find(item => item.type.startsWith('image/'));
    if (!image) return;
    event.preventDefault();
    const file = image.getAsFile();
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => onSaveImage(file.name || 'pasted-image.png', reader.result);
    reader.readAsDataURL(file);
  });

  promptEl.addEventListener('dragover', (event) => event.preventDefault());
  promptEl.addEventListener('drop', (event) => {
    event.preventDefault();
    const files = Array.from(event.dataTransfer?.files || []);
    files.forEach(file => {
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = () => onSaveImage(file.name || 'dropped-image.png', reader.result);
        reader.readAsDataURL(file);
      } else if (file.path) {
        onInsertMention(file.path.replace(/\\/g, '/'));
        resizeTextarea();
      }
    });
  });
}
