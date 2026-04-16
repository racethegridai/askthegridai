import sys
sys.stdout.reconfigure(encoding='utf-8')
with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'r', encoding='utf-8') as f:
    html = f.read()
# find all instances of API KEY MODAL
pos = 0
while True:
    idx = html.find('API KEY MODAL', pos)
    if idx < 0: break
    print(f"pos {idx}:", repr(html[idx-40:idx+30]))
    pos = idx + 1
