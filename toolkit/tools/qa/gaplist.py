import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8')); lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0; hi = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
bottom = None
for r in d['rows']:
    gap = '' if bottom is None else r['y'] - bottom
    if lo <= r['y'] <= hi:
        print(f"{r['y']:6} gap {str(gap):>5} | {r['tag']:6} x{r['x']:3} w{r['w']:3} h{r['h']:4} fs {r['fs']:>7} fw {r['fw']} {r['ta'][:6]:6} bg {str(r['bg'])[:22]:22} | {r['text'][:42]}")
    bottom = max(bottom or 0, r['y'] + r['h'])
