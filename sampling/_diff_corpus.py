import json
import sys
from pathlib import Path


def load(n):
    d = json.loads((Path(__file__).resolve().parent / f"l3-corpus-{n}.json").read_text(encoding="utf-8"))
    return {(c["family"], int(k), tuple(c["evidence_refs"]), c["detail"][:14]): c["detail"]
            for k, ch in d.items() for c in ch["candidates"]}


a, b = load(sys.argv[1]), load(sys.argv[2])
print("LOST")
for k in sorted(a):
    if k not in b:
        print("  %s ch%02d %s | %s" % (k[0], k[1], ";".join(k[2]), a[k][:80]))
print("GAINED")
for k in sorted(b):
    if k not in a:
        print("  %s ch%02d %s | %s" % (k[0], k[1], ";".join(k[2]), b[k][:80]))
