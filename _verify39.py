import hashlib, io

src = io.open('src/editor.html', 'rb').read()
dist = io.open('dist39/mdEditor/_internal/editor.html', 'rb').read()
h1 = hashlib.sha256(src).hexdigest().upper()
h2 = hashlib.sha256(dist).hexdigest().upper()
print('SRC_SHA :', h1)
print('DIST_SHA:', h2)
print('MATCH   :', h1 == h2)

feats = ['tblDragPend', 'tblDragRaf', 'elementFromPoint',
         'v3.29c', 'canStore', 'setQuoteCaret']
txt = dist.decode('utf-8', errors='replace')
for f in feats:
    print('FEAT %-16s : %s' % (f, f in txt))
