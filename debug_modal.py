import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'r', encoding='utf-8') as f:
    html = f.read()

idx = html.find('API KEY MODAL')
print(repr(html[idx-10:idx+30]))
print('---')
idx2 = html.find('.modal-overlay')
print(repr(html[idx2-10:idx2+40]))
print('---')
# Check if modal CSS block still exists after change1 script ran
print('modal-overlay count:', html.count('.modal-overlay'))
print('api-btn count:', html.count('.api-btn'))
