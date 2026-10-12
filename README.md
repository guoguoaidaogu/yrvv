# yrvv

本仓库收录了与「圆锥曲线题目的三维矢量解法」相关的若干内容。

原作者为[知乎用户：质点](https://www.zhihu.com/people/shu-di-fu-deng)，原文目录见[圆锥曲线题目的三维矢量解法](https://zhuanlan.zhihu.com/p/103884912)。本仓库未经额外授权，如有侵权请联系删除。

## Markdown 版本

[`md/`](md/) 目录包含原文目录及*部分章节*内容的完整转写，由 [`html2md.py`](html2md.py) 生成。

## XeLaTeX 版本

[`tex/`](tex/) 目录包含根据收录章节改写的半正式教材，改写工作由 DeepSeek-V41-Flash 完成；部分提示词见 [`tex/notes/REWRITE-SPEC.md`](tex/notes/REWRITE-SPEC.md)。

目前此版本在理论完整性和语言规范性上均欠佳，仅供参考。

### XeLaTeX 版本的编译

编译需要 TeX Live 环境。Git 仓库中不含成品 PDF 文件，但提供了编译脚本 [`tex/build.sh`](tex/build.sh) 与 [`tex/build.bat`](tex/build.bat)。
