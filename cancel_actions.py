#!/usr/bin/env python
"""取消 GitHub Actions 的运行并禁用 workflow（用户要求"关了"）。

用 git credential manager 里已存的凭据调 API，不回显 token。
"""
import json
import subprocess
import urllib.error
import urllib.request

REPO = "YesNewBeeBar/bedrock-recipe-renderer"
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github+json"}


def token() -> str:
    out = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, check=False).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return ""


def api(tok: str, path: str, method: str = "GET"):
    req = urllib.request.Request(f"https://api.github.com{path}", method=method,
                                 headers=dict(UA, Authorization=f"Bearer {tok}"))
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:200]
    except Exception as exc:
        return 0, str(exc)


def main() -> int:
    tok = token()
    if not tok:
        print("!! 拿不到凭据，无法操作")
        return 1
    print("凭据 OK（已隐藏）")

    st, runs = api(tok, f"/repos/{REPO}/actions/runs?per_page=50")
    if st != 200 or not isinstance(runs, dict):
        print("拉取 runs 失败:", st, runs)
        return 1
    active = [r for r in runs.get("workflow_runs", [])
              if r.get("status") in ("in_progress", "queued", "requested", "waiting",
                                     "pending")]
    print(f"共 {len(runs.get('workflow_runs', []))} 条运行记录，其中活动 {len(active)} 条")
    for r in active:
        code, _ = api(tok, f"/repos/{REPO}/actions/runs/{r['id']}/cancel", "POST")
        print(f"  取消 #{r['run_number']} ({r['name']}, {r['status']}) → HTTP {code}")

    st, wfs = api(tok, f"/repos/{REPO}/actions/workflows")
    if st == 200 and isinstance(wfs, dict):
        for wf in wfs.get("workflows", []):
            code, _ = api(tok, f"/repos/{REPO}/actions/workflows/{wf['id']}/disable",
                          "PUT")
            print(f"  禁用 workflow「{wf['name']}」({wf['path']}) → HTTP {code}")
    else:
        print("拉取 workflows 失败:", st, wfs)

    st, runs = api(tok, f"/repos/{REPO}/actions/runs?per_page=5")
    if st == 200 and isinstance(runs, dict):
        print("\n最新几条状态：")
        for r in runs.get("workflow_runs", [])[:5]:
            print(f"  #{r['run_number']} {r['name']}: {r['status']} / {r.get('conclusion')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
