#Requires -Version 5.1
<#
.SYNOPSIS
    One-Command Reviewer Setup Script for Tenant Intelligence (Windows PowerShell).
.DESCRIPTION
    Configures environment secrets, builds Docker services, applies migrations,
    and bootstraps the Tenant Administrator without host Python dependencies.
#>

[CmdletBinding()]
param(
    [string]$TenantName = "Instructor Evaluation",
    [string]$TenantCode = "instructor-review",
    [string]$AdminEmail = "instructor@demo.example",
    [string]$AdminFullName = "Instructor Reviewer",
    [string]$AdminPassword = "",
    [string]$GroqApiKey = "",
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    $scriptDir = $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($scriptDir)) {
        if ($MyInvocation.MyCommand.Path) {
            $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
        } else {
            $scriptDir = Get-Location
        }
    }
    $rootDir = [System.IO.Path]::GetFullPath((Join-Path -Path $scriptDir -ChildPath ".."))
    return $rootDir
}

function New-Base64UrlSecret([int]$byteCount = 32) {
    $bytes = New-Object byte[] $byteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $base64 = [Convert]::ToBase64String($bytes)
    return $base64.Replace('+', '-').Replace('/', '_').TrimEnd('=')
}

function Test-IsPlaceholder([string]$val) {
    if ([string]::IsNullOrWhiteSpace($val)) { return $true }
    $v = $val.Trim().ToLowerInvariant()
    if ($v.StartsWith("replace-") -or $v.StartsWith("change-me") -or $v.StartsWith("changeme") -or $v.StartsWith("your-")) { return $true }
    return $false
}

function Test-IsGroqKeyValid([string]$val) {
    if (Test-IsPlaceholder $val) { return $false }
    if ($val.Trim().Length -lt 20) { return $false }
    return $true
}

function Get-EnvMap([string]$filePath) {
    $map = @{}
    if (Test-Path $filePath) {
        foreach ($line in Get-Content $filePath) {
            $trimmed = $line.Trim()
            if ($trimmed -and -not $trimmed.StartsWith("#") -and $trimmed.Contains("=")) {
                $parts = $trimmed.Split("=", 2)
                $map[$parts[0].Trim()] = $parts[1].Trim()
            }
        }
    }
    return $map
}

function Set-EnvVariable([string]$filePath, [string]$key, [string]$value) {
    $lines = @()
    if (Test-Path $filePath) {
        $lines = Get-Content $filePath
    }
    $updated = $false
    $newLines = foreach ($line in $lines) {
        if ($line -match "^\s*${key}\s*=") {
            "${key}=${value}"
            $updated = $true
        } else {
            $line
        }
    }
    if (-not $updated) {
        $newLines += "${key}=${value}"
    }
    $newLines | Set-Content $filePath -Encoding UTF8
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "TENANT INTELLIGENCE - REVIEWER SETUP" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# Stage 1: Checking prerequisites
Write-Host "[Stage 1/7] Checking prerequisites..." -ForegroundColor Cyan
if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is required but not found in PATH. Please install and start Docker Desktop."
    exit 1
}

$dockerComposeCmd = "docker compose"
$composeCheck = & docker compose version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker Compose v2 is required but 'docker compose' failed."
    exit 1
}

function Test-IsPortOccupied([int]$port) {
    try {
        $con = New-Object System.Net.Sockets.TcpClient
        $con.Connect("127.0.0.1", $port)
        $con.Close()
        return $true
    } catch {
        return $false
    }
}

function Get-RequestedPort([string]$envVarName, [string]$altEnvVarName, [string]$fileKey, [int]$defaultPort, [string]$envFilePath) {
    $val = [Environment]::GetEnvironmentVariable($envVarName)
    if (-not [string]::IsNullOrWhiteSpace($val)) {
        if ($val -match "^\d+$") { return [int]$val }
    }
    if ($altEnvVarName) {
        $altVal = [Environment]::GetEnvironmentVariable($altEnvVarName)
        if (-not [string]::IsNullOrWhiteSpace($altVal)) {
            if ($altVal -match "^\d+$") { return [int]$altVal }
        }
    }
    if (Test-Path $envFilePath) {
        $map = Get-EnvMap $envFilePath
        if ($map.ContainsKey($fileKey) -and -not [string]::IsNullOrWhiteSpace($map[$fileKey])) {
            if ($map[$fileKey] -match "^\d+$") { return [int]$map[$fileKey] }
        }
    }
    return $defaultPort
}

