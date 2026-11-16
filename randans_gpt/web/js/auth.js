/* Google-only sign-in screen. New accounts are created on the first successful Google sign-in. */
(() => {
  const U = window.UI, $ = U.$, api = U.api, ic = n => window.icon(n);
  const A = { legal: {} };
  const ORB = '<div class="orb"><i class="orb-glow"></i><svg class="orb-ring r1" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46"/></svg><svg class="orb-ring r2" viewBox="0 0 100 100"><circle cx="50" cy="50" r="46"/></svg><i class="orb-core"></i></div>';

  const head = (title, lead) => `${ORB}<h2>${title}</h2><p class="lead">${lead}</p>`;
  const consentLinks = () => {
    const legal = A.legal || {};
    const terms = legal.terms ? `<a class="link" data-url="${U.esc(legal.terms)}">Terms</a>` : 'Terms';
    const privacy = legal.privacy ? `<a class="link" data-url="${U.esc(legal.privacy)}">Privacy Policy</a>` : 'Privacy Policy';
    return `By continuing with Google, you agree to our ${terms} and ${privacy}.`;
  };
  const bindLegalLinks = root => root.querySelectorAll('[data-url]').forEach(a => a.onclick = () => api.open_url(a.dataset.url));
  const err = () => $('#aErr');

  function showErr(message) {
    const element = err();
    if (!element) return;
    element.textContent = message || '';
    element.className = 'form-error';
    if (message) { void element.offsetWidth; element.classList.add('shake'); }
  }

  async function busy(button, action) {
    button.classList.add('loading');
    showErr('');
    try { await action(); }
    catch (error) { showErr('Something went wrong: ' + error); }
    finally { button.classList.remove('loading'); }
  }

  function render() {
    const card = $('#authCard');
    card.innerHTML = `${head('Welcome', 'Sign in or create your account with Google.')}<div class="auth-form">
      <button class="btn block google" id="aGoogle"><span class="google-mark" aria-hidden="true">G</span>Continue with Google</button>
      <label class="check"><input type="checkbox" id="aGoogleTerms"><span>${consentLinks()}</span></label>
      <div class="form-error" id="aErr"></div></div>`;
    card.style.animation = 'none';
    void card.offsetWidth;
    card.style.animation = '';
    bindLegalLinks(card);
    $('#aGoogle').onclick = event => busy(event.currentTarget, async () => {
      if (!$('#aGoogleTerms').checked) return showErr('Please accept the terms before continuing with Google.');
      const result = await api.auth_google_sign_in();
      if (result.ok) U.afterAuth(); else showErr(result.error);
    });
  }

  function open(_auth, legal) {
    A.legal = legal || {};
    $('#onboard').hidden = true;
    $('#auth').hidden = false;
    render();
  }

  function close() {
    $('#auth').hidden = true;
    $('#authCard').innerHTML = '';
  }

  window.Auth = { open, close };
})();
