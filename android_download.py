"""带进度条的下载器（curl 在本机受 schannel 限制，Adoptium 又要求 UA）。

用法：python download.py <url> [<url2> ...] <目标文件>
      前几个 URL 依次尝试，第一个成功的即写入目标文件。
"""
import os
import sys
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"


def fetch(url: str, dest: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as fh:
            total = int(resp.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = resp.read(262144)
                if not chunk:
                    break
                fh.write(chunk)
                got += len(chunk)
                if total:
                    sys.stderr.write("\r  %5.1f%%  %.1f/%.1f MB" %
                                     (got * 100.0 / total, got / 1048576, total / 1048576))
                    sys.stderr.flush()
        sys.stderr.write("\n")
        return True
    except Exception as exc:
        sys.stderr.write("\n  失败 %s: %s\n" % (type(exc).__name__, exc))
        if os.path.exists(dest):
            os.remove(dest)
        return False


def main() -> int:
    if len(sys.argv) < 3:
        print("用法: download.py <url> [<url2> ...] <dest>")
        return 2
    urls, dest = sys.argv[1:-1], sys.argv[-1]
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    for url in urls:
        for attempt in range(1, 4):
            print("下载 %s（第 %d 次）" % (url, attempt))
            if fetch(url, dest):
                print("已下载 -> " + dest)
                return 0
            time.sleep(2 * attempt)
    print("全部下载源都失败")
    return 1


if __name__ == "__main__":
    sys.exit(main())
