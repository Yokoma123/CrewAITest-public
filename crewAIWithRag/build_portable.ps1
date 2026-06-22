param(
    [string]$Python = "python",
    [switch]$NoExe
)

$ErrorActionPreference = "Stop"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ArgsList = @((Join-Path $SourceDir "build_portable.py"), "--python", $Python)
if ($NoExe) {
    $ArgsList += "--no-exe"
}

& $Python $ArgsList
