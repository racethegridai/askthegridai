import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('pitwall-ai.html', 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. REPLACE CSS ────────────────────────────────────────────────────────────
css_old_start = '    .drv-tab-wrap {'
css_old_end   = '      .drv-grid { grid-template-columns: repeat(2, 1fr); }\n    }'
i1 = content.find(css_old_start)
i2 = content.find(css_old_end) + len(css_old_end)
assert i1 != -1 and i2 > i1, 'CSS markers not found'

NEW_CSS = """    /* ── DRIVERS TAB ──────────────────────────────── */
    .drv-tab-wrap { flex:1; display:flex; flex-direction:column; overflow:hidden; min-height:0; }

    /* Grid view */
    .drv-grid-view { flex:1; display:flex; flex-direction:column; overflow:hidden; min-height:0; }
    .drv-search-bar { flex-shrink:0; padding:10px 16px; border-bottom:1px solid var(--border); }
    .drv-search-input { width:100%; background:#111; border:1px solid var(--border); color:var(--white);
      padding:8px 14px; font-family:'Titillium Web',sans-serif; font-size:12px; outline:none; }
    .drv-search-input:focus { border-color:var(--red); }
    .drv-search-input::placeholder { color:#333; }
    .drv-grid-scroll { flex:1; overflow-y:auto; padding:16px 20px; }
    .drv-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }

    /* Driver card */
    .drv-card { background:var(--bg2); border:1px solid var(--border); padding:14px;
      cursor:pointer; position:relative; transition:border-color .15s, background .15s; border-radius:6px; }
    .drv-card:hover { border-color:var(--red); background:rgba(225,6,0,.05); }
    .drv-card-top { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
    .drv-card-helmet { width:44px; height:44px; border-radius:50%; display:flex; align-items:center;
      justify-content:center; font-size:11px; font-weight:900; flex-shrink:0; letter-spacing:.5px; }
    .drv-card-meta { flex:1; min-width:0; }
    .drv-card-name { font-size:14px; font-weight:700; color:var(--white); white-space:nowrap;
      overflow:hidden; text-overflow:ellipsis; }
    .drv-card-team { font-size:10px; color:#555; margin-top:2px; text-transform:uppercase; letter-spacing:.5px; }
    .drv-card-num-sm { font-size:10px; font-weight:700; color:#333; margin-top:2px; }
    .drv-card-arrow { position:absolute; top:12px; right:12px; color:#2a2a2a; font-size:16px;
      transition:color .15s; line-height:1; }
    .drv-card:hover .drv-card-arrow { color:var(--red); }
    .drv-pos-badge { display:inline-block; font-size:9px; font-weight:900; padding:3px 8px;
      border-radius:2px; margin-bottom:8px; letter-spacing:.5px; }
    .drv-pos-p1 { background:#ffd700; color:#000; }
    .drv-pos-p2 { background:#C0C0C0; color:#000; }
    .drv-pos-p3 { background:#CD7F32; color:#fff; }
    .drv-pos-pn { background:#1a1a1a; color:#555; }
    .drv-card-stats { display:grid; grid-template-columns:1fr 1fr; gap:4px; margin-bottom:8px; }
    .drv-card-stat { text-align:center; background:#0d0d0d; border-radius:3px; padding:5px 4px; }
    .drv-card-stat-num { font-size:14px; font-weight:700; color:var(--white); }
    .drv-card-stat-lbl { font-size:8px; color:#444; text-transform:uppercase; letter-spacing:.5px; }
    .drv-card-nat { font-size:9px; color:#444; text-align:center; }

    /* Profile view */
    .drv-profile-view { flex:1; display:flex; flex-direction:column; overflow:hidden; min-height:0; }
    .drv-profile-hdr { flex-shrink:0; display:flex; align-items:center; gap:12px;
      padding:10px 16px; border-bottom:1px solid var(--border); }
    .drv-back-btn { background:transparent; border:1px solid #2a2a2a; color:#888;
      padding:6px 14px; font-family:'Titillium Web',sans-serif; font-size:10px; font-weight:700;
      letter-spacing:1.5px; text-transform:uppercase; cursor:pointer;
      transition:border-color .15s, color .15s; white-space:nowrap; }
    .drv-back-btn:hover { border-color:var(--red); color:var(--red); }
    .drv-profile-breadcrumb { font-size:12px; color:#444; }
    .drv-profile-body { flex:1; display:flex; overflow:hidden; min-height:0; }

    /* Bio left column */
    .drv-bio-col { width:280px; flex-shrink:0; border-right:1px solid var(--border);
      background:var(--bg2); overflow-y:auto; padding:20px; }
    .drv-bio-helmet { width:72px; height:72px; border-radius:50%; display:flex;
      align-items:center; justify-content:center; font-size:20px; font-weight:900;
      margin:0 auto 10px; }
    .drv-bio-name { font-size:18px; font-weight:900; text-align:center; letter-spacing:1px; margin-bottom:2px; }
    .drv-bio-num { font-size:13px; font-weight:900; color:var(--red); text-align:center; margin-bottom:3px; }
    .drv-bio-team { font-size:11px; color:#555; text-align:center; margin-bottom:14px; }
    .drv-bio-divider { height:1px; background:var(--border); margin:12px 0; }
    .drv-bio-stitle { font-size:9px; font-weight:700; color:var(--red); letter-spacing:2px;
      text-transform:uppercase; margin:10px 0 7px; }
    .drv-bio-row { display:flex; justify-content:space-between; align-items:center; padding:4px 0; }
    .drv-bio-lbl { font-size:11px; color:#444; }
    .drv-bio-val { font-size:11px; font-weight:700; color:var(--white); text-align:right; max-width:55%; }
    .drv-bio-val.gold { color:var(--yellow); }
    .drv-bio-val.red  { color:var(--red); }
    .drv-bio-fact { display:flex; gap:8px; margin-bottom:6px; align-items:flex-start; }
    .drv-bio-fact-dot { width:4px; height:4px; border-radius:50%; background:var(--red);
      flex-shrink:0; margin-top:5px; }
    .drv-bio-fact-txt { font-size:11px; color:#888; line-height:1.5; }
    .drv-bio-tl { padding:5px 0; border-bottom:1px solid #111; font-size:11px; color:#888; line-height:1.4; }
    .drv-bio-tl:last-child { border-bottom:none; }
    .drv-bio-tl-yr { color:var(--yellow); font-weight:700; margin-right:4px; }

    /* Right content column */
    .drv-content-col { flex:1; overflow-y:auto; padding:20px; min-width:0; }
    .drv-content-stitle { font-size:9px; font-weight:700; color:var(--red); letter-spacing:2px;
      text-transform:uppercase; margin-bottom:12px; }
    .drv-perf-cards { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-bottom:20px; }
    .drv-perf-card { background:#111; border:1px solid var(--border); border-radius:4px;
      padding:12px; text-align:center; }
    .drv-perf-num { font-size:22px; font-weight:900; color:var(--white); line-height:1; }
    .drv-perf-num.gold { color:var(--yellow); }
    .drv-perf-num.red  { color:var(--red); }
    .drv-perf-lbl { font-size:8px; color:#444; text-transform:uppercase; letter-spacing:.8px; margin-top:4px; }

    /* AI section */
    .drv-ai-wrap { border:1px solid var(--border); border-radius:4px; overflow:hidden; }
    .drv-ai-hdr { background:var(--bg2); padding:11px 14px; border-bottom:1px solid var(--border);
      display:flex; align-items:center; justify-content:space-between; }
    .drv-ai-title { font-size:12px; font-weight:700; color:var(--white); letter-spacing:.5px; }
    .drv-ai-pro { background:var(--red); color:#fff; font-size:9px; font-weight:900;
      padding:3px 8px; letter-spacing:1px; }
    .drv-ai-body { padding:14px; }

    /* Locked overlay */
    .drv-lock { text-align:center; padding:4px 0; }
    .drv-lock-icon { font-size:26px; margin-bottom:10px; }
    .drv-lock-title { font-size:14px; font-weight:700; color:var(--white); margin-bottom:6px; }
    .drv-lock-sub { font-size:11px; color:#555; margin-bottom:14px; line-height:1.5; }
    .drv-lock-chips { display:flex; flex-wrap:wrap; gap:6px; justify-content:center; margin-bottom:14px; }
    .drv-lock-chip { padding:6px 12px; border:1px solid #1a1a1a; border-radius:20px;
      font-size:11px; color:#333; filter:blur(2px); }
    .drv-lock-btn { width:100%; background:var(--red); color:#fff; border:none; padding:11px;
      font-size:12px; font-weight:900; letter-spacing:1px; cursor:pointer;
      font-family:'Titillium Web',sans-serif; text-transform:uppercase; margin-bottom:6px;
      transition:background .15s; border-radius:3px; }
    .drv-lock-btn:hover { background:#c50500; }
    .drv-lock-price { font-size:10px; color:var(--red); }

    /* Pro chat elements */
    .drv-chips { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px; }
    .drv-chip { padding:7px 12px; border:1px solid #2a2a2a; background:transparent; color:#999;
      font-family:'Titillium Web',sans-serif; font-size:11px; font-weight:600; cursor:pointer;
      border-radius:20px; transition:all .15s; white-space:nowrap; }
    .drv-chip:hover { border-color:var(--red); color:var(--white); background:var(--red-dim); }
    .drv-chat-msgs { display:flex; flex-direction:column; gap:10px; margin-bottom:12px; min-height:20px; }
    .drv-input-row { display:flex; border:1px solid #2a2a2a; border-radius:2px; overflow:hidden; }
    .drv-chat-input { flex:1; background:#111; border:none; color:var(--white);
      font-family:'Titillium Web',sans-serif; font-size:12px; padding:10px 12px; outline:none; }
    .drv-chat-input::placeholder { color:#333; }
    .drv-send-btn { background:var(--red); color:#fff; border:none; padding:0 18px;
      font-family:'Titillium Web',sans-serif; font-size:11px; font-weight:900; letter-spacing:1.5px;
      text-transform:uppercase; cursor:pointer; flex-shrink:0; transition:background .15s; }
    .drv-send-btn:hover { background:#c50500; }
    .drv-send-btn:disabled { background:#2a2a2a; cursor:not-allowed; }

    @media (max-width: 1200px) { .drv-grid { grid-template-columns: repeat(3, 1fr); } }
    @media (max-width: 900px)  { .drv-grid { grid-template-columns: repeat(2, 1fr); }
      .drv-perf-cards { grid-template-columns: repeat(2, 1fr); }
      .drv-bio-col { width:240px; } }
    @media (max-width: 600px)  { .drv-grid { grid-template-columns: 1fr; }
      .drv-profile-body { flex-direction: column; }
      .drv-bio-col { width:100%; border-right:none; border-bottom:1px solid var(--border); } }"""

content = content[:i1] + NEW_CSS + content[i2:]
print('CSS replaced')

# ── 2. REPLACE HTML ───────────────────────────────────────────────────────────
html_old_start = '<!-- \u2500\u2500\u2500 TAB: DRIVERS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 -->'
html_old_end   = '</div>\n\n</div><!-- /tab-view -->'
h1 = content.find(html_old_start)
h2 = content.find(html_old_end, h1)
assert h1 != -1 and h2 != -1, 'HTML markers not found'

NEW_HTML = """<!-- \u2500\u2500\u2500 TAB: DRIVERS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 -->
<div class="tab-panel" id="tab-drivers">
  <div class="drv-tab-wrap">
    <!-- GRID VIEW -->
    <div class="drv-grid-view" id="drvGridView">
      <div class="panel-hdr">
        <div>
          <div class="panel-hdr-title" style="color:var(--red)">2026 F1 Driver Profiles</div>
          <div class="panel-hdr-meta">Click any driver \u2192 free bio + Pro AI chat</div>
        </div>
        <div class="panel-hdr-meta" style="align-self:center">22 Drivers</div>
      </div>
      <div class="drv-search-bar">
        <input class="drv-search-input" id="drvSearchInput"
          placeholder="Search driver or team\u2026" oninput="_drvSearchFilter()">
      </div>
      <div class="drv-grid-scroll">
        <div class="drv-grid" id="drvGrid"></div>
      </div>
    </div>
    <!-- PROFILE VIEW (hidden until a card is clicked) -->
    <div class="drv-profile-view" id="drvProfileView" style="display:none"></div>
  </div>
</div>

</div><!-- /tab-view -->"""

content = content[:h1] + NEW_HTML + content[h2 + len(html_old_end):]
print('HTML replaced')

# ── 3. REPLACE renderDriversGrid ─────────────────────────────────────────────
jg1 = content.find('function renderDriversGrid() {')
jg_end_sig = '}\n\n/* '
jg2 = content.find(jg_end_sig, jg1) + 1  # keep the }
assert jg1 != -1 and jg2 > jg1, 'renderDriversGrid not found'

NEW_GRID_FN = r"""function _helmtText(tc) {
  const hex = (tc || '#888888').replace('#','');
  const r = parseInt(hex.substr(0,2),16)||0;
  const g = parseInt(hex.substr(2,2),16)||0;
  const b = parseInt(hex.substr(4,2),16)||0;
  return (0.299*r + 0.587*g + 0.114*b)/255 > 0.55 ? '#000' : '#fff';
}

function _drvLivePos(d) {
  if (_chmpData && _chmpData.standings) {
    const s = _chmpData.standings.find(x =>
      x.driver.toLowerCase() === d.surname.toLowerCase());
    if (s) return {pos: s.position, pts: s.points, wins: s.wins};
  }
  return {pos: d.cp, pts: d.pts, wins: d.sw};
}

function _drvSearchFilter() {
  const q = (document.getElementById('drvSearchInput')?.value || '').toLowerCase().trim();
  document.querySelectorAll('#drvGrid .drv-card').forEach(card => {
    const name = (card.dataset.name || '').toLowerCase();
    const team = (card.dataset.team || '').toLowerCase();
    card.style.display = (!q || name.includes(q) || team.includes(q)) ? '' : 'none';
  });
}

function renderDriversGrid() {
  const grid = document.getElementById('drvGrid');
  if (!grid) return;
  const sorted = [...DRIVERS].sort((a, b) => a.cp - b.cp);
  grid.innerHTML = sorted.map(d => {
    const {pos, pts, wins} = _drvLivePos(d);
    const badgeCls = pos===1?'drv-pos-p1':pos===2?'drv-pos-p2':pos===3?'drv-pos-p3':'drv-pos-pn';
    const tc = d.tc || '#888';
    return `
      <div class="drv-card" data-name="${escapeHtml(d.name.toLowerCase())}" data-team="${escapeHtml(d.team.toLowerCase())}"
           onclick="openDriverProfile('${d.id}')">
        <div class="drv-card-top">
          <div class="drv-card-helmet" style="background:${tc};color:${_helmtText(tc)}">${d.code}</div>
          <div class="drv-card-meta">
            <div class="drv-card-name">${escapeHtml(d.name)}</div>
            <div class="drv-card-team">${escapeHtml(d.team)}</div>
            <div class="drv-card-num-sm">#${d.num}</div>
          </div>
        </div>
        <div class="drv-card-arrow">\u203a</div>
        <div class="drv-pos-badge ${badgeCls}">P${pos} \u00b7 ${pts} pts</div>
        <div class="drv-card-stats">
          <div class="drv-card-stat">
            <div class="drv-card-stat-num">${wins}</div>
            <div class="drv-card-stat-lbl">Wins</div>
          </div>
          <div class="drv-card-stat">
            <div class="drv-card-stat-num">${d.sp}</div>
            <div class="drv-card-stat-lbl">Podiums</div>
          </div>
        </div>
        <div class="drv-card-nat">${d.flag} ${escapeHtml(d.nat)} \u00b7 Age ${d.age}</div>
      </div>`;
  }).join('');
}"""

content = content[:jg1] + NEW_GRID_FN + content[jg2:]
print('renderDriversGrid replaced')

# ── 4. REPLACE openDriverProfile (update breadcrumb logic) ───────────────────
old_open = """function openDriverProfile(id) {
  const driver = DRIVERS.find(d => d.id === id);
  if (!driver) return;
  _activeDrvId = id;
  if (!_drvHistories[id]) _drvHistories[id] = [];

  const gridView    = document.getElementById('drvGridView');
  const profileView = document.getElementById('drvProfileView');
  gridView.style.display    = 'none';
  profileView.style.display = 'flex';
  profileView.innerHTML     = _buildProfileHTML(driver);
  _renderDrvMsgs(id);
}"""
# same logic, already correct - no change needed for openDriverProfile

# ── 5. REPLACE _buildProfileHTML ─────────────────────────────────────────────
jp1 = content.find('function _buildProfileHTML(d) {')
jp_end_sig = '}\n\n/* \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n   DRIVER PROFILE CHAT'
jp2 = content.find(jp_end_sig, jp1) + 1
assert jp1 != -1 and jp2 > jp1, '_buildProfileHTML not found'

NEW_PROF_FN = r"""function _buildProfileHTML(d) {
  const isPro = isOwnerMode();

  /* Live standings merge */
  let {pos, pts, wins} = _drvLivePos(d);
  let gapToLeader = 'LEADER';
  if (_chmpData && _chmpData.standings && pos !== 1) {
    const leaderPts = _chmpData.standings[0]?.points ?? pts;
    gapToLeader = '\u2212' + (leaderPts - pts);
  } else if (pos !== 1) {
    const ld = DRIVERS.find(x => x.cp === 1);
    gapToLeader = '\u2212' + (ld ? ld.pts - d.pts : 0);
  }

  /* Timeline parsing */
  const tlHTML = d.tl.map(t => {
    const dash = t.indexOf(' \u2014 ');
    const yr   = dash > -1 ? t.substring(0, dash) : '';
    const txt  = dash > -1 ? t.substring(dash + 3) : t;
    return `<div class="drv-bio-tl"><span class="drv-bio-tl-yr">${escapeHtml(yr)}</span>${escapeHtml(txt)}<\/div>`;
  }).join('');

  /* AI section */
  let aiHTML;
  if (isPro) {
    const qs = [
      `Where did ${d.surname} grow up?`,
      `What makes ${d.surname} special as a driver?`,
      `What is ${d.surname}'s biggest career moment?`,
      `Who is ${d.surname}'s biggest rival?`
    ];
    aiHTML = `
      <div class="drv-chips">
        ${qs.map(q => `<button class="drv-chip" onclick="drvChipClick('${d.id}',this)">${escapeHtml(q)}<\/button>`).join('')}
      <\/div>
      <div class="drv-chat-msgs" id="drvMsgs_${d.id}"><\/div>
      <div class="drv-input-row">
        <input class="drv-chat-input" id="drvInput_${d.id}"
          placeholder="Ask anything about ${escapeHtml(d.name)}\u2026"
          onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendDriverMsg('${d.id}');}">
        <button class="drv-send-btn" id="drvSendBtn_${d.id}" onclick="sendDriverMsg('${d.id}')">ASK NOW<\/button>
      <\/div>`;
  } else {
    const fq = [
      `Where did ${d.surname} grow up?`,
      `What makes ${d.surname} special?`,
      `${d.surname}'s biggest rival?`
    ];
    aiHTML = `
      <div class="drv-lock">
        <div class="drv-lock-icon">\uD83D\uDD12<\/div>
        <div class="drv-lock-title">Ask AI anything about ${escapeHtml(d.name)}<\/div>
        <div class="drv-lock-sub">Get the full story \u2014 career, personality, rivalries, driving style, and what makes them special. In plain English, no F1 knowledge needed.<\/div>
        <div class="drv-lock-chips">
          ${fq.map(q => `<div class="drv-lock-chip">${escapeHtml(q)}<\/div>`).join('')}
        <\/div>
        <button class="drv-lock-btn" onclick="handleUpgradeClick()">Unlock Driver AI \u2014 $3\/month<\/button>
        <div class="drv-lock-price">Free during Miami GP weekend \u00b7 No credit card needed<\/div>
      <\/div>`;
  }

  const champClass = pos === 1 ? 'gold' : '';
  const tc = d.tc || '#888';

  return `
    <div class="drv-profile-hdr">
      <button class="drv-back-btn" onclick="closeDriverProfile()">\u2190 All Drivers<\/button>
      <span class="drv-profile-breadcrumb">${escapeHtml(d.name)} \u00b7 ${escapeHtml(d.team)}<\/span>
    <\/div>
    <div class="drv-profile-body">

      <!-- LEFT BIO -->
      <div class="drv-bio-col">
        <div class="drv-bio-helmet" style="background:${tc};color:${_helmtText(tc)}">${d.code}<\/div>
        <div class="drv-bio-name">${escapeHtml(d.name.toUpperCase())}<\/div>
        <div class="drv-bio-num">#${d.num}<\/div>
        <div class="drv-bio-team">${escapeHtml(d.team)}<\/div>

        <div class="drv-bio-divider"><\/div>
        <div class="drv-bio-stitle">2026 Season<\/div>
        <div class="drv-bio-row"><span class="drv-bio-lbl">Championship<\/span><span class="drv-bio-val ${champClass}">P${pos} \u00b7 ${pts} pts<\/span><\/div>
        <div class="drv-bio-row"><span class="drv-bio-lbl">Wins<\/span><span class="drv-bio-val">${wins}<\/span><\/div>
        <div class="drv-bio-row"><span class="drv-bio-lbl">Podiums<\/span><span class="drv-bio-val">${d.sp}<\/span><\/div>

        <div class="drv-bio-divider"><\/div>
        <div class="drv-bio-stitle">Career Stats<\/div>
        <div class="drv-bio-row"><span class="drv-bio-lbl">Total Races<\/span><span class="drv-bio-val">${d.cr.races}<\/span><\/div>
        <div class="drv-bio-row"><span class="drv-bio-lbl">Total Wins<\/span><span class="drv-bio-val">${d.cr.wins}<\/span><\/div>
        <div class="drv-bio-row"><span class="drv-bio-lbl">Total Podiums<\/span><span class="drv-bio-val">${d.cr.pods}<\/span><\/div>
        <div class="drv-bio-row"><span class="drv-bio-lbl">First Race<\/span><span class="drv-bio-val" style="font-size:10px">${escapeHtml(d.cr.fr)}<\/span><\/div>
        <div class="drv-bio-row"><span class="drv-bio-lbl">First Win<\/span><span class="drv-bio-val ${d.cr.fw==='—'?'':'red'}" style="font-size:10px">${d.cr.fw==='—'?'None yet':escapeHtml(d.cr.fw)}<\/span><\/div>

        <div class="drv-bio-divider"><\/div>
        <div class="drv-bio-stitle">Fast Facts<\/div>
        <div class="drv-bio-fact"><div class="drv-bio-fact-dot"><\/div><div class="drv-bio-fact-txt">Born in ${escapeHtml(d.pf.home)} \u00b7 Age ${d.age}<\/div><\/div>
        <div class="drv-bio-fact"><div class="drv-bio-fact-dot"><\/div><div class="drv-bio-fact-txt">Started karting at age ${d.pf.kart}<\/div><\/div>
        <div class="drv-bio-fact"><div class="drv-bio-fact-dot"><\/div><div class="drv-bio-fact-txt">Known for: ${escapeHtml(d.pf.known)}<\/div><\/div>
        <div class="drv-bio-fact"><div class="drv-bio-fact-dot"><\/div><div class="drv-bio-fact-txt">${escapeHtml(d.pf.fun)}<\/div><\/div>

        <div class="drv-bio-divider"><\/div>
        <div class="drv-bio-stitle">Career Path to F1<\/div>
        ${tlHTML}
      <\/div>

      <!-- RIGHT CONTENT -->
      <div class="drv-content-col">
        <div class="drv-content-stitle">Season Performance<\/div>
        <div class="drv-perf-cards">
          <div class="drv-perf-card"><div class="drv-perf-num ${champClass}">P${pos}<\/div><div class="drv-perf-lbl">Championship<\/div><\/div>
          <div class="drv-perf-card"><div class="drv-perf-num gold">${pts}<\/div><div class="drv-perf-lbl">Points<\/div><\/div>
          <div class="drv-perf-card"><div class="drv-perf-num">${d.sp}<\/div><div class="drv-perf-lbl">Podiums<\/div><\/div>
          <div class="drv-perf-card"><div class="drv-perf-num ${pos===1?'':'red'}" style="font-size:${gapToLeader==='LEADER'?'13px':'22px'}">${gapToLeader}<\/div><div class="drv-perf-lbl">Gap to Leader<\/div><\/div>
        <\/div>

        <div class="drv-content-stitle">Ask AI about ${escapeHtml(d.name)}<\/div>
        <div class="drv-ai-wrap">
          <div class="drv-ai-hdr">
            <span class="drv-ai-title">AI Driver Intelligence<\/span>
            <span class="drv-ai-pro">PRO<\/span>
          <\/div>
          <div class="drv-ai-body">${aiHTML}<\/div>
        <\/div>
      <\/div>

    <\/div>`;
}"""

content = content[:jp1] + NEW_PROF_FN + content[jp2:]
print('_buildProfileHTML replaced')

# ── 6. UPDATE _renderDrvMsgs to use new class names ───────────────────────────
old_msgs = """function _renderDrvMsgs(id) {
  const el = document.getElementById(`drvMsgs_${id}`);
  if (!el) return;
  const hist = _drvHistories[id] || [];
  el.innerHTML = hist.map(m => {
    const isUser = m.role === 'user';
    return `
      <div class="msg-row ${isUser ? 'user' : 'ai'}">
        <div class="msg-avatar">${isUser ? 'YOU' : 'AI'}</div>
        <div class="msg-bubble">${escapeHtml(m.content).replace(/\\n/g,'<br>')}</div>
      </div>`;
  }).join('');
  el.scrollTop = el.scrollHeight;
}

function drvChipClick(id, btn) {
  const input = document.getElementById(`drvInput_${id}`);
  if (input) { input.value = btn.textContent.trim(); sendDriverMsg(id); }
}"""
# no change needed for _renderDrvMsgs, it reuses existing msg-row classes which still exist

with open('pitwall-ai.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('File saved')

# Verify
for check in ['drv-search-bar', 'drv-pos-p1', 'drv-bio-col', 'drv-content-col', 'drv-ai-wrap', 'drv-lock', '_helmtText', '_drvSearchFilter', 'drv-profile-breadcrumb', 'Miami GP weekend']:
    n = content.count(check)
    print(f'  {check}: {n}')
