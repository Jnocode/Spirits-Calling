[CmdletBinding()]
[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$EngineRoot = "",
    [string]$OutputDirectory = "",
    [string]$VersionFile = "",
    [switch]$DryRun,
    [string[]]$AdditionalUatArgs = @()
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

function Resolve-AbsolutePath([string]$Path, [string]$BasePath) {
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $BasePath $Path))
}

function Assert-File([string]$Path, [string]$Description) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description not found: $Path"
    }
}

$ProjectRoot = Resolve-AbsolutePath $ProjectRoot (Get-Location).Path
if ([string]::IsNullOrWhiteSpace($EngineRoot)) {
    $EngineRoot = if ($env:UE_5_8_ROOT) { $env:UE_5_8_ROOT } else { "D:\Epic Games\UE_5.8" }
}
$EngineRoot = Resolve-AbsolutePath $EngineRoot (Get-Location).Path
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $ProjectRoot "Builds\Windows"
} else {
    $OutputDirectory = Resolve-AbsolutePath $OutputDirectory $ProjectRoot
}
if ([string]::IsNullOrWhiteSpace($VersionFile)) {
    $VersionFile = Join-Path $ProjectRoot "Config\SpiritsVersion.json"
} else {
    $VersionFile = Resolve-AbsolutePath $VersionFile $ProjectRoot
}

$ProjectFile = Join-Path $ProjectRoot "Spirits_Calling.uproject"
$DefaultGameIni = Join-Path $ProjectRoot "Config\DefaultGame.ini"
$DefaultEngineIni = Join-Path $ProjectRoot "Config\DefaultEngine.ini"
$BuildVersionFile = Join-Path $EngineRoot "Engine\Build\Build.version"
$RunUat = Join-Path $EngineRoot "Engine\Build\BatchFiles\RunUAT.bat"

Assert-File $ProjectFile "Unreal project"
Assert-File $DefaultGameIni "DefaultGame.ini"
Assert-File $DefaultEngineIni "DefaultEngine.ini"
Assert-File $VersionFile "version source-of-truth"
Assert-File $BuildVersionFile "UE Build.version"

$Project = Get-Content -LiteralPath $ProjectFile -Raw -Encoding UTF8 | ConvertFrom-Json
$Version = Get-Content -LiteralPath $VersionFile -Raw -Encoding UTF8 | ConvertFrom-Json
$EngineBuild = Get-Content -LiteralPath $BuildVersionFile -Raw -Encoding UTF8 | ConvertFrom-Json
$GameIni = Get-Content -LiteralPath $DefaultGameIni -Raw -Encoding UTF8
$EngineIni = Get-Content -LiteralPath $DefaultEngineIni -Raw -Encoding UTF8

if ([string]$Project.EngineAssociation -ne "5.8") {
    throw "Spirits_Calling.uproject EngineAssociation must be 5.8; found '$($Project.EngineAssociation)'."
}
if ([string]$Version.engineVersion -ne "5.8") {
    throw "Version source-of-truth must declare engineVersion 5.8; found '$($Version.engineVersion)'."
}
if ([int]$Version.schemaVersion -ne 1) {
    throw "Unsupported version source schema: $($Version.schemaVersion)"
}
if ([string]$Version.displayVersion -ne "v$($Version.projectVersion)") {
    throw "displayVersion '$($Version.displayVersion)' must be the canonical projectVersion prefixed with 'v'."
}
if ([string]$Version.projectName -ne "Spirits Calling" -or [string]$Version.companyName -ne "XiuJiang Studio") {
    throw "Version metadata identity does not match the project identity."
}
if ($GameIni -notmatch '(?m)^\s*ProjectName=Spirits Calling\s*$' -or
    $GameIni -notmatch '(?m)^\s*ProjectDisplayedTitle=.*Spirits Calling' -or
    $GameIni -notmatch '(?m)^\s*CompanyName=XiuJiang Studio\s*$') {
    throw "DefaultGame.ini project identity does not match the version source-of-truth."
}

$projectVersionMatch = [regex]::Match($GameIni, "(?m)^\s*ProjectVersion=([^\r\n]+)")
if (-not $projectVersionMatch.Success) {
    throw "DefaultGame.ini does not define ProjectVersion."
}
if ($projectVersionMatch.Groups[1].Value.Trim() -ne [string]$Version.projectVersion) {
    throw "ProjectVersion '$($projectVersionMatch.Groups[1].Value.Trim())' does not match version source '$($Version.projectVersion)'."
}
$RequiredGameConfig = @(
    "Build=IfProjectHasCode",
    "BuildConfiguration=PPBC_Shipping",
    'StagingDirectory=(Path="Builds/Windows")',
    "bUseIoStore=True",
    '+MapsToCook=(FilePath="/Game/Maps/DemoMap")'
)
foreach ($ConfigEntry in $RequiredGameConfig) {
    if ($GameIni -notmatch [regex]::Escape($ConfigEntry)) {
        throw "DefaultGame.ini is missing required packaging setting: $ConfigEntry"
    }
}
if ($EngineIni -notmatch '(?m)^\s*GameDefaultMap=/Game/Maps/DemoMap\.DemoMap\s*$') {
    throw "DefaultEngine.ini GameDefaultMap must remain /Game/Maps/DemoMap.DemoMap."
}

