import sys

with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'r', encoding='utf-8') as f:
    html = f.read()

# ── 1. INSERT NEW CSS after .radio-loading block ──────────────────────────────
OLD_CSS = """    .radio-loading {
      font-size: 10px;
      color: #444;
      letter-spacing: 1px;
      margin-top: 6px;
      animation: skeleton-pulse 1.4s ease-in-out infinite;
    }"""

NEW_CSS = OLD_CSS + """

    /* ── RADIO HERO CARD ──────────────────────────────── */
    .radio-hero {
      background: #e10600;
      border-radius: 6px;
      padding: 14px 16px;
      margin-bottom: 10px;
      cursor: pointer;
      flex-shrink: 0;
      transition: background .15s;
    }
    .radio-hero:hover { background: #c50500; }

    .radio-hero-live {
      display: flex;
      align-items: center;
      gap: 7px;
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: rgba(255,255,255,0.7);
      margin-bottom: 10px;
    }

    .radio-hero-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #fff;
      flex-shrink: 0;
      animation: wjh-blink 1.2s ease-in-out infinite;
    }

    .radio-hero-msg {
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 16px;
      color: #fff;
      line-height: 1.5;
      font-style: italic;
      margin-bottom: 10px;
    }

    .radio-hero-msg.listening {
      font-size: 13px;
      color: rgba(255,255,255,0.65);
      animation: skeleton-pulse 2s ease-in-out infinite;
      font-style: normal;
    }

    .radio-hero-meta {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .radio-hero-driver {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 1px;
      color: rgba(255,255,255,0.85);
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .radio-translate-badge {
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      background: rgba(255,255,255,0.18);
      color: #fff;
      padding: 4px 9px;
      border-radius: 20px;
      white-space: nowrap;
    }

    /* ── RADIO FULL VIEW ─────────────────────────────── */
    .radio-full-view {
      position: absolute;
      inset: 0;
      background: #0d0d0d;
      z-index: 20;
      display: flex;
      flex-direction: column;
    }

    .radio-full-hdr {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
      border-bottom: 1px solid #1a1a1a;
      flex-shrink: 0;
    }

    .radio-back-btn {
      background: none;
      border: none;
      color: var(--red);
      font-family: 'Titillium Web', sans-serif;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1px;
      cursor: pointer;
      padding: 0;
    }

    .radio-full-title {
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      color: #555;
    }

    .radio-full-body {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
    }

    .radio-full-latest {
      background: #161616;
      border-radius: 6px;
      padding: 14px;
      margin-bottom: 16px;
    }

    .radio-full-call-driver {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 1px;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 10px;
    }

    .radio-full-call-msg {
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 15px;
      color: #fff;
      font-style: italic;
      line-height: 1.55;
      margin-bottom: 14px;
    }

    .radio-full-section { margin-bottom: 12px; }

    .radio-full-section-label {
      font-size: 8px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: var(--red);
      margin-bottom: 5px;
    }

    .radio-full-section-text {
      font-size: 12px;
      color: #ccc;
      line-height: 1.55;
    }

    .radio-full-divider {
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: #333;
      margin: 14px 0 10px;
    }

    .radio-full-entry {
      padding: 10px 0;
      border-bottom: 1px solid #161616;
      cursor: pointer;
    }
    .radio-full-entry:last-child { border-bottom: none; }

    .radio-full-entry-driver {
      font-size: 10px;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 5px;
    }

    .radio-full-entry-msg {
      font-size: 12px;
      color: #aaa;
      font-style: italic;
      line-height: 1.4;
    }

    .radio-full-entry-expand {
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid #1e1e1e;
    }"""

assert OLD_CSS in html, "CSS anchor not found"
html = html.replace(OLD_CSS, NEW_CSS, 1)
print("CSS inserted OK")

# ── 2. REPLACE chat-panel HTML ────────────────────────────────────────────────
OLD_CHAT = """  <!-- CHAT PANEL -->
  <div class="chat-panel">
    <div class="panel-hdr">
      <div class="panel-hdr-title">Ask The Grid AI</div>
    </div>

    <button class="wjh-btn" id="wjhBtn" onclick="wjhClick()">
      <span class="wjh-pulse"></span>
      What just happened?
    </button>"""

