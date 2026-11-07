# Adds the {{NAME}} stinger to the Aitum Vertical plugin's transition list, so the vertical scenes
# of this kit play it. The vertical scenes already ask for it by name; this makes it exist.
# Only the transition list changes: stream keys and every other setting stay as they are.
# Run it with OBS closed (Aitum rewrites its settings when OBS exits).
param([string]$ConfigPath = "$env:APPDATA\obs-studio\plugin_config\vertical-canvas\config.json")

$ErrorActionPreference = "Stop"
$Name  = "{{NAME}}"
$Point = {{POINT}}
$Stinger = Join-Path $PSScriptRoot "assets\{{FILE}}"

if (Get-Process obs64 -ErrorAction SilentlyContinue) {
    Write-Host "Close OBS first, then run this again." -ForegroundColor Yellow; exit 1
}
if (-not (Test-Path -LiteralPath $Stinger)) {
    Write-Host "Can't find $Stinger. Run this from the unzipped kit folder." -ForegroundColor Yellow; exit 1
}
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    Write-Host "Aitum Vertical isn't set up yet. Open OBS once with the plugin installed, close it, then run this again." -ForegroundColor Yellow
    exit 1
}

$backup = "$ConfigPath.before-kit"
if (-not (Test-Path -LiteralPath $backup)) { Copy-Item -LiteralPath $ConfigPath -Destination $backup }

$raw = [IO.File]::ReadAllText($ConfigPath, [Text.Encoding]::UTF8)
$cfg = ConvertFrom-Json -InputObject $raw
if (-not $cfg.canvas) { Write-Host "No vertical canvas found in the Aitum settings." -ForegroundColor Yellow; exit 1 }

$entry = [pscustomobject]@{
    name = $Name; id = "obs_stinger_transition"; versioned_id = "obs_stinger_transition"
    settings = [pscustomobject]@{
        path = ($Stinger -replace '\\', '/'); tp_type = 0; transition_point = $Point
        audio_monitoring = 0; audio_fade_style = 0; track_matte_enabled = $false; preload = $true
    }
}
$done = 0
foreach ($c in @($cfg.canvas)) {
    if ($c.width -and $c.height -and ($c.width -lt $c.height) -eq $false) { continue }  # vertical canvases only
    $list = @(@($c.transitions) | Where-Object { $_ -and $_.name -ne $Name }) + $entry
    if ($c.PSObject.Properties.Name -contains "transitions") { $c.transitions = $list }
    else { $c | Add-Member -NotePropertyName transitions -NotePropertyValue $list }
    $done++
}
$json = ConvertTo-Json -InputObject $cfg -Depth 100
[IO.File]::WriteAllText($ConfigPath, $json, (New-Object Text.UTF8Encoding $false))
Write-Host "Added '$Name' to Aitum Vertical ($done canvas). Open OBS and switch to the kit's collection." -ForegroundColor Green
