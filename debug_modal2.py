import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find the exact CSS block start and end
start = html.find('    /* \u2500\u2500 API KEY MODAL')
end = html.find('.modal-note {\n      font-size: 10px;\n      color: var(--gray);\n      text-align: center;\n      margin-top: 10px;\n    }')
end2 = end + len('.modal-note {\n      font-size: 10px;\n      color: var(--gray);\n      text-align: center;\n      margin-top: 10px;\n    }')
print(f"CSS block: {start} to {end2}")
print(repr(html[start:start+50]))
print('...')
print(repr(html[end2-5:end2+5]))
