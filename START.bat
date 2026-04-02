@echo off
echo.
echo  ========================================
echo   Ethinos AI Voice Demo - Starting...
echo  ========================================
echo.
echo  Installing dependencies...
pip install flask flask-cors requests -q
echo.
echo  Starting server...
echo  Open http://localhost:5000 in your browser
echo.
python server.py
pause