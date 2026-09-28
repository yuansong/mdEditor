import io, sys
for f in sys.argv[1:]:
    try:
        t = io.open('tests/' + f, encoding='utf-8', errors='replace').read()
    except OSError as e:
        print(f, 'ERR', e)
        continue
    fails = [l for l in t.splitlines() if l.startswith('FAIL')]
    done = 'DONE' in t
    print(f, 'FAIL=', len(fails), 'DONE=', done)
    for l in fails:
        print('   ', l[:220])
