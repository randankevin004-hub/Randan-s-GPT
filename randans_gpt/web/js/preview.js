/* Live preview for AI-written web pages: sandboxed iframe + code view + console capture. */
(() => {
  const U = window.UI, $ = U.$, $$ = U.$$;
  const P = { doc: '', clean: '', open: false, errors: 0, logs: [] };

  // Runs inside the preview page: forwards console output and errors to the app.
  const CONSOLE = `<script>(function(){var s=function(t,a){try{parent.postMessage({__rg:1,t:t,m:a.map(function(x){try{return typeof x==='string'?x:JSON.stringify(x)}catch(e){return String(x)}}).join(' ')},'*')}catch(e){}};
['log','info','warn','error'].forEach(function(k){var o=console[k];console[k]=function(){s(k,[].slice.call(arguments));o&&o.apply(console,arguments)}});
addEventListener('error',function(e){s('error',[(e.error&&e.error.message?e.error.name+': '+e.error.message:e.message)+(e.lineno?' (line '+e.lineno+')':'')])});
addEventListener('unhandledrejection',function(e){s('error',['Unhandled promise rejection: '+((e.reason&&e.reason.message)||e.reason)])});})();<\/script>`;

  const kind = l => { l = (l || '').toLowerCase(); return /^(html?|xhtml)$/.test(l) ? 'html' : l === 'svg' ? 'svg' : /^(css|scss)$/.test(l) ? 'css' : /^(js|javascript|mjs)$/.test(l) ? 'js' : ''; };

  /* Pull html / css / js / svg code blocks out of a message. */
  function collect(text) {
    const out = { html: '', svg: '', css: [], js: [] };
    const re = /```[ \t]*([\w+#.-]*)[^\n]*\n([\s\S]*?)(?:```|$)/g;
    let m;
    while ((m = re.exec(text || ''))) {
      if (!m[0]) break;
      let k = kind(m[1]); const code = m[2];
      if (!k && /^\s*(<!doctype html|<html)/i.test(code)) k = 'html';
      if (k === 'html') out.html = code; else if (k === 'svg') out.svg = code; else if (k === 'css') out.css.push(code); else if (k === 'js') out.js.push(code);
    }
    return out;
  }
  const needsDom = js => /document\.|canvas|getElementById|querySelector|addEventListener/.test(js);
  const canPreview = text => { const p = collect(text); return !!(p.html || p.svg || (p.js.length && needsDom(p.js.join('\n')))); };

  const inject = (html, re, snippet, after) => {
    const m = html.match(re);
    if (!m) return after ? snippet + html : html + snippet;
    const at = after ? m.index + m[0].length : m.index;
    return html.slice(0, at) + snippet + html.slice(at);
  };

  /* Combine the blocks into one document. Returns {doc (with console hook), clean (for display/export)}. */
  function build(p) {
    let html = p.html;
    if (!html && p.svg) html = `<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#fff">${p.svg}</body></html>`;
    if (!html && p.js.length && needsDom(p.js.join('\n'))) html = '<!doctype html><html><head><meta charset="utf-8"><title>Preview</title></head><body></body></html>';
    if (!html) return null;
    if (!/<html[\s>]/i.test(html) && !/<!doctype/i.test(html))
      html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>${html}</body></html>`;
    const css = p.css.join('\n'), js = p.js.join('\n');
    if (css && !html.includes(css.slice(0, 40))) html = inject(html, /<\/head>/i, `<style>\n${css}\n</style>\n`);
    if (js && !html.includes(js.slice(0, 40))) html = inject(html, /<\/body>/i, `<script>\n${js}\n<\/script>\n`);
    return { clean: html, doc: inject(html, /<head[^>]*>/i, CONSOLE, true) };
  }

  /* ---------------------------------------------------------------- UI */
  function setTab(tab) {
    U.setSeg($('#pvTabs'), 'tab', tab);
    $$('.pv-pane').forEach(p => p.classList.toggle('on', p.dataset.pane === tab));
  }
  function setDevice(dev) { U.setSeg($('#pvDevices'), 'dev', dev); $('#pvDevice').className = 'pv-device ' + (dev === 'desktop' ? '' : dev); }
  function clearConsole() { P.errors = 0; P.logs = []; $('#pvBadge').hidden = true; $('#pvConsole').innerHTML = '<div class="empty">No console output yet.</div>'; }
  function addLog(t, m) {
    const box = $('#pvConsole'); if (!P.logs.length) box.innerHTML = '';
    P.logs.push({ t, m });
    const line = document.createElement('div'); line.className = 'pv-line ' + t; line.innerHTML = `<b>${t}</b><span></span>`; $('span', line).textContent = m; box.appendChild(line);
    if (t === 'error') { P.errors++; $('#pvBadge').hidden = false; $('#pvBadge').textContent = P.errors; }
  }
  function load() {
    clearConsole();
    $('#pvCode').innerHTML = MD.highlight(P.clean, 'html');
    $('#pvFrame').srcdoc = P.doc;
  }
  function show(text, { auto = false } = {}) {
    const built = build(collect(text));
    if (!built) { if (!auto) U.toast('Nothing to preview in this message.', true); return; }
    Object.assign(P, built, { open: true });
    $('#preview').hidden = false; $('#chatBody').classList.add('has-preview');
    U.S.previewOpen = true; U.syncShell();
    requestAnimationFrame(() => { setTab('preview'); setDevice('desktop'); });
    load();
  }
  function close() {
    if (!P.open) return;
    P.open = false; $('#preview').hidden = true; $('#preview').classList.remove('expanded');
    $('#chatBody').classList.remove('has-preview', 'preview-expanded');
    $('#pvFrame').srcdoc = ''; U.S.previewOpen = false; U.syncShell();
  }
  /* open by itself only when the AI wrote a proper page, not a small snippet */
  function autoOpen(text) {
    const p = collect(text);
    const pageLike = p.svg || /<html[\s>]|<body[\s>]|<!doctype/i.test(p.html) || p.html.split('\n').length >= 10 || (!p.html && p.js.length && needsDom(p.js.join('\n')));
    if (pageLike) show(text, { auto: true });
  }

  $('#pvTabs').addEventListener('click', e => { const b = e.target.closest('[data-tab]'); if (b) setTab(b.dataset.tab); });
  $('#pvDevices').addEventListener('click', e => { const b = e.target.closest('[data-dev]'); if (b) setDevice(b.dataset.dev); });
  $('#pvReload').onclick = () => { if (P.open) load(); };
  $('#pvClose').onclick = close;
  $('#pvExpand').onclick = () => {
    const on = $('#preview').classList.toggle('expanded'); $('#chatBody').classList.toggle('preview-expanded', on);
    $('#pvExpand').innerHTML = window.icon(on ? 'shrink' : 'expand'); requestAnimationFrame(() => { U.setSeg($('#pvTabs'), 'tab', ($('#pvTabs .on') || {}).dataset?.tab); });
  };
  $('#pvExternal').onclick = () => { if (P.open) U.api.open_preview_external(P.clean); };
  $('#pvSave').onclick = async () => { if (!P.open) return; const r = await U.api.save_text('page.html', P.clean); if (r.ok) U.toast('Saved to ' + r.path); else if (r.error) U.toast(r.error, true); };
  addEventListener('message', e => {
    const d = e.data; if (!d || !d.__rg || e.source !== $('#pvFrame').contentWindow) return;
    addLog(d.t, String(d.m).slice(0, 2000));
  });

  window.Preview = { canPreview, show, close, autoOpen, collect, build };
})();