function Resolve-AvailableHostPort([string]$label, [int]$requestedPort, [int]$maxScans = 100) {
    if ($requestedPort -lt 1 -or $requestedPort -gt 65535) {
        Write-Error "Invalid $label host port: $requestedPort. Port must be between 1 and 65535."
        exit 1
    }

    if (-not (Test-IsPortOccupied $requestedPort)) {
        return $requestedPort
    }

    Write-Host "[Warning] $label host port $requestedPort is already in use." -ForegroundColor Yellow

    $candidateLimit = [Math]::Min($requestedPort + $maxScans, 65535)
    for ($p = $requestedPort + 1; $p -le $candidateLimit; $p++) {
        if (-not (Test-IsPortOccupied $p)) {
            Write-Host "[Resolution] Automatically selected $label host port $p." -ForegroundColor Green
            return $p
        }
    }

    Write-Error "Could not find an available $label host port within $maxScans ports of $requestedPort."
    exit 1
}

if (-not (Test-Path "docker-compose.yml") -or -not (Test-Path ".env.example")) {
    Write-Error "Required project files docker-compose.yml and .env.example not found in $repoRoot"
    exit 1
}

$envPath = Join-Path $repoRoot ".env"
$envExamplePath = Join-Path $repoRoot ".env.example"

if (-not (Test-Path $envPath)) {
    if (Test-Path $envExamplePath) {
        Copy-Item $envExamplePath $envPath
        Write-Host "Created .env from .env.example" -ForegroundColor Green
    }
}

$reqFrontendPort = Get-RequestedPort "FRONTEND_PORT" $null "FRONTEND_PORT" 3000 $envPath
$frontendPort = Resolve-AvailableHostPort "Frontend" $reqFrontendPort

$reqApiPort = Get-RequestedPort "API_PORT" "BACKEND_PORT" "API_PORT" 8000 $envPath
$apiPort = Resolve-AvailableHostPort "API" $reqApiPort

$reqPostgresPort = Get-RequestedPort "POSTGRES_HOST_PORT" "POSTGRES_PORT" "POSTGRES_HOST_PORT" 55432 $envPath
$postgresHostPort = Resolve-AvailableHostPort "PostgreSQL" $reqPostgresPort

$reqMinioPort = Get-RequestedPort "MINIO_CONSOLE_HOST_PORT" "MINIO_CONSOLE_PORT" "MINIO_CONSOLE_HOST_PORT" 9001 $envPath
$minioConsolePort = Resolve-AvailableHostPort "MinIO Console" $reqMinioPort

$env:FRONTEND_PORT = "$frontendPort"
$env:API_PORT = "$apiPort"
$env:BACKEND_PORT = "$apiPort"
$env:POSTGRES_HOST_PORT = "$postgresHostPort"
$env:POSTGRES_PORT = "$postgresHostPort"
$env:MINIO_CONSOLE_HOST_PORT = "$minioConsolePort"
$env:MINIO_CONSOLE_PORT = "$minioConsolePort"

Write-Host "Host Port Summary:" -ForegroundColor Cyan
Write-Host "  Frontend:          $frontendPort" -ForegroundColor Green
Write-Host "  API:               $apiPort" -ForegroundColor Green
Write-Host "  PostgreSQL:        $postgresHostPort" -ForegroundColor Green
Write-Host "  MinIO Console:     $minioConsolePort" -ForegroundColor Green

# Stage 2: Preparing configuration
Write-Host "[Stage 2/7] Preparing configuration..." -ForegroundColor Cyan
$envPath = Join-Path $repoRoot ".env"
$envExamplePath = Join-Path $repoRoot ".env.example"

if (-not (Test-Path $envPath)) {
    Copy-Item $envExamplePath $envPath
    Write-Host "Created .env from .env.example" -ForegroundColor Green
}

$envMap = Get-EnvMap $envPath

# Generate JWT_SECRET if missing or placeholder
$jwtSecret = $envMap["JWT_SECRET"]
if (Test-IsPlaceholder $jwtSecret -or ($jwtSecret -and $jwtSecret.Length -lt 32)) {
    $newJwt = New-Base64UrlSecret 48
    Set-EnvVariable $envPath "JWT_SECRET" $newJwt
    Write-Host "Generated secure JWT_SECRET" -ForegroundColor Green
}

