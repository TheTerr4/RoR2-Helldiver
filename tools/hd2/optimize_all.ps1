# Rebuild the shipped low-poly models (Model/*.hdx + _tex.png + _nrm.png) from the high-poly sources with Blender 4.0 (optimize.py).
# The sources are private (converted from the player's own Helldivers 2 install, see README.md); budgets are the ones shipped in 1.0.0.
#   optimize_all.ps1 [-Src <highpoly folder>] [-Out <Model folder>] [-Preview <folder for before/after renders>]
param(
    [string]$Src = "H:\universal-modder\work\hd2-extract\highpoly",
    [string]$Out = "$PSScriptRoot\..\..\Model",
    [string]$Preview = "",
    [string]$Blender = "C:\Program Files\Blender Foundation\Blender 4.0\blender.exe"
)
$opt = "$PSScriptRoot\optimize.py"
#        source                   texture                        output      triangles  texture  smoothing  ray      detail (HD2 normal maps)  normal map size (default: texture)
$jobs = @(
    @("helldiver_mesh.bin",       "helldiver_mesh_tex.png",       "body",      12000,     2048,    70,        0.012,   "", 1024),
    @("weapon_liberator.bin",     "weapon_liberator_tex.png",     "liberator", 3500,      1024,    50,        0.004,   "weapon_liberator_detail.npz"),
    @("weapon_breaker.bin",       "weapon_breaker_tex.png",       "breaker",   3600,      1024,    50,        0.004,   "weapon_breaker_detail.npz"),
    @("jumppack.bin",             "jumppack_tex.png",             "jumppack",  1800,      1024,    50,        0.006,   "jumppack_detail.npz")
)
foreach ($j in $jobs) {
    $a = @("-b", "--factory-startup", "--python-exit-code", "1", "-P", $opt, "--", "$Src\$($j[0])", "$Src\$($j[1])", "$Out\$($j[2])",
           "--tris", $j[3], "--size", $j[4], "--angle", $j[5], "--extrude", $j[6])
    if ($j[7]) { $a += @("--detail", "$Src\$($j[7])") }
    if ($j.Count -gt 8) { $a += @("--nrm-size", $j[8]) }
    if ($Preview) { New-Item -ItemType Directory -Force $Preview | Out-Null; $a += @("--preview", "$Preview\prev_$($j[2])") }
    & $Blender @a 2>&1 | Select-String "\[optimize\]|Error|Traceback" | % { $_.Line }
    if ($LASTEXITCODE -ne 0) { throw "optimize.py failed on $($j[0])" }
}
