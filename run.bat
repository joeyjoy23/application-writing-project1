@echo off
cd /d "%~dp0"
echo Starting Streamlit on http://localhost:8502
if exist "venv\Scripts\streamlit.exe" (
    venv\Scripts\streamlit.exe run app.py --server.port 8502
) else (
    streamlit run app.py --server.port 8502
)
pause