# Generate CONNECTION_ENCRYPTION_KEY if missing or placeholder
$connKey = $envMap["CONNECTION_ENCRYPTION_KEY"]
if (Test-IsPlaceholder $connKey) {
    $newConn = New-Base64UrlSecret 32
    Set-EnvVariable $envPath "CONNECTION_ENCRYPTION_KEY" $newConn
    Write-Host "Generated secure CONNECTION_ENCRYPTION_KEY" -ForegroundColor Green
}

# Generate RESULT_MASKING_KEY if missing or placeholder
$maskKey = $envMap["RESULT_MASKING_KEY"]
if (Test-IsPlaceholder $maskKey -or ($maskKey -and $maskKey.Length -lt 32)) {
    $newMask = New-Base64UrlSecret 48
    Set-EnvVariable $envPath "RESULT_MASKING_KEY" $newMask
    Write-Host "Generated secure RESULT_MASKING_KEY" -ForegroundColor Green
}

# Ensure MinIO object-storage credentials are non-placeholder values
$minioUser = $envMap["MINIO_ROOT_USER"]
if (Test-IsPlaceholder $minioUser -or (-not $minioUser) -or $minioUser.Length -lt 8) {
    Set-EnvVariable $envPath "MINIO_ROOT_USER" "local-minio-root-user"
}
$minioPass = $envMap["MINIO_ROOT_PASSWORD"]
if (Test-IsPlaceholder $minioPass -or (-not $minioPass) -or $minioPass.Length -lt 8) {
    Set-EnvVariable $envPath "MINIO_ROOT_PASSWORD" "local-minio-root-password-32-bytes"
}
$minioKey = $envMap["MINIO_APP_ACCESS_KEY"]
if (Test-IsPlaceholder $minioKey -or (-not $minioKey) -or $minioKey.Length -lt 8) {
    Set-EnvVariable $envPath "MINIO_APP_ACCESS_KEY" "local-minio-app-user"
}
$minioSecret = $envMap["MINIO_APP_SECRET_KEY"]
if (Test-IsPlaceholder $minioSecret -or (-not $minioSecret) -or $minioSecret.Length -lt 8) {
    Set-EnvVariable $envPath "MINIO_APP_SECRET_KEY" "local-minio-app-password-32-bytes"
}

# Reload env map after auto-generations
$envMap = Get-EnvMap $envPath

# Check GROQ_API_KEY
$currentGroq = $envMap["GROQ_API_KEY"]
if ($GroqApiKey) {
    Set-EnvVariable $envPath "GROQ_API_KEY" $GroqApiKey
    $currentGroq = $GroqApiKey
}

if (-not (Test-IsGroqKeyValid $currentGroq)) {
    if ($NonInteractive) {
        Write-Error "GROQ_API_KEY is missing or invalid in .env and script is running in NonInteractive mode."
        exit 1
    }
    Write-Host ""
    Write-Host "A valid Groq API key is required for the AI Text-to-SQL and document-chat features." -ForegroundColor Yellow
    $secureGroq = Read-Host -Prompt "Please enter your GROQ_API_KEY" -AsSecureString
    $bstrGroq = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureGroq)
    $enteredGroq = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstrGroq)
    
    if (-not (Test-IsGroqKeyValid $enteredGroq)) {
        Write-Error "Invalid GROQ_API_KEY entered. Key must be at least 20 characters and non-placeholder."
        exit 1
    }
    Set-EnvVariable $envPath "GROQ_API_KEY" $enteredGroq
    Write-Host "GROQ_API_KEY updated successfully." -ForegroundColor Green
}

# Check Administrator Password
if (-not $AdminPassword) {
    if ($NonInteractive) {
        Write-Error "AdminPassword parameter is required in NonInteractive mode."
        exit 1
    }
    $securePass = Read-Host -Prompt "Enter desired Administrator password (min 12 chars)" -AsSecureString
    $bstrPass = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePass)
    $AdminPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstrPass)
}

if (-not $AdminPassword -or $AdminPassword.Length -lt 12) {
    Write-Error "Administrator password must be at least 12 characters."
    exit 1
}

# Validate compose configuration
$configCheck = & docker compose config --quiet 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker Compose configuration validation failed. Please inspect .env for missing required values."
    exit 1
}

