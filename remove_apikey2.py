import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'r', encoding='utf-8') as f:
    html = f.read()

changes = []

# 1. Remove .api-btn CSS — find exact block
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
assert old in html, f"api-btn CSS not found"
html = html.replace(old, "\n", 1)
changes.append("Removed .api-btn CSS")

# 2. Remove API KEY MODAL CSS — use index-based slice
css_start = html.find('    /* \u2500\u2500 API KEY MODAL')
modal_note_end = html.find('    }\n\n    /* \u2500\u2500 RACE BAR')
assert css_start > 0 and modal_note_end > css_start, "Modal CSS block not found"
html = html[:css_start] + html[modal_note_end:]
changes.append("Removed API key modal CSS")

# 3. Remove API KEY MODAL HTML
html_start = html.find('<!-- \u2550' * 1)
# Find the specific modal comment block
modal_comment = '     API KEY MODAL\n'
idx = html.find(modal_comment)
assert idx > 0, "Modal HTML comment not found"
block_start = html.rfind('\n\n', 0, idx) + 2
block_end = html.find('</div>\n\n<!-- \u2550', idx)
block_end = html.find('\n\n<!-- \u2550', idx)
assert block_end > idx, "Modal HTML end not found"
html = html[:block_start] + html[block_end+2:]
changes.append("Removed API key modal HTML")

# 4. Remove api-btn button from header
old = '\n  <button class="api-btn" id="apiStatusBtn" onclick="openApiModal()">&#9679; API Key</button>'
assert old in html, f"api-btn button not found: {repr(old[:50])}"
html = html.replace(old, '', 1)
changes.append("Removed API Key button from header")

# 5. Remove apiKey localStorage variable
old = "let apiKey  = localStorage.getItem('pitwall_apikey') || '';\n"
assert old in html, "apiKey variable not found"
html = html.replace(old, '', 1)
changes.append("Removed apiKey localStorage variable")

# 6. Remove API KEY MODAL JS section
js_start = html.find('/* \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n   API KEY MODAL')
js_end = html.find('\n/* \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n   CHIPS', js_start)
assert js_start > 0 and js_end > js_start, f"JS modal block not found: start={js_start} end={js_end}"
html = html[:js_start] + html[js_end+1:]
changes.append("Removed openApiModal/saveApiKey/updateApiBtn JS functions")

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
