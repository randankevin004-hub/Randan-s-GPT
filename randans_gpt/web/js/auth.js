/* Sign-in / account creation screen (Supabase email auth, handled by the Python backend). */
(() => {
  const U = window.UI, $ = U.$, esc = U.esc, api = U.api, ic = n => window.icon(n);
  const A = { view: 'signin', email: '', password: '', timer: null, legal: {} };
  const ORB = '<div class="orb"><i class="orb-glow"></i><svg class="orb-ring r1" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46"/></svg><svg class="orb-ring r2" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46"/></svg><i class="orb-core"></i></div>';

  const field = (id, type, icon, ph, val = '', ac = '') => `<div class="input"><span class="ico">${ic(icon)}</span><input id="${id}" type="${type}" placeholder="${ph}" value="${esc(val)}" autocomplete="${ac}" spellcheck="false">${type === 'password' ? `<button type="button" class="eye" data-eye aria-label="Show password">${ic('eye')}</button>` : ''}</div>`;
  const head = (title, lead) => `${ORB}<h2>${title}</h2><p class="lead">${lead}</p>`;
  const err = () => $('#aErr');
  function showErr(msg, ok = false) { const e = err(); if (!e) return; e.textContent = msg || ''; e.className = 'form-error' + (ok ? ' form-ok' : ''); if (msg && !ok) { void e.offsetWidth; e.classList.add('shake'); } }
  async function busy(btn, fn) {
    btn.classList.add('loading'); showErr('');
    try { return await fn(); } catch (e) { showErr('Something went wrong: ' + e); } finally { btn.classList.remove('loading'); }
  }
  const strength = pw => { let s = 0; if (pw.length >= 8) s++; if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s++; if (/\d/.test(pw)) s++; if (/[^A-Za-z0-9]/.test(pw) || pw.length >= 14) s++; return pw ? Math.max(1, s) : 0; };

  function bindCommon(root) {
    root.querySelectorAll('[data-eye]').forEach(b => b.onclick = () => { const i = b.parentElement.querySelector('input'); const show = i.type === 'password'; i.type = show ? 'text' : 'password'; b.innerHTML = ic(show ? 'eyeoff' : 'eye'); });
    root.querySelectorAll('[data-go]').forEach(b => b.onclick = () => render(b.dataset.go));
    root.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.tagName === 'INPUT') { e.preventDefault(); const p = root.querySelector('.btn.primary'); p && p.click(); } });
  }

  const views = {
    signin() {
      const guest = !U.S.auth.required ? '<div class="divider">or</div><button class="btn block ghost" id="aGuest">Continue without an account</button>' : '';
      return { html: `${head('Welcome back', 'Sign in to your Randan\'s GPT account')}<div class="auth-form">
        ${field('aEmail', 'email', 'atsign', 'Email address', A.email, 'email')}${field('aPw', 'password', 'lock', 'Password', '', 'current-password')}
        <div class="form-error" id="aErr"></div><button class="btn primary block" id="aGo">Sign in</button>
        <div class="link-row"><button class="link" data-go="reset">Forgot password?</button><button class="link" id="aCode">Email me a code instead</button></div>
        <div class="divider">New here?</div><button class="btn block" data-go="signup">Create an account</button>${guest}</div>`,
        bind(r) {
          $('#aGo').onclick = e => busy(e.currentTarget, async () => {
            A.email = $('#aEmail').value.trim(); A.password = $('#aPw').value;
            const res = await api.auth_sign_in(A.email, A.password);
            if (res.ok) return U.afterAuth();
            if (res.code === 'email_not_confirmed') { await api.auth_resend(A.email); return render('code', { kind: 'signup', note: 'Your email isn\'t confirmed yet. We sent you a fresh code.' }); }
            showErr(res.error);
          });
          $('#aCode').onclick = e => busy(e.currentTarget, async () => {
            A.email = $('#aEmail').value.trim(); const res = await api.auth_send_code(A.email);
            if (res.ok) render('code', { kind: 'email' }); else showErr(res.error);
          });
          const g = $('#aGuest'); if (g) g.onclick = async () => { const res = await api.auth_guest(); if (res.ok) U.afterAuth(); };
        } };
    },
    signup() {
      const legal = A.legal || {};
      const terms = (legal.terms || legal.privacy) ? `I agree to the ${legal.terms ? '<a class="link" data-url="' + esc(legal.terms) + '">Terms</a>' : 'Terms'}${legal.privacy ? ' and <a class="link" data-url="' + esc(legal.privacy) + '">Privacy Policy</a>' : ''}` : 'I agree to the Terms and Privacy Policy';
      return { html: `${head('Create your account', 'Your chats stay private on this PC. The account just keeps your profile safe.')}<div class="auth-form">
        ${field('aName', 'text', 'user', 'Your name', '', 'name')}${field('aEmail', 'email', 'atsign', 'Email address', A.email, 'email')}${field('aPw', 'password', 'lock', 'Password (8+ characters)', '', 'new-password')}
        <div class="strength" id="aStr"><i></i><i></i><i></i><i></i></div>
        <label class="check"><input type="checkbox" id="aTerms"><span>${terms}</span></label>
        <div class="form-error" id="aErr"></div><button class="btn primary block" id="aGo">Create account</button>
        <div class="link-row" style="justify-content:center">Already have an account?&nbsp;<button class="link" data-go="signin">Sign in</button></div></div>`,
        bind() {
          $('#aPw').oninput = e => { $('#aStr').className = 'strength s' + strength(e.target.value); };
          $('#authCard').querySelectorAll('[data-url]').forEach(a => a.onclick = () => api.open_url(a.dataset.url));
          $('#aGo').onclick = e => busy(e.currentTarget, async () => {
            A.email = $('#aEmail').value.trim(); A.password = $('#aPw').value;
            if (!$('#aTerms').checked) return showErr('Please accept the terms to continue.');
            const res = await api.auth_sign_up(A.email, A.password, $('#aName').value);
            if (!res.ok) return showErr(res.error);
            if (res.needs_confirmation) return render('code', { kind: 'signup', note: 'Account created! Enter the 6-digit code from the email we just sent.' });
            U.afterAuth();
          });
        } };
    },
    code(o) {
      const kind = o.kind || 'email';
      const sub = kind === 'recovery' ? 'Enter the 6-digit code we emailed to reset your password.' : (o.note || 'Enter the 6-digit code we emailed you.');
      return { html: `${head('Check your email', `<b>${esc(A.email)}</b><br>${sub}`)}<div class="auth-form">
        <input class="input code-input" style="padding:0" id="aCodeIn" inputmode="numeric" maxlength="8" placeholder="······" autocomplete="one-time-code">
        <div class="form-error" id="aErr"></div><button class="btn primary block" id="aGo">Verify</button>
        <div class="link-row"><button class="link" id="aResend">Resend code</button><button class="link" data-go="signin">Use a different email</button></div>
        ${kind === 'signup' ? '<button class="btn block ghost" id="aConfirmed">I clicked the link in the email</button>' : ''}</div>`,
        bind() {
          const inp = $('#aCodeIn'); inp.focus();
          const verify = btn => busy(btn, async () => {
            const res = await api.auth_verify(A.email, inp.value, kind);
            if (!res.ok) return showErr(res.error);
            if (kind === 'recovery') render('newpass'); else U.afterAuth();
          });
          inp.oninput = () => { inp.value = inp.value.replace(/\D/g, ''); if (inp.value.length === 6) verify($('#aGo')); };
          $('#aGo').onclick = e => verify(e.currentTarget);
          const rs = $('#aResend'); let left = 30; clearInterval(A.timer);
          const tick = () => { rs.disabled = left > 0; rs.textContent = left > 0 ? `Resend code (${left})` : 'Resend code'; left--; if (left < -1) clearInterval(A.timer); };
          tick(); A.timer = setInterval(tick, 1000);
          rs.onclick = async () => { const res = kind === 'email' ? await api.auth_send_code(A.email) : kind === 'recovery' ? await api.auth_reset(A.email) : await api.auth_resend(A.email);
            if (res.ok) { showErr('A new code is on its way.', true); left = 30; tick(); } else showErr(res.error); };
          const c = $('#aConfirmed'); if (c) c.onclick = e => busy(e.currentTarget, async () => {
            if (!A.password) return render('signin');
            const res = await api.auth_sign_in(A.email, A.password); if (res.ok) U.afterAuth(); else showErr(res.error);
          });
        } };
    },
    reset() {
      return { html: `${head('Reset your password', 'We\'ll email you a 6-digit code.')}<div class="auth-form">${field('aEmail', 'email', 'atsign', 'Email address', A.email, 'email')}
        <div class="form-error" id="aErr"></div><button class="btn primary block" id="aGo">Send code</button><button class="btn block ghost" data-go="signin">Back to sign in</button></div>`,
        bind() { $('#aGo').onclick = e => busy(e.currentTarget, async () => { A.email = $('#aEmail').value.trim(); const res = await api.auth_reset(A.email); if (res.ok) render('code', { kind: 'recovery' }); else showErr(res.error); }); } };
    },
    newpass() {
      return { html: `${head('Choose a new password', 'Use at least 8 characters.')}<div class="auth-form">${field('aPw', 'password', 'lock', 'New password', '', 'new-password')}<div class="strength" id="aStr"><i></i><i></i><i></i><i></i></div>
        <div class="form-error" id="aErr"></div><button class="btn primary block" id="aGo">Save password</button></div>`,
        bind() {
          $('#aPw').oninput = e => { $('#aStr').className = 'strength s' + strength(e.target.value); };
          $('#aGo').onclick = e => busy(e.currentTarget, async () => { const res = await api.auth_set_password($('#aPw').value); if (res.ok) { U.toast('Password updated'); U.afterAuth(); } else showErr(res.error); });
        } };
    },
  };

  function render(view, opts = {}) {
    clearInterval(A.timer); A.view = view;
    const v = views[view](opts); const card = $('#authCard');
    card.innerHTML = v.html; card.style.animation = 'none'; void card.offsetWidth; card.style.animation = '';
    bindCommon(card); v.bind(); const first = card.querySelector('input'); if (first) first.focus();
  }
  function open(auth, legal) {
    A.legal = legal || {}; A.email = A.password = '';
    $('#onboard').hidden = true; $('#auth').hidden = false; render('signin');
  }
  function close() { clearInterval(A.timer); $('#auth').hidden = true; $('#authCard').innerHTML = ''; }
  window.Auth = { open, close, render };
})();
