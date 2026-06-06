# build-data.ps1 - Converts data/mattresses.csv to data/mattresses.json
# Run from repo root: .\build-data.ps1
# Uses $PSScriptRoot so it works regardless of the current working directory.

$csvPath = Join-Path $PSScriptRoot "data\mattresses.csv"
$jsonPath = Join-Path $PSScriptRoot "data\mattresses.json"
$esCsvPath = Join-Path $PSScriptRoot "data\mattresses-es.csv"

if (-not (Test-Path $csvPath)) {
    Write-Error "CSV not found at $csvPath"
    exit 1
}

$rows = Import-Csv -Path $csvPath

# Load Spanish translation CSV if it exists
$esLookup = @{}
if (Test-Path $esCsvPath) {
    $esRows = Import-Csv -Path $esCsvPath
    foreach ($esRow in $esRows) {
        $esLookup[$esRow.id.Trim()] = $esRow
    }
    Write-Host "Loaded $($esLookup.Count) Spanish translations from $esCsvPath"
} else {
    Write-Host "No Spanish CSV found at $esCsvPath - skipping Spanish fields"
}

$result = @{ gold = @(); silver = @(); bronze = @() }

foreach ($row in $rows) {
    $tier = $row.tier.Trim().ToLower()
    if (-not $result.ContainsKey($tier)) {
        Write-Warning "Unknown tier '$tier' for mattress $($row.id) - skipping"
        continue
    }

    # Build features array from pipe-delimited features column (scoring tags)
    # Convert kebab-case to camelCase to match quiz score keys
    $features = @()
    if ($row.features -and $row.features.Trim()) {
        $features = $row.features.Split('|') | ForEach-Object {
            $tag = $_.Trim().ToLower()
            # kebab-case to camelCase: split on hyphens, capitalize subsequent parts
            $parts = $tag.Split('-')
            $camel = $parts[0]
            for ($i = 1; $i -lt $parts.Length; $i++) {
                if ($parts[$i].Length -gt 0) {
                    $camel += $parts[$i].Substring(0,1).ToUpper() + $parts[$i].Substring(1)
                }
            }
            $camel
        }
    }

    # Build tags array from pipe-delimited displayBadges (display chips)
    $tags = @()
    if ($row.displayBadges -and $row.displayBadges.Trim()) {
        $tags = $row.displayBadges.Split('|') | ForEach-Object { $_.Trim() }
    }

    # Build reasons object from reason_* columns
    $reasons = @{}
    $reasonKeys = @(
        @{ csv = "reason_cooling";          json = "cooling" },
        @{ csv = "reason_pressureRelief";   json = "pressureRelief" },
        @{ csv = "reason_motionIsolation";  json = "motionIsolation" },
        @{ csv = "reason_support";          json = "support" },
        @{ csv = "reason_plush";            json = "plush" },
        @{ csv = "reason_medium";           json = "medium" },
        @{ csv = "reason_firm";             json = "firm" },
        @{ csv = "reason_durability";       json = "durability" },
        @{ csv = "reason_default";          json = "default" }
    )
    foreach ($rk in $reasonKeys) {
        $val = $row.($rk.csv)
        if ($val -and $val.Trim()) {
            $reasons[$rk.json] = $val.Trim()
        }
    }

    # Parse firmness score
    $firmness = 5
    if ($row.firmnessScore -and $row.firmnessScore.Trim()) {
        $firmness = [int]$row.firmnessScore.Trim()
    }

    # Parse locally-made to boolean
    $locallyMade = $false
    if ($row.'locally-made' -and $row.'locally-made'.Trim().ToLower() -eq 'yes') {
        $locallyMade = $true
    }

    $subBrand = ""
    if ($row.subBrand -and $row.subBrand.Trim()) { $subBrand = $row.subBrand.Trim() }
    # pitchKey is internal-only — used by SUBBRAND_NOTES lookup cascade in the renderer
    # (pitchKey || subBrand). Customer display reads subBrand. Most rows leave this empty;
    # populated only when one subBrand banner needs to split into multiple sales pitches.
    $pitchKey = ""
    if ($row.pitchKey -and $row.pitchKey.Trim()) { $pitchKey = $row.pitchKey.Trim() }
    # archetype is customer/RSA-visible — renders as the chip tag "[tier] · [archetype]"
    # in the handoff redesign. See docs/5d-content-spec.md "Handoff Screen Redesign".
    $archetype = ""
    if ($row.archetype -and $row.archetype.Trim()) { $archetype = $row.archetype.Trim() }
    # displayPriority is a sequencing tiebreaker — lower = earlier. Manufacturer brands
    # default to 1, retailer-house brands to 2, so a tied score never elevates a house
    # pick above a manufacturer pick. Defaults to 1 if missing.
    $displayPriority = 1
    if ($row.displayPriority -and $row.displayPriority.Trim()) {
        $displayPriority = [int]$row.displayPriority.Trim()
    }
    $firmnessLbl = ""
    if ($row.firmnessLabel -and $row.firmnessLabel.Trim()) { $firmnessLbl = $row.firmnessLabel.Trim() }
    $highlight = ""
    if ($row.highlight -and $row.highlight.Trim()) { $highlight = $row.highlight.Trim() }
    $topPickEn = ""
    if ($row.topPickReason -and $row.topPickReason.Trim()) { $topPickEn = $row.topPickReason.Trim() }
    $differentiatorEn = @(
        @{
            title  = if ($row.differentiator1Title) { $row.differentiator1Title.Trim() } else { "" }
            detail = if ($row.differentiator1Detail) { $row.differentiator1Detail.Trim() } else { "" }
        },
        @{
            title  = if ($row.differentiator2Title) { $row.differentiator2Title.Trim() } else { "" }
            detail = if ($row.differentiator2Detail) { $row.differentiator2Detail.Trim() } else { "" }
        }
    )

    # Auto-resolve image URL from images/mattresses/ folder
    $imageUrl = ""
    $imgName = $row.name.Trim().ToLower()
    $imgDir = Join-Path $PSScriptRoot "images\mattresses"
    foreach ($ext in @("jpg", "png", "webp")) {
        if (Test-Path "$imgDir\$imgName.$ext") {
            $imageUrl = "images/mattresses/$imgName.$ext"
            break
        }
    }

    # Build Spanish fields if translation exists
    $tags_es = @()
    $highlight_es = ""
    $reasons_es = @{}
    $topPickEs = ""
    $differentiatorEs = @(
        @{ title = ""; detail = "" },
        @{ title = ""; detail = "" }
    )
    $mattressId = $row.id.Trim()
    if ($esLookup.ContainsKey($mattressId)) {
        $esRow = $esLookup[$mattressId]

        # Spanish display badges -> tags_es
        if ($esRow.displayBadges -and $esRow.displayBadges.Trim()) {
            $tags_es = $esRow.displayBadges.Split('|') | ForEach-Object { $_.Trim() }
        }

        # Spanish highlight
        if ($esRow.highlight -and $esRow.highlight.Trim()) {
            $highlight_es = $esRow.highlight.Trim()
        }

        # Spanish reasons
        foreach ($rk in $reasonKeys) {
            $esVal = $esRow.($rk.csv)
            if ($esVal -and $esVal.Trim()) {
                $reasons_es[$rk.json] = $esVal.Trim()
            }
        }

        # Spanish top-pick reason (single string, not an object of keys)
        if ($esRow.topPickReason -and $esRow.topPickReason.Trim()) {
            $topPickEs = $esRow.topPickReason.Trim()
        }

        $differentiatorEs = @(
            @{
                title  = if ($esRow.differentiator1Title) { $esRow.differentiator1Title.Trim() } else { "" }
                detail = if ($esRow.differentiator1Detail) { $esRow.differentiator1Detail.Trim() } else { "" }
            },
            @{
                title  = if ($esRow.differentiator2Title) { $esRow.differentiator2Title.Trim() } else { "" }
                detail = if ($esRow.differentiator2Detail) { $esRow.differentiator2Detail.Trim() } else { "" }
            }
        )
    }

    # Assemble bilingual {en, es} object. Only emit if at least one language is populated.
    $topPickReason = $null
    if ($topPickEn -or $topPickEs) {
        $topPickReason = [ordered]@{
            en = $topPickEn
            es = $topPickEs
        }
    }

    $differentiators = @()
    for ($i = 0; $i -lt 2; $i++) {
        $enTitle = $differentiatorEn[$i].title
        $enDetail = $differentiatorEn[$i].detail
        $esTitle = $differentiatorEs[$i].title
        $esDetail = $differentiatorEs[$i].detail
        if ($enTitle -or $enDetail -or $esTitle -or $esDetail) {
            $differentiators += ,([ordered]@{
                title = [ordered]@{ en = $enTitle; es = $esTitle }
                detail = [ordered]@{ en = $enDetail; es = $esDetail }
            })
        }
    }

    $mattress = [ordered]@{
        id              = $row.id.Trim()
        name            = $row.name.Trim()
        brand           = $row.brand.Trim()
        subBrand        = $subBrand
        pitchKey        = $pitchKey
        archetype       = $archetype
        displayPriority = $displayPriority
        firmness        = $firmness
        firmnessLabel   = $firmnessLbl
        locallyMade     = $locallyMade
        features        = $features
        tags            = $tags
        highlight       = $highlight
        tags_es         = $tags_es
        highlight_es    = $highlight_es
        imageUrl        = $imageUrl
        reasons         = $reasons
        reasons_es      = $reasons_es
        differentiators = $differentiators
    }
    if ($null -ne $topPickReason) {
        $mattress["topPickReason"] = $topPickReason
    }

    $result[$tier] += $mattress
}

# Convert to JSON and write
$json = $result | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText($jsonPath, $json, (New-Object System.Text.UTF8Encoding $false))

$counts = "gold: $($result.gold.Count), silver: $($result.silver.Count), bronze: $($result.bronze.Count)"
Write-Host "Built $jsonPath - $counts"
