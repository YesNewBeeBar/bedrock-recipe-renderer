#!/usr/bin/env bash
# 查 Chaquopy 官方轮子索引里有哪几个 Pillow 版本 / 哪个 Python 版本
set -u
echo "== 索引根 =="
curl -s --max-time 25 https://chaquo.com/pypi-13.1/ | head -c 300; echo
echo
echo "== pillow 目录 =="
curl -s --max-time 25 https://chaquo.com/pypi-13.1/pillow/ -o /tmp/pillow_idx.html
echo "  文件大小: $(wc -c < /tmp/pillow_idx.html) 字节"
grep -oE 'Pillow-[0-9.]+-cp3[0-9]+' /tmp/pillow_idx.html | sort -u | tail -12
echo
echo "== 换个常见镜像名（Pillow 也常写成 pillow）=="
curl -s --max-time 25 https://chaquo.com/pypi-13.1/Pillow/ | grep -oE 'Pillow-[0-9.]+-cp3[0-9]+' | sort -u | tail -8
