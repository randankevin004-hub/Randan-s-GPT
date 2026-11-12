/* Randan's GPT - front-end controller. Talks to Python via window.pywebview.api (no web server). */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = MD.esc;
  const api = new Proxy({}, { get: (_, name) => (...a) => window.pywebview.api[name](...a) });
  const ICON_MAP = { grid: 'percent' };
  const S = {
    app: {}, settings: {}, models: [], chats: [], tools: [], moreTools: [], templates: [],
    chatId: null, messages: [], page: 'chat', model: 'auto', tool: null, reasoning: false, research: false, toolsOn: false,
    attach: null, gen: null, buffer: '', live: null, liveLabel: '', early: [], timer: null, online: null, installed: [],
    notes: [], avatar: '', pop: null, mcp: [], mcpBusy: false,
    raw: new WeakMap(), auth: {}, useCases: [], previewOpen: false, built: false, entered: false,
  };

  /* ------------------------------------------------------------ helpers */
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const labelOf = tag => (S.models.find(m => m.tag === tag) || { label: tag }).label;
  const initial = () => (S.settings.user_name || '?').trim().charAt(0).toUpperCase();
  const ic = n => window.icon(ICON_MAP[n] || n);

  function toast(text, err = false) {
    const t = document.createElement('div');
    t.className = 'toast' + (err ? ' err' : ''); t.textContent = text;
    $('#toasts').appendChild(t); setTimeout(() => t.remove(), 3300);
  }
  function hint(text, err = false) { const h = $('#hint'); h.textContent = text || ''; h.classList.toggle('err', !!err); }
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch (e) { /* fall back */ }
    const ta = document.createElement('textarea'); ta.value = text; ta.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(ta); ta.select();
    let ok = false; try { ok = document.execCommand('copy'); } catch (e) { /* ignore */ }
    ta.remove(); return ok;
  }

  /* ------------------------------------------------------- segmented control */
  function setSeg(seg, attr, value) {
    if (!seg) return;
    let active = null;
    $$('button', seg).forEach(b => { const on = b.dataset[attr] === value; b.classList.toggle('on', on); if (on) active = b; });
    const ind = $('.seg-ind', seg);
    if (!active) { ind.style.width = '0'; return; }
    ind.style.left = active.offsetLeft + 'px'; ind.style.width = active.offsetWidth + 'px';
  }
  const syncSegs = () => { setSeg($('#nav'), 'page', ['dashboard', 'chat', 'help', 'account'].includes(S.page) ? S.page : null);
    setSeg($('#themeSeg'), 'themeBtn', S.settings.theme); setSeg($('#setTheme'), 'themeBtn', S.settings.theme); };

  /* ---------------------------------------------------------------- overlays */
  function closePopover() { if (S.pop) { S.pop.remove(); S.pop = null; } }
  function openPopover(anchor, content, { align = 'left', side = 'below', width } = {}) {
    closePopover();
    const pop = document.createElement('div'); pop.className = 'popover';
    if (width) pop.style.width = width + 'px';
    pop.appendChild(content); $('#layer').appendChild(pop);
    const r = anchor.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
    let left, top, origin;
    if (side === 'right') { left = r.right + 12; top = r.top; origin = 'left top'; }
    else {
      left = align === 'right' ? r.right - w : r.left; top = r.bottom + 10; origin = (align === 'right' ? 'top right' : 'top left');
      if (top + h > innerHeight - 10) { top = r.top - h - 10; origin = origin.replace('top', 'bottom'); }
    }
    left = Math.max(10, Math.min(left, innerWidth - w - 10)); top = Math.max(10, Math.min(top, innerHeight - h - 10));
    pop.style.cssText += `left:${left}px;top:${top}px;--ox:${origin}`;
    S.pop = pop; S.popAnchor = anchor; return pop;
  }
  function menu(items) {
    const box = document.createElement('div');
    items.forEach(it => {
      if (it.sep) { const s = document.createElement('div'); s.className = 'menu-sep'; box.appendChild(s); return; }
      const b = document.createElement('button');
      b.className = 'menu-item' + (it.danger ? ' danger' : '') + (it.checked ? ' checked' : '');
      b.innerHTML = (it.icon ? ic(it.icon) : '') + `<span>${esc(it.label)}</span>` + (it.checked ? `<span class="tick">${window.icon('check')}</span>` : '');
      b.onclick = () => { closePopover(); it.onClick && it.onClick(); };
      box.appendChild(b);
    });
    return box;
  }
  document.addEventListener('pointerdown', e => { if (S.pop && !S.pop.contains(e.target) && !S.popAnchor.contains(e.target)) closePopover(); }, true);

  /* modal: returns a promise of {value, fields} */
  function modal({ title, text = '', fields = [], pre = '', tool = '', actions }) {
    return new Promise(resolve => {
      closePopover();
      const back = document.createElement('div'); back.className = 'backdrop';
      back.innerHTML = `<div class="modal" role="dialog" aria-modal="true"><h3>${esc(title)}</h3>${text ? `<p>${esc(text)}</p>` : ''}
        ${tool ? `<div class="tool-name">${window.icon('plug')}${esc(tool)}</div>` : ''}${pre ? `<pre>${esc(pre)}</pre>` : ''}
        ${fields.map(f => `<label>${esc(f.label)}<input data-f="${f.id}" value="${esc(f.value || '')}" placeholder="${esc(f.placeholder || '')}" autocomplete="off"></label>`).join('')}
        <div class="actions"></div></div>`;
      const done = value => { back.remove(); document.removeEventListener('keydown', onKey, true);
        resolve({ value, fields: Object.fromEntries($$('input', back).map(i => [i.dataset.f, i.value])) }); };
      const onKey = e => { if (e.key === 'Escape') { e.stopPropagation(); done(null); } else if (e.key === 'Enter' && fields.length) { e.preventDefault(); done(actions.find(a => a.primary).value); } };
      actions.forEach(a => { const b = document.createElement('button'); b.className = 'btn' + (a.primary ? ' primary' : '') + (a.danger ? ' danger-text' : '');
        b.textContent = a.label; b.onclick = () => done(a.value); $('.actions', back).appendChild(b); });
      document.addEventListener('keydown', onKey, true); $('#layer').appendChild(back);
      const first = $('input', back); (first || $('.btn.primary', back) || $('.btn', back)).focus();
    });
  }

  /* ------------------------------------------------------------ appearance */
  function applySettings() {
    const s = S.settings, root = document.documentElement;
    root.dataset.theme = s.theme.toLowerCase(); root.dataset.fx = s.reduce_effects ? 'low' : '';
    root.style.setProperty('--chat-size', s.font_size + 'px');
    $('#fontVal').textContent = s.font_size; syncSegs();
  }
  async function setSetting(key, value) {
    const r = await api.set_setting(key, value);
    if (r && r.settings) S.settings = r.settings;
    applySettings();
  }
  function renderAvatar() {
    const html = S.avatar ? `<img alt="" src="${S.avatar}">` : esc(initial());
    $('#btnAvatar').innerHTML = html; $('#accAvatar').innerHTML = html;
  }

  /* ---------------------------------------------------------------- pages */
  function showPage(name) {
    closePopover(); S.page = name;
    $$('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + name));
    syncShell();
    syncSegs();
    ({ dashboard: loadDashboard, account: loadAccount, settings: loadSettings, tools: loadTools, chat: () => $('#input').focus() }[name] || (() => {}))();
  }

  function syncShell() { $('#shell').classList.toggle('no-history', !(S.page === 'chat' && S.settings.show_history && !S.previewOpen)); }

  /* ------------------------------------------------------------------ chat */
  const inner = () => $('.messages-inner');
  const nearBottom = () => { const b = $('#messages'); return b.scrollHeight - b.scrollTop - b.clientHeight < 140; };
  const scrollBottom = () => { const b = $('#messages'); b.scrollTo({ top: b.scrollHeight, behavior: 'auto' }); };
  const setWelcome = on => $('#chatCol').classList.toggle('is-welcome', on);
  function greeting() {
    const h = new Date().getHours();
    return `${h < 12 ? 'Good Morning' : h < 17 ? 'Good Afternoon' : 'Good Evening'}, ${S.settings.user_name}! How can I assist you?`;
  }

  function addMsg(m, { typing = false } = {}) {
    const el = document.createElement('div'); el.className = 'msg ' + m.role; if (m.id) el.dataset.id = m.id;
    const orb = m.role === 'assistant' ? '<span class="avatar orb xs"><svg class="orb-ring r1" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46"/></svg><i class="orb-core"></i></span>' : '';
    const label = m.role === 'assistant' ? esc(m.label || m.model || '') : '';
    const meta = m.role === 'error' ? '' : `<div class="meta">${label ? `<span>${label}</span>` : ''}<button class="mini" data-copy-msg>${window.icon('copy')}Copy</button></div>`;
    el.innerHTML = `${orb}<div class="msg-main"><div class="bubble md"></div>${meta}</div>`;
    const bubble = $('.bubble', el);
    if (typing) bubble.innerHTML = '<div class="typing"><i></i><i></i><i></i></div>';
    else if (m.role === 'user') bubble.textContent = m.content;
    else if (m.role === 'error') bubble.innerHTML = MD.render('⚠  ' + m.content);
    else bubble.innerHTML = MD.render(m.content);
    inner().appendChild(el); S.raw.set(el, m.content || '');
    if (m.role === 'assistant' && !typing) decorateMsg(el, m.content);
    if (m.role !== 'error' && !typing) S.messages.push({ role: m.role, content: m.content });
    return { el, bubble };
  }
  /* add a Preview button to messages that contain web code */
  function decorateMsg(el, text) {
    const meta = $('.meta', el); if (!meta || $('[data-preview-msg]', meta) || !window.Preview || !Preview.canPreview(text)) return;
    const b = document.createElement('button'); b.className = 'mini accent'; b.dataset.previewMsg = '1'; b.innerHTML = window.icon('eye') + 'Preview';
    meta.insertBefore(b, $('[data-copy-msg]', meta));
  }
  function clearMessages() { inner().innerHTML = ''; S.messages = []; }

  function newChat() {
    if (S.gen) return hint('Please wait for the current reply to finish, or press Stop.');
    if (window.Preview) Preview.close(); S.chatId = null; clearMessages(); setWelcome(true); $('#greeting').textContent = greeting(); hint('');
    renderHistory(); showPage('chat');
  }
  async function openChat(id) {
    if (S.gen) return hint('Please wait for the current reply to finish, or press Stop.');
    const r = await api.open_chat(id); if (r.error) return toast(r.error, true);
    if (window.Preview) Preview.close(); S.chatId = id; clearMessages(); hint('');
    r.messages.forEach(m => addMsg(m)); setWelcome(!r.messages.length);
    renderHistory(); showPage('chat'); requestAnimationFrame(scrollBottom);
  }

  function setSending(busy) {
    const b = $('#btnSend'); b.classList.toggle('stop', busy);
    b.innerHTML = window.icon(busy ? 'stop' : 'arrowup'); b.setAttribute('aria-label', busy ? 'Stop' : 'Send');
  }
  async function send() {
    if (S.gen) return stop();
    const input = $('#input'), text = input.value.trim();
    if (!text && !S.attach) { hint('Please type a message before sending.', true); input.focus(); return; }
    const payload = { chat_id: S.chatId, text, attachment: S.attach,
      options: { model: S.model, tool: S.tool, reasoning: S.reasoning, research: S.research, tools: S.toolsOn } };
    input.value = ''; autosize(); clearAttach(); hint(''); setWelcome(false);
    S.early = []; S.gen = -1;                              // reserve: block double sends while waiting
    let r;
    try { r = await api.send(payload); } catch (e) { S.gen = null; return toast('Could not send: ' + e, true); }
    if (r.error) { S.gen = null; hint(r.error, true); if (!S.messages.length) setWelcome(true); return; }
    S.chatId = r.chat_id; if (r.chats) { S.chats = r.chats; renderHistory(); }
    addMsg(r.user);
    if (r.assistant) { S.gen = null; addMsg(r.assistant); scrollBottom(); return; }
    S.liveLabel = r.modelLabel; S.buffer = '';
    S.live = addMsg({ role: 'assistant', content: '', label: r.modelLabel, id: 'live' }, { typing: true });
    S.gen = r.gen; setSending(true); updateModelLabel(); scrollBottom();
    const early = S.early; S.early = []; early.forEach(ev => App.event(ev));   // events that outran the reply
  }
  async function stop() { if (S.gen && S.gen > 0) await api.stop(); }

  function renderLive() {
    S.timer = null; if (!S.live) return;
    const follow = nearBottom();
    S.live.bubble.innerHTML = MD.render(S.buffer, true); S.raw.set(S.live.el, S.buffer);
    if (follow) scrollBottom();
  }
  function finishGen(ev) {
    clearTimeout(S.timer); S.timer = null;
    const live = S.live; S.gen = null; S.live = null;
    if (live) {
      if (ev.message) {
        live.bubble.innerHTML = MD.render(ev.message.content); live.el.dataset.id = ev.message.id;
        S.raw.set(live.el, ev.message.content); decorateMsg(live.el, ev.message.content);
        if (S.settings.auto_preview && window.Preview) Preview.autoOpen(ev.message.content);
        S.messages.push({ role: 'assistant', content: ev.message.content });
      } else live.el.remove();
    }
    if (ev.error) addMsg({ role: 'error', content: ev.error });
    else if (!ev.message) hint('The model returned an empty response. Try again.', true);
    if (ev.chats) { S.chats = ev.chats; renderHistory(); }
    setSending(false); updateModelLabel(); scrollBottom(); checkStatus(); $('#input').focus();
  }

  const App = window.App = {
    event(ev) {
      const mine = () => { if (S.gen === ev.gen) return true; if (S.gen === -1) S.early.push(ev); return false; };
      switch (ev.type) {
        case 'token': if (!mine()) return; S.buffer += ev.text; if (!S.timer) S.timer = setTimeout(renderLive, 60); break;
        case 'done': if (!mine()) return; finishGen(ev); break;
        case 'info': hint(ev.text); break;
        case 'pull': window.Onboard && Onboard.onPull(ev); break;
        case 'pull_done': window.Onboard && Onboard.onPullDone(ev); break;
        case 'auth_lost': toast('Your session expired. Please sign in again.', true); signedOut(); break;
        case 'approve': showApproval(ev); break;
        case 'mcp': S.mcpBusy = ev.busy; if (ev.message) $('#mcpMsg').textContent = ev.message;
          else if (!ev.busy) { $('#mcpMsg').textContent = ''; if (S.toolsOn) hint('Tools ready - the model can use your tool servers.'); }
          refreshMcp(); break;
      }
    },
  };

  async function showApproval(ev) {
    const r = await modal({ title: 'Allow this tool?', text: 'The model wants to run:', tool: ev.tool, pre: ev.args,
      actions: [{ label: 'Deny', value: false }, { label: 'Allow', value: true, primary: true }] });
    api.approve(ev.id, r.value === true);
  }

  /* --------------------------------------------------------------- composer */
  function autosize() { const i = $('#input'); i.style.height = 'auto'; i.style.height = Math.min(i.scrollHeight, 200) + 'px'; }
  function clearAttach() { S.attach = null; $('#attachRow').hidden = true; $('#attachRow').innerHTML = ''; }
  function renderAttach() {
    const row = $('#attachRow'); row.hidden = !S.attach; if (!S.attach) return;
    row.innerHTML = `<span class="file-chip">${window.icon('paperclip')}${esc(S.attach.name)}<button aria-label="Remove attachment">${window.icon('x')}</button></span>`;
    $('button', row).onclick = () => { clearAttach(); hint(''); };
  }
  function setToggle(btn, on) { btn.setAttribute('aria-pressed', on ? 'true' : 'false'); }
  function updateModelLabel() {
    let t;
    if (S.gen && S.liveLabel) t = S.model === 'auto' && !S.reasoning ? `Auto → ${S.liveLabel}` : S.liveLabel;
    else if (S.reasoning) t = labelOf(S.app.reasoningModel) + ' (Reasoning)';
    else t = S.model === 'auto' ? 'Auto' : labelOf(S.model);
    $('#modelLabel').textContent = t;
    const tool = S.tools.concat(S.moreTools).find(x => x.key === S.tool);
    const chip = $('#modeChip'); chip.hidden = !tool; if (tool) chip.innerHTML = `${esc(tool.label)} ${window.icon('x')}`;
    $$('#railTools .icon-btn').forEach(b => b.classList.toggle('on', b.dataset.key === S.tool));
  }
  function selectModel(tag) { S.model = tag; S.reasoning = false; setToggle($('#btnReason'), false); updateModelLabel(); }
  function selectTool(key) {
    const t = S.tools.concat(S.moreTools).find(x => x.key === key);
    if (!t || key === S.tool) { S.tool = null; hint(''); }
    else { S.tool = key; S.model = t.model; S.reasoning = false; setToggle($('#btnReason'), false); hint(`${t.label} mode on - using ${t.modelLabel}.`); }
    updateModelLabel(); showPage('chat');
  }

  function buildRail() {
    const rail = $('#railTools'); rail.innerHTML = '';
    S.tools.forEach(t => {
      const b = document.createElement('button'); b.className = 'icon-btn'; b.dataset.key = t.key; b.dataset.tip = t.label; b.dataset.tipPos = 'right';
      b.setAttribute('aria-label', t.label); b.innerHTML = ic(t.icon); b.onclick = () => selectTool(t.key); rail.appendChild(b);
    });
    const more = document.createElement('button'); more.className = 'icon-btn'; more.dataset.tip = 'More tools'; more.dataset.tipPos = 'right'; more.setAttribute('aria-label', 'More tools');
    more.innerHTML = window.icon('chevron');
    more.onclick = () => openPopover(more, menu(S.moreTools.map(t => ({ label: t.label, icon: t.icon, checked: t.key === S.tool, onClick: () => selectTool(t.key) }))), { side: 'right' });
    rail.appendChild(more);
  }
  function buildStarters() {
    const items = [['Explain a concept simply', 'Explain this simply, with an example: '], ['Write a Python function', 'Write a Python function that '],
      ['Draft a professional email', 'Write a professional email about: '], ['Brainstorm ideas', 'Give me 10 creative ideas for: ']];
    $('#starters').innerHTML = '';
    items.forEach(([label, text]) => { const b = document.createElement('button'); b.className = 'starter'; b.textContent = label;
      b.onclick = () => { $('#input').value = text; autosize(); $('#input').focus(); }; $('#starters').appendChild(b); });
  }

  /* ---------------------------------------------------------------- history */
  function groupLabel(updated) {
    const d = new Date(updated.replace(' ', 'T')), n = new Date();
    const days = Math.round((new Date(n.getFullYear(), n.getMonth(), n.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 864e5);
    return days <= 0 ? 'Today' : days === 1 ? 'Yesterday' : days < 30 ? `${days} Days Ago` : 'Older';
  }
  function renderHistory() {
    const list = $('#historyList'); list.innerHTML = '';
    if (!S.chats.length) { list.innerHTML = '<div class="empty">No chats yet.<br>Start a conversation!</div>'; return; }
    let last = '';
    S.chats.forEach((c, i) => {
      const g = groupLabel(c.updated);
      if (g !== last) { const h = document.createElement('div'); h.className = 'h-group'; h.textContent = g; list.appendChild(h); last = g; }
      const b = document.createElement('div'); b.className = 'h-item' + (c.id === S.chatId ? ' active' : ''); b.tabIndex = 0; b.setAttribute('role', 'button');
      b.style.animationDelay = Math.min(i, 12) * 25 + 'ms';
      b.innerHTML = `<span class="ico">${window.icon('chat')}</span><span class="t">${esc(c.title)}</span><button class="more" aria-label="Chat options">${window.icon('dots')}</button>`;
      b.onclick = e => { if (e.target.closest('.more')) return; openChat(c.id); };
      b.onkeydown = e => { if (e.key === 'Enter') openChat(c.id); };
      const more = $('.more', b);
      more.onclick = e => { e.stopPropagation(); openPopover(more, menu(chatMenu(c)), { align: 'right' }); };
      b.oncontextmenu = e => { e.preventDefault(); openPopover(more, menu(chatMenu(c)), { align: 'right' }); };
      list.appendChild(b);
    });
  }
  const chatMenu = c => [{ label: 'Rename', icon: 'pen', onClick: () => renameChat(c) }, { label: 'Delete', icon: 'trash', danger: true, onClick: () => deleteChat(c) }];
  async function renameChat(c) {
    const r = await modal({ title: 'Rename chat', fields: [{ id: 'title', label: 'Title', value: c.title }], actions: [{ label: 'Cancel', value: null }, { label: 'Save', value: true, primary: true }] });
    if (r.value) { S.chats = await api.rename_chat(c.id, r.fields.title); renderHistory(); }
  }
  async function deleteChat(c) {
    if (S.gen) return hint('Please wait for the current reply to finish, or press Stop.');
    const r = await modal({ title: 'Delete this chat?', text: `"${c.title}" will be removed permanently.`, actions: [{ label: 'Cancel', value: null }, { label: 'Delete', value: true, primary: true }] });
    if (!r.value) return;
    S.chats = await api.delete_chat(c.id);
    if (c.id === S.chatId) newChat(); else renderHistory();
  }
  function chatOptions() {
    const items = [{ label: 'New chat', icon: 'plus', onClick: newChat },
      { label: 'Export as TXT', icon: 'download', onClick: () => exportChat('TXT') }, { label: 'Export as PDF', icon: 'download', onClick: () => exportChat('PDF') },
      { label: 'Copy conversation', icon: 'copy', onClick: async () => { if (!S.messages.length) return toast('Nothing to copy yet.', true);
        await copyText(S.messages.map(m => `${m.role === 'user' ? 'You' : "Randan's GPT"}: ${m.content.replace(/<think>[\s\S]*?(<\/think>|$)/g, '').trim()}`).join('\n\n')); toast('Conversation copied'); } }];
    const c = S.chats.find(x => x.id === S.chatId);
    if (c) items.push({ sep: true }, { label: 'Rename chat', icon: 'pen', onClick: () => renameChat(c) }, { label: 'Delete chat', icon: 'trash', danger: true, onClick: () => deleteChat(c) });
    return menu(items);
  }
  async function exportChat(kind) {
    if (!S.chatId) return toast('Nothing to export yet - start a chat first.', true);
    const r = await api.export_chat(S.chatId, kind);
    if (r.error) toast(r.error, true); else if (r.ok) toast('Exported to ' + r.path);
  }

  /* ----------------------------------------------------------- notifications */
  function notify(title, body, link = '') {
    S.notes.unshift({ title, body, link, time: new Date().toTimeString().slice(0, 5), read: false }); S.notes = S.notes.slice(0, 30);
    $('#bellDot').hidden = false;
  }
  function showNotes() {
    const box = document.createElement('div'); box.style.width = '320px';
    box.innerHTML = `<div class="pop-title"><span>Notifications</span><button class="mini" id="clearNotes">Clear</button></div>` +
      (S.notes.length ? S.notes.slice(0, 8).map((n, i) => `<div class="note-card${n.read ? '' : ' unread'}"><b>${esc(n.title)}<em>${n.time}</em></b><p>${esc(n.body)}</p>${n.link ? `<button class="link" data-note-link="${i}">View release</button>` : ''}</div>`).join('')
        : '<div class="empty" style="padding:24px">You\'re all caught up.</div>');
    openPopover($('#btnBell'), box, { align: 'right' });
    $('#clearNotes', box).onclick = () => { S.notes = []; closePopover(); };
    $$('[data-note-link]', box).forEach(b => {
      const note = S.notes[+b.dataset.noteLink];
      b.onclick = () => api.open_url(note.link);
    });
    S.notes.forEach(n => n.read = true); $('#bellDot').hidden = true;
  }

  async function checkForUpdates(manual = false) {
    const status = $('#updateStatus');
    if (status) status.textContent = 'Checking GitHub Releases…';
    const result = await api.check_updates();
    if (!result.ok) {
      if (status) status.textContent = result.error;
      if (manual) toast(result.error, true);
      return;
    }
    if (status) status.textContent = `Current: ${result.current}${result.available ? ` · Version ${result.latest} is available` : ' · You’re up to date'}`;
    if (result.available) notify('Update available', `Randan’s GPT ${result.latest} is ready to download.`, result.url);
    else if (manual) toast('You’re using the latest version.');
  }

  /* ---------------------------------------------------------------- status */
  async function checkStatus() {
    let r; try { r = await api.check_ollama(); } catch (e) { return; }
    if (r.online !== S.online) {
      if (S.online !== null || !r.online) notify(r.online ? 'Ollama is online' : 'Ollama is offline', r.online ? 'Connected to your local Ollama server.' : 'Start the Ollama app (or run `ollama serve`) to chat.');
      S.online = r.online;
    }
    S.installed = r.installed;
    if (JSON.stringify(r.missing) !== S.missingKey && r.missing.length) { notify('Models not installed', 'Run `ollama pull <name>` for: ' + r.missing.join(', ')); }
    S.missingKey = JSON.stringify(r.missing);
    if (JSON.stringify(r.models) !== JSON.stringify(S.models)) { S.models = r.models; fillModelSelect(); updateModelLabel(); }
    $('#ollamaState').textContent = `Ollama is ${r.online ? 'online' : 'offline - start the Ollama app'}.  Installed models: ${r.installed.join(', ') || 'none detected'}`;
  }
  function fillModelSelect() {
    const sel = $('#setDefaultModel'); sel.innerHTML = S.models.map(m => `<option value="${esc(m.tag)}">${esc(m.label)}</option>`).join('');
    sel.value = S.settings.default_model;
  }

  /* -------------------------------------------------------------- dashboard */
  function countUp(el, to) {
    const t0 = performance.now(), dur = 700;
    const step = t => { const k = Math.min(1, (t - t0) / dur); el.textContent = Math.round(to * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }
  async function loadDashboard() {
    const s = await api.stats();
    $('#dashSub').textContent = `Welcome back, ${S.settings.user_name}. Here's your activity.`;
    const cards = [['chat', 'Chats', s.chats], ['user', 'Questions asked', s.questions], ['lines', 'Total messages', s.messages], ['note', 'Memories', s.memories]];
    $('#statCards').innerHTML = cards.map(([i, l, v], n) => `<div class="stat" style="animation-delay:${n * 70}ms"><span class="ico">${window.icon(i)}</span><b data-v="${v}">0</b><span>${l}</span></div>`).join('');
    $$('#statCards b').forEach(b => countUp(b, +b.dataset.v));
    const top = Math.max(1, ...s.daily.map(d => d.count));
    $('#weekChart').innerHTML = s.daily.map((d, n) => `<div class="bar">${d.count ? `<em>${d.count}</em>` : ''}<i class="${d.count ? '' : 'zero'}" style="height:${d.count ? Math.max(8, d.count / top * 100) : 3}%;animation-delay:${n * 60}ms"></i><span>${d.label}</span></div>`).join('');
    const total = Math.max(1, s.models.reduce((a, m) => a + m.count, 0));
    $('#modelBars').innerHTML = s.models.length ? s.models.map((m, n) => `<div class="hbar"><div class="lbl"><span>${esc(m.label)}</span><b>${m.count}</b></div><div class="track"><div class="fill" style="width:${m.count / total * 100}%;animation-delay:${n * 80}ms"></div></div></div>`).join('')
      : '<div class="empty">No answers yet - ask something!</div>';
    checkStatus();
  }

  /* ---------------------------------------------------------------- account */
  function updateAccountUi() {
    const u = S.auth && S.auth.user;
    $('#accEmail').textContent = u ? u.email + (S.auth.offline ? '  ·  offline' : '') : 'Local profile · not signed in';
    $('#btnLogout2').textContent = S.auth && S.auth.signedIn ? 'Sign out' : 'Quit';
    $('#btnAvatar').dataset.tip = u ? `${S.settings.user_name} · ${u.email}` : 'Profile';
  }
  async function loadAccount() {
    updateAccountUi();
    const s = await api.stats(); renderAvatar();
    $('#accName').value = S.settings.user_name;
    $('#accStats').innerHTML = `Member since ${esc(S.settings.member_since)}<br>${s.chats} chats · ${s.questions} questions · ${s.memories} memories`;
  }

  /* --------------------------------------------------------------- settings */
  async function loadSettings() {
    const s = S.settings;
    fillModelSelect();
    [['#setAuto', s.auto_mode], ['#setPreview', s.auto_preview], ['#setMemory', s.memory_enabled], ['#setEffects', s.reduce_effects], ['#setConfirm', s.mcp_confirm]].forEach(([id, on]) => $(id).setAttribute('aria-checked', on ? 'true' : 'false'));
    $('#fontVal').textContent = s.font_size; syncSegs();
    const names = (S.useCases || []).filter(u => (s.use_cases || []).includes(u.key)).map(u => u.label);
    $('#setupSummary').textContent = names.length ? 'Set up for: ' + names.join(', ') : 'Check this PC and pick the right AI models';
    renderMemories(await api.memories());
  }
  function renderMemories(list) {
    const box = $('#memList');
    if (!list.length) { box.innerHTML = '<div class="empty" style="padding:24px">Nothing saved yet. Say "Remember that …" in a chat.</div>'; return; }
    box.innerHTML = list.map(m => `<div class="mem-row"><span>${esc(m.content)}</span><button class="icon-btn" data-mem="${m.id}" aria-label="Delete memory">${window.icon('trash')}</button></div>`).join('');
    $$('[data-mem]', box).forEach(b => b.onclick = async () => renderMemories(await api.delete_memory(+b.dataset.mem)));
  }
  function bindSwitch(id, key) {
    const el = $(id); el.onclick = async () => { const on = el.getAttribute('aria-checked') !== 'true'; el.setAttribute('aria-checked', on); await setSetting(key, on); };
  }

  /* -------------------------------------------------------------- MCP tools */
  async function loadTools() { S.mcp = await api.mcp_state(); refreshMcp(); }
  async function refreshMcp() { if (S.page !== 'tools' && !S.mcpBusy && !S.toolsOn) return; S.mcp = await api.mcp_state(); renderMcp(); }
  function renderMcp() {
    const box = $('#mcpList');
    if (!S.mcp.length) { box.innerHTML = '<div class="empty">No tool servers yet.<br>Click “Import from Codex” to bring in REA and your other Codex tools.</div>'; return; }
    const label = { connected: ['Connected', 'ok'], connecting: ['Connecting…', 'idle'], error: ['Error', 'bad'], idle: ['Not connected', 'idle'], stopped: ['Stopped', 'idle'] };
    box.innerHTML = S.mcp.map(r => { const [t, c] = label[r.status] || label.idle;
      return `<div class="server"><span class="ico">${window.icon('plug')}</span><span class="name">${esc(r.name)}</span>
        <span class="side"><button class="switch" data-en="${esc(r.name)}" role="switch" aria-checked="${r.enabled}"><i></i></button><button class="btn ghost sm danger-text" data-rm="${esc(r.name)}">Remove</button></span>
        <span class="st ${c}">${t}${r.status === 'connected' ? ` · ${r.tools} tools` : ''}${r.status === 'error' ? ': ' + esc(r.error) : ''}</span><span class="cmd" title="${esc(r.command)}">${esc(r.command)}</span></div>`; }).join('');
    $$('[data-en]', box).forEach(b => b.onclick = async () => { S.mcp = await api.mcp_enable(b.dataset.en, b.getAttribute('aria-checked') !== 'true'); renderMcp(); });
    $$('[data-rm]', box).forEach(b => b.onclick = async () => { S.mcp = await api.mcp_remove(b.dataset.rm); renderMcp(); });
  }
  async function toggleTools() {
    S.toolsOn = !S.toolsOn; setToggle($('#btnTools'), S.toolsOn);
    if (!S.toolsOn) return hint('');
    S.mcp = await api.mcp_state();
    if (!S.mcp.length) { hint('No tool servers yet - import them from Codex on the Tools page.', true); return showPage('tools'); }
    if (await api.mcp_ready()) hint("Tools on - the model can use your tool servers (you'll be asked first).");
    else { await api.mcp_connect(); hint('Tools on - connecting your tool servers…'); }
  }

  /* ------------------------------------------------------------------ help */
  function buildHelp() {
    const cards = [
      ['Getting started', '1. Make sure the Ollama app is running (see the Dashboard).\n2. Pick a model from the pill at the top of the chat, or choose Auto.\n3. Type your request and press Enter.'],
      ['Keyboard shortcuts', '<kbd>Enter</kbd> send   <kbd>Shift</kbd>+<kbd>Enter</kbd> new line   <kbd>Ctrl</kbd>+<kbd>N</kbd> new chat   <kbd>Ctrl</kbd>+<kbd>,</kbd> settings   <kbd>Esc</kbd> stop / close'],
      ['Chat tools', 'The round icons on the left switch the assistant\'s role and model: Code, Math, Writing, Translator, Summarizer, Brainstorm (and more under the arrow). Click the active one again to switch it off.\nReasoning thinks step by step with DeepSeek R1. Deep Research writes long, structured reports (offline - it does not browse the web). The paperclip attaches a text or code file, the note icon inserts prompt templates, and the mic starts Windows voice typing.'],
      ['Tools (MCP / REA)', 'Open Settings → Tool servers → Manage, click “Import from Codex” to bring in REA and your other Codex tools, then switch on Tools in the chat. The model picks relevant tools for each question and asks your permission before running them. Use a tool-capable model (Qwen 2.5, Qwen3.5, Llama 3.2).'],
      ['Code preview', 'When the AI writes a web page (HTML, CSS and JavaScript, or an SVG), a live preview opens beside the chat. Switch between Preview, Code and Console, try Desktop / Tablet / Phone sizes, save the page as .html or open it in your browser. Previews run in a sandbox, so generated code can never touch your chats or files. Turn automatic opening off in Settings.'],
      ['Models for your PC', 'The setup wizard checks your memory, processor, graphics and disk space, asks what you use the app for (coding, studying, writing, maths, languages) and installs models that run well on this PC. Run it again any time from Settings → Models & hardware.'],
      ['Account & privacy', 'Your chats, memories and files stay on this PC, in a separate folder for each account. Only your email and sign-in details go to the account service (Supabase). Sign out from the Account page or the exit button.'],
      ['Memory', 'Say “Remember that I\'m building Podchain.” to save a fact, “What do you know about me?” to list them, or “Forget everything” to clear them. Manage memories in Settings.'],
      ['Troubleshooting', '“Can\'t reach Ollama” - start the Ollama app or run `ollama serve`.\n“Model isn\'t installed” - run `ollama pull <model>` in a terminal.\nSlow or choppy - turn on Reduce effects in Settings and use a smaller model.'],
    ];
    $('#helpBody').innerHTML = '<h2 class="title">Help</h2>' + cards.map(([t, b]) => `<div class="help-card"><h3>${t}</h3><p>${b.includes('<kbd>') ? b : esc(b)}</p></div>`).join('') +
      `<div class="help-card about"><div class="orb"><svg class="orb-ring r1" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46"/></svg><svg class="orb-ring r2" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46"/></svg><i class="orb-core"></i></div><h3 style="color:var(--text)">${esc(S.app.app)}</h3><p style="white-space:normal">Version ${esc(S.app.version)} · Powered by Ollama · Llama · Gemma · DeepSeek · Qwen</p>
      <div class="row-btns"><button class="btn sm" id="lnkOllama">Open Ollama website</button><button class="btn sm" id="lnkData">Open data folder</button></div></div>`;
    $('#lnkOllama').onclick = () => api.open_url('https://ollama.com'); $('#lnkData').onclick = () => api.open_data_folder();
  }

  /* ------------------------------------------------------------- event wiring */
  function bind() {
    $$('#nav button').forEach(b => b.onclick = () => showPage(b.dataset.page));
    $$('[data-theme-btn]').forEach(b => b.onclick = () => setSetting('theme', b.dataset.themeBtn));
    $('#btnHistory').onclick = async () => { await setSetting('show_history', !S.settings.show_history); showPage('chat'); };
    $('#btnBell').onclick = showNotes; $('#btnAvatar').onclick = () => showPage('account');
    $('#btnSettings').onclick = () => showPage('settings');
    $('#btnCheckUpdates').onclick = () => checkForUpdates(true);
    const logout = async () => {
      const signed = !!S.auth.signedIn;
      const r = await modal({ title: signed ? 'Sign out?' : "Quit Randan's GPT?", text: 'Your chats stay saved on this PC.',
        actions: [{ label: 'Cancel', value: null }, ...(signed ? [{ label: 'Quit app', value: 'quit' }, { label: 'Sign out', value: 'out', primary: true }] : [{ label: 'Quit', value: 'quit', primary: true }])] });
      if (r.value === 'quit') api.quit();
      else if (r.value === 'out') { await api.auth_sign_out(); S.auth = Object.assign(S.auth, { signedIn: false, user: null }); signedOut(); }
    };
    $('#btnLogout').onclick = logout; $('#btnLogout2').onclick = logout;
    $('#btnNew').onclick = newChat;
    $('#modelPill').onclick = () => openPopover($('#modelPill'), menu([{ label: 'Auto (smart routing)', icon: 'sparkle', checked: S.model === 'auto' && !S.reasoning, onClick: () => selectModel('auto') },
      ...S.models.map(m => ({ label: m.label, checked: S.model === m.tag && !S.reasoning, onClick: () => selectModel(m.tag) }))]), { width: 270 });
    $('#modeChip').onclick = () => selectTool(S.tool);
    $('#btnMore').onclick = () => openPopover($('#btnMore'), chatOptions(), { align: 'right' });
    $('#btnSend').onclick = send;
    const input = $('#input');
    input.addEventListener('input', autosize);
    input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
    $('#btnAttach').onclick = async () => { const r = await api.pick_attachment(); if (r.error) return toast(r.error, true);
      if (r.name) { S.attach = { name: r.name, text: r.text }; renderAttach(); hint(`Attached ${r.name}. ${r.note || ''}`); } };
    $('#btnNotes').onclick = () => openPopover($('#btnNotes'), menu(S.templates.map(t => ({ label: t.label, icon: 'note', onClick: () => { input.value += t.text; autosize(); input.focus(); } }))), { width: 270 });
    $('#btnReason').onclick = () => { S.reasoning = !S.reasoning; setToggle($('#btnReason'), S.reasoning); updateModelLabel(); hint(S.reasoning ? 'Reasoning on - DeepSeek R1 will think step by step.' : ''); };
    $('#btnResearch').onclick = () => { S.research = !S.research; setToggle($('#btnResearch'), S.research); hint(S.research ? 'Deep Research on - long, structured answers (offline, no web browsing).' : ''); };
    $('#btnTools').onclick = toggleTools;
    $('#btnMic').onclick = async () => { input.focus(); const r = await api.start_voice(); hint(r.message, !r.ok); };
    // settings
    $('#setDefaultModel').onchange = async e => { await setSetting('default_model', e.target.value); S.model = e.target.value; updateModelLabel(); };
    bindSwitch('#setAuto', 'auto_mode'); bindSwitch('#setPreview', 'auto_preview');
    $('#btnRunSetup').onclick = () => Onboard.open({ rerun: true }); bindSwitch('#setMemory', 'memory_enabled'); bindSwitch('#setEffects', 'reduce_effects'); bindSwitch('#setConfirm', 'mcp_confirm');
    $('#fontMinus').onclick = () => setSetting('font_size', Math.max(12, S.settings.font_size - 1));
    $('#fontPlus').onclick = () => setSetting('font_size', Math.min(22, S.settings.font_size + 1));
    $('#btnManageTools').onclick = () => showPage('tools');
    $('#btnClearMem').onclick = async () => { const r = await modal({ title: 'Delete all memories?', actions: [{ label: 'Cancel', value: null }, { label: 'Delete', value: true, primary: true }] }); if (r.value) renderMemories(await api.clear_memories()); };
    // account
    $('#btnPhoto').onclick = async () => { const r = await api.pick_avatar(); if (r.error) return toast(r.error, true); if (r.avatar !== undefined) { S.avatar = r.avatar; renderAvatar(); } };
    $('#btnPhotoRemove').onclick = async () => { S.avatar = (await api.remove_avatar()).avatar; renderAvatar(); };
    $('#btnSaveName').onclick = async () => { S.settings.user_name = await api.set_user_name($('#accName').value); renderAvatar(); $('#greeting').textContent = greeting(); toast('Profile saved'); loadAccount(); };
    $('#accName').addEventListener('keydown', e => { if (e.key === 'Enter') $('#btnSaveName').click(); });
    $('#btnToSettings').onclick = () => showPage('settings');
    // tools page
    $('#btnImport').onclick = async () => { const r = await api.mcp_import(); $('#mcpMsg').textContent = r.message; S.mcp = r.servers; renderMcp(); };
    $('#btnConnect').onclick = async () => { if (!(await api.mcp_connect())) $('#mcpMsg').textContent = 'Nothing to connect - add or enable a server first.'; else $('#mcpMsg').textContent = 'Connecting…'; };
    $('#btnAddServer').onclick = async () => {
      const r = await modal({ title: 'Add tool server', fields: [{ id: 'name', label: 'Name', placeholder: 'rea' }, { id: 'command', label: 'Command', placeholder: 'python  /  npx  /  C:\\path\\server.exe' }, { id: 'args', label: 'Arguments', placeholder: '-m rea_server --stdio' }],
        actions: [{ label: 'Cancel', value: null }, { label: 'Add', value: true, primary: true }] });
      if (r.value) { S.mcp = await api.mcp_add(r.fields.name, r.fields.command, r.fields.args); renderMcp(); }
    };
    // delegated clicks: copy buttons + links
    document.addEventListener('click', async e => {
      const cc = e.target.closest('[data-copy-code]');
      if (cc) { await copyText($('code', cc.closest('.code')).textContent); cc.lastChild.textContent = 'Copied'; setTimeout(() => cc.lastChild.textContent = 'Copy', 1400); return; }
      const cm = e.target.closest('[data-copy-msg]');
      if (cm) { const b = $('.bubble', cm.closest('.msg')); await copyText(b.innerText); cm.lastChild.textContent = 'Copied'; setTimeout(() => cm.lastChild.textContent = 'Copy', 1400); return; }
      const pv = e.target.closest('[data-preview-code],[data-preview-msg]');
      if (pv) { Preview.show(S.raw.get(pv.closest('.msg')) || ''); return; }
      const a = e.target.closest('a[data-href]'); if (a) api.open_url(a.dataset.href);
    });
    document.addEventListener('keydown', e => {
      if (e.ctrlKey && e.key.toLowerCase() === 'n') { e.preventDefault(); newChat(); }
      else if (e.ctrlKey && e.key === ',') { e.preventDefault(); showPage('settings'); }
      else if (e.key === 'Escape') { if (S.pop) closePopover(); else if (S.gen > 0) stop(); }
    });
    addEventListener('resize', syncSegs);
  }

  /* ------------------------------------------------------------------- boot */
  function populate(b) {
    Object.assign(S, { app: b, auth: b.auth, settings: b.settings, models: b.models, chats: b.chats, tools: b.tools, moreTools: b.moreTools, templates: b.templates, useCases: b.useCases });
    S.model = S.settings.auto_mode ? 'auto' : S.settings.default_model; S.avatar = b.avatar;
    applySettings(); renderAvatar(); buildRail(); buildHelp(); renderHistory(); fillModelSelect(); updateModelLabel(); updateAccountUi();
  }
  function build() {                                   // one-time DOM setup
    const mi = document.createElement('div'); mi.className = 'messages-inner'; $('#messages').appendChild(mi);
    hydrateIcons(); buildStarters(); setSending(false); bind(); S.built = true;
  }
  async function enter() {                              // the user is signed in (or auth is off): show the app
    newChat(); requestAnimationFrame(syncSegs); setTimeout(syncSegs, 400); checkStatus();
    checkForUpdates();
    if (!S.entered) {
      S.entered = true; setInterval(checkStatus, 30000);
      notify("Welcome to Randan's GPT", 'Tip: say "Remember that …" and I\'ll keep it in memory. Pick a tool on the left to change my role.');
    }
    document.body.dataset.ready = '1';
    if (!S.settings.onboarded) setTimeout(() => Onboard.open(), 350);
  }
  async function afterAuth() { const b = await api.boot(); populate(b); Auth.close(); await enter(); }
  function signedOut() {
    if (window.Preview) Preview.close();
    clearMessages(); S.chats = []; S.chatId = null; S.gen = null; S.live = null; setSending(false); renderHistory();
    document.body.dataset.ready = ''; Auth.open(S.auth);
  }
  function applyModels(d) {                             // after the setup wizard saved new choices
    Object.assign(S, { settings: d.settings, models: d.models, tools: d.tools, moreTools: d.moreTools });
    S.model = S.settings.auto_mode ? 'auto' : S.settings.default_model;
    applySettings(); buildRail(); fillModelSelect(); updateModelLabel();
  }
  async function start() {
    let b;
    try { b = await api.boot(); } catch (e) { document.body.insertAdjacentHTML('beforeend', `<p style="position:fixed;inset:40px;color:#ff6259">Could not reach the app backend: ${esc(String(e))}</p>`); return; }
    window.UI = Object.assign(window.UI || {}, { api, S, $, $$, esc, toast, hint, modal, copyText, showPage, openPopover, menu, setSetting, setSeg, syncShell, afterAuth, applyModels, populate });
    build(); populate(b); document.body.dataset.booted = '1';
    if (b.ready) await enter(); else Auth.open(b.auth, b.legal);
  }
  window.UI = { api, S, $, $$, esc, toast, hint, modal, copyText, showPage, openPopover, menu, setSetting, setSeg, syncShell, afterAuth, applyModels, populate };
  const run = () => { const go = () => start(); if (window.pywebview && window.pywebview.api) go(); else window.addEventListener('pywebviewready', go, { once: true }); };
  if (document.readyState === 'complete') run(); else addEventListener('load', run);
})();
