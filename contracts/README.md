# Contracts

A contract is an agreement between lanes: what one lane produces and another relies on. Each lane builds against the contract rather than against the other lane's code, which is what lets lanes work in parallel.

- The planner owns these files. Builders read them and never change them alone.
- If a contract turns out to be wrong or incomplete, the builder writes the problem under Open questions, sets status `blocked`, and stops.
- Each contract has a version line. A breaking change bumps the version and comes with tasks for every lane it touches.

| Contract | Between |
|---|---|
| [events.md](events.md) | Trading (bidder, simulator, ingest, compiler) and Platform (KPIs, reports) |
| [advertiser-app.md](advertiser-app.md) | Experience (Advertiser App) and Platform (campaign-api) |