NEW_CHAT = """  <!-- CHAT PANEL -->
  <div class="chat-panel" style="position:relative">
    <div class="panel-hdr">
      <div class="panel-hdr-title">Ask The Grid AI</div>
    </div>

    <!-- RADIO HERO CARD -->
    <div class="radio-hero" id="radioHero" onclick="openRadioView()">
      <div class="radio-hero-live">
        <span class="radio-hero-dot"></span>
        Team Radio &middot; Live
      </div>
      <div class="radio-hero-msg listening" id="radioHeroMsg">Listening for team radio&hellip;</div>
      <div class="radio-hero-meta" id="radioHeroMeta" style="display:none">
        <div class="radio-hero-driver" id="radioHeroDriver"></div>
        <div class="radio-translate-badge">Tap to translate &rarr;</div>
      </div>
    </div>

    <!-- RADIO FULL VIEW OVERLAY -->
    <div class="radio-full-view" id="radioFullView" style="display:none">
      <div class="radio-full-hdr">
        <button class="radio-back-btn" onclick="closeRadioView()">&larr; Back</button>
        <span class="radio-full-title">Team Radio &middot; Live</span>
      </div>
      <div class="radio-full-body" id="radioFullBody"></div>
    </div>

    <button class="wjh-btn" id="wjhBtn" onclick="wjhClick()">
      <span class="wjh-pulse"></span>
      What just happened?
    </button>"""

assert OLD_CHAT in html, "Chat HTML anchor not found"
html = html.replace(OLD_CHAT, NEW_CHAT, 1)
print("Chat HTML updated OK")

# ── 3. REMOVE team radio info-card from side-cards ────────────────────────────
OLD_RADIO_CARD = """    <!-- Team Radio -->
    <div class="info-card">
      <div class="card-title">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
        Team Radio
      </div>
      <div class="card-body" id="radioCard">
        <div class="radio-entry">
          <div class="radio-driver">
            <span class="team-dot" style="background:#FF8000"></span>
            Norris
            <span class="radio-team-label">McLaren</span>
          </div>
          <div class="radio-msg">"Tyres are completely dead, man. Massive sliding."</div>
          <div class="radio-divider"></div>
          <div class="radio-meaning-label">What this means:</div>
          <div class="radio-meaning-text">His tyres have worn down so much the car is sliding around uncontrollably.</div>
          <div class="radio-hook">He has to pit soon or he'll lose positions fast.</div>
        </div>
        <div class="radio-entry">
          <div class="radio-driver">
            <span class="team-dot" style="background:#3671C6"></span>
            Verstappen
            <span class="radio-team-label">Red Bull</span>
          </div>
          <div class="radio-msg">"What's the gap? Can we close it on fresher rubber?"</div>
          <div class="radio-divider"></div>
          <div class="radio-meaning-label">What this means:</div>
          <div class="radio-meaning-text">He's asking how far behind the leader is, hoping new tyres give him the speed to catch up.</div>
          <div class="radio-hook">If the gap is small enough, this could set up a dramatic late charge.</div>
        </div>
      </div>
    </div>

    <!-- Race Incidents -->"""

NEW_RADIO_CARD = """    <!-- Race Incidents -->"""

assert OLD_RADIO_CARD in html, "Radio card HTML anchor not found"
html = html.replace(OLD_RADIO_CARD, NEW_RADIO_CARD, 1)
print("Side radio card removed OK")