$engineMajorMinor = "$($EngineBuild.MajorVersion).$($EngineBuild.MinorVersion)"
if ($engineMajorMinor -ne "5.8") {
    throw "Selected engine root is not UE 5.8; Build.version reports $engineMajorMinor."
}

$SourceRevision = "unknown"
$Git = Get-Command git -ErrorAction SilentlyContinue
if ($null -ne $Git) {
    $SourceRevision = (& $Git.Source -C $ProjectRoot rev-parse --short HEAD 2>$null).Trim()
}
if ([string]::IsNullOrWhiteSpace($SourceRevision)) {
    $SourceRevision = "unknown"
}
if ($SourceRevision -eq "unknown" -and -not $DryRun) {
    throw "Cannot produce reproducible package metadata without a git source revision."
}

$UatArguments = @(
    "BuildCookRun",
    "-project=$ProjectFile",
    "-noP4",
    "-platform=Win64",
    "-clientconfig=Shipping",
    "-serverconfig=Shipping",
    "-build",
    "-cook",
    "-stage",
    "-pak",
    "-iostore",
    "-archive",
    "-archivedirectory=$OutputDirectory",
    "-map=/Game/Maps/DemoMap",
    "-utf8output"
)
$ReservedArgumentPatterns = @(
    '^-[Pp]roject=', '^-[Pp]latform=', '^-[Cc]lient[Cc]onfig=', '^-[Ss]erver[Cc]onfig=',
    '^-build$', '^-cook$', '^-stage$', '^-pak$', '^-iostore$', '^-archive$',
    '^-[Aa]rchive[Dd]irectory=', '^-[Mm]ap='
)
$ConflictingAdditionalArgs = @(
    $AdditionalUatArgs | Where-Object {
        $Candidate = [string]$_
        @($ReservedArgumentPatterns | Where-Object { $Candidate -match $_ }).Count -gt 0
    }
)
if ($ConflictingAdditionalArgs.Count -gt 0) {
    throw "AdditionalUatArgs cannot override the fixed packaging contract: $($ConflictingAdditionalArgs -join ', ')"
}
$UatArguments += $AdditionalUatArgs

$RequiredArguments = @("-platform=Win64", "-clientconfig=Shipping", "-serverconfig=Shipping", "-build", "-cook", "-stage", "-pak", "-iostore", "-archive", "-archivedirectory=$OutputDirectory", "-map=/Game/Maps/DemoMap")
$MissingArguments = @($RequiredArguments | Where-Object { $_ -notin $UatArguments })
if ($MissingArguments.Count -gt 0) {
    throw "BuildCookRun argument contract is incomplete: $($MissingArguments -join ', ')"
}

if (-not (Test-Path -LiteralPath $RunUat -PathType Leaf)) {
    if ($DryRun) {
        Write-Warning "RunUAT.bat not found under selected UE 5.8 root; dry-run will print the command only: $RunUat"
    } else {
        throw "RunUAT.bat not found under selected UE 5.8 root: $RunUat"
    }
}

$CommandPreview = "`"$RunUat`" " + (($UatArguments | ForEach-Object { if ($_ -match "\s") { "`"$_`"" } else { $_ } }) -join " ")
Write-Host "UE toolchain : $engineMajorMinor ($EngineRoot)"
Write-Host "Project      : $ProjectFile"
Write-Host "Version      : $($Version.projectVersion)"
Write-Host "Source       : $SourceRevision"
Write-Host "Output       : $OutputDirectory"
Write-Host "BuildCookRun : $CommandPreview"

if ($DryRun) {
    Write-Host "Dry-run complete; no build, cook, stage, archive, or metadata write was performed."
    exit 0
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
& $RunUat @UatArguments
if ($LASTEXITCODE -ne 0) {
    throw "BuildCookRun failed with exit code $LASTEXITCODE."
}

$Metadata = [ordered]@{
    schemaVersion = 1
    projectName = [string]$Version.projectName
    companyName = [string]$Version.companyName
    projectVersion = [string]$Version.projectVersion
    displayVersion = [string]$Version.displayVersion
    sourceRevision = $SourceRevision
    engineVersion = $engineMajorMinor
    engineBuild = [ordered]@{
        majorVersion = [int]$EngineBuild.MajorVersion
        minorVersion = [int]$EngineBuild.MinorVersion
        patchVersion = [int]$EngineBuild.PatchVersion
        changelist = [int64]$EngineBuild.Changelist
        branchName = [string]$EngineBuild.BranchName
    }
    engineRoot = $EngineRoot
    projectFile = $ProjectFile
    targetPlatform = "Win64"
    configuration = "Shipping"
    projectCodeBuild = $true
    ioStore = $true
    cookMaps = @("/Game/Maps/DemoMap")
    packagePath = $OutputDirectory
    generatedAtUtc = [DateTime]::UtcNow.ToString("o")
    buildCookRunArguments = $UatArguments
    declaredRuntimeVariants = @("Void", "Sands")
    declaredRuntimeReferences = @(
        "four civilization pattern hooks",
        "PC and PCVR menu",
        "achievement fallback/local log path",
        "nine audio assets",
        "S_Ambient loop or documented runtime fallback"
    )
    excludedStoreOnlyAssets = @("RawAssets/AI/Store/Store_capsule_concept.png")
}
$MetadataPath = Join-Path $OutputDirectory "SpiritsCalling-PackageMetadata.json"
$Metadata | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $MetadataPath -Encoding UTF8
Write-Host "Package metadata: $MetadataPath"
