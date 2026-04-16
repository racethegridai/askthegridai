import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'r', encoding='utf-8') as f:
    html = f.read()

changes = []

# ── 1. Remove .api-btn CSS (17 lines, well-bounded) ───────────────────────────
old = (
    "    .api-btn {\n"
    "      height: 34px;\n"
    "      padding: 0 12px;\n"
    "      background: transparent;\n"
    "      border: 1px solid #2e2e2e;\n"
    "      color: var(--gray);\n"
    "      font-family: 'Titillium Web', sans-serif;\n"
    "      font-size: 10px;\n"
    "      font-weight: 700;\n"
    "      letter-spacing: 2px;\n"
    "      text-transform: uppercase;\n"
    "      cursor: pointer;\n"
    "      transition: all 0.18s;\n"
    "      flex-shrink: 0;\n"
    "    }\n\n"
    "    .api-btn:hover { border-color: var(--gray); color: var(--white); }\n"
    "    .api-btn.connected { border-color: var(--green); color: var(--green); }\n\n"
)
assert old in html, "FAIL: .api-btn CSS"
html = html.replace(old, '', 1)
changes.append("Removed .api-btn CSS")

# ── 2. Remove API KEY MODAL CSS block only ────────────────────────────────────
# Start: the comment line; End: closing } of .modal-note  + newline before next section
css_start = html.find('    /* \u2500\u2500 API KEY MODAL \u2500\u2500\u2500')
assert css_start > 0, "FAIL: modal CSS comment not found"
modal_note_open = html.find('    .modal-note {', css_start)
assert modal_note_open > css_start, "FAIL: .modal-note not found"
css_end = html.find('\n    }', modal_note_open) + len('\n    }')
# verify the next char is a newline before next section
html = html[:css_start] + html[css_end:]
changes.append("Removed API key modal CSS")

# ── 3. Remove API KEY MODAL HTML (the div, not anything else) ─────────────────
_anchor = '     API KEY MODAL\n'
_anchor_idx = html.find(_anchor)
assert _anchor_idx > 0, "FAIL: modal HTML anchor not found"
modal_html_start = html.rfind('<!--', 0, _anchor_idx)
assert modal_html_start > 0, "FAIL: modal HTML comment not found"
# The modal closes with </div>\n</div> (inner box + outer overlay)
modal_html_end = html.find('</div>\n</div>\n', modal_html_start) + len('</div>\n</div>\n')
assert modal_html_end > modal_html_start, "FAIL: modal HTML end not found"
html = html[:modal_html_start] + html[modal_html_end:]
changes.append("Removed API key modal HTML")

# ── 4. Remove the API key button from the header (single line) ────────────────
old = '\n  <button class="api-btn" id="apiStatusBtn" onclick="openApiModal()">\u25cf API Key</button>'
assert old in html, "FAIL: api-btn button"
html = html.replace(old, '', 1)
changes.append("Removed API Key button from header")

# ── 5. Remove only the apiKey localStorage line ───────────────────────────────
old = "let apiKey  = localStorage.getItem('pitwall_apikey') || '';\n"
assert old in html, "FAIL: apiKey variable"
html = html.replace(old, '', 1)
changes.append("Removed apiKey localStorage variable")

# ── 6. Remove ONLY the three API modal functions (openApiModal, saveApiKey, updateApiBtn)
# Anchor: the comment block header for API KEY MODAL in JS
js_section_start = html.find('/* \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n   API KEY MODAL\n\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */')
assert js_section_start > 0, "FAIL: JS API KEY MODAL section comment"
# End: the closing } of updateApiBtn — find it by looking for the specific function end
update_api_btn_end = html.find('\n}\n', html.find('async function updateApiBtn()', js_section_start)) + len('\n}\n')
assert update_api_btn_end > js_section_start, "FAIL: updateApiBtn end"
# Remove from the section comment (minus leading newlines) to end of updateApiBtn
section_start_with_newlines = html.rfind('\n\n', 0, js_section_start)
html = html[:section_start_with_newlines] + html[update_api_btn_end:]
changes.append("Removed openApiModal / saveApiKey / updateApiBtn JS functions")

# ── 7. Remove the if (!apiKey) auto-open block in init() ─────────────────────
old = "\n  if (!apiKey) {\n    setTimeout(() => document.getElementById('apiModal').classList.add('open'), 600);\n  }\n"
assert old in html, "FAIL: apiKey init block"
html = html.replace(old, '\n', 1)
changes.append("Removed auto-open modal trigger in init()")

# ── 8. Fix any remaining localhost:8000 references ────────────────────────────
old_url = 'http://localhost:8000'
new_url = 'https://web-production-86197.up.railway.app'
count = html.count(old_url)
if count:
    html = html.replace(old_url, new_url)
    changes.append(f"Replaced {count} localhost:8000 reference(s) with Railway URL")

with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Done. Changes made:")
for c in changes:
    print(f"  \u2713 {c}")

# Verify
bad = [x for x in ['apiModal','apiKeyInput','openApiModal','saveApiKey','pitwall_apikey','api-btn','localhost:8000'] if x in html]
good = [x for x in ['renderRadio','standingsTbody','chatMessages','incidentsCard','focusMomentContent','openRadioView'] if x in html]
print(f"\nAPI key references remaining: {bad if bad else 'none \u2713'}")
print(f"Key sections present: {good}")
