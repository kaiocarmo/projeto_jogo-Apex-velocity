@echo off
cd /d "%~dp0"
py -3 apex_velocity.py
if errorlevel 1 python apex_velocity.py
if errorlevel 1 pause
