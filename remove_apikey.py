with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'r', encoding='utf-8') as f:
    html = f.read()

changes = []

# 1. Remove .api-btn CSS block
OLD = """    .api-btn {
      height: 34px;
      padding: 0 12px;
      background: transparent;
      border: 1px solid #2e2e2e;
      color: var(--gray);
      font-family: 'Titillium Web', sans-serif;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
      cursor: pointer;
      transition: all 0.18s;
      flex-shrink: 0;
    }

    .api-btn:hover { border-color: var(--gray); color: var(--white); }
    .api-btn.connected { border-color: var(--green); color: var(--green); }

    /* \u2500\u2500 RACE BAR"""
NEW = """    /* \u2500\u2500 RACE BAR"""
assert OLD in html; html = html.replace(OLD, NEW, 1); changes.append("Removed .api-btn CSS")

# 2. Remove API KEY MODAL CSS block
OLD = """    /* \u2500\u2500 API KEY MODAL \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */
    .modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,.92);
      z-index: 999;
      display: flex;
      align-items: center;
      justify-content: center;
      display: none;
    }

    .modal-overlay.open { display: flex; }

    .modal-box {
      background: var(--bg2);
      border: 1px solid var(--red);
      padding: 32px;
      width: 440px;
      max-width: 90vw;
      box-shadow: 0 0 60px rgba(225,6,0,.15);
    }

    .modal-hdr {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 20px;
    }

    .modal-hdr-icon {
      width: 36px;
      height: 36px;
      background: var(--red);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      font-weight: 900;
      color: #fff;
      font-family: 'Titillium Web', sans-serif;
      flex-shrink: 0;
    }

    .modal-title { font-size: 18px; font-weight: 900; letter-spacing: 3px; }
    .modal-subtitle { font-size: 8px; letter-spacing: 3px; color: var(--gray); text-transform: uppercase; margin-top: 2px; }

    .modal-desc {
      font-size: 12px;
      line-height: 1.7;
      color: var(--gray-lt);
      margin-bottom: 20px;
    }

    .modal-input {
      width: 100%;
      padding: 11px 14px;
      background: #000;
      border: 1px solid #2a2a2a;
      color: var(--white);
      font-family: 'Titillium Web', sans-serif;
      font-size: 13px;
      outline: none;
      margin-bottom: 10px;
      transition: border-color .15s;
    }

    .modal-input:focus { border-color: var(--red); }

    .modal-error {
      font-size: 11px;
      color: var(--red);
      margin-bottom: 10px;
      min-height: 16px;
    }

    .modal-submit {
      width: 100%;
      padding: 12px;
      background: var(--red);
      border: none;
      color: #fff;
      font-family: 'Titillium Web', sans-serif;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 3px;
      text-transform: uppercase;
      cursor: pointer;
      transition: background .15s;
    }

    .modal-submit:hover { background: #c50500; }

    .modal-note {
      font-size: 10px;
      color: var(--gray);
      text-align: center;
      margin-top: 10px;
    }"""
NEW = ""
assert OLD in html; html = html.replace(OLD, NEW, 1); changes.append("Removed modal CSS")

# 3. Remove API KEY MODAL HTML
OLD = """<!-- \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
     API KEY MODAL
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 -->
<div class="modal-overlay" id="apiModal">
  <div class="modal-box">
    <div class="modal-hdr">
      <div class="modal-hdr-icon">P</div>
      <div>
        <div class="modal-title">ASK THE GRID <em style="color:var(--red)">AI</em></div>
        <div class="modal-subtitle">Connect your Anthropic API key</div>
      </div>
    </div>
    <p class="modal-desc">
      Enter your Anthropic API key to power the AI race analyst. Your key is stored only in your browser's local storage and sent directly to Anthropic \u2014 it never touches any other server.
    </p>
    <input class="modal-input" id="apiKeyInput" type="password" placeholder="sk-ant-api03-..." autocomplete="off" spellcheck="false">
    <div class="modal-error" id="apiError"></div>
    <button class="modal-submit" onclick="saveApiKey()">ENGAGE ASK THE GRID AI</button>
    <p class="modal-note">Get your key at console.anthropic.com</p>
  </div>
</div>"""
NEW = ""
assert OLD in html; html = html.replace(OLD, NEW, 1); changes.append("Removed modal HTML")

# 4. Remove api-btn button from header
OLD = '\n  <button class="api-btn" id="apiStatusBtn" onclick="openApiModal()">&#9679; API Key</button>'
NEW = ""
assert OLD in html; html = html.replace(OLD, NEW, 1); changes.append("Removed API key button from header")

# 5. Remove apiKey variable from app state
OLD = "let apiKey  = localStorage.getItem('pitwall_apikey') || '';\n"
NEW = ""
assert OLD in html; html = html.replace(OLD, NEW, 1); changes.append("Removed apiKey localStorage variable")

# 6. Remove API KEY MODAL JS functions
OLD = """/* \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
   API KEY MODAL
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */
function openApiModal() {
  document.getElementById('apiKeyInput').value = apiKey;
  document.getElementById('apiError').textContent = '';
  document.getElementById('apiModal').classList.add('open');
}

function saveApiKey() {
  const val = document.getElementById('apiKeyInput').value.trim();
  if (!val) {
    document.getElementById('apiError').textContent = 'Please enter your API key.';
    return;
  }
  apiKey = val;
  localStorage.setItem('pitwall_apikey', apiKey);
  document.getElementById('apiModal').classList.remove('open');
  updateApiBtn();
}

async function updateApiBtn() {
  const btn = document.getElementById('apiStatusBtn');
  try {
    const r = await fetch(`${BACKEND}/api/health`, { signal: AbortSignal.timeout(4000) });
    const data = await r.json();
    if (data.api_key_set) {
      btn.textContent = '\u25cf Claude Ready';
      btn.classList.add('connected');
    } else {
      btn.textContent = '\u26a0 No API Key in .env';
      btn.classList.remove('connected');
      btn.style.color = 'var(--yellow)';
    }
  } catch {
    btn.textContent = '\u25cf Backend Offline';
    btn.classList.remove('connected');
  }
}"""
NEW = ""
assert OLD in html; html = html.replace(OLD, NEW, 1); changes.append("Removed openApiModal/saveApiKey/updateApiBtn JS functions")

# 7. Remove if (!apiKey) block in init()
OLD = """
  if (!apiKey) {
    setTimeout(() => document.getElementById('apiModal').classList.add('open'), 600);
  }

  updateFreeLimitUI"""
NEW = "\n  updateFreeLimitUI"
assert OLD in html; html = html.replace(OLD, NEW, 1); changes.append("Removed auto-open modal trigger in init()")

with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Done. Changes made:")
for c in changes:
    print(f"  \u2713 {c}")
