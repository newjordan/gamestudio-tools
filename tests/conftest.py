import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d in os.listdir(ROOT):
    p = os.path.join(ROOT, d)
    if os.path.isdir(p) and not d.startswith((".", "tests")):
        sys.path.insert(0, p)
