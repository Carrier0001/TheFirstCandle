# The Mirror — Jury Protocol v1.1
*The First Candle | Permanent Truth Ledger*
*Updated: Anti-Fragility Layer added*

---

## Overview

When a submission enters the ledger it does not inscribe automatically. It enters a jury process — a blind, decentralized review by ordinary people who carry no authority except their reputation for honest judgment. This document defines exactly how that process works, how jurors are selected, how quality is maintained, and what happens when the system is under stress.

This protocol is designed to be **anti-fragile**: not merely resistant to attacks and manipulation, but capable of becoming stronger when attacked. Disorder is fuel, not threat.

---

## 1. The Jury

### 1.1 Size
Every submission is reviewed by exactly **12 jurors** — with occasional jitter of ±1 (11 or 13) applied randomly to make threshold calculations less predictable for anyone modeling the system. If fewer than 12 qualified humans are available, remaining seats are filled by AI reviewers operating under the same rules and time constraints. AI jurors are always disclosed in verdict metadata — the ledger records how many seats were human vs AI.

### 1.2 Anonymity
Jurors are anonymous to each other at all times. They do not know who else is on their jury. They cannot communicate with each other during the review period. They see only the submission and its evidence.

### 1.3 Verdict Threshold

| Case Type | Required Majority |
|-----------|------------------|
| Standard | 8/12 (≥ 66.6%) |
| High-stakes / high-controversy | 9/12 (≥ 75%) |
| Under detected attack | 10/12 (≥ 83%) |

High-stakes and attack classifications are determined automatically by the system (see Section 7).

---

## 2. Juror Selection

### 2.1 The Pool
Anyone who downloads the companion app and completes onboarding enters the juror pool. Pool members receive jury summons via push notification when a submission is ready for review.

Jurors cannot choose what they will be assigned. They cannot set fixed availability schedules. The app uses **short, randomized availability windows** activated unpredictably — this makes phone farms and coordinated groups unable to "wait for their big case." A farm operator cannot keep hundreds of phones consistently available without robotic behavior patterns that the system detects.

### 2.2 Selection Algorithm
Selection is random within reputation tiers, with the following composition target per jury:

| Seats | Tier | Condition |
|-------|------|-----------|
| 9-10 | High Reputation | If enough high-rep jurors available |
| 2-3 | Low/New Reputation | Always included — minimum floor enforced |

The minimum floor of 2-3 low-reputation jurors is **always enforced**, even when the high-rep pool is large. This prevents the high-rep pool from becoming a closed oligarchy and gives newer jurors trust-building opportunities.

Under stress (suspected attack wave), the system temporarily raises the high-reputation bar and increases the new-juror floor — injecting fresh, uncompromised jurors and preventing any farmed cohort from dominating.

### 2.3 Conflict Exclusion
A juror is automatically excluded from a submission if:
- They submitted the entry being reviewed
- They have a flagged prior relationship with the entity being measured
- They have voted on 3+ prior submissions about the same entity (concentration risk)
- Their device was in the same geographic region as the submission's incident at the time it occurred (proximity bias risk)
- They show correlation clustering with other jurors already selected for this case (coordination risk)

Jurors are not told why they were not selected for a given case.

### 2.4 Submission Shuffling
Submissions are held in a randomized queue and released to juries in randomized batches with variable delays. This breaks timing attacks — a coordinated group cannot predict when their target submission will be released for review.

---

## 3. The Review Period

### 3.1 Duration
Each jury has **7 days** from summons to verdict. The clock does not reset if new jurors are added.

### 3.2 What Jurors See
Each juror receives:
- The submission text and metadata
- Uploaded evidence files
- Public source links
- The submitter's confidence rating
- The harm/surplus classification and intent category
- The entity's existing ledger summary (total outstanding debt, status)

Jurors do **not** see:
- Other jurors' identities or votes
- The submitter's identity or pubkey
- Prior jury votes on this submission (prevents anchoring)