# ── 4. REPLACE JS radio functions ────────────────────────────────────────────
OLD_JS = """const _radioTranslations = new Map(); // key \u2192 'loading' | 'error' | { meaning, hook }

function _radioKey(r) {
  return `${r.driver}|${r.team}|${r.message || r.msg || r.text || r.url || ''}`;
}

function renderRadio(radio) {
  const el = document.getElementById('radioCard');
  if (!el) return;
  if (!radio || !radio.length) {
    el.innerHTML = '<div style="color:var(--gray);font-size:11px;">No team radio available</div>';
    return;
  }

  // Newest first
  el.innerHTML = [...radio].reverse().map(r => {
    const key    = _radioKey(r);
    const msg    = r.message || r.msg || r.text || '';
    const cached = _radioTranslations.get(key);
    const clr    = _teamColor(r.team);

    let translationHtml = '';
    if (msg) {
      if (!cached || cached === 'loading') {
        translationHtml = `<div class="radio-loading">Translating\u2026</div>`;
      } else if (cached !== 'error') {
        translationHtml = `
          <div class="radio-divider"></div>
          <div class="radio-meaning-label">What this means:</div>
          <div class="radio-meaning-text">${escapeHtml(cached.meaning)}</div>
          <div class="radio-hook">${escapeHtml(cached.hook)}</div>`;
      }
    }

    return `
      <div class="radio-entry">
        <div class="radio-driver">
          <span class="team-dot" style="background:${clr}"></span>
          ${escapeHtml(r.driver)}
          <span class="radio-team-label">${escapeHtml(r.team)}</span>
        </div>
        ${msg ? `<div class="radio-msg">"${escapeHtml(msg)}"</div>` : ''}
        ${r.url ? `<audio controls style="width:100%;height:22px;margin-top:6px;" src="${escapeHtml(r.url)}"></audio>` : ''}
        ${translationHtml}
      </div>`;
  }).join('');

  // Kick off translation for any new messages not yet cached
  radio.forEach(r => {
    const key = _radioKey(r);
    const msg = r.message || r.msg || r.text || '';
    if (msg && !_radioTranslations.has(key)) {
      _translateRadio(r);
    }
  });
}

async function _translateRadio(r) {
  const key = _radioKey(r);
  const msg = r.message || r.msg || r.text || '';
  if (!msg || _radioTranslations.has(key)) return;

  _radioTranslations.set(key, 'loading');
  if (liveData.radio) renderRadio(liveData.radio);

  try {
    const res = await fetch(`${BACKEND}/api/chat`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        system: `You are explaining F1 team radio messages to a brand new F1 fan who knows nothing about racing. When given a radio message reply with EXACTLY 2 lines and nothing else:
Line 1: Explain what the message means in plain English, one sentence maximum.
Line 2: Explain why it matters for the race outcome, one sentence with an emotional hook.
Never use F1 jargon without explaining it first. Be exciting but very brief. Two lines only.`,
        messages: [{ role: 'user', content: `Driver: ${r.driver} (${r.team})\\nRadio message: "${msg}"` }],
      }),
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const lines = (data.reply || '').trim().split('\\n').map(l => l.trim()).filter(Boolean);
    _radioTranslations.set(key, {
      meaning: lines[0] || '',
      hook:    lines[1] || '',
    });
  } catch {
    _radioTranslations.set(key, 'error');
  }

  if (liveData.radio) renderRadio(liveData.radio);
}"""

