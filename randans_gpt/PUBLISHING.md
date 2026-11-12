# Publishing Randan's GPT

## 1. Set up accounts (Supabase) — about 10 minutes
1. Create a free project at https://supabase.com → **Project Settings → API**. Copy the **Project URL** and the **anon / public** key.
   *Never* put the `service_role` key in the app.
2. Copy `supabase.json.example` to `supabase.json` and fill it in:
   ```json
   { "url": "https://abcd1234.supabase.co", "anon_key": "eyJ…", "require_login": true,
     "terms_url": "https://randankevin004-hub.github.io/Randan-s-GPT/terms.html",
     "privacy_url": "https://randankevin004-hub.github.io/Randan-s-GPT/privacy.html",
     "updates_repo": "randankevin004-hub/Randan-s-GPT" }
   ```
   `require_login: false` adds a "Continue without an account" button. Without `supabase.json` the app runs in local mode (no sign-in).
   The terms and privacy URLs assume GitHub Pages is enabled for the `docs/` folder of `randankevin004-hub/Randan-s-GPT`. Only the Supabase project URL and public anon key go in this file. Never include a service-role key.
3. **Authentication → Providers → Email**: keep *Confirm email* ON, set *Minimum password length* to 8.
4. **Authentication → Email Templates**: the app signs people in with a 6-digit code, so put `{{ .Token }}` in these templates
   (for example: `Your Randan's GPT code is <b>{{ .Token }}</b>`):
   *Confirm signup*, *Magic Link* (used for "Email me a code") and *Reset Password*.
5. **Authentication → SMTP Settings**: Supabase's built-in email sender only allows a few emails per hour. Before launch connect your own SMTP
   (Resend, Brevo, SendGrid, Gmail SMTP…). Optional: enable CAPTCHA protection in *Authentication → Attack Protection*.

How it works: email + password, passwordless code, password reset by code. The sign-in token is kept in the Windows Credential Manager
(never in a plain file). Each account gets its own private chat database in `%APPDATA%\RandansGPT\users\<id>\`.

## 2. Build the app
1. Double-click `setup_and_run.bat` once (creates the `venv`).
2. Put your `supabase.json` next to `build_exe.bat`, then double-click **`build_exe.bat`** → `dist\RandansGPT.exe`.

## 3. Build an installer
Install [Inno Setup](https://jrsoftware.org/isdl.php), open `installer.iss`, press **Compile** → `Output\RandansGPT-Setup.exe`.
It installs per-user (no admin prompt), adds Start-menu / desktop shortcuts and an uninstaller, and reminds the user to install the free
Edge WebView2 runtime if it is missing (already included in Windows 11).

## 4. Publish the website and legal pages
The one-page landing page and short beta policies are in `docs/` (`index.html`, `terms.html`, `privacy.html`). The landing page's app-window artwork is an illustration, not a real capture; replace it with a screenshot of the tested build before wider public launch. The legal drafts identify the operator as Randan Kevin, provide WhatsApp contact at +254 708 063 827, and specify Kenya; they are not legal advice. Verify the account-deletion process before public distribution.

Enable GitHub Pages in the `Randan-s-GPT` repository under **Settings → Pages**, selecting the `main` branch and `/docs` folder. The pages should be available at:
* `https://randankevin004-hub.github.io/Randan-s-GPT/`
* `https://randankevin004-hub.github.io/Randan-s-GPT/terms.html`
* `https://randankevin004-hub.github.io/Randan-s-GPT/privacy.html`

Verify all three URLs after GitHub Pages finishes deploying. Put the Terms and Privacy URLs in the private `supabase.json` used by the build; `supabase.json.example` has the planned links.

## 5. Before you share it publicly
* **Code signing** — unsigned apps trigger Windows SmartScreen / antivirus warnings (common with PyInstaller). A code-signing certificate
  (Azure Trusted Signing, SSL.com, Sectigo…) removes most of them; submit the exe to Microsoft Defender's false-positive form if it is still flagged.
* **Legal** — publish a Terms of Use and Privacy Policy and put the links in `supabase.json`. Chats, memories and files are stored locally; prompts go to local Ollama. Account data goes to Supabase, model downloads come from Ollama, startup update checks contact GitHub, and optional MCP tools can send relevant content to their configured services.
* **Model licences** — Llama, Gemma, Qwen, DeepSeek and Phi each have their own licence/acceptable-use terms. Mention them (the Help → About page
  already credits them) and link to the originals. The app downloads models on the user's PC instead of redistributing them.
* **Hosting and checksum** — create a release in `randankevin004-hub/Randan-s-GPT` with a tag such as `v1.0`. Attach `Output\RandansGPT-Setup.exe`. In PowerShell, calculate the checksum with `Get-FileHash .\Output\RandansGPT-Setup.exe -Algorithm SHA256`; publish the resulting hash in the release notes or as a `.sha256` release asset. Test it by downloading the installer and comparing its hash.
* **Virus scan** — upload the exact release installer to VirusTotal and review the results before sharing the release. A VirusTotal submission is shared with its analysis partners, so do not upload private builds or files containing secrets.
* **Updates** — the app checks `randankevin004-hub/Randan-s-GPT` for the latest GitHub Release at startup and has a manual check in Settings. It only announces a newer version and opens the release page; users install it themselves. Bump `APP_VERSION` in `settings/config.py` and the version in `installer.iss`, build, create a matching version tag/release, and attach the installer.
* **Support** — the landing page and legal policies link to WhatsApp at `https://wa.me/254708063827`.

## 6. Users' first run
After signing in the setup wizard checks the PC (RAM, CPU, graphics, free disk), asks what they want to use the app for, recommends models that
run well, and downloads them with Ollama. If Ollama isn't installed the wizard links to https://ollama.com/download.
