@echo off
rem 编译本书。需要 xelatex（TeX Live 2026 已验证）。
rem 用法：build.bat
rem
rem 共编译三遍：本书交叉引用很多，且目录本身会改变页码，
rem 两遍之后仍会有未解析的引用，第三遍才完全稳定。
setlocal
chcp 65001 >nul

rem 相当于 cd "$(dirname "$0")"：切到脚本所在目录
cd /d "%~dp0"
if errorlevel 1 exit /b 1

rem 相当于 set -e：任一遍编译失败立即退出
xelatex -interaction=nonstopmode main.tex
if errorlevel 1 exit /b 1
xelatex -interaction=nonstopmode main.tex
if errorlevel 1 exit /b 1
xelatex -interaction=nonstopmode main.tex
if errorlevel 1 exit /b 1

echo ==^> 生成 main.pdf
set "UNDEFINED=0"
for /f %%c in ('findstr /r /c:"Reference .* undefined" main.log ^| find /c /v ""') do set "UNDEFINED=%%c"
echo     未解析引用数: %UNDEFINED%
set "OVERFULL=0"
for /f %%c in ('findstr /c:"Overfull \hbox" main.log ^| find /c /v ""') do set "OVERFULL=%%c"
echo     溢出页面数:   %OVERFULL%

endlocal
