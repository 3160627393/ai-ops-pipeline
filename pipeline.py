# -*- coding: utf-8 -*-
r"""
AI 运维自动流水
一条命令跑完整条链：
  ① 主机巡检出日报  →  ② 日志故障归因  →  ③ 合并成运维日报  →  ④ 推送（飞书/企业微信机器人）

用法：
    python pipeline.py                 # 跑全流程（按 config.json 决定是否推送）
    python pipeline.py --no-push       # 只生成，不推送
    python pipeline.py --no-webhook    # 同上
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "config.json")
REPORT_DIR = os.path.join(BASE, "reports")
PY = r"D:\Dev\Python313\python.exe"
HOST_SCRIPT = r"D:\Dev\host-inspection\host_report.py"
LOG_SCRIPT = r"D:\Dev\ai-log-analyzer\analyze.py"
MONITOR_LOG = r"D:\Dev\ollama-monitor\monitor.log"
HOST_REPORTS = r"D:\Dev\host-inspection\reports"
LOG_REPORTS = r"D:\Dev\ai-log-analyzer\reports"

DEFAULT_CONFIG = {
    "webhook_type": "none",          # none / feishu / wecom
    "webhook_url": "",
    "push_max_chars": 3000           # 机器人消息有长度限制，超了截断
}


def load_config():
    if not os.path.exists(CONFIG):
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        print(f"已生成默认配置：{CONFIG}（先不推送，填了 webhook_url 再开）")
        return dict(DEFAULT_CONFIG)
    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


def run_step(title, script, extra=None):
    cmd = [PY, script] + (extra or [])
    print(f"\n[{title}] 执行中……")
    ps = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    print((ps.stdout or "").strip()[-800:])
    if ps.returncode != 0:
        print((ps.stderr or "").strip()[-500:])
        return False
    return True


def latest_file(folder, pattern):
    if not os.path.isdir(folder):
        return None
    items = [os.path.join(folder, f) for f in os.listdir(folder) if f.startswith(pattern) and f.endswith(".md")]
    return max(items, key=os.path.getmtime) if items else None


def read(path):
    if not path or not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def merge(host_md, log_md, ok_host, ok_log):
    now = datetime.now()
    head = [
        f"# AI 运维日报 · {now:%Y-%m-%d}",
        "",
        f"> 生成时间：{now:%Y-%m-%d %H:%M}　｜　来源：本机自动流水",
        "",
        "## 今日概览",
        "",
        f"- 主机巡检：{'成功' if ok_host else '失败'}",
        f"- 日志归因：{'成功' if ok_log else '失败'}",
        "",
    ]
    body = []
    if host_md:
        body += ["---", "", host_md.strip(), ""]
    if log_md:
        body += ["---", "", "## 附：日志故障归因", "", log_md.strip(), ""]
    return "\n".join(head + body)


def push(cfg, content):
    if cfg.get("webhook_type") in ("", "none") or not cfg.get("webhook_url"):
        print("未配置 webhook，跳过推送（只保存本地报告）")
        return False

    text = content
    limit = int(cfg.get("push_max_chars") or 3000)
    if len(text) > limit:
        text = text[:limit] + "\n\n…（内容过长已截断，完整版见本机报告）"

    import urllib.request
    if cfg["webhook_type"] == "feishu":
        payload = {"msg_type": "text", "content": {"text": text}}
    elif cfg["webhook_type"] == "wecom":
        payload = {"msgtype": "markdown", "markdown": {"content": text}}
    else:
        print(f"不认识的 webhook_type：{cfg['webhook_type']}")
        return False

    req = urllib.request.Request(
        cfg["webhook_url"],
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8", "ignore")
        print(f"推送完成：{body[:120]}")
        return True
    except Exception as e:
        print(f"推送失败：{e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", "--no-webhook", dest="no_push", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    ok_host = run_step("① 主机巡检", HOST_SCRIPT)
    ok_log = run_step("② 日志归因", LOG_SCRIPT, ["--file", MONITOR_LOG, "--tail", "200"])

    host_md = read(latest_file(HOST_REPORTS, "巡检日报_"))
    log_md = read(latest_file(LOG_REPORTS, "report_"))
    report = merge(host_md, log_md, ok_host, ok_log)

    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, f"运维日报_{datetime.now():%Y%m%d}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n运维日报已生成：{path}")

    if not args.no_push:
        push(cfg, report)


if __name__ == "__main__":
    main()
