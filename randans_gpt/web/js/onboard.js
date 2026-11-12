/* First-run setup wizard: scan this PC -> ask what you'll use it for -> recommend & install models. */
(() => {
  const U = window.UI, $ = U.$, esc = U.esc, api = U.api, ic = n => window.icon(n);
  const STEPS = ['welcome', 'scan', 'uses', 'plan', 'install', 'done'];
  const O = { step: 0, rerun: false, uses: new Set(), pref: 'balanced', specs: null, cap: null, online: true, plan: null, picked: new Set(), results: null, installing: false, busy: false, got: new Set() };
  const ORB = '<div class="orb"><i class="orb-glow"></i><svg class="orb-ring r1" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46"/></svg><svg class="orb-ring r2" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46"/></svg><svg class="orb-ring r3" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46"/></svg><i class="orb-core"></i></div>';
  const gb = n => (n == null ? '—' : (n >= 10 ? Math.round(n) : n.toFixed(1)) + ' GB');
  const SPEED = { fast: ['fast', 'Runs smoothly'], ok: ['ok', 'Slower'] };

  function nav({ back = true, next, nextLabel = 'Continue', nextDisabled = false, skip = true, backLabel = 'Back' } = {}) {
    const b = $('#obBack'), n = $('#obNext');
    b.hidden = !back; b.textContent = backLabel; n.hidden = !next; n.textContent = nextLabel; n.disabled = nextDisabled;
    n.classList.toggle('loading', false); n.onclick = next || null; $('#obSkip').hidden = !skip;
    $('#obDots').innerHTML = STEPS.map((_, i) => `<i class="${i === O.step ? 'on' : i < O.step ? 'past' : ''}"></i>`).join('');
  }
  function body(html) { const el = $('#obBody'); el.innerHTML = html; el.style.animation = 'none'; void el.offsetWidth; el.style.animation = ''; return el; }
  const go = i => { O.step = i; render(); };

  /* ---------------------------------------------------------------- steps */
  const R = {
    welcome() {
      body(`<div class="ob-center">${ORB}<h1>Let's set up your AI</h1><p>We'll take a quick look at this PC, ask what you want to use Randan's GPT for, and install the AI models that will run best for you. Everything runs privately on your computer.</p></div>`);
      nav({ back: false, next: () => go(1), nextLabel: 'Get started' });
    },
    async scan() {
      body(`<div class="scan"><div class="orb" style="width:90px;height:90px">${ORB.replace('<div class="orb">', '').replace(/<\/div>$/, '')}</div><div>Checking your PC…</div></div>`);
      nav({ back: true, next: null, skip: true });
      try {
        O.specs = await api.get_specs();
        const probe = await api.recommend_models(['general'], 'balanced');
        O.cap = probe.capacity; O.online = probe.ollama_online; O.probeWarn = probe.warnings;
      } catch (e) { O.specs = O.specs || {}; O.cap = O.cap || { label: 'Standard', fast_gb: 2, mode: 'cpu' }; }
      if (O.step !== 1) return;
      const s = O.specs, c = O.cap;
      const gpu = s.gpu_accel ? `${esc(s.gpu_name)} · ${gb(s.vram_gb)} VRAM` : (s.gpu_name ? esc(s.gpu_name) : 'No dedicated GPU found');
      const cards = [['memory', 'Memory', gb(s.ram_gb), 'RAM available to the AI'], ['cpu', 'Processor', esc((s.cpu || 'Unknown').replace(/\(R\)|\(TM\)|CPU /g, '').replace(/\s*@.*$/, '').slice(0, 44)), `${s.cores || '?'} cores · ${s.threads || '?'} threads`],
        ['gpu', 'Graphics', gpu, s.gpu_accel ? 'Accelerates the AI (CUDA)' : 'AI will run on the processor'], ['disk', 'Free disk space', gb(s.disk_free_gb), 'Where models get stored']];
      const pct = { Entry: 28, Standard: 55, Good: 78, Strong: 100 }[c.label] || 50;
      const text = c.mode === 'gpu' ? `Your graphics card can run models up to about ${gb(c.fast_gb)} quickly.` : `This PC runs small and medium models (up to about ${gb(c.fast_gb)}) smoothly on the processor.`;
      body(`<div class="ob-title">Your PC</div><div class="ob-sub">Here's what we found. This decides which AI models will feel fast and which would be too heavy.</div>
        <div class="spec-grid">${cards.map(([i, t, v, d], n) => `<div class="spec" style="animation-delay:${n * 80}ms"><span class="ico">${ic(i)}</span><div><small>${t}</small><b>${v}</b><span class="v">${d}</span></div></div>`).join('')}</div>
        <div class="power"><div style="flex:1"><b>AI power: ${esc(c.label)}</b><div style="color:var(--text-2);font-size:13px;margin-top:3px">${text}</div></div><div class="meter"><i style="width:0" data-w="${pct}%"></i></div></div>
        ${O.online ? '' : '<div class="ob-note">Ollama (the engine that runs the models) isn\'t running yet. You can install it in a moment.</div>'}
        ${(O.probeWarn || []).map(w => `<div class="ob-note">${esc(w)}</div>`).join('')}
        <div style="margin-top:12px"><button class="link" id="obRescan">Scan again</button></div>`);
      requestAnimationFrame(() => { const m = $('.meter i'); if (m) m.style.width = m.dataset.w; });
      $('#obRescan').onclick = async () => { await api.rescan_specs(); render(); };
      nav({ back: true, next: () => go(2) });
    },
    uses() {
      const prefs = [['speed', 'Fastest'], ['balanced', 'Balanced'], ['quality', 'Best quality']];
      body(`<div class="ob-title">What will you use it for?</div><div class="ob-sub">Pick everything that applies. We'll choose a specialist model for each, so you don't download more than you need.</div>
        <div class="use-grid">${U.S.useCases.map((u, n) => `<button class="use ${O.uses.has(u.key) ? 'on' : ''}" data-use="${u.key}" style="animation:rise .5s var(--ease) ${n * 50}ms both"><span class="ico">${ic(u.icon)}</span><b>${esc(u.label)}</b><small>${esc(u.desc)}</small><span class="tick">${ic('check')}</span></button>`).join('')}</div>
        <div class="pref"><span>I care most about</span><div class="seg compact" id="obPref"><i class="seg-ind"></i>${prefs.map(([k, l]) => `<button data-pref="${k}" class="${O.pref === k ? 'on' : ''}">${l}</button>`).join('')}</div></div>`);
      const sync = () => nav({ back: true, next: () => go(3), nextDisabled: O.uses.size === 0 });
      $('#obBody').querySelectorAll('[data-use]').forEach(b => b.onclick = () => { const k = b.dataset.use; O.uses.has(k) ? O.uses.delete(k) : O.uses.add(k); b.classList.toggle('on', O.uses.has(k)); sync(); });
      $('#obPref').onclick = e => { const b = e.target.closest('[data-pref]'); if (b) { O.pref = b.dataset.pref; U.setSeg($('#obPref'), 'pref', O.pref); } };
      requestAnimationFrame(() => U.setSeg($('#obPref'), 'pref', O.pref)); sync();
    },
    async plan() {
      body('<div class="scan"><div>Finding the best models for you…</div></div>'); nav({ back: true, next: null });
      O.plan = await api.recommend_models([...O.uses], O.pref); O.online = O.plan.ollama_online;
      if (O.step !== 3) return;
      O.picked = new Set(O.plan.picks.filter(p => !p.installed).map(p => p.tag));
      const draw = () => {
        const p = O.plan, size = p.picks.filter(x => O.picked.has(x.tag)).reduce((a, x) => a + x.size_gb, 0);
        $('#obBody').innerHTML = `<div class="ob-title">Recommended for you</div><div class="ob-sub">Chosen for your ${esc(p.capacity.label.toLowerCase())}-power PC${O.pref === 'speed' ? ', favouring speed' : O.pref === 'quality' ? ', favouring quality' : ''}. Tap a card to include or skip it.</div>
          <div class="picks">${p.picks.map((x, n) => { const [cls, lab] = SPEED[x.speed] || SPEED.ok; const on = O.picked.has(x.tag) || x.installed;
            return `<div class="pick" data-tag="${esc(x.tag)}" style="animation-delay:${n * 70}ms;${on ? '' : 'opacity:.45'}"><span class="ico">${ic(U.S.useCases.find(u => u.key === x.use)?.icon || 'sparkle')}</span>
            <div><div class="t">${esc(x.label)} <span class="tag">${esc(x.tag)}</span></div><div class="d">${esc(x.blurb)}</div><div class="d" style="color:var(--text-3)">For ${[x.use_label, ...x.also].join(', ')}</div></div>
            <div class="side">${x.installed ? '<span class="chip have">Already installed</span>' : `<span class="chip ${cls}">${lab}</span><span style="color:var(--text-2);font-size:12.5px">${gb(x.size_gb)}</span>`}</div></div>`; }).join('')}</div>
          ${p.warnings.map(w => `<div class="ob-note ${p.disk_ok ? '' : 'bad'}">${esc(w)}</div>`).join('')}
          <div class="total"><span>Download: <b>${gb(size)}</b> · Free space: <b>${gb(p.disk_free_gb)}</b></span></div>`;
        $('#obBody').querySelectorAll('.pick').forEach(el => el.onclick = () => { const x = p.picks.find(q => q.tag === el.dataset.tag); if (x.installed) return; O.picked.has(x.tag) ? O.picked.delete(x.tag) : O.picked.add(x.tag); draw(); });
        const n = O.picked.size;
        nav({ back: true, next: () => (n ? go(4) : go(5)), nextLabel: n ? `Install ${n} model${n > 1 ? 's' : ''} · ${gb(size)}` : 'Continue', nextDisabled: n > 0 && !p.disk_ok && size > (p.disk_free_gb ?? 1e9) });
      };
      draw();
    },
    async install() {
      O.results = null; O.installing = true;
      const tags = [...O.picked];
      const rows = () => tags.map(t => { const x = O.plan.picks.find(p => p.tag === t); return `<div class="dl-item" data-dl="${esc(t)}"><div class="top"><span>${esc(x.label)} <span class="tag" style="font:11.5px var(--mono);color:var(--text-3)">${esc(t)}</span></span><span class="pc">Waiting…</span></div><div class="bar2"><i></i></div><div class="st"><span class="msg">Queued</span><span class="eta"></span></div></div>`; }).join('');
      body(`<div class="ob-title">Installing your models</div><div class="ob-sub">This downloads once and then works offline. You can keep this window open — it's safe to leave while it runs.</div><div class="dl" id="obDl">${rows()}</div>`);
      nav({ back: true, backLabel: 'Cancel', next: null, skip: false });
      $('#obBack').onclick = async () => { await api.cancel_install(); };
      const r = await api.start_install(tags);
      if (!r.ok) {
        O.installing = false;
        if (r.code === 'ollama_down') {
          body(`<div class="ob-center">${ORB}<h1 style="font-size:26px">Ollama isn't running</h1><p>Randan's GPT uses <b>Ollama</b> to run models on your PC. Install it (free), start it, then press <b>Check again</b>.</p>
            <div class="row-btns" style="margin-top:18px"><button class="btn primary" id="obGetOllama">Download Ollama</button><button class="btn" id="obRetry">Check again</button></div></div>`);
          $('#obGetOllama').onclick = () => api.open_url('https://ollama.com/download'); $('#obRetry').onclick = () => render();
          nav({ back: true, next: () => go(5), nextLabel: 'Skip installing', skip: false });
        } else { body(`<div class="ob-note bad">${esc(r.error)}</div>`); nav({ back: true, next: () => go(5), nextLabel: 'Continue' }); }
      }
    },
    async done() {
      body('<div class="scan"><div>Saving your setup…</div></div>'); nav({ back: false, next: null, skip: false });
      const plan = O.plan, failed = new Set(((O.results && O.results.failed) || []).map(f => f.tag).filter(t => !O.got.has(t)));
      const have = t => { const p = plan && plan.picks.find(x => x.tag === t); return !!p && (p.installed || O.got.has(t)); };
      let map = { ...(plan ? plan.route_map : {}) }, def = plan ? plan.default_model : '';
      const okTag = (plan ? plan.picks : []).map(p => p.tag).find(t => !failed.has(t) && have(t));
      Object.keys(map).forEach(k => { if (failed.has(map[k])) map[k] = okTag || ''; });
      if (failed.has(def)) def = okTag || '';
      if (!okTag) { map = {}; def = ''; }
      const saved = await api.finish_setup({ uses: [...O.uses], pref: O.pref, route_map: map, default_model: def });
      U.applyModels(saved);
      const rows = (plan && okTag ? plan.picks.filter(p => !failed.has(p.tag) && have(p.tag)) : []);
      body(`<div class="ob-center">${ORB}<h1>You're all set</h1><p>${rows.length ? 'Smart routing is on: each question goes to the best model you installed for it.' : 'You can run this setup again any time from Settings.'}</p>
        ${rows.length ? `<div class="done-list">${rows.map(p => `<div><b>${esc([p.use_label, ...p.also].join(' · '))}</b><span>${esc(p.label)}</span></div>`).join('')}</div>` : ''}</div>`);
      nav({ back: false, next: close, nextLabel: 'Start chatting', skip: false });
    },
  };

  function render() { O.busy = false; $('#obBack').onclick = () => go(Math.max(0, O.step - 1)); $('#obSkip').onclick = skip; Promise.resolve(R[STEPS[O.step]]()); }
  async function skip() {
    if (O.installing) return;
    if (!O.rerun && !U.S.settings.onboarded) { const saved = await api.finish_setup({ uses: [], pref: 'balanced', route_map: {}, default_model: '' }); U.applyModels(saved); }
    close();
  }
  function open({ rerun = false } = {}) {
    Object.assign(O, { step: 0, rerun, specs: null, plan: null, results: null, installing: false, got: new Set() });
    O.uses = new Set(U.S.settings.use_cases || []); O.pref = U.S.settings.perf_pref || 'balanced';
    $('#onboard').hidden = false; render();
  }
  function close() { $('#onboard').hidden = true; O.installing = false; U.showPage('chat'); }

  /* --------------------------------------------------- live download events */
  function onPull(ev) {
    const el = $(`[data-dl="${CSS.escape(ev.tag)}"]`); if (!el) return;
    const set = (sel, t) => { const n = $(sel, el); if (n) n.textContent = t; };
    if (ev.error) { el.classList.add('bad'); set('.pc', 'Failed'); set('.msg', ev.error); return; }
    $('.bar2 i', el).style.width = (ev.pct || 0) + '%';
    if (ev.done) { el.classList.add('ok'); set('.pc', 'Installed'); set('.msg', 'Ready to use'); set('.eta', ''); return; }
    set('.pc', Math.round(ev.pct || 0) + '%');
    set('.msg', ev.total_mb ? `${ev.mb} / ${ev.total_mb} MB` : (ev.status || 'Starting…'));
    set('.eta', ev.speed_mbs ? `${ev.speed_mbs} MB/s${ev.eta ? ' · ' + (ev.eta > 90 ? Math.round(ev.eta / 60) + ' min' : ev.eta + ' s') + ' left' : ''}` : '');
  }
  function onPullDone(ev) {
    O.results = ev; O.installing = false; ev.ok.forEach(t => O.got.add(t));
    if (O.step !== 4) return;
    if (ev.cancelled) { go(3); return; }
    if (ev.failed.length) {
      nav({ back: true, backLabel: 'Back', next: () => go(5), nextLabel: ev.ok.length ? 'Continue with what installed' : 'Continue anyway', skip: false });
      $('#obBack').onclick = () => go(3);
      const retry = document.createElement('button'); retry.className = 'btn'; retry.textContent = 'Retry failed'; retry.style.marginTop = '14px';
      retry.onclick = () => { O.picked = new Set(ev.failed.map(f => f.tag)); render(); }; $('#obBody').appendChild(retry);
    } else setTimeout(() => { if (O.step === 4) go(5); }, 900);
  }

  window.Onboard = { open, close, onPull, onPullDone };
})();