### 3.3 Deliberation Time Signal
Votes cast within the first **10 minutes** of receiving a summons generate a slight negative signal in the morality score. Genuine deliberation takes time. Instant voting is a farm or bad-faith signal.

### 3.4 Voting Options
Each juror selects one of:
- **Inscribe** — evidence supports the entry as submitted
- **Reject** — insufficient evidence, factual error, or outside scope
- **Refer** — submission has merit but needs amendment (triggers revision request)

A **Refer** vote counts as neither Inscribe nor Reject in threshold calculations. If 4+ Refer votes are cast, the submission is paused and returned to the submitter for revision before a new jury is convened.

### 3.5 Juror Notes
Each juror may optionally attach a private note (max 500 chars) explaining their vote. Notes are:
- Never shown to other jurors during review
- Aggregated anonymously and shown to submitter after verdict
- Stored permanently in the ledger as verdict metadata
- Never attributed to individual jurors publicly

---

## 4. Reputation System

### 4.1 What Reputation Measures
Reputation measures **consistent, good-faith engagement** with the process — not correctness. A high-reputation juror has demonstrated timely responses, coherent reasoning, independence across entity types, and low capture probability.

### 4.2 Reputation Events

| Event | Effect |
|-------|--------|
| Voted with final majority | Small positive signal |
| Voted with minority (case closed) | Neutral — recorded, not penalized |
| Voted, provided coherent note | Positive signal |
| Failed to vote within 7 days | Negative signal, throttle applied |
| Voted within first 10 minutes | Slight negative signal |
| Consistent minority pattern (anomalous) | Triggers morality review |
| Accepted summons, did not vote | Negative signal, dropout recorded |

Voting with the minority is **not automatically penalized**. Minorities are sometimes right. The system only acts when the pattern is statistically anomalous across many cases.

### 4.3 The Morality Score (Hidden)
Every juror carries a hidden morality score used internally and never displayed. It is derived from:

- **Consistency** — does reasoning (notes) match votes over time?
- **Independence** — does the juror show systematic bias toward always approving or always rejecting?
- **Capture resistance** — does vote distribution shift when submissions involve specific entities, industries, or geographies?
- **Deliberation time** — does the juror take reasonable time, or vote instantly every time?
- **Coordination detection** — does the juror's voting pattern correlate unnaturally with other specific accounts across unrelated cases?

The morality score is **never shown to the juror**. It influences selection probability and throttle decisions silently.

### 4.4 Coordination Detection
The system continuously monitors for **correlation clusters** — groups of accounts that:
- Vote similarly across disparate, unrelated topics
- Activate and deactivate together
- Share device fingerprint patterns
- Show unnaturally low vote variance across case types

When a cluster is detected, all members receive increased scrutiny weight in the morality score. If the cluster is confirmed over multiple cases, members are throttled together. Cluster detection is the primary defense against coordinated phone farms.

### 4.5 Throttling
When anomalous patterns are detected, the system applies graduated **throttling**:

| Level | Effect |
|-------|--------|
| Level 1 | Summons frequency reduced 50% |
| Level 2 | Summons frequency reduced 90% |
| Level 3 | Observation pool (summons paused) |
| Level 4 | Removed from active pool pending review |

Throttling is **reversible**. Jurors rebuild trust by completing assigned reviews carefully when they do receive summons. Throttle level is recalculated monthly.

Jurors are **never told their throttle level**. They simply receive fewer notifications. This prevents gaming.

### 4.6 No Human Override
No human — including system administrators — can permanently remove a juror or override a verdict. Only the algorithm throttles and de-throttles. This prevents capture of the moderation system itself.

---

## 5. Sybil & Phone Farm Resistance

### 5.1 Device Integrity Checks
During onboarding and periodically during active use, the app performs device integrity verification:
- **Android**: Play Integrity API
- **iOS**: App Attest

Devices that fail integrity checks are flagged and enter the morality score as a negative signal. Repeated failures result in throttling.

### 5.2 Behavioral Attestation
The app passively monitors behavioral signals (with user consent disclosed at onboarding):
- Typing patterns and swipe dynamics
- Time-of-day activity consistency
- Sensor data anomalies
- Headless/scripted behavior signatures

