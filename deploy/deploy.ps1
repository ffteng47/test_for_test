<#
一键升级部署（Windows 开发机 → tff@192.168.31.213）
流程：① npm run build
      ② scp 安装器到 alexandria/deploy_patches，用 venv/bin/python 跑（幂等）
      ③ 打包 dist 覆盖 alexandria/studio（静态，免重启）
      ④ 安全检查（无生成任务在跑）后 stop/start 主服务
用法：
  powershell -ExecutionPolicy Bypass -File deploy/deploy.ps1
  powershell -ExecutionPolicy Bypass -File deploy/deploy.ps1 -Installers add_clone_ref_text.py
  powershell -ExecutionPolicy Bypass -File deploy/deploy.ps1 -SkipFrontend -NoRestart
  powershell -ExecutionPolicy Bypass -File deploy/deploy.ps1 -DryRun      # 只打印命令，不动服务器
#>
param(
  [string[]]$Installers = @('add_clone_ref_text.py'),
  [string]$Server = 'tff@192.168.31.213',
  [string]$Base   = '/home/tff/software/novel-audiobook',
  [switch]$SkipFrontend,
  [switch]$NoRestart,
  [switch]$Force,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$OutputEncoding = [System.Text.Encoding]::UTF8
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
$Alex = "$Base/alexandria"
$Tasks = @('script', 'review', 'audio', 'persona', 'm4b_export', 'audacity_export')

function Say([string]$m) { Write-Host "== $m" -ForegroundColor Cyan }
function Ok([string]$m) { Write-Host "   $m" -ForegroundColor Green }
function Die([string]$m) { throw "X $m" }

function RunRemote([string]$cmd) {
  if ($DryRun) { Write-Host "   [dry] ssh $Server '$cmd'" -ForegroundColor DarkGray; return }
  & ssh $Server $cmd
  if ($LASTEXITCODE -ne 0) { Die "远程命令失败: $cmd" }
}
function CapRemote([string]$cmd) {
  if ($DryRun) { Write-Host "   [dry] ssh $Server '$cmd'" -ForegroundColor DarkGray; return '' }
  $out = & ssh $Server $cmd
  if ($LASTEXITCODE -ne 0) { Die "远程命令失败: $cmd" }
  return (($out -join "`n")).Trim()
}
function CopyTo([string]$local, [string]$remote) {
  if ($DryRun) { Write-Host "   [dry] scp $local -> ${Server}:${remote}" -ForegroundColor DarkGray; return }
  & scp $local "${Server}:${remote}"
  if ($LASTEXITCODE -ne 0) { Die "scp 失败: $local" }
}

foreach ($bin in 'ssh', 'scp') {
  if (-not (Get-Command $bin -ErrorAction SilentlyContinue)) { Die "缺少 $bin（装 OpenSSH 客户端）" }
}

Say "连通性自检 ($Server)"
$hello = CapRemote "echo READY"
if (-not $DryRun -and $hello -notmatch 'READY') { Die "SSH 不通，先确认免密登录" }
Ok $hello

# ---- 1) 前端构建 ----
if (-not $SkipFrontend) {
  Say "构建前端 (npm run build)"
  if (-not (Get-Command tar -ErrorAction SilentlyContinue)) { Die "缺少 tar（Windows 10 1803+ 自带）" }
  Push-Location (Join-Path $root 'frontend')
  try {
    & npm run build
    if ($LASTEXITCODE -ne 0) { Die "npm run build 失败" }
  } finally { Pop-Location }
  if (-not (Test-Path (Join-Path $root 'frontend/dist/index.html'))) { Die "frontend/dist 里没有 index.html" }
}

# ---- 2) 安装器：同步 + 运行 ----
Say "同步并运行安装器: $($Installers -join ', ')"
RunRemote "mkdir -p $Alex/deploy_patches"
foreach ($i in $Installers) {
  $p = Join-Path $root "deploy/patches/$i"
  if (-not (Test-Path $p)) { Die "找不到安装器 deploy/patches/$i" }
  CopyTo $p "$Alex/deploy_patches/$i"
  RunRemote "cd $Alex/deploy_patches && ../venv/bin/python $i"
}
Ok "安装器完成（输出 PATCHED=本次写入 / ALREADY=已在盘上）"

# ---- 3) 前端 dist 覆盖 studio（静态，免重启）----
if (-not $SkipFrontend) {
  Say "发布前端 dist -> $Alex/studio"
  $tgz = Join-Path $env:TEMP ('studio_dist_' + [guid]::NewGuid().ToString('N') + '.tgz')
  Push-Location (Join-Path $root 'frontend/dist')
  try {
    & tar -czf $tgz index.html assets
    if ($LASTEXITCODE -ne 0) { Die "打包 dist 失败" }
  } finally { Pop-Location }
  CopyTo $tgz "$Base/studio_dist.tgz"
  RunRemote "mkdir -p $Alex/studio && cd $Alex/studio && tar -xzf $Base/studio_dist.tgz && rm -f $Base/studio_dist.tgz"
  Remove-Item $tgz -ErrorAction SilentlyContinue
  Ok (CapRemote "ls -1 $Alex/studio/assets | grep index")
}

# ---- 4) 安全检查 + 重启 ----
if ($NoRestart) {
  Say "已跳过重启 (-NoRestart)。手动: ssh $Server 'bash $Base/stop_novelTTS.sh && bash $Base/start_novelTTS.sh'"
  return
}

Say "重启前安全检查"
$up = CapRemote "curl -s -m 5 http://127.0.0.1:4200/api/system/stats >/dev/null 2>&1 && echo UP || echo DOWN"
if ($up -eq 'UP') {
  $busy = @()
  foreach ($t in $Tasks) {
    $s = CapRemote "curl -s -m 5 http://127.0.0.1:4200/api/status/$t"
    if (($s -replace '\s', '') -match '"running":true') { $busy += $t }
  }
  if ($busy.Count -gt 0) {
    if (-not $Force) { Die "有生成任务在跑: $($busy -join ', ')。等它跑完再部署，或加 -Force 强推（会中断任务）" }
    Write-Host "   [!] -Force: 将中断这些任务: $($busy -join ', ')" -ForegroundColor Yellow
  } else {
    Ok "无生成任务在跑"
  }
} else {
  Ok "后端当前未响应，按停机窗口处理"
}

Say "停止主服务"
RunRemote "bash $Base/stop_novelTTS.sh"
Say "启动主服务（脚本内轮询就绪，最长 240s）"
RunRemote "bash $Base/start_novelTTS.sh"

# ---- 5) 收尾自检 ----
Say "就绪自检"
$code = CapRemote "curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:4200/"
if ($code -ne '200') { Die "主服务未就绪（HTTP $code），查 $Base/logs/alexandria.log" }
Ok "主服务 200 OK"
Ok ("clone_voices/list -> " + (CapRemote "curl -s -m 5 http://127.0.0.1:4200/api/clone_voices/list | head -c 60"))
Say "完成。前端记得强刷（index.html no-store，但已加载的旧 JS 不会自换）"
