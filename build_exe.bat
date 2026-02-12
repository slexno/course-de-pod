@echo off
setlocal

if not exist .venv (
  python -m venv .venv
)

call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

pyinstaller --noconfirm --clean course-de-pod.spec

echo.
echo Build termine. Executable: dist\course-de-pod.exe
endlocal