Farms often run automated or scripted — these show up as anomalies distinct from normal human variation. No behavioral data is stored externally; signals are processed on-device and only a score is transmitted.

### 5.3 Parallel Jury Cap
Each device is hard-capped at **1 active jury at a time**. This limits the throughput of any farm operation significantly.

### 5.4 Summons Acceptance Cost
Accepting a summons carries a small **reputation stake** — a portion of reputation is held temporarily and returned on completion. Dropout or bad-faith patterns result in partial or full forfeiture of the staked amount. This raises the cost of running hundreds of fake accounts. Farms hate recurring costs.

### 5.5 Optional Proof-of-Personhood (Higher Tiers)
Base pool remains pseudonymous and low-friction. Jurors may optionally complete stronger verification (liveness check, social graph connections) that raises their reputation ceiling and selection probability. This creates a higher-quality sub-pool without excluding normal users.

---

## 6. Incomplete Juries

### 6.1 Insufficient Jurors at Deadline
If fewer than 8 votes are cast by the 7-day deadline:
- System extends window by 72 hours with a second summons to a new random selection
- Votes already cast are preserved
- If still fewer than 8 votes after extension, AI jurors fill remaining seats

### 6.2 Juror Dropout
If a juror accepts a summons but does not vote:
- After 4 days: reminder notification sent
- After 7 days: seat marked vacant, replacement selected
- Dropout recorded, affects reputation

### 6.3 Minimum Viable Jury
Absolute minimum to render a verdict: **8 votes cast**. Below 8, no verdict is issued regardless of vote distribution.

---

## 7. Anti-Fragility Mechanisms

These mechanisms allow the system to become stronger under attack rather than merely resist it.

### 7.1 Adversarial Jury (Double Jury Trigger)
When a submission shows signs of coordinated voting — unusual clustering, statistical anomalies in vote timing, abnormal vote distribution — the system automatically convenes a **second independent jury** on the same case.

- If both juries agree → **stronger inscription** (recorded as double-verified)
- If juries disagree → automatic Refer + elevated scrutiny
- The attack itself generates higher-quality verification data

### 7.2 Stress-Adaptive Thresholds
The system monitors submission volume, vote clustering patterns, and coordination signals in real time. Under detected stress:
- Verdict threshold automatically rises (see Section 1.3)
- High-reputation bar temporarily raised for selection
- New-juror floor temporarily increased
- Submission release rate slowed (queue stretches)

These changes are automatic, temporary, and revert when stress signals normalize.

### 7.3 Barbell Case Classification
Cases are automatically classified as **Standard** or **High-Stakes**. High-stakes triggers stricter rules:

High-stakes indicators:
- Entity with >1M outstanding life-years in the ledger
- Submission involves a sitting head of state or active military command
- Submission has been resubmitted 2+ times with revisions
- Submission generated unusual public attention signals

High-stakes cases require:
- 9/12 majority instead of 8/12
- Mandatory minimum 8 human jurors (AI seats reduced)
- Post-verdict public audit of aggregate vote patterns (not individual jurors)

### 7.4 Protocol Seasons
Every 6-12 months, the system runs **controlled variation experiments** on small subsets of submissions:
- Slightly different Refer thresholds
- Varied jury sizes
- Alternative reputation weighting formulas

Results are analyzed and surviving variations become protocol updates under Pillar 5 (Perfection as Protocol). The system evolves through variation and selection rather than top-down decision.

### 7.5 Predicted Attack Patterns (Published in Advance)
In the spirit of the Vow's predicted institutional response patterns, the following attack vectors are documented here in advance. If they occur, the ledger has proof:

