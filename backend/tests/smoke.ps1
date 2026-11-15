param(
    [string]$BackendBaseUrl = 'http://127.0.0.1:8000',
    [string]$FrontendBaseUrl = 'http://127.0.0.1:5173'
)

$ErrorActionPreference = 'Stop'

function Assert-Equal($Actual, $Expected, [string]$Name) {
    if ($Actual -ne $Expected) {
        throw "$Name failed: expected '$Expected', got '$Actual'."
    }
    Write-Output "PASS $Name"
}

function Get-HttpStatus([scriptblock]$Request) {
    try {
        $null = & $Request
        return 200
    } catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            return [int]$_.Exception.Response.StatusCode.value__
        }
        throw
    }
}

$health = Invoke-RestMethod -Uri "$BackendBaseUrl/api/health" -TimeoutSec 5
Assert-Equal $health.status 'healthy' 'backend health'

$spec = Invoke-RestMethod -Uri "$BackendBaseUrl/openapi.json" -TimeoutSec 5
if (-not $spec.paths.'/api/mission/analyze'.post) { throw 'Mission route is missing from OpenAPI.' }
Write-Output 'PASS mission route registered'
if (-not $spec.paths.'/api/experiments'.get -or -not $spec.paths.'/api/experiments/compare'.post -or -not $spec.paths.'/api/reports/mission'.post -or -not $spec.paths.'/api/reports/experiments/compare'.post) { throw 'Phase 4 experiment or report API route is missing from OpenAPI.' }
Write-Output 'PASS Phase 4 experiment explorer and mission report routes registered'
if (-not $spec.paths.'/api/ai/query'.post) { throw 'AI query route is missing from OpenAPI.' }
Write-Output 'PASS AI query route registered'
foreach ($path in @('/api/dashboard/stats', '/api/investigations', '/api/search', '/api/analytics/datapoints', '/api/sources')) {
    if ($spec.paths.PSObject.Properties.Name -notcontains $path) { throw "Existing API route is missing: $path" }
}
Write-Output 'PASS existing dashboard, investigation, search, analytics and source routes remain registered'

$invalidBody = '{"parameters":{"environment":"ISS Cabin","oxygen_percent":41,"pressure_atm":1,"airflow_cm_s":10,"gravity":"microgravity","material":"pmma"},"question":"Validate an out-of-range oxygen value."}'
$invalidStatus = Get-HttpStatus { Invoke-RestMethod -Method Post -Uri "$BackendBaseUrl/api/mission/analyze" -ContentType 'application/json' -Body $invalidBody -TimeoutSec 5 }
Assert-Equal $invalidStatus 422 'mission input validation'

$invalidPressureBody = '{"parameters":{"environment":"Lunar Habitat","oxygen_percent":34,"pressure_atm":1.6,"airflow_cm_s":15,"gravity":"lunar","material":"pmma"},"question":"Validate an out-of-range pressure value."}'
$invalidPressureStatus = Get-HttpStatus { Invoke-RestMethod -Method Post -Uri "$BackendBaseUrl/api/mission/analyze" -ContentType 'application/json' -Body $invalidPressureBody -TimeoutSec 5 }
Assert-Equal $invalidPressureStatus 422 'mission pressure validation'

$missingParametersBody = '{"parameters":{"environment":"Lunar Habitat","oxygen_percent":34,"airflow_cm_s":15,"gravity":"lunar","material":"pmma"}}'
$missingParametersStatus = Get-HttpStatus { Invoke-RestMethod -Method Post -Uri "$BackendBaseUrl/api/mission/analyze" -ContentType 'application/json' -Body $missingParametersBody -TimeoutSec 5 }
Assert-Equal $missingParametersStatus 422 'mission required parameters validation'

if (-not $health.gemini_configured) {
    $validBody = '{"parameters":{"environment":"Lunar Habitat","oxygen_percent":34,"pressure_atm":0.56,"airflow_cm_s":15,"gravity":"lunar","material":"pmma"},"question":"How does 34% oxygen affect PMMA combustion in a lunar habitat?"}'
    $missingGeminiStatus = Get-HttpStatus { Invoke-RestMethod -Method Post -Uri "$BackendBaseUrl/api/mission/analyze" -ContentType 'application/json' -Body $validBody -TimeoutSec 5 }
    Assert-Equal $missingGeminiStatus 503 'missing Gemini configuration'
} else {
    Write-Output 'SKIP missing Gemini test: Gemini is configured; no live generation request sent.'
}

$emptyEvidence = Invoke-RestMethod -Method Post -Uri "$BackendBaseUrl/api/ai/query" -ContentType 'application/json' -Body '{"question":"What evidence is recorded?","investigation_filter":"NO_MATCHING_AUDIT_RECORD"}' -TimeoutSec 5
Assert-Equal $emptyEvidence.has_sufficient_evidence $false 'AI insufficient evidence flag'
if ($emptyEvidence.answer -notmatch 'Insufficient evidence') { throw 'AI insufficient evidence message was not returned.' }
Write-Output 'PASS AI insufficient evidence response'

