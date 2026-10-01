# -*- coding: utf-8 -*-
"""v3.31.2 FMT 修复四轮：
G6: 链接尾巴剥离并入 MKS 收缩循环（剥尾后新暴露的 ~~ / ` 需继续收缩），
    且支持嵌套形态（[~~`x`~~](u) 选区内层文字时左邻不是 [ ，需向左定位
    最近 '[' 并校验其间无其它 '['）。
"""
import io
import sys

PATH = r"E:\WorkBuddy\md-editor\src\editor.html"

OLD = """        var mchg = true;
        while (mchg && rawEnd > rawOff) {
          mchg = false;
          for (var mi = 0; mi < MKS.length; mi++) {
            var mls = MKS[mi].length;
            while (rawEnd - mls >= rawOff && raw.slice(rawEnd - mls, rawEnd) === MKS[mi]) {
              rawEnd -= mls; mchg = true;
            }
            while (rawOff + mls <= rawEnd && raw.slice(rawOff, rawOff + mls) === MKS[mi]) {
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
"""

NEW = """        var mchg = true;
        while (mchg && rawEnd > rawOff) {
          mchg = false;
          for (var mi = 0; mi < MKS.length; mi++) {
            var mls = MKS[mi].length;
            while (rawEnd - mls >= rawOff && raw.slice(rawEnd - mls, rawEnd) === MKS[mi]) {
              rawEnd -= mls; mchg = true;
            }
            while (rawOff + mls <= rawEnd && raw.slice(rawOff, rawOff + mls) === MKS[mi]) {
              rawOff += mls; mchg = true;
            }
          }
          /* v3.31.2（FMT 批 G4/G6）：idx===L 在链接 / 图片节点上返回 n.re（含
             ](url) 收尾）—— 区间尾带着 ](url) 时包裹动作会把标记包到外面
             （[~~x](u)~~ 损坏）。向左定位最近 '[' 并校验其间无其它 '['（嵌套
             [~~`x`~~](u) 选内层文字时左邻不是 '['），收敛到链接文字尾；
             剥尾后新暴露的 ~~ / ` 由下一轮标记收缩继续处理 */
          var _lts = raw.slice(rawOff, rawEnd);
          var _me2 = _lts.match(/\\]\\(([^)\\n]*)\\)$/);
          if (_me2) {
            var _br = rawEnd - _me2[0].length;
            var _p2 = raw.lastIndexOf('[', _br - 1);
            if (_p2 >= 0 && _p2 < rawOff && raw.indexOf('[', _p2 + 1) > _br) {
              rawEnd = _br; mchg = true;
            }
          }
        }
      }
"""

with io.open(PATH, "r", encoding="utf-8") as f:
    txt = f.read()
n = txt.count(OLD)
if n != 1:
    print("FAIL count=%d" % n)
    sys.exit(1)
txt = txt.replace(OLD, NEW)
with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(txt)
print("OK")
