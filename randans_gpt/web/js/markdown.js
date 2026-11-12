/* Tiny, safe Markdown renderer + syntax highlighter (no dependencies).
   Everything is HTML-escaped first; only tags generated here ever reach the DOM. */
(function () {
  const esc = s => s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  /* ------------------------------- highlighter ------------------------------- */
  const WORDS = {
    py: 'and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield None True False self print',
    js: 'async await break case catch class const continue debugger default delete do else export extends finally for from function if import in instanceof let new of return static super switch this throw try typeof var void while with yield null true false undefined interface type enum implements public private protected readonly',
    c: 'auto break case char class const continue default do double else enum extern float for goto if inline int long namespace new nullptr operator private protected public register return short signed sizeof static struct switch template this throw try typedef union unsigned using virtual void volatile while bool true false null NULL string var fun val override final abstract interface package import fn let mut impl trait pub use mod match loop where func go defer chan select range',
    sql: 'select from where insert into values update set delete create table alter drop index join left right inner outer on group by order having limit offset as and or not null is in like distinct union all primary key foreign references default count sum avg min max case when then else end',
    sh: 'if then else elif fi for while do done case esac function in echo cd ls rm mv cp cat grep export source sudo pip npm git python node',
  };
  const ALIAS = { python: 'py', py: 'py', javascript: 'js', js: 'js', typescript: 'js', ts: 'js', jsx: 'js', tsx: 'js', json: 'js',
    java: 'c', c: 'c', cpp: 'c', 'c++': 'c', cs: 'c', csharp: 'c', kotlin: 'c', kt: 'c', go: 'c', rust: 'c', rs: 'c', swift: 'c', php: 'c', dart: 'c',
    sql: 'sql', bash: 'sh', sh: 'sh', shell: 'sh', zsh: 'sh', powershell: 'sh', ps1: 'sh', yaml: 'sh', yml: 'sh', ruby: 'sh', rb: 'sh', html: 'html', xml: 'html', css: 'css' };
  const SETS = {};
  for (const k in WORDS) SETS[k] = new Set(WORDS[k].split(' '));
  const COMMENT = { py: '#[^\\n]*', sh: '#[^\\n]*', sql: '--[^\\n]*', html: '<!--[\\s\\S]*?-->', css: '\\/\\*[\\s\\S]*?\\*\\/', c: '\\/\\/[^\\n]*|\\/\\*[\\s\\S]*?\\*\\/', js: '\\/\\/[^\\n]*|\\/\\*[\\s\\S]*?\\*\\/' };
  const RE = {};

  function highlight(code, lang) {
    const fam = ALIAS[(lang || '').toLowerCase()];
    if (!fam) return esc(code);
    if (!RE[fam]) RE[fam] = new RegExp(
      `(${COMMENT[fam]})|("(?:\\\\.|[^"\\\\\\n])*"|'(?:\\\\.|[^'\\\\\\n])*'|\`(?:\\\\.|[^\`\\\\])*\`)|(\\b0x[\\da-fA-F]+\\b|\\b\\d+(?:\\.\\d+)?\\b)|(@[A-Za-z_]\\w*)|(<\\/?[A-Za-z][\\w-]*)|([A-Za-z_$][\\w$]*)(\\s*\\()?`, 'g');
    const kw = SETS[fam] || new Set();
    const caseless = fam === 'sql';
    let out = '', last = 0, m;
    RE[fam].lastIndex = 0;
    while ((m = RE[fam].exec(code))) {
      out += esc(code.slice(last, m.index));
      last = RE[fam].lastIndex;
      const t = m[0];
      if (m[1]) out += `<span class="t-c">${esc(t)}</span>`;
      else if (m[2]) out += `<span class="t-s">${esc(t)}</span>`;
      else if (m[3]) out += `<span class="t-n">${esc(t)}</span>`;
      else if (m[4]) out += `<span class="t-d">${esc(t)}</span>`;
      else if (m[5]) out += fam === 'html' ? `<span class="t-k">${esc(t)}</span>` : esc(t);
      else {
        const word = m[6];
        if (kw.has(caseless ? word.toLowerCase() : word)) out += `<span class="t-k">${esc(word)}</span>${esc(m[7] || '')}`;
        else if (m[7]) out += `<span class="t-f">${esc(word)}</span>${esc(m[7])}`;
        else if (/^[A-Z][a-z]/.test(word)) out += `<span class="t-t">${esc(word)}</span>`;
        else out += esc(t);
      }
    }
    return out + esc(code.slice(last));
  }

  /* --------------------------------- inline --------------------------------- */
  function inline(s) {
    return s.split(/(`[^`\n]+`)/).map((p, i) => {
      if (i % 2) return `<code>${esc(p.slice(1, -1))}</code>`;
      return esc(p)
        .replace(/\*\*(?=\S)(.+?)(?<=\S)\*\*/g, '<strong>$1</strong>')
        .replace(/(^|[^*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?!\*)/g, '$1<em>$2</em>')
        .replace(/~~(.+?)~~/g, '<del>$1</del>')
        .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a data-href="$2">$1</a>');
    }).join('');
  }

  /* ---------------------------------- blocks --------------------------------- */
  function codeBlock(lang, code, pending) {
    const label = lang || 'code';
    const web = /^(html?|svg|xhtml)$/i.test(lang) || (!lang && /^\s*(<!doctype html|<html)/i.test(code));
    const preview = web && !pending ? `<button class="mini accent" data-preview-code>${window.icon('eye')}Preview</button>` : '';
    return `<div class="code"><div class="code-head"><span>${esc(label)}</span><span class="code-actions">${preview}<button class="mini" data-copy-code>${window.icon('copy')}Copy</button></span></div><pre><code>${highlight(code, lang)}</code></pre></div>`;
  }

  function blocks(text, streaming) {
    const lines = text.split('\n'), out = [];
    let i = 0;
    const special = l => /^\s*(```|#{1,4}\s|>|[-*+]\s+|\d+[.)]\s+|\|.*\|)/.test(l) || /^\s*([-*_])\1{2,}\s*$/.test(l);
    while (i < lines.length) {
      const line = lines[i];
      let m;
      if ((m = line.match(/^\s*```\s*([\w+#.-]*)/))) {
        const buf = []; i++;
        while (i < lines.length && !/^\s*```/.test(lines[i])) buf.push(lines[i++]);
        const closed = i < lines.length;
        i++;
        out.push(codeBlock(m[1], buf.join('\n'), streaming && !closed));
        continue;
      }
      if (!line.trim()) { i++; continue; }
      if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { out.push(`<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`); i++; continue; }
      if (/^\s*([-*_])\1{2,}\s*$/.test(line)) { out.push('<hr>'); i++; continue; }
      if (/^>\s?/.test(line)) {
        const buf = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, ''));
        out.push(`<blockquote>${blocks(buf.join('\n'), streaming)}</blockquote>`);
        continue;
      }
      if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
        const ordered = /^\s*\d+[.)]/.test(line), items = [];
        while (i < lines.length && /^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) {
          const mm = lines[i].match(/^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$/);
          items.push(`<li style="margin-left:${Math.min(3, Math.floor(mm[1].length / 2)) * 1.2}em">${inline(mm[2])}</li>`); i++;
        }
        out.push(`<${ordered ? 'ol' : 'ul'}>${items.join('')}</${ordered ? 'ol' : 'ul'}>`);
        continue;
      }
      if (/\|/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(lines[i + 1])) {
        const cells = r => r.trim().replace(/^\||\|$/g, '').split('|').map(c => inline(c.trim()));
        const head = cells(line); i += 2;
        const rows = [];
        while (i < lines.length && /\|/.test(lines[i]) && lines[i].trim()) rows.push(cells(lines[i++]));
        out.push(`<table><thead><tr>${head.map(c => `<th>${c}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`);
        continue;
      }
      if ((m = line.match(/^\*Using tool `([^`]+)`\.\.\.\*\s*$/))) { out.push(`<div class="toolnote">${window.icon('plug')}Using tool <b>${esc(m[1])}</b></div>`); i++; continue; }
      const buf = [line]; i++;
      while (i < lines.length && lines[i].trim() && !special(lines[i])) buf.push(lines[i++]);
      out.push(`<p>${buf.map(inline).join('<br>')}</p>`);
    }
    return out.join('');
  }

  /* Render a full message: handles <think>…</think> reasoning blocks (also unclosed while streaming). */
  function render(text, streaming) {
    let html = '', pos = 0, m;
    const re = /<think>([\s\S]*?)(<\/think>|$)/g;
    while ((m = re.exec(text))) {
      html += blocks(text.slice(pos, m.index), streaming);
      const done = !!m[2];
      html += `<details class="think"${done ? ' data-done' : ' open'}><summary>${done ? 'Thought process' : 'Thinking…'}</summary><div>${esc(m[1].trim())}</div></details>`;
      pos = m.index + m[0].length;
      if (!m[0].length) break;
    }
    return html + blocks(text.slice(pos), streaming);
  }

  window.MD = { render, esc, highlight };
})();
