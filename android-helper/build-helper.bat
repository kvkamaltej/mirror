@echo off
rem Builds assets\mirror-helper.dex (runs on the phone; see src\com\mirror\IconDump.java).
rem Needs a JDK (8+) and the Android SDK (a platform's android.jar + build-tools' d8).
rem The built .dex is committed, so building Mirror itself does not need any of this.
setlocal
cd /d "%~dp0"
if "%ANDROID_SDK_ROOT%"=="" set ANDROID_SDK_ROOT=%ANDROID_HOME%
set PLATFORM=%ANDROID_SDK_ROOT%\platforms\android-30\android.jar
for /f "delims=" %%d in ('dir /b /ad /o-n "%ANDROID_SDK_ROOT%\build-tools"') do (set BT=%ANDROID_SDK_ROOT%\build-tools\%%d& goto :bt)
:bt
if not exist "%PLATFORM%" (echo Missing %PLATFORM% & exit /b 1)
if not exist "%BT%\d8.bat" (echo Missing d8 in %BT% & exit /b 1)
if exist out rmdir /s /q out
mkdir out\classes
javac -source 8 -target 8 -bootclasspath "%PLATFORM%" -Xlint:-options -d out\classes src\com\mirror\IconDump.java || exit /b 1
call "%BT%\d8.bat" --release --min-api 21 --lib "%PLATFORM%" --output out out\classes\com\mirror\IconDump.class || exit /b 1
copy /y out\classes.dex ..\assets\mirror-helper.dex >nul
rmdir /s /q out
echo Built assets\mirror-helper.dex
