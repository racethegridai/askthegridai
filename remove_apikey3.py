import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'r', encoding='utf-8') as f:
    html = f.read()

changes = []

# 1. Remove .api-btn CSS block
old = """    .api-btn {
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

"""
assert old in html, "api-btn CSS not found"
html = html.replace(old, "\n", 1)
changes.append("Removed .api-btn CSS")

# 2. Remove API KEY MODAL CSS — index-based
css_start = html.find('    /* \u2500\u2500 API KEY MODAL')
modal_note_close = html.find('}', html.find('    .modal-note {') + 50)
assert css_start > 0 and modal_note_close > css_start
html = html[:css_start] + html[modal_note_close + 1:]
changes.append("Removed API key modal CSS")

# 3. Remove API KEY MODAL HTML — index-based
idx = html.find('     API KEY MODAL\n')
block_start = html.rfind('<!--', 0, idx)
modal_end = html.find('</div>\n</div>\n', idx)
full_end = modal_end + len('</div>\n</div>\n')
assert block_start > 0 and modal_end > idx
html = html[:block_start] + html[full_end:]
changes.append("Removed API key modal HTML")

# 4. Remove api-btn button from header
old = '\n  <button class="api-btn" id="apiStatusBtn" onclick="openApiModal()">\u25cf API Key</button>'
assert old in html, "api-btn button not found"
html = html.replace(old, '', 1)
changes.append("Removed API Key button from header")

# 5. Remove apiKey localStorage variable
old = "let apiKey  = localStorage.getItem('pitwall_apikey') || '';\n"
assert old in html, "apiKey variable not found"
html = html.replace(old, '', 1)
changes.append("Removed apiKey localStorage variable")

# 6. Remove API KEY MODAL JS section
js_start = html.find('\n/* \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n   API KEY MODAL')
js_end   = html.find('\n/* \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n   CHIPS', js_start + 1)
assert js_start > 0 and js_end > js_start, f"JS section not found: {js_start}, {js_end}"
html = html[:js_start] + html[js_end:]
changes.append("Removed API key modal JS functions")

# 7. Remove if (!apiKey) block in init()
old = "\n  if (!apiKey) {\n    setTimeout(() => document.getElementById('apiModal').classList.add('open'), 600);\n  }\n"
assert old in html, "apiKey init block not found"
html = html.replace(old, '\n', 1)
changes.append("Removed auto-open modal trigger in init()")

with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Done. Changes made:")
for c in changes:
    print(f"  \u2713 {c}")

# Verify nothing left
remaining = [x for x in ['apiModal','apiKeyInput','openApiModal','saveApiKey','pitwall_apikey','api-btn'] if x in html]
if remaining:
    print(f"\nWARNING - still present: {remaining}")
else:
    print("\nVerification: No API key references remaining.")
