# -*- coding: utf-8 -*-
import io
s = io.open(r"E:\WorkBuddy\md-editor\src\exporters.py", encoding="utf-8").read()
out = []
out.append("plain count = %d" % s.count(".tip{color:#8a8a8a;font-style:italic}"))
needle = ".tip{color:#8a8a8a;font-style:italic}" + chr(10) + '"""'
out.append("with quote = %d" % s.count(needle))
with io.open(r"E:\WorkBuddy\md-editor\tests\_csschk4.txt", "w", encoding="utf-8") as f:
    f.write(chr(10).join(out))
print("done")
