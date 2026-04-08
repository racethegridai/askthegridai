import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'r', encoding='utf-8') as f:
    html = f.read()

css_start = html.find('    /* \u2500\u2500 API KEY MODAL')
print("css_start:", css_start)

# find what comes after modal-note block
idx = html.find('    .modal-note {')
print("modal-note start:", idx)
if idx > 0:
    print(repr(html[idx:idx+100]))
    end_idx = html.find('}', idx + 50)
    print("end_idx:", end_idx)
    print(repr(html[end_idx:end_idx+60]))
