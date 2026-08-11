from __future__ import annotations

import argparse
import json
import signal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .control_plane import ControlPlane


PAGE = """<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><title>Market Ops Control Center</title><style>
:root{color-scheme:dark;--bg:#08111f;--card:#111d30;--line:#243552;--text:#eaf1ff;--muted:#96a7c2;--ok:#35d39a;--warn:#ffbf69;--bad:#ff6577}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% 0,#17335a 0,transparent 38%),var(--bg);font:15px system-ui;color:var(--text)}main{max-width:1180px;margin:auto;padding:48px 24px}.eyebrow{color:#70a7ff;text-transform:uppercase;letter-spacing:.15em;font-size:12px}h1{font-size:42px;margin:8px 0}.sub{color:var(--muted);max-width:760px;line-height:1.6}.hero{display:flex;justify-content:space-between;gap:30px;align-items:end}.pill{padding:10px 16px;border:1px solid var(--line);border-radius:999px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:30px}.card{background:linear-gradient(145deg,#14233a,#0d1727);border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:0 16px 40px #0004}.wide{grid-column:span 3}.label{color:var(--muted);font-size:12px;text-transform:uppercase}.value{font-size:28px;margin-top:7px}.row{display:flex;justify-content:space-between;gap:16px;padding:11px 0;border-bottom:1px solid var(--line)}.row:last-child{border:0}.status{font-weight:700;text-align:right}.ready,.pass,.configured{color:var(--ok)}.degraded,.warn,.not_configured{color:var(--warn)}.blocked,.fail{color:var(--bad)}@media(max-width:760px){.grid{grid-template-columns:1fr}.wide{grid-column:auto}.hero{display:block}h1{font-size:32px}}</style><body><main><div class=\"hero\"><div><div class=\"eyebrow\">Autonomous Creative Growth OS</div><h1>Market Ops Control Center</h1><div class=\"sub\">真实收入驱动的创意增长闭环：洞察、决策、审批、执行和学习共用一条可审计账本。</div></div><div id=\"overall\" class=\"pill\">读取中…</div></div><section class=\"grid\"><div class=\"card\"><div class=\"label\">系统状态</div><div id=\"status\" class=\"value\">—</div></div><div class=\"card\"><div class=\"label\">运行模式</div><div id=\"mode\" class=\"value\">—</div></div><div class=\"card\"><div class=\"label\">有效报告</div><div id=\"reports\" class=\"value\">—</div></div><div class=\"card\"><div class=\"label\">待审批动作</div><div id=\"pending\" class=\"value\">—</div></div><div class=\"card wide\"><div class=\"label\">系统检查</div><div id=\"checks\"></div></div><div class=\"card\"><div class=\"label\">闭环状态</div><div id=\"loops\"></div></div></section></main><script>const esc=s=>String(s??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));fetch('/api/status').then(r=>r.json()).then(x=>{status.textContent=x.status;status.className='value '+x.status;mode.textContent=x.mode;reports.textContent=x.metrics.active_reports;pending.textContent=x.metrics.loop.pending_approvals;overall.textContent='v'+x.version+' · '+new Date(x.generated_at).toLocaleString();overall.className='pill '+x.status;checks.innerHTML=x.checks.map(c=>`<div class=\"row\"><span>${esc(c.name)}</span><span class=\"status ${esc(c.status)}\">${esc(c.status)} · ${esc(c.message)}</span></div>`).join('');loops.innerHTML=Object.entries(x.metrics.loop.cycles).map(([k,v])=>`<div class=\"row\"><span>${esc(k)}</span><span class=\"status\">${esc(v)}</span></div>`).join('')||'<div class=\"row\"><span>尚无循环</span></div>'});</script></body></html>"""


shutdown_flag = False


class Handler(BaseHTTPRequestHandler):
    control_plane: ControlPlane

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send(PAGE.encode(), "text/html; charset=utf-8")
        elif path in {"/api/status", "/healthz", "/readyz"}:
            payload = self.control_plane.snapshot().to_dict()
            code = HTTPStatus.OK if path != "/readyz" or payload["status"] != "blocked" else HTTPStatus.SERVICE_UNAVAILABLE
            self._send(json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8", code)
        elif path == "/api/loop":
            self._send(json.dumps(self.control_plane.loop_overview(), ensure_ascii=False).encode(), "application/json; charset=utf-8")
        elif path == "/api/diagnostic":
            self._send(json.dumps(self.control_plane.diagnostic_report(), ensure_ascii=False).encode(), "application/json; charset=utf-8")
        elif path.startswith("/api/cycles/"):
            cycle = self.control_plane.cycle(path.rsplit("/", 1)[-1])
            self._send(json.dumps(cycle or {"error": "not found"}, ensure_ascii=False).encode(), "application/json; charset=utf-8", HTTPStatus.OK if cycle else HTTPStatus.NOT_FOUND)
        else:
            self._send(b'{"error":"not found"}', "application/json", HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, body: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
        self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)


def _handle_signal(signum: int, frame: object) -> None:
    global shutdown_flag
    shutdown_flag = True


def main() -> None:
    parser = argparse.ArgumentParser(description="Market Ops Control Center")
    parser.add_argument("--host", default="0.0.0.0"); parser.add_argument("--port", type=int, default=8000); parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(); Handler.control_plane = ControlPlane(args.root)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Market Ops Control Center: http://{args.host}:{args.port}")
    while not shutdown_flag:
        server.handle_request()


if __name__ == "__main__":
    main()
