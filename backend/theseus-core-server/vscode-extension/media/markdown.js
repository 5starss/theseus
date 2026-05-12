(function () {
  'use strict';

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function renderMarkdown(text) {
    text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const id = 'cb' + Math.random().toString(36).slice(2);
      const escaped = escHtml(code.trimEnd());
      const label = lang || 'code';
      return (
        `<div class="code-block">` +
        `<div class="code-header"><span class="code-lang">${label}</span>` +
        `<button class="copy-btn" data-id="${id}">Copy</button></div>` +
        `<pre id="${id}"><code>${escaped}</code></pre></div>`
      );
    });
    text = text.replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>');
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\n/g, '<br>');
    return text;
  }

  window.TheseusMarkdown = {
    escHtml,
    renderMarkdown,
  };
}());
