# Guard: must be dot-sourced, not executed directly
if ($MyInvocation.InvocationName -ne '.') {
    Write-Error "ERROR: dot-source this file, don't execute it: . .\setenv.ps1"
    exit 1
}

# Required: Confluence REST API base URL
$env:CONFLUENCE_HOST = "https://your-confluence.example.com/confluence/rest/api"

# Required: Personal Access Token for Confluence
$env:CONFLUENCE_TOKEN = "your-token"

# Optional: Separate integration Confluence instance (defaults to CONFLUENCE_HOST)
# $env:CONFLUENCE_INT_HOST = "https://your-confluence-int.example.com/confluence/rest/api"

# Optional: Token for integration instance (prompted interactively if unset)
# $env:CONFLUENCE_INT_TOKEN = "your-int-token"

# Required: Confluence space key to sync into
$env:CONFLUENCE_SPACE = "MYSPACE"

# uv wrapper: auto-run osv-scanner after lockfile-changing commands
function uv {
    & uv.exe @args
    $rc = $LASTEXITCODE
    if ($rc -eq 0) {
        if ($args[0] -in @('lock', 'add', 'remove', 'sync')) {
            Write-Host "Running osv-scanner..."
            pre-commit run osv-scanner --all-files
        }
    }
    return $rc
}
