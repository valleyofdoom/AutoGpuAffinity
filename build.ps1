function Is-Admin() {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function main() {
    if (-not (Is-Admin)) {
        Write-Host "error: administrator privileges required"
        return 1
    }

    if (Test-Path ".\build\") {
        Remove-Item -Path ".\build\" -Recurse -Force
    }

    mkdir ".\build\"

    # entrypoint relative to .\build\pyinstaller\
    $entryPoint = "..\..\AutoGpuAffinity\main.py"

    # create folder structure
    mkdir ".\build\AutoGpuAffinity\"

    # pack executable
    mkdir ".\build\pyinstaller\"
    Push-Location ".\build\pyinstaller\"
    pyinstaller $entryPoint --onefile --name AutoGpuAffinity
    Pop-Location

    # create final package
    Copy-Item ".\build\pyinstaller\dist\AutoGpuAffinity.exe" ".\build\AutoGpuAffinity\"
    Copy-Item ".\AutoGpuAffinity\bin\" ".\build\AutoGpuAffinity\" -Recurse
    Copy-Item ".\AutoGpuAffinity\config.ini" ".\build\AutoGpuAffinity\"

    return 0
}

$_exitCode = main
Write-Host # new line
exit $_exitCode
