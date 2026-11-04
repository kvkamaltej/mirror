# Downloads the official scrcpy Windows release into .\bin (needed only to BUILD the exe).
# scrcpy is Apache-2.0: https://github.com/Genymobile/scrcpy
param(
    [string]$Version = "2.5",
    [string]$Dest = (Join-Path $PSScriptRoot "bin")
)
$ErrorActionPreference = "Stop"
$name = "scrcpy-win64-v$Version"
$url = "https://github.com/Genymobile/scrcpy/releases/download/v$Version/$name.zip"
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("scrcpy-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force $tmp | Out-Null
try {
    Write-Host "Downloading $url"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile (Join-Path $tmp "$name.zip") -UseBasicParsing
    Expand-Archive (Join-Path $tmp "$name.zip") -DestinationPath $tmp -Force
    New-Item -ItemType Directory -Force $Dest | Out-Null
    $keep = "scrcpy.exe", "scrcpy-server", "icon.png", "adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll",
            "SDL2.dll", "avcodec-*.dll", "avformat-*.dll", "avutil-*.dll", "swresample-*.dll", "libusb-1.0.dll"
    foreach ($pattern in $keep) {
        Copy-Item (Join-Path $tmp "$name\$pattern") $Dest -Force
    }
    Write-Host "scrcpy $Version files are in $Dest"
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
