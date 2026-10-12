#!/bin/sh
# 编译本书。需要 xelatex（TeX Live 2026 已验证）。
# 用法：sh build.sh
#
# 共编译三遍：本书交叉引用很多，且目录本身会改变页码，
# 两遍之后仍会有未解析的引用，第三遍才完全稳定。
set -e
cd "$(dirname "$0")"
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex

echo "==> 生成 main.pdf"
printf '    未解析引用数: '
grep -c 'Reference .* undefined' main.log || true
printf '    溢出页面数:   '
grep -c 'Overfull \\hbox' main.log || true
