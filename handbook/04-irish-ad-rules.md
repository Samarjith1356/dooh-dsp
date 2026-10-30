# Irish ad rules the product enforces

The compliance engine gives the customer a clear yes, no or "fix this" before they pay, and nothing reaches the bidder without passing it. This is an engineering summary, not legal advice. A solicitor reviews the terms and the ad acceptance policy before go-live.

## Launch restrictions (decided for the prototype)

No alcohol, no gambling, no political or issue ads. The engine detects and refuses them. Alcohol comes back after the geofences are proven.

## Rules

| Rule | What it means | How the engine enforces it |
|---|---|---|
| Public Health (Alcohol) Act 2018, s.14 | No alcohol ads at public transport stops or stations, on public service vehicles, or within 200m of a school, early years service or council playground | Every screen is tagged with stop/station status and its distance to schools, crèches and playgrounds from official lists. Alcohol campaigns can't bid on tagged screens |
| ASAI Code (all media, including outdoor and influencer marketing) | Legal, decent, honest, truthful | AI check of copy and image. Anything flagged goes to human review |
| ASAI HFSS rules | No more than 33% of available outdoor space for HFSS food. No HFSS ads where over 50% of the audience is under 15 | Flag HFSS advertisers at onboarding, track their share per screen, block near schools |
| Gambling Regulation Act 2024 | Its advertising sections are not commenced yet | Refused at launch. Review when they commence |
| EU political advertising rules (Reg. 2024/900) | In force since 10 Oct 2025, online and offline: labelling, transparency notices, records | Refused at launch |
| EU AI Act, Article 50 | Since 2 Aug 2026, people must be told they are dealing with an AI, and AI-generated content must be marked | The Advertiser Agent says it is an AI. Studio creatives carry an AI marking in their metadata |
| GDPR | Bidding uses screens and context, never people. Customer accounts are personal data | Data minimisation, retention rules, a DPIA before any camera work |
| Media-owner and SSP policies | Each partner has its own content rules and approval steps | Per-partner rule sets, and creatives registered before we bid with them |
| Personal messages (after launch) | Harassment, defamation and privacy risk | ID check, consent for named people, template text only, human review |

## How the engine must behave

- **Deterministic rules first, AI second.** Geofences and category bans are code, not prompts. The AI only reviews content.
- **Every verdict is stored**: the rule, the evidence and the version of the rule set. We must be able to show why an ad ran.
- **Unsure means human review.** The engine never auto-approves an uncertain case.
