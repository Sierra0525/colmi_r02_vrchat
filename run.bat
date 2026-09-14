@echo off
REM colmi_r02_vrchat をワンクリックで起動するためのバッチファイル
REM
REM 使い方:
REM   1. 下の ADDRESS を自分のリングの Bluetooth アドレスに書き換える
REM      (colmi_r02_util scan で調べられます)
REM   2. このファイルをダブルクリックして起動を確認する
REM   3. 問題なければこのファイルの「ショートカットを作成」して
REM      デスクトップに置けばワンクリック起動になります

setlocal

set ADDRESS=B3:08:A8:19:82:24
set OSC_IP=127.0.0.1
set OSC_PORT=9000
REM colmi_r02_client が要求する Python バージョン (3.11-3.13) に合わせて変更してください
set PYVER=-3.11

cd /d "%~dp0"

py %PYVER% -m colmi_r02_vrchat.cli --address %ADDRESS% --osc-ip %OSC_IP% --osc-port %OSC_PORT%

echo.
echo 終了しました。ウィンドウを閉じるには何かキーを押してください。
pause >nul
