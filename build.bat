@echo off
rem Build dist\PhoneMirror.exe - a single portable exe with scrcpy + adb inside.
rem Needs Python 3.8+ on the BUILD machine only:  python -m pip install pyinstaller sv-ttk qrcode
setlocal
cd /d "%~dp0"
if not exist bin\scrcpy.exe (
  echo bin\ is empty - downloading the official scrcpy 2.5 release...
  powershell -NoProfile -ExecutionPolicy Bypass -File get-scrcpy.ps1 || exit /b 1
)
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name PhoneMirror --icon assets\icon.ico ^
  --collect-data sv_ttk --hidden-import qrcode --exclude-module PIL --exclude-module numpy ^
  --add-data "bin;bin" --add-data "assets;assets" --add-data "NOTICE.txt;." ^
  mirror.pyw || exit /b 1
copy /y NOTICE.txt dist\ >nul
echo.
echo Built dist\PhoneMirror.exe
