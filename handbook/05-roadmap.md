# Roadmap to go-live

The prototype is feature-complete on 5 Feb 2027, UAT runs until 26 Feb, and go-live is the week of 1 Mar 2027. Go-live happens only once an SSP has certified our connection. The supply side sets the launch date, not the code.

## Sprints

| Sprint | Dates | Goal |
|---|---|---|
| 0 | 2-13 Nov 2026 | Foundations: CI, spend booked on plays, KPI fix, Advertiser App skeleton, EUR, `brain` renamed `compiler` |
| 1 | 16-27 Nov | Accounts and organisations, wallet (test payments), staging environment in the EU |
| 2 | 30 Nov-11 Dec | Advertiser App v1 on real APIs: plan, upload, pay, launch, report |
| 3 | 14 Dec-8 Jan | Compliance engine v1: geofences, category bans, HFSS share, AI content review, human queue |
| 4 | 11-22 Jan | Advertiser Agent v1 and Central Brain v1: workflows, approvals, audit log, AI creative studio |
| 5 | 25 Jan-5 Feb | SSP adapter to the partner's spec, reconciliation, pacing, bidder p99, load test |
| UAT | 8-26 Feb | Pilot customers run the full journey on simulator or sandbox |
| Go-live | from 1 Mar 2027 | Soft launch on real screens with a small capped budget |

## Gates

- **Gate 1, prototype complete (5 Feb):** all ten go-live items below work end to end against the simulator or an SSP sandbox, with CI green.
- **Gate 2, UAT passed (26 Feb):** pilot customers complete sign-up to report without help, no open critical bugs, and our spend matches the SSP's figures within the agreed tolerance.
- **Gate 3, go-live:** SSP certification passed, legal documents in place, spend caps and kill switch tested.

## The ten go-live items

1. A signed and certified SSP connection
2. Spend booked on billing notices and reconciled daily
3. Creative approval per partner before bidding
4. EUR wallet, card/SEPA payments, VAT invoices, refunds
5. Accounts, organisations, roles, audit log
6. The Irish compliance gate
7. Bidder p99 inside the SSP's time limit, load-tested
8. EU hosting, TLS, secrets, monitoring, backups, kill switch
9. The Advertiser App, minimum version
10. Legal basics: company, terms, ad policy, privacy policy, insurance
