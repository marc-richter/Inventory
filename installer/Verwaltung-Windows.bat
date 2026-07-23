@echo off
setlocal
title Inventarprogramm - Verwaltung
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Verwaltung-Windows.ps1"
endlocal
