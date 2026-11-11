param([int]$Port = 8766, [switch]$CheckRuntime, [string]$PythonExecutable = '')
$ErrorActionPreference = 'Stop'
$atlasPython = $null
$atlasArgs = @()
if ($PythonExecutable) {
    if (-not (Test-Path -LiteralPath $PythonExecutable)) { throw 'The specified PythonExecutable was not found.' }
    $atlasPython = $PythonExecutable
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $atlasPython = (Get-Command py).Source
    $atlasArgs = @('-3')
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $atlasPython = (Get-Command python).Source
} else {
    $atlasPackages = Get-ChildItem -Path "$env:ProgramFiles\WindowsApps\OpenAI.CodexPrimaryRuntime.*" -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending
    foreach ($atlasPackage in $atlasPackages) {
        $atlasCandidate = Join-Path $atlasPackage.FullName 'dependencies\python\python.exe'
        if (Test-Path -LiteralPath $atlasCandidate) { $atlasPython = $atlasCandidate; break }
    }
    # WindowsApps enumeration can be denied even when a known runtime is readable.
    if (-not $atlasPython) {
        $atlasKnownRuntime = 'C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1104-2876-0_26.1104.2876.0_arm64__3k8sg7r9htsxt\dependencies\python\python.exe'
        if (Test-Path -LiteralPath $atlasKnownRuntime) { $atlasPython = $atlasKnownRuntime }
    }
}
if (-not $atlasPython) { throw 'Python 3.10+ was not found. Install Python or run with your chosen Python interpreter.' }
if ($CheckRuntime) { & $atlasPython @atlasArgs --version; exit $LASTEXITCODE }
Push-Location $PSScriptRoot
try {
    & $atlasPython @atlasArgs (Join-Path $PSScriptRoot 'atlas_server.py') --port $Port
} finally { Pop-Location }
