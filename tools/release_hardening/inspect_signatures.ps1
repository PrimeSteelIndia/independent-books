[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InputJson,
    [Parameter(Mandatory=$true)][string]$OutputJson
)
$ErrorActionPreference = 'Stop'
$items = @(Get-Content -LiteralPath $InputJson -Raw | ConvertFrom-Json)
$results = @(
    foreach ($item in $items) {
        $signature = Get-AuthenticodeSignature -LiteralPath $item.path
        [pscustomobject]@{
            name = $item.name
            status = $signature.Status.ToString()
            signer = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null }
            thumbprint = if ($signature.SignerCertificate) { $signature.SignerCertificate.Thumbprint } else { $null }
            timestamped = [bool]$signature.TimeStamperCertificate
        }
    }
)
ConvertTo-Json -InputObject $results -Depth 5 | Set-Content -LiteralPath $OutputJson -Encoding utf8
