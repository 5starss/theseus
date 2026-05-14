(function () {
  'use strict';

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function escAttr(s) {
    return escHtml(s).replace(/"/g, '&quot;');
  }

  function safeHttpUrl(url) {
    const value = String(url || '').trim();
    if (!/^https?:\/\//i.test(value)) return '';
    try {
      const parsed = new URL(value);
      return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : '';
    } catch {
      return '';
    }
  }

  function splitTrailingUrlPunctuation(url) {
    let value = String(url || '');
    let trailing = '';
    while (/[.,!?;:]$/.test(value)) {
      trailing = value.slice(-1) + trailing;
      value = value.slice(0, -1);
    }
    while (value.endsWith(')')) {
      const opens = (value.match(/\(/g) || []).length;
      const closes = (value.match(/\)/g) || []).length;
      if (closes <= opens) break;
      trailing = ')' + trailing;
      value = value.slice(0, -1);
    }
    return { url: value, trailing };
  }

  function linkHtml(url, label) {
    const safe = safeHttpUrl(url);
    if (!safe) return escHtml(label || url || '');
    return `<a class="external-link" href="${escAttr(safe)}" data-external-url="${escAttr(safe)}" title="${escAttr(safe)}">${escHtml(label || url)}</a>`;
  }

  function renderMarkdown(text) {
    const tokens = [];
    const token = html => {
      const key = `\u0000MD${tokens.length}\u0000`;
      tokens.push(html);
      return key;
    };

    text = String(text || '').replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const id = 'cb' + Math.random().toString(36).slice(2);
      const escaped = escHtml(code.trimEnd());
      const label = escHtml(lang || 'code');
      return token(
        `<div class="code-block">` +
        `<div class="code-header"><span class="code-lang">${label}</span>` +
        `<button class="copy-btn" data-id="${id}">Copy</button></div>` +
        `<pre id="${id}"><code>${escaped}</code></pre></div>`
      );
    });

    text = text.replace(/`([^`\n]+)`/g, (_, code) => token(`<code class="inline-code">${escHtml(code)}</code>`));

    text = text.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/gi, (_, label, url) => token(linkHtml(url, label)));

    text = text.replace(/https?:\/\/[^\s<]+/gi, (rawUrl) => {
      const { url, trailing } = splitTrailingUrlPunctuation(rawUrl);
      return token(linkHtml(url, url)) + trailing;
    });

    text = escHtml(text);
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\n/g, '<br>');
    text = text.replace(/\u0000MD(\d+)\u0000/g, (_, idx) => tokens[Number(idx)] || '');
    return text;
  }

  window.TheseusMarkdown = {
    escHtml,
    renderMarkdown,
  };
}());
