"""Enterprise agent workforce for the DOOH DSP control plane.

These agents never sit on the Go bid path. They reason over snapshots,
campaigns, infrastructure, and audits asynchronously.
"""

ROSTER = (
    "architect",
    "compliance",
    "devops",
    "analytics",
    "frontend",
    "qa",
    "product",
)
