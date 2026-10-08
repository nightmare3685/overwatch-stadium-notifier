# Explicit allowlist: never package webhook.txt, logs, recordings or local settings.
$ErrorActionPreference = 'Stop'
$packageNames = @(
    '.gitignore', 'app.py', 'detector.py', 'language.py', 'discord_notify.py',
    'process_audio.py', 'ProcessAudio.cs', 'ProcessAudio.exe', 'build-audio.bat',
    'start.bat', 'requirements.txt', 'templates.npz', 'template-info.json',
    'validation-results.json', 'README.md', 'PRIVACY.md', 'RELEASE-NOTES.md',
    'test_app.py', 'test_process_audio.py', 'test_discord_notify.py', 'build-package.ps1'
)
$packagePaths = @($packageNames | ForEach-Object { Join-Path $PSScriptRoot $_ })
$packageDestination = Join-Path (Split-Path $PSScriptRoot -Parent) 'overwatch-stadium-notifier.zip'
Compress-Archive -LiteralPath $packagePaths -DestinationPath $packageDestination -Force
Write-Output $packageDestination
