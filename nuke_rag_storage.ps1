$ragStoragePath = Join-Path $PSScriptRoot "rag_storage"

if (Test-Path $ragStoragePath) {
    Write-Host "[*] Deleting rag_storage folder..."
    Remove-Item $ragStoragePath -Recurse -Force
    Write-Host "[+] rag_storage deleted!"
} else {
    Write-Host "[*] rag_storage not found - nothing to delete"
}
