import json, sys, re
file_path = r"tempt\0421_修改旧图.ipynb"
with open(file_path, "r", encoding="utf-8") as f: content = f.read()
try:
    json.loads(content)
    print("JSON is valid.")
except json.JSONDecodeError as e:
    print(f"Error: {e.msg}")
    print(f"Line: {e.lineno}, Col: {e.colno}, Pos: {e.pos}")
    lines = content.splitlines()
    for i in range(max(0, e.lineno-4), min(len(lines), e.lineno+3)):
        p = ">>>" if i == e.lineno-1 else "   "
        print(f"{i+1:4}: {p} {lines[i]}")
lines = content.splitlines()
print("\nLines 145-165:")
for i in range(144, min(165, len(lines))): print(f"{i+1:4}: {lines[i]}")
print("\nLines 300-320:")
for i in range(299, min(320, len(lines))): print(f"{i+1:4}: {lines[i]}")
print("\nSuspicious Double Quotes:")
for i, line in enumerate(lines):
    u = re.findall(r"(?<!\\)\"", line)
    if len(u) > 2 and len(u) % 2 != 0: print(f"Line {i+1}: {line.strip()}")