$investigationsResponse = Invoke-WebRequest -UseBasicParsing -Uri "$BackendBaseUrl/api/investigations" -TimeoutSec 5
$parsedInvestigations = ConvertFrom-Json -InputObject $investigationsResponse.Content
$investigations = @()
if ($null -ne $parsedInvestigations) {
    $investigations = @($parsedInvestigations)
}
$investigationsBefore = $investigations.Count
if ($investigationsBefore -lt 1) { throw 'Existing investigation records are missing.' }
Assert-Equal $investigationsBefore 5 'investigation response count'
$verifiedResponse = Invoke-WebRequest -UseBasicParsing -Uri "$BackendBaseUrl/api/analytics/datapoints?flight_only=true" -TimeoutSec 5
$parsedVerified = ConvertFrom-Json -InputObject $verifiedResponse.Content
$verifiedOnly = @()
if ($null -ne $parsedVerified) {
    $verifiedOnly = @($parsedVerified)
}
Assert-Equal $verifiedOnly.Count 0 'legacy flags excluded from verified flight data'
$localResponse = Invoke-WebRequest -UseBasicParsing -Uri "$BackendBaseUrl/api/analytics/datapoints?flight_only=false" -TimeoutSec 5
$parsedLocalData = ConvertFrom-Json -InputObject $localResponse.Content
$localData = @()
if ($null -ne $parsedLocalData) {
    $localData = @($parsedLocalData)
}
Assert-Equal $localData.Count 12 'local datapoint response count'
$unverifiedStatusFailures = @($localData | Where-Object {
    $_.evidence_status -notlike '*provenance unverified*'
})
if ($unverifiedStatusFailures.Count -gt 0) {
    throw 'A local datapoint was returned without the unverified provenance status.'
}
Write-Output 'PASS local datapoints carry unverified provenance status'

$statsAfter = Invoke-RestMethod -Uri "$BackendBaseUrl/api/dashboard/stats" -TimeoutSec 5
Assert-Equal $statsAfter.total_investigations $investigationsBefore 'existing database records preserved'
Assert-Equal $statsAfter.total_investigations 5 'investigation record count'
Assert-Equal $statsAfter.total_datapoints 12 'datapoint record count'

$storedExperiments = Invoke-RestMethod -Uri "$BackendBaseUrl/api/experiments" -TimeoutSec 5
$storedPsi = @($storedExperiments.records | Where-Object { $_.record_kind -eq 'psi_investigation' })
$storedNtrs = @($storedExperiments.records | Where-Object { $_.record_kind -eq 'ntrs_publication' })
if ($storedPsi.Count -lt 1 -or $storedNtrs.Count -lt 1) { throw 'Stored PSI or NTRS records are missing from the experiment explorer.' }
Write-Output "PASS stored NASA experiment records (PSI=$($storedPsi.Count), NTRS=$($storedNtrs.Count))"

$psiDetail = Invoke-RestMethod -Uri "$BackendBaseUrl/api/experiments/$($storedPsi[0].record_id)" -TimeoutSec 5
if ($psiDetail.provenance_category -ne 'nasa_origin_source_link_verified') { throw 'PSI source-link provenance label is missing.' }
if (@($psiDetail.dataset_files | Where-Object { $_.retrieval_status -eq 'retrieved' -and $_.measurements_parsed -eq $false }).Count -lt 1) {
    throw 'Stored PSI raw download is not distinguished from parsed measurements.'
}
Write-Output 'PASS PSI source provenance and raw-file / unparsed-measurement labels'

$recordIds = @($storedExperiments.records | Select-Object -First 2 | ForEach-Object { $_.record_id })
if ($recordIds.Count -eq 2) {
    $compareBody = @{ record_ids = $recordIds } | ConvertTo-Json -Compress
    $compareResult = Invoke-RestMethod -Method Post -Uri "$BackendBaseUrl/api/experiments/compare" -ContentType 'application/json' -Body $compareBody -TimeoutSec 5
    if ($compareResult.limitations -notcontains 'This comparison does not establish scientific equivalence or show that the combined conditions were tested.') {
        throw 'Experiment comparison is missing its scientific-equivalence limitation.'
    }
    Write-Output 'PASS comparison reports evidence limits without a similarity score'
}

$proxyHealth = Invoke-RestMethod -Uri "$FrontendBaseUrl/api/health" -TimeoutSec 10
Assert-Equal $proxyHealth.status 'healthy' 'Vite API proxy reaches backend'
$proxyExperiments = Invoke-RestMethod -Uri "$FrontendBaseUrl/api/experiments" -TimeoutSec 10
Assert-Equal @($proxyExperiments.records).Count @($storedExperiments.records).Count 'Vite proxy reaches stored NASA experiment API'
$proxiedMissionStatus = Get-HttpStatus { Invoke-RestMethod -Method Post -Uri "$FrontendBaseUrl/api/mission/analyze" -ContentType 'application/json' -Body $invalidBody -TimeoutSec 10 }
Assert-Equal $proxiedMissionStatus 422 'Vite proxy reaches the current mission API'
if (-not $health.gemini_configured) {
    $proxiedMissingGeminiStatus = Get-HttpStatus { Invoke-RestMethod -Method Post -Uri "$FrontendBaseUrl/api/mission/analyze" -ContentType 'application/json' -Body $validBody -TimeoutSec 10 }
    Assert-Equal $proxiedMissingGeminiStatus 503 'Vite proxy preserves mission service configuration error'
} else {
    Write-Output 'SKIP proxied Gemini generation: Gemini is configured; no live generation request sent.'
}