# Stage 3: Building services
Write-Host "[Stage 3/7] Building and starting services..." -ForegroundColor Cyan
& docker compose up --build -d
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start Docker Compose services."
    exit 1
}

# Stage 4 & 5: Waiting for readiness
Write-Host "[Stage 4/7] Waiting for database and services..." -ForegroundColor Cyan
Write-Host "[Stage 5/7] Applying migrations and verifying API readiness..." -ForegroundColor Cyan

$timeoutSeconds = 120
$startTime = Get-Date
$backendReady = $false
$frontendReady = $false

while (((Get-Date) - $startTime).TotalSeconds -lt $timeoutSeconds) {
    try {
        if (-not $backendReady) {
            $res = Invoke-RestMethod -Uri "http://localhost:${apiPort}/api/health/ready" -Method Get -TimeoutSec 3 -ErrorAction SilentlyContinue
            if ($res -and $res.status -eq "ready") {
                $backendReady = $true
            }
        }
        if (-not $frontendReady) {
            $fRes = Invoke-RestMethod -Uri "http://localhost:${frontendPort}/api/health" -Method Get -TimeoutSec 3 -ErrorAction SilentlyContinue
            if ($fRes -and $fRes.status -eq "ok") {
                $frontendReady = $true
            }
        }
    } catch {}

    if ($backendReady -and $frontendReady) {
        break
    }
    Start-Sleep -Seconds 3
}

if (-not $backendReady -or -not $frontendReady) {
    Write-Host "Services did not report ready within $timeoutSeconds seconds." -ForegroundColor Red
    Write-Host "Collecting safe diagnostic evidence..." -ForegroundColor Yellow
    Write-Host "Failed Service: api" -ForegroundColor Red
    $apiLogs = & docker compose logs --no-color --tail=100 api 2>&1
    $safeReasons = $apiLogs | Select-String -Pattern "ValidationError|Error|Exception|failed|Value error" | Select-Object -Last 5
    if ($safeReasons) {
        Write-Host "Safe API Error Reason:" -ForegroundColor Red
        $safeReasons | ForEach-Object { Write-Host "  $($_.Line.Trim())" -ForegroundColor Yellow }
    }
    exit 1
}

# Stage 6: Provisioning workspace administrator
Write-Host "[Stage 6/7] Provisioning workspace administrator..." -ForegroundColor Cyan
$env:BOOTSTRAP_ADMIN_PASSWORD = $AdminPassword
$execCode = 1
$execResult = ""
try {
    $execResult = & docker compose exec -T -e BOOTSTRAP_ADMIN_PASSWORD api python -m scripts.bootstrap `
        --tenant-name "$TenantName" `
        --tenant-code "$TenantCode" `
        --admin-email "$AdminEmail" `
        --admin-full-name "$AdminFullName" 2>&1
    $execCode = $LASTEXITCODE
} finally {
    Remove-Item Env:BOOTSTRAP_ADMIN_PASSWORD -ErrorAction SilentlyContinue
    $AdminPassword = ""
}

if ($execCode -ne 0) {
    Write-Host "Administrator provisioning failed safely:" -ForegroundColor Red
    Write-Host $execResult
    exit 1
}

# Stage 7: Verifying login readiness
Write-Host "[Stage 7/7] Verifying login readiness..." -ForegroundColor Cyan
try {
    $meCheck = Invoke-RestMethod -Uri "http://localhost:${apiPort}/api/health/live" -Method Get -TimeoutSec 3
} catch {
    Write-Error "API liveness check failed after bootstrap."
    exit 1
}

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "INSTRUCTOR EVALUATION WORKSPACE READY" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "Frontend URL:            http://localhost:$frontendPort"
Write-Host "API URL:                 http://localhost:$apiPort"
Write-Host "API Documentation URL:   http://localhost:${apiPort}/docs"
Write-Host "Health URL:              http://localhost:${apiPort}/api/health/ready"
Write-Host "MinIO Console URL:       http://localhost:$minioConsolePort"
Write-Host "Tenant Code:             $TenantCode"
Write-Host "Administrator Email:     $AdminEmail"
Write-Host "Administrator Full Name: $AdminFullName"
Write-Host "Password:                (The password supplied in the private document)"
Write-Host "======================================================================" -ForegroundColor Green
