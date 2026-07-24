@echo off
cd /d "%~dp0"
echo Starting JETTY at http://localhost:4719 (leave this window open)
where py >nul 2>nul
if %errorlevel%==0 (py -3 server.py) else (python server.py)
pause
