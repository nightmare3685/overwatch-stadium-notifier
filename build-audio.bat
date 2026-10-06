@echo off
cd /d "%~dp0"
"%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /platform:x64 /optimize+ /out:ProcessAudio.exe ProcessAudio.cs
exit /b %errorlevel%
