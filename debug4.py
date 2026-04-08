import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\Users\socce\Desktop\pitwall-ai\pitwall-ai.html', 'r', encoding='utf-8') as f:
    html = f.read()

idx = html.find('     API KEY MODAL\n')
block_start = html.rfind('<!--', 0, idx)
# modal closes with </div>\n</div>\n\n
modal_end = html.find('</div>\n</div>\n', idx)
print("block_start:", block_start, repr(html[block_start:block_start+20]))
print("modal_end:", modal_end, repr(html[modal_end:modal_end+20]))
full_end = modal_end + len('</div>\n</div>\n')
print("full_end:", full_end, repr(html[full_end:full_end+30]))
