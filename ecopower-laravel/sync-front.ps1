# Recopie le front React du projet d'origine (..\src) vers resources\js.
# A lancer depuis le dossier ecopower-laravel après chaque modification du front d'origine.
$src = Join-Path $PSScriptRoot "..\src"
$dst = Join-Path $PSScriptRoot "resources\js"
Copy-Item -Path (Join-Path $src "*") -Destination $dst -Recurse -Force
Copy-Item -Path (Join-Path $PSScriptRoot "..\public\products") -Destination (Join-Path $PSScriptRoot "public") -Recurse -Force
Copy-Item -Path (Join-Path $PSScriptRoot "..\public\logos") -Destination (Join-Path $PSScriptRoot "public") -Recurse -Force
Write-Host "Front synchronisé. Lancez 'npm run build' (ou 'npm run dev')."
