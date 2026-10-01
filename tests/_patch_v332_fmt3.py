# -*- coding: utf-8 -*-
"""v3.31.2 FMT 修复三轮：
G4: MKS 边界收缩后补「链接尾巴剥离」—— plainToRawOffset 在 idx===L 时返回
    n.re（含 ](url) 收尾），凡选区为链接/图片 alt 文字，包裹类动作此前会把
    标记包到 ](url) 外面（[~~x](u)~~ 语法损坏）；统一收缩到链接文字本身。
G5: clearSelectionFormat 的 markerChar 扩展 [ ] ( ) —— 嵌套链接+删除线+行内码
    的复合态清理需要把整条链接外壳吸附进区间才能一次剥净。
"""
import io
import sys

PATH = r"E:\WorkBuddy\md-editor\src\editor.html"

PAIRS = [
    # ---------- G4：链接尾巴剥离（插在 MKS 收缩块之后、跨行守卫之前） ----------
    ("""            while (rawOff + mls <= rawEnd && raw.slice(rawOff, rawOff + mls) === MKS[mi]) {
              rawOff += mls; mchg = true;
            }
          }
        }
      }
      /* v3.30.18（LIST-1 止血）：CommonMark 行内标记不可跨行""",
     """            while (rawOff + mls <= rawEnd && raw.slice(rawOff, rawOff + mls) === MKS[mi]) {
              rawOff += mls; mchg = true;
            }
          }
        }
      }
      /* v3.31.2（FMT 批 G4）：idx===L 在链接 / 图片节点上返回 n.re（含 ](url)
         收尾）—— 选区为链接文字时区间尾带着 ](url)，包裹动作会把标记包到
         外面（[~~x](u)~~ 损坏）。凡左邻为 [ 且区间尾为 ](url)，收缩到文字 */
      var _lts = raw.slice(rawOff, rawEnd);
      var _me2 = _lts.match(/\\]\\(([^)\\n]*)\\)$/);
      if (_me2 && raw.charAt(rawOff - 1) === '[') rawEnd = rawOff + _me2.index;
      /* v3.30.18（LIST-1 止血）：CommonMark 行内标记不可跨行"""),
    # ---------- G5：markerChar 扩展括号类 ----------
    ("""    var markerChar = /[*_~`$=]/;
""",
     """    var markerChar = /[*_~`$=\\[\\()\\)]/;
"""),
]

with io.open(PATH, "r", encoding="utf-8") as f:
    txt = f.read()
for i, (old, new) in enumerate(PAIRS, 1):
    n = txt.count(old)
    if n != 1:
        print("FAIL pair#%d count=%d" % (i, n))
        sys.exit(1)
    txt = txt.replace(old, new)
with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(txt)
print("OK %d patches applied" % len(PAIRS))
