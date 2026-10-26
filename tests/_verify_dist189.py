# -*- coding: utf-8 -*-
"""校验 dist189 产物：内核 HTML 特征 + PYZ 模块特征 + 版本号 + SHA。"""
from __future__ import annotations

import hashlib
import os
import sys

ROOT = r"E:\WorkBuddy\md-editor"
DIST = os.path.join(ROOT, "dist189", "mdEditor")
EXE = os.path.join(DIST, "mdEditor.exe")


def find_file(name: str) -> str | None:
    for base, _dirs, files in os.walk(DIST):
        if name in files:
            return os.path.join(base, name)
    return None


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    fails = []

    def check(tag, cond, detail=""):
        print(("PASS " if cond else "FAIL ") + tag + (("  | " + str(detail)) if detail else ""))
        if not cond:
            fails.append(tag)

    check("D1_EXE", os.path.isfile(EXE), EXE)
    digest = sha256(EXE)
    check("D2_SHA_MATCH_FILE",
          digest == open(os.path.join(ROOT, "dist189.sha256")).read().split()[0], digest[:16])

    html = find_file("editor.html")
    check("D3_HTML_FOUND", html is not None, html)
    blob = b""
    if html:
        blob = open(html, "rb").read()
        for feat in (b"aiSelSnapshot", b"aiReplaceAnchor", b"hint-used",
                     b"block-changed", b"text-mismatch", b"_replaceRangeWithText",
                     b"markHintsUsed"):
            check("D4_HTML_" + feat.decode(), feat in blob)

    # PYZ 内模块常量
    try:
        sys.path.insert(0, os.path.join(
            os.environ.get("LOCALAPPDATA", ""), r"Programs\Python"))
        from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
        car = CArchiveReader(EXE)
        key = [k for k in car.toc if "PYZ" in str(k)][0]
        raw = car.extract(key)
        tmp = os.path.join(ROOT, "tests", "_pyz_tmp.pyz")
        with open(tmp, "wb") as f:
            f.write(raw)
        z = ZlibArchiveReader(tmp)
        cfg = z.extract("config")
        pane = z.extract("ai_pane")
        mw = z.extract("mainwindow")
        def consts(code):
            """递归收集嵌套 code object 的字符串常量与名字（类方法在子 code 里）。"""
            out = set(code.co_names)
            for c in code.co_consts:
                if isinstance(c, str):
                    out.add(c)
                elif hasattr(c, "co_consts"):
                    out |= consts(c)
            return out
        ccfg, cpane, cmw = consts(cfg), consts(pane), consts(mw)
        check("D5_VERSION_34833", "3.48.33" in ccfg, sorted(x for x in ccfg if x.startswith("3.48"))[:3])
        check("D6_PANE_TIP", "_frag_fail_tip" in cpane)
        check("D7_PANE_ANCHOR", "_frag_target_hint" in cpane and "orig_anchor" in cpane)
        check("D8_MW_ANCHOR", "get_fragment_anchor" in cmw and "replace_at_anchor" in cmw)
        os.remove(tmp)
    except Exception as exc:  # noqa: BLE001
        check("D9_PYZ_CHECK", False, repr(exc))

    print("")
    print("FAIL_COUNT=%d" % len(fails))
    print("RESULT=" + ("OK" if not fails else "FAILED:" + ",".join(fails)))


if __name__ == "__main__":
    main()
