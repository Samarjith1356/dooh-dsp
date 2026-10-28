from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

WEB = Path(__file__).resolve().parents[2] / "apps" / "web"

PILLARS = {
    "command_center": WEB / "app" / "(console)" / "page.tsx",
    "inventory": WEB / "app" / "(console)" / "inventory" / "page.tsx",
    "studio": WEB / "app" / "(console)" / "studio" / "page.tsx",
    "ledger": WEB / "app" / "(console)" / "analytics" / "page.tsx",
}

ROLES = ("org_admin", "campaign_manager", "client_viewer", "auditor")


class Finding(BaseModel):
    id: str
    severity: str  # pass | warn | critical | info
    area: str
    evidence: str
    remediation: str


class UxAudit(BaseModel):
    verdict: str  # HEALTHY | DEGRADED | BLOCKED
    pillars: dict[str, bool] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    rbac_server_enforced: bool = False


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _walk_tsx() -> list[Path]:
    if not WEB.exists():
        return []
    return [p for p in WEB.rglob("*.tsx") if "node_modules" not in p.parts]


def audit() -> UxAudit:
    findings: list[Finding] = []
    pillars = {name: path.exists() for name, path in PILLARS.items()}
    for name, ok in pillars.items():
        findings.append(
            Finding(
                id=f"pillar-{name}",
                severity="pass" if ok else "critical",
                area="architecture",
                evidence=str(PILLARS[name].relative_to(WEB.parent.parent)) if ok else f"missing {name} page",
                remediation="Restore App Router (console) four-pillar routes" if not ok else "Keep route group (console)",
            )
        )

    pkg = _read(WEB / "package.json")
    try:
        meta = json.loads(pkg) if pkg else {}
    except json.JSONDecodeError:
        meta = {}
    ts = str((meta.get("devDependencies") or {}).get("typescript") or "")
    if ts.startswith("5."):
        findings.append(
            Finding(
                id="typescript-5",
                severity="pass",
                area="build",
                evidence=f"typescript {ts}",
                remediation="Do not bump to TypeScript 7 in Docker — next build failed once",
            )
        )
    else:
        findings.append(
            Finding(
                id="typescript-pin",
                severity="critical",
                area="build",
                evidence=f"typescript={ts or 'missing'}",
                remediation="Pin typescript 5.7.x for the Next Docker image",
            )
        )

    deps = {**(meta.get("dependencies") or {}), **(meta.get("devDependencies") or {})}
    for lib, area in (
        ("next", "architecture"),
        ("@tanstack/react-query", "telemetry"),
        ("leaflet", "map"),
        ("recharts", "charts"),
        ("@tanstack/react-virtual", "grid"),
        ("tailwind-merge", "design-system"),
    ):
        findings.append(
            Finding(
                id=f"dep-{lib}",
                severity="pass" if lib in deps else "warn",
                area=area,
                evidence=f"{lib} {'present' if lib in deps else 'missing'}",
                remediation=f"Keep {lib} for control-center density" if lib not in deps else "ok",
            )
        )

    rbac = _read(WEB / "lib" / "rbac.tsx")
    missing_roles = [r for r in ROLES if r not in rbac]
    if missing_roles:
        findings.append(
            Finding(
                id="rbac-roles",
                severity="warn",
                area="rbac",
                evidence=f"missing role tokens: {missing_roles}",
                remediation="Keep org_admin, campaign_manager, client_viewer, auditor in the shell",
            )
        )
    else:
        findings.append(
            Finding(
                id="rbac-roles",
                severity="pass",
                area="rbac",
                evidence="all four roles present in rbac.tsx",
                remediation="ok",
            )
        )
    findings.append(
        Finding(
            id="rbac-client-only",
            severity="warn",
            area="rbac",
            evidence="RoleProvider is client state; API has no auth",
            remediation="Do not market the dropdown as tenancy. Architect: add server sessions before calling it secure.",
        )
    )

    api = _read(WEB / "lib" / "api.ts")
    if "localhost:8000" in api:
        findings.append(
            Finding(
                id="public-api-localhost",
                severity="info",
                area="contracts",
                evidence="NEXT_PUBLIC_API_URL defaults to http://localhost:8000 (browser, not Docker DNS)",
                remediation="Keep localhost for the host browser; do not use campaign-api hostname in NEXT_PUBLIC_*",
            )
        )

    files = _walk_tsx()
    blob = "\n".join(_read(p) for p in files)
    if re.search(r"guarantee|best in the world|miracle cure", blob, re.I):
        findings.append(
            Finding(
                id="compliance-copy",
                severity="critical",
                area="copy",
                evidence="hyperbolic claim copy in UI",
                remediation="Hand off to Compliance; remove guaranteed delivery / win-rate claims",
            )
        )

    skeleton_pages = []
    for name, path in PILLARS.items():
        text = _read(path)
        if "Skeleton" in text or name == "command_center" and "KpiStrip" in text:
            skeleton_pages.append(name)
        elif name == "command_center":
            kpi = _read(WEB / "components" / "blocks" / "kpi-strip.tsx")
            if "Skeleton" in kpi:
                skeleton_pages.append(name)
    for name in PILLARS:
        if name in skeleton_pages:
            findings.append(
                Finding(
                    id=f"skeleton-{name}",
                    severity="pass",
                    area="usability",
                    evidence=f"{name} has loading skeleton path",
                    remediation="ok",
                )
            )
        else:
            findings.append(
                Finding(
                    id=f"skeleton-{name}",
                    severity="warn",
                    area="usability",
                    evidence=f"{name} has no Skeleton — empty flash risk",
                    remediation="Add Skeleton while TanStack Query isLoading; never flash raw empty tables",
                )
            )

    events = _read(WEB / "components" / "blocks" / "events-table.tsx")
    if "useVirtualizer" in events:
        findings.append(
            Finding(
                id="virtual-events",
                severity="pass",
                area="grid",
                evidence="EventsTable uses @tanstack/react-virtual",
                remediation="ok",
            )
        )
    if "No proof-of-play" in events or "rows.length === 0" in events:
        findings.append(
            Finding(
                id="empty-events",
                severity="pass",
                area="usability",
                evidence="empty-state for proof-of-play",
                remediation="ok",
            )
        )

    smap = _read(WEB / "components" / "blocks" / "spatial-map.tsx")
    if "leaflet" in smap.lower() or "L.map" in smap or "tileLayer" in smap:
        findings.append(
            Finding(
                id="leaflet-map",
                severity="pass",
                area="map",
                evidence="spatial-map uses Leaflet",
                remediation="Keep Carto dark tiles + invalidateSize after layout",
            )
        )

    studio = _read(PILLARS["studio"])
    if "plan" in studio.lower() and "chat" in studio.lower():
        findings.append(
            Finding(
                id="hitl-studio",
                severity="pass",
                area="hitl",
                evidence="Agent Studio has chat + plan preview/approval",
                remediation="Keep approve → compile toast; do not crash on Brain CORS",
            )
        )

    error_tsx = list(WEB.rglob("error.tsx"))
    if not error_tsx:
        findings.append(
            Finding(
                id="error-boundary",
                severity="warn",
                area="usability",
                evidence="no app/error.tsx error boundary",
                remediation="Add App Router error.tsx + not-found.tsx with dense fallback copy",
            )
        )

    client_pages = sum(1 for p in PILLARS.values() if _read(p).lstrip().startswith('"use client"'))
    findings.append(
        Finding(
            id="rsc-split",
            severity="info",
            area="architecture",
            evidence=f"{client_pages}/4 pillar pages are Client Components (charts/maps/query)",
            remediation="Keep layout.tsx as Server Component wrapping AppShell; only interactivity needs use client",
        )
    )

    crit = [f for f in findings if f.severity == "critical"]
    warns = [f for f in findings if f.severity == "warn"]
    if crit or not all(pillars.values()):
        verdict = "BLOCKED"
    elif warns:
        verdict = "DEGRADED"
    else:
        verdict = "HEALTHY"

    return UxAudit(
        verdict=verdict,
        pillars=pillars,
        findings=findings,
        rbac_server_enforced=False,
        notes=[
            "Four pillars: Command Center, Inventory, Agent Studio, Ledger.",
            "RBAC is UI-only until campaign-api grows sessions.",
            "Do not fetch bidder /openrtb from the browser.",
        ],
    )


CHECKLIST = [
    "Command Center KPIs + fleet health + campaign states",
    "Inventory Leaflet geofences + spec filter GB/IE",
    "Studio chat / plan preview / approve + compile toast",
    "Ledger Recharts + virtualized events + insight sentence",
    "Skeletons on load; empty states; no guaranteed-delivery copy",
    "TypeScript 5 pin; localhost NEXT_PUBLIC API URLs",
]
