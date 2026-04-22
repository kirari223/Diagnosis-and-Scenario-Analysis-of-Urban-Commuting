import json

file_path = r'tempt\0421_修改旧图.ipynb'
try:
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
        lines = content.splitlines()

    print('--- Suspicious Lines ---')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('\"'):
            unescaped_indices = []
            for j in range(len(line)):
                if line[j] == '\"':
                    bs_count = 0
                    k = j - 1
                    while k >= 0 and line[k] == '\\':
                        bs_count += 1
                        k -= 1
                    if bs_count % 2 == 0:
                        unescaped_indices.append(j)
            
            if len(unescaped_indices) > 2:
                print(f'Line {i+1}: {line}')

    print('\n--- JSON Validation ---')
    try:
        json.loads(content)
        print('JSON Result: Valid')
    except json.JSONDecodeError as e:
        print(f'JSON Result: Error at Line {e.lineno}, Column {e.colno}: {e.msg}')
        start = max(0, e.lineno - 3)
        end = min(len(lines), e.lineno + 2)
        for i in range(start, end):
            if i < len(lines):
                prefix = '>>' if i + 1 == e.lineno else '  '
                print(f'{prefix} {i+1}: {lines[i]}')

except Exception as e:
    print(f'Execution Error: {e}')
