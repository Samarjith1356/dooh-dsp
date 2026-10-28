# Verify agents :8091 has an LLM key and Product/Architect return a live completion.
$ErrorActionPreference = "Stop"
Write-Host "GET http://localhost:8091/health"
$h = Invoke-RestMethod -Uri "http://localhost:8091/health" -Method Get
$h.llm | ConvertTo-Json -Compress
if (-not $h.llm.configured) {
  Write-Host "Grok not configured. Put XAI_API_KEY in .env at the repo root (from console.x.ai), then:"
  Write-Host "  docker compose -f infra/docker-compose.yml up -d --build agents"
  exit 2
}
if ($h.llm.provider -ne "xai") {
  Write-Host "Expected provider xai, got $($h.llm.provider)"
  exit 2
}
$body = @{
  objective = "In two sentences: what is the golden rule for the Go OpenRTB bidder vs LLM/Postgres/ClickHouse?"
  reply_to  = "architect"
  context   = @{ agent = "architect" }
} | ConvertTo-Json -Depth 5
Write-Host "POST /v1/agents/dispatch architect"
$r = Invoke-RestMethod -Uri "http://localhost:8091/v1/agents/dispatch" -Method Post -ContentType "application/json" -Body $body
"ok=$($r.ok) agent=$($r.agent)"
$r.result.summary
$body2 = @{
  objective = "Sam: confirm you are the Product & Client Campaign Agent. Name one HITL surface you own."
  reply_to  = "product"
  context   = @{ agent = "product" }
} | ConvertTo-Json -Depth 5
Write-Host "POST /v1/agents/dispatch product"
$p = Invoke-RestMethod -Uri "http://localhost:8091/v1/agents/dispatch" -Method Post -ContentType "application/json" -Body $body2
"ok=$($p.ok) agent=$($p.agent)"
$p.result.summary
