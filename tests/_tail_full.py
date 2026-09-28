import io
t = io.open('tests/_full_out.txt', encoding='utf-8', errors='replace').read()
lines = t.splitlines()
print('TOTAL_LINES', len(lines))
print('\n'.join(lines[-45:]))
