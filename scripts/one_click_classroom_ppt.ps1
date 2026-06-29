#Requires -Version 5.1
<#
.SYNOPSIS
  从应用文 HTML/Word 导出一键生成 V1 课堂 PPTX。

.DESCRIPTION
  运行 one_click_classroom_ppt.py：prepare_ppt_source → generate_classroom_pptx → WPS on-click 动画。

.PARAMETER ExportPath
  应用文导出的 .html 或 .docx 文件路径。

.PARAMETER OutDir
  输出目录。默认：导出文件同级的 ppt-work 文件夹。

.PARAMETER NoAnim
  跳过 WPS on-click 动画注入。

.EXAMPLE
  .\scripts\one_click_classroom_ppt.ps1 "D:\Downloads\应用文分析_2026-06-18.html"

.EXAMPLE
  .\scripts\one_click_classroom_ppt.ps1 ".\report.docx" -OutDir "D:\Downloads\ppt-work"
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ExportPath,

    [string]$OutDir = "",

    [switch]$NoAnim
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$OneClickScript = Join-Path $ProjectRoot "scripts\one_click_classroom_ppt.py"

if (-not (Test-Path $OneClickScript)) {
    throw "找不到 one_click_classroom_ppt.py：$OneClickScript"
}

$ExportPath = (Resolve-Path -LiteralPath $ExportPath).Path
$ext = [System.IO.Path]::GetExtension($ExportPath).ToLowerInvariant()
if ($ext -notin @(".html", ".docx")) {
    throw "ExportPath 须为 .html 或 .docx，当前：$ext"
}

$args = @($OneClickScript, $ExportPath)
if (-not [string]::IsNullOrWhiteSpace($OutDir)) {
    $resolvedOut = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutDir)
    $args += @("-o", $resolvedOut)
}
if ($NoAnim) {
    $args += "--no-anim"
}

Write-Host "== 应用文 → V1 课堂 PPTX ==" -ForegroundColor Cyan
Write-Host "导出文件: $ExportPath"
if (-not [string]::IsNullOrWhiteSpace($OutDir)) {
    Write-Host "输出目录: $resolvedOut"
}
Write-Host ""

python @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
