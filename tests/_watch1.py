# -*- coding: utf-8 -*-
"""缺陷1实机监控：连接调试端口，每0.5s快照所有表格状态，变化即落日志。
用法: python _watch1.py [分钟数，默认10]
日志: tests/_watch1.log
"""
import json
import sys
import time
import urllib.request
import websocket

LOG = r"E:\WorkBuddy\md-editor\tests\_watch1.log"


_no_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get_ws():
    with _no_proxy.open("http://localhost:9222/json", timeout=5) as r:
        pages = json.loads(r.read().decode("utf-8"))
    for p in pages:
        if p.get("type") == "page" and "editor.html" in p.get("url", ""):
            return p["webSocketDebuggerUrl"]
    return None

SNAP_JS = r"""
JSON.stringify((function(){
  var out = [];
  var tbls = document.querySelectorAll('#editor table');
  for (var i = 0; i < tbls.length; i++) {
    var t = tbls[i];
    var cs = getComputedStyle(t);
    var cols = [];
    var cg = t.querySelectorAll('colgroup > col');
    for (var k = 0; k < cg.length; k++) {
      var wm = (cg[k].getAttribute('style')||'').match(/width:\s*([\d.]+)px/i);
      cols.push(wm ? +wm[1] : -1);
    }
    var merges = [];
    var trs = t.querySelectorAll('tr');
    for (var r = 0; r < trs.length; r++) {
      var tds = trs[r].children;
      for (var c = 0; c < tds.length; c++) {
        var rs = +tds[c].getAttribute('rowspan') || 1;
        var csx = +tds[c].getAttribute('colspan') || 1;
        if (rs > 1 || csx > 1) merges.push('r' + r + 'c' + c + '(' + rs + 'x' + csx + ')');
      }
    }
    var geo = [];
    if (trs.length) {
      var tr0 = trs[0];
      for (var c = 0; c < tr0.children.length && c < 8; c++) {
        var rc = tr0.children[c].getBoundingClientRect();
        geo.push(Math.round(rc.left) + '+' + Math.round(rc.width));
      }
    }
    var tblR = t.getBoundingClientRect();
    out.push({i:i, w:(t.getAttribute('style')||''), layout:cs.tableLayout,
              rectW:Math.round(tblR.width), cols:cols, merges:merges,
              hasThead:!!t.tHead, rows:trs.length, geo0:geo});
  }
  return {ts:Date.now(), n:document.querySelectorAll('#editor .blk').length, tbls:out};
})())
"""


def main():
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    f = open(LOG, "a", encoding="utf-8")
    f.write("\n==== watch start %s ====\n" % time.strftime("%H:%M:%S"))
    f.flush()
    ws = None
    wurl = None
    for _ in range(20):
        try:
            wurl = get_ws()
        except Exception as e:
            f.write("[%s] get_ws err: %s\n" % (time.strftime("%H:%M:%S"), e))
            f.flush()
            wurl = None
        if wurl:
            break
        time.sleep(3)
    if not wurl:
        f.write("NO_PAGE\n")
        f.close()
        print("NO_PAGE")
        return
    try:
        ws = websocket.create_connection(
            wurl, timeout=5, http_no_proxy=["localhost", "127.0.0.1"])
    except Exception as e:
        f.write("WS_CONNECT_ERR %s\n" % e)
        f.close()
        print("WS_CONNECT_ERR")
        return
    prev = None
    msg_id = 0
    t0 = time.time()
    last_evt = 0.0
    while time.time() - t0 < minutes * 60:
        msg_id += 1
        try:
            ws.send(json.dumps({"id": msg_id, "method": "Runtime.evaluate",
                                "params": {"expression": SNAP_JS, "returnByValue": True}}))
            resp = json.loads(ws.recv())
            val = resp.get("result", {}).get("result", {}).get("value")
        except Exception as e:
            f.write("[%s] WS_ERR %s\n" % (time.strftime("%H:%M:%S"), e))
            f.flush()
            time.sleep(2)
            try:
                wurl = get_ws()
                ws = websocket.create_connection(
                    wurl, timeout=5, http_no_proxy=["localhost", "127.0.0.1"]) if wurl else None
            except Exception:
                pass
            if ws is None:
                continue
        if val is None:
            time.sleep(0.5)
            continue
        if val != prev:
            now = time.time()
            mark = "EVT" if now - last_evt > 2 else "..."
            f.write("[%s %s] %s\n" % (time.strftime("%H:%M:%S"), mark, val))
            f.flush()
            prev = val
            last_evt = now
        time.sleep(0.5)
    f.write("==== watch end %s ====\n" % time.strftime("%H:%M:%S"))
    f.close()
    ws.close()
    print("WATCH_DONE")


if __name__ == "__main__":
    main()