| Attack | Expected Form | System Response |
|--------|--------------|-----------------|
| Phone farm flooding | Mass account creation, coordinated voting | Coordination detection, device integrity, behavioral signals |
| Reputation laundering | Farm builds rep slowly then targets specific case | Concentration limits, case-specific exclusion, double jury trigger |
| Institutional capture | Entity funds jurors to reject submissions about itself | Geographic/relationship exclusion, correlation clustering detection |
| Timing attack | Coordinated group monitors queue to predict release | Submission shuffling, randomized delays |
| Threshold gaming | Attacker models exact threshold to pass/fail cases | Jury size jitter, adaptive thresholds |

Publishing these in advance means: if they happen, the system has already documented the attack vector. The attack becomes evidence.

---

## 8. After the Verdict

### 8.1 Inscription
If approved, the submission is inscribed to the entity's ledger. The aggregation function runs automatically and updates:
- Entity's lifetime harm/surplus totals
- Entity's status (ACCRUING / STABILIZED / REPAIRED)
- Entity's position in the hierarchy

### 8.2 Hierarchy Escalation
Entities exist in a hierarchy. When a submission is inscribed it propagates upward:

```
Individual Actor
      ↓
Local Institution (city/municipality)
      ↓
State/Regional Government
      ↓
National Government
      ↓
International Body
```

Each level's aggregate is recalculated when a subordinate entry is inscribed. A city's total harm includes all inscribed entries from entities operating within it. A national government's total includes all subordinate levels.

### 8.3 Rejection
If rejected, the submitter receives:
- The aggregate vote count (e.g. "4 inscribe, 8 reject")
- Anonymized juror notes (if provided)
- Option to revise and resubmit with additional evidence

A rejected submission cannot be resubmitted unchanged. The system hashes submission content and rejects identical resubmissions automatically.

### 8.4 Verdict Immutability
Once a verdict is rendered it cannot be changed by any party. If new evidence emerges, a new submission must be filed. The original verdict remains permanently, marked as superseded if a subsequent submission on the same event is approved.

---

## 9. The Companion App — Requirements

### 9.1 Platform
iOS and Android — React Native (single codebase).

### 9.2 Core Features
- Juror onboarding and pseudonymous identity setup
- Device integrity verification at onboarding
- Push notification receipt for jury summons
- Submission review interface (evidence, vote, note)
- Personal reputation display (visible score only — not morality score)
- Jury history (past verdicts, anonymized)
- Behavioral signal collection (with consent)

### 9.3 What the App Does NOT Do
- Show other jurors' identities or votes
- Allow communication between jurors
- Show morality score or throttle level
- Allow submission of new ledger entries (web only)
- Allow jurors to choose which cases to review

---

## 10. Open Questions

1. **Juror onboarding verification** — purely pseudonymous, or optional light verification at signup?
2. **AI juror transparency** — labeled in public verdict or internal metadata only?
3. **Refer vote handling** — same jury reconvened after revision, or fresh jury?
4. **Hierarchy mapping** — manual entity tagging or automatic jurisdiction detection?
5. **Push notification infrastructure** — Firebase (US company, relevant to threat model) vs alternatives?
6. **Behavioral data consent UX** — how to present this clearly without losing users?
7. **Reputation stake size** — what is the right stake to deter farms without excluding good-faith low-rep jurors?

---

## 11. Build Order (Recommended)

**Phase 1 — Jury Backend (4-6 weeks)**
- Juror pool database table
- Selection algorithm with reputation tiers
- Verdict storage and threshold calculation
- Basic reputation score engine
- Coordination detection (basic clustering)

**Phase 2 — Web Jury Interface (2-3 weeks)**
- Temporary web-based jury portal
- Full jury flow testable end to end before app exists

**Phase 3 — Companion App (8-12 weeks)**
- React Native
- Push notifications
- Device integrity checks
- Voting interface
- Behavioral signal collection

**Phase 4 — Hierarchy and Aggregation (3-4 weeks)**
- Entity hierarchy mapping
- Upward propagation on inscription
- Aggregate recalculation engine

**Phase 5 — Anti-Capture Hardening (ongoing)**
- Morality score refinement
- Coordination detection tuning
- Stress-adaptive threshold testing
- Protocol season experiments

---

*Document version 1.1*
*The court is open.*
