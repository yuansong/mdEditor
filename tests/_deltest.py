import os,traceback
open('E:/WorkBuddy/md-editor/tests/_deltest.tmp','w').write('x')
try:
    os.remove('E:/WorkBuddy/md-editor/tests/_deltest.tmp')
    print('REMOVED-OK')
except BaseException as e:
    print('CAUGHT:', type(e).__name__, e)
print('AFTER')