NEW_JS = """const _radioTranslations = new Map(); // key -> 'loading' | 'error' | { what, why, next }
let _radioFullOpen = false;

function _radioKey(r) {
  return `${r.driver}|${r.team}|${r.message || r.msg || r.text || r.url || ''}`;
}

function renderRadio(radio) {
  const heroMsg  = document.getElementById('radioHeroMsg');
  const heroMeta = document.getElementById('radioHeroMeta');
  const heroDrv  = document.getElementById('radioHeroDriver');
  if (!heroMsg) return;

  if (!radio || !radio.length) {
    heroMsg.textContent = 'Listening for team radio\u2026';
    heroMsg.classList.add('listening');
    if (heroMeta) heroMeta.style.display = 'none';
    if (_radioFullOpen) renderRadioFullView(radio);
    return;
  }

  const sorted = [...radio].reverse();
  const latest = sorted[0];
  const msg    = latest.message || latest.msg || latest.text || '';
  const clr    = _teamColor(latest.team);

  heroMsg.textContent = msg ? `"${msg}"` : 'Radio call received';
  heroMsg.classList.remove('listening');

  if (heroMeta) heroMeta.style.display = 'flex';
  if (heroDrv)  heroDrv.innerHTML =
    `<span style="width:8px;height:8px;border-radius:50%;background:${clr};flex-shrink:0;display:inline-block"></span>
     ${escapeHtml(latest.driver)} &middot; ${escapeHtml(latest.team)}`;

  sorted.forEach(r => {
    const key = _radioKey(r);
    const m   = r.message || r.msg || r.text || '';
    if (m && !_radioTranslations.has(key)) _translateRadio(r);
  });

  if (_radioFullOpen) renderRadioFullView(radio);
}

function openRadioView() {
  _radioFullOpen = true;
  const el = document.getElementById('radioFullView');
  if (el) el.style.display = 'flex';
  renderRadioFullView(liveData.radio);
}

function closeRadioView() {
  _radioFullOpen = false;
  const el = document.getElementById('radioFullView');
  if (el) el.style.display = 'none';
}

function _radioSectionHtml(cached) {
  if (!cached || cached === 'loading') {
    return `<div class="radio-loading">Translating\u2026</div>`;
  }
  if (cached === 'error') {
    return `<div class="radio-loading" style="color:#444">Translation unavailable</div>`;
  }
  return `
    <div class="radio-full-section">
      <div class="radio-full-section-label">What it means</div>
      <div class="radio-full-section-text">${escapeHtml(cached.what)}</div>
    </div>
    <div class="radio-full-section">
      <div class="radio-full-section-label">Why it matters</div>
      <div class="radio-full-section-text">${escapeHtml(cached.why)}</div>
    </div>
    <div class="radio-full-section">
      <div class="radio-full-section-label">What happens next</div>
      <div class="radio-full-section-text">${escapeHtml(cached.next)}</div>
    </div>`;
}

function renderRadioFullView(radio) {
  const body = document.getElementById('radioFullBody');
  if (!body) return;

  if (!radio || !radio.length) {
    body.innerHTML = `<div style="color:#555;font-size:12px;padding:20px 0">Listening for team radio\u2026</div>`;
    return;
  }

  const sorted = [...radio].reverse();
  const latest = sorted[0];
  const latestKey    = _radioKey(latest);
  const latestMsg    = latest.message || latest.msg || latest.text || '';
  const latestClr    = _teamColor(latest.team);
  const latestCached = _radioTranslations.get(latestKey);

  let out = `
    <div class="radio-full-latest">
      <div class="radio-full-call-driver">
        <span style="width:8px;height:8px;border-radius:50%;background:${latestClr};flex-shrink:0;display:inline-block"></span>
        ${escapeHtml(latest.driver)} &middot; ${escapeHtml(latest.team)}
      </div>
      ${latestMsg ? `<div class="radio-full-call-msg">"${escapeHtml(latestMsg)}"</div>` : ''}
      ${_radioSectionHtml(latestCached)}
    </div>`;

  if (sorted.length > 1) {
    out += `<div class="radio-full-divider">Earlier calls</div>`;
    sorted.slice(1).forEach((r, i) => {
      const key    = _radioKey(r);
      const msg    = r.message || r.msg || r.text || '';
      const clr    = _teamColor(r.team);
      const cached = _radioTranslations.get(key);
      const eid    = `rfe_${i}`;
      out += `
        <div class="radio-full-entry" onclick="_toggleRadioEntry('${eid}')">
          <div class="radio-full-entry-driver">
            <span style="width:7px;height:7px;border-radius:50%;background:${clr};flex-shrink:0;display:inline-block"></span>
            ${escapeHtml(r.driver)} &middot; ${escapeHtml(r.team)}
          </div>
          ${msg ? `<div class="radio-full-entry-msg">"${escapeHtml(msg)}"</div>` : ''}
          <div class="radio-full-entry-expand" id="${eid}" style="display:none">
            ${_radioSectionHtml(cached)}
          </div>
        </div>`;
    });
  }

  body.innerHTML = out;
}

function _toggleRadioEntry(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}

async function _translateRadio(r) {
  const key = _radioKey(r);
  const msg = r.message || r.msg || r.text || '';
  if (!msg || _radioTranslations.has(key)) return;

  _radioTranslations.set(key, 'loading');
  if (liveData.radio) renderRadio(liveData.radio);

  try {
    const res = await fetch(`${BACKEND}/api/chat`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        system: `You are explaining F1 team radio to a brand new fan. Reply with EXACTLY 3 lines, nothing else.
Line 1: Plain English explanation of what the message means, one sentence.
Line 2: Why this matters for the race, one sentence.
Line 3: What will likely happen next because of this, one sentence.
No labels, no jargon, no extra lines. Three sentences only.`,
        messages: [{ role: 'user', content: `Driver: ${r.driver} (${r.team})\\nRadio: "${msg}"` }],
      }),
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const lines = (data.reply || '').trim().split('\\n').map(l => l.trim()).filter(Boolean);
    _radioTranslations.set(key, {
      what: lines[0] || '',
      why:  lines[1] || '',
      next: lines[2] || '',
    });
  } catch {
    _radioTranslations.set(key, 'error');
  }

  if (liveData.radio) renderRadio(liveData.radio);
}"""

assert OLD_JS in html, "JS anchor not found"
html = html.replace(OLD_JS, NEW_JS, 1)
print("JS updated OK")

with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("File saved OK")
