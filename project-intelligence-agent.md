# Project Intelligence Agent

## What It Is

An agent that reads the team's conversations — Teams, email, meeting transcripts — and keeps track of what's actually happening in a project: decisions made, things assumed, questions left open, and contradictions between what different people said.

It doesn't summarize. It maintains a structured record that gets updated as conversations happen, and it actively flags problems: a decision made in a side thread that the group doesn't know about, two people who think they agreed but mean different things, a claim attributed to someone who never said it, a deadline that nobody set but everyone is waiting on.

We tried meeting summaries. They don't work because the problem isn't that people don't know what was said — it's that decisions don't get formalized, assumptions stay implicit, and nobody is tracking what's still unresolved.

---

## Problems It Solves

**1. People lose track of parts of a big project**
The agent keeps a running structured record of every decision, open question, and assumption. You can query it at any time.

**2. Decisions made in side conversations never reach the group**
When two people make a call in a DM or a small email thread that affects everyone else, the agent flags it and surfaces it to the group.

**3. Decisions rest on assumptions that nobody checked**
Every decision is stored with the assumptions it depends on. If an assumption turns out to be wrong later, the decisions that relied on it get flagged automatically.

**4. People think they agreed but understood different things**
After a significant decision is logged, the agent asks each person involved: "What does this mean for your work?" It compares the answers and flags if they're saying different things.

**5. Things stall because people forget or there's no deadline**
If an open question or pending decision has no deadline, the agent assigns one. Then it follows up — first a reminder to the owner, then a reminder visible to the group, then a public overdue flag. It chases, it doesn't just record.

**6. Information gets misattributed to people who never said it**
Every claim is stored with a source: who said it, in what conversation, who was in the room. If someone attributes a statement to a person who wasn't in that conversation, the agent flags it. You can also ask "what has [person] actually said?" and get verified sources.

**7. The same communication problems keep repeating and nobody notices**
The agent tracks patterns over time — both for the team and for individuals — so recurring issues become visible instead of being relitigated every few months.

---

## Core Concepts

### Project State
Four types of structured objects, updated continuously as conversations come in. Stored in a database, published to Confluence automatically.

| Object | Key Fields |
|---|---|
| **Decision** | what, owner, rationale, status, assumptions it rests on, source, participants |
| **Assumption** | what is being treated as true, verified/unverified, which decisions depend on it |
| **Open Question** | question, assigned owner, deadline, escalation status, source |
| **Tension** | what contradicts what, sources on both sides, resolution status |

### Source Tracking
Every object links back to the original conversation: the specific message or transcript excerpt, timestamp, and who was present. Attribution can always be checked against who was actually in the conversation.

### Escalation Ladder
Any item with a deadline (set by a person or auto-assigned by the agent) goes through this sequence:

1. Deadline assigned — if auto-assigned, the agent explains why
2. Halfway to deadline: reminder to owner
3. At deadline: second reminder, now visible to the group
4. Past deadline by N days: flagged as overdue in the group channel

### Restatement Check
After a significant decision is logged, the agent sends each relevant person a question: "What does this decision mean for your work?" It collects responses, compares them, and reports back if they diverge: "[Person A] understood X. [Person B] understood Y. These may not be the same thing."

### Feedback Tiers

**Individual (visible only to yourself)**
Things that could affect how others see you if made public — so they stay private:
- How often your attributions turn out to be accurate
- How often you said yes but then contradicted or didn't follow through
- Whether you typically resolve things before or after escalation
- How often decisions you're involved in happen outside the group channel
- How often assumptions you stated turned out to be wrong

**Team (visible to everyone)**
Process patterns that don't single anyone out:
- Which topics keep generating conflicts or reversed decisions
- Which channels produce the most untracked decisions
- Which open questions stagnate longest
- Recurring patterns in where the team tends to misalign

**Manager access**: A manager only sees a person's individual feedback if that person explicitly shares it. Off by default.

---

## What Needs to Be Built

### Layer 1: Ingestion
Pull conversations from sources and normalize them: participants, timestamp, channel, raw text.

- MS Teams (Graph API) — channels and DMs
- Email (Outlook API) — threads and replies
- Meeting transcripts — Teams auto-transcripts or uploaded files
- Manual paste (for MVP)

### Layer 2: Extraction Engine (Claude API)
Takes a conversation chunk, returns structured updates to the project state. Identifies decisions, assumptions, open questions, and tensions. Extracts source quotes. Flags conflicts with what's already in the state.

- Extraction prompt + JSON schema
- Conflict detection — checks new items against existing state
- Attribution check — verifies attributed persons were present in the source conversation

### Layer 3: State Store
Database that holds everything.

- Tables: decisions, assumptions, open_questions, tensions
- Source table: quotes linked back to objects
- Dependency table: decisions linked to the assumptions they rest on
- MVP: SQLite. Production: Postgres.

### Layer 4: Intervention Engine
Logic that runs on schedule and on state changes.

- Escalation scheduler: tracks deadlines, triggers each step of the ladder
- Auto-deadline assignment: derives from known project milestones or applies a default
- Restatement dispatcher: sends targeted questions after decisions are logged
- Restatement comparator: detects divergence across responses
- Side-channel surfacer: flags private decisions with group relevance

### Layer 5: Output & Integration
- Confluence sync (REST API): keeps project pages current automatically
- Notifications: Teams and email for escalations, restatement requests, conflict alerts
- Query interface: ask questions against the project state in plain language

### Layer 6: Feedback
- Individual feedback: self-visible communication patterns per person
- Team analytics: aggregate patterns visible to everyone
- Pattern aggregator: accumulates signal over time across conversations

---

## MVP (Hackathon Scope)

### Build for real
1. Extraction engine — Claude prompt + JSON schema, tested on realistic conversations
2. State store — SQLite, four tables
3. Conflict detector — after each ingestion, check new items against existing state
4. Restatement flow — generate questions, compare two sample responses, show divergence
5. Attribution verifier — flag claims where the attributed person wasn't in the source conversation
6. Streamlit UI — paste conversation → view structured state → view flags

### Mock
- Ingestion connectors → manual paste
- Notifications → show what would be sent, don't send it
- Confluence → render the formatted output in the UI
- Escalation timers → "simulate N days passing" button
- Feedback tiers → one pre-seeded fictional example each

### Build order
**Day 1**: Extraction prompt + schema, SQLite store, basic UI (paste → extract → display state)

**Day 2**: Conflict detection, attribution verifier, restatement check

**Day 3**: UI polish, mock escalation panel, mock feedback cards, seeded demo data, walkthrough script

### Demo sequence
Three conversations prepared in advance:
1. Project kickoff chat — a decision buried in the thread, an assumption never stated explicitly, one claim misattributed to a senior person
2. Side-thread between two people — directly contradicts the decision from conversation 1
3. Follow-up email — repeats the misattribution as established fact

Show what the agent caught. The restatement divergence and the attribution flag are the most concrete moments.

---

## Tech Stack

| Layer | MVP | Production |
|---|---|---|
| Extraction | Anthropic SDK (Python) | Same |
| State store | SQLite | Postgres |
| UI | Streamlit | Web app (TBD) |
| Ingestion | Manual paste | Teams Graph API, Outlook API |
| Notifications | Display only | Teams bot + email |
| Confluence | Rendered view | REST API sync |
| Feedback | Mocked | Aggregation pipeline |

---

## ZaloPay Core Values Integration

ZaloPay has 9 core values across three clusters. The agent's behaviors and feedback are grounded in these — not as labels applied after the fact, but as the actual lens for what the agent notices, challenges, and reports.

### The 9 values

**Think cluster**: Think Deeper · Think Different · Think Bigger

**Deliver cluster**: Perfect All Details · Act Like an Owner · Get It Done

**Trust cluster**: Assume Good Intentions · Put ZaloPay First · Build Trust Through Communication

---

### How the agent uses values in challenges

When the agent flags a problem or challenges a discussion, it references the relevant value explicitly. Examples:

| What the agent detects | Value flagged | What it says |
|---|---|---|
| Decision made without root cause analysis | Think Deeper | "The problem definition here may be treating a symptom. What's the root cause?" |
| Solution is an incremental fix when a bigger redesign may be warranted | Think Bigger | "This improves things by ~10%. What would a breakthrough look like?" |
| Team defaulting to the standard approach without questioning it | Think Different | "What assumptions is this approach based on? What would a non-obvious alternative look like?" |
| Decision made in a side thread, group not informed | Build Trust Through Communication | "A decision was made that affects the broader team — surfacing it here." |
| Owner silent on a blocked item | Act Like an Owner | "This item has been unresolved for N days. Ownership means pushing until it's addressed, not waiting." |
| Claim attributed to someone not present in the source conversation | Assume Good Intentions + Build Trust Through Communication | "This attribution can't be verified. Misattribution — even unintentional — erodes trust." |
| Decision optimizing for one team's metric, not ZaloPay overall | Put ZaloPay First | "Does this optimize for ZaloPay overall, or for one function's KPI?" |
| An assumption has been invalidated but dependent decisions haven't been revisited | Act Like an Owner | "An assumption underlying Decision #X has changed. Someone needs to own a revisit." |

---

### Think Deeper checklist as the challenge framework

When a significant decision is logged, the agent runs a lightweight version of the Think Deeper checklist and flags which questions the discussion hasn't answered. It doesn't ask all of them — it identifies the 1–3 most relevant gaps.

Short checklist the agent works from:
- Are we solving a real and specific problem, or a symptom?
- How do we know this solution addresses the root cause?
- Are we optimizing for ZaloPay overall, or one function/KPI?
- If this fails, what's the most likely reason?
- Are we honest about risks and tradeoffs?
- What would make us decide NOT to do this?
- What's the smallest version worth testing first?

If a decision was logged without addressing these, the agent surfaces the relevant questions to the team — not as a blocker, but as a prompt to think more carefully before proceeding.

---

### How values frame individual feedback

Individual feedback is framed as values-based observations, not performance judgments. The agent ties patterns to the value they relate to, so the person understands the behavior in terms they already know.

| Pattern observed | Value lens | How it's framed |
|---|---|---|
| Consistently agrees in the moment, contradicts later | Build Trust Through Communication | "Your 'yes' and your follow-through have diverged N times recently. Clear disagreement in the moment builds more trust than alignment that doesn't hold." |
| Decisions made in side channels | Build Trust Through Communication | "N decisions you were part of were made outside the group. Build Trust Through Communication means the group should know." |
| Open questions consistently resolved after escalation, not before | Act Like an Owner | "Most of your open items get resolved after escalation. Act Like an Owner means pushing for resolution before it reaches that point." |
| Attribution inaccuracies | Assume Good Intentions + Build Trust Through Communication | "N attributions you passed on couldn't be verified at the source. Double-checking before passing on a claim is part of building trust." |

---

### How values frame team feedback

Team-level patterns are surfaced with the same value framing, but without attributing them to individuals.

Examples:
- "Decisions in [topic area] are being revisited frequently. The team may be skipping root cause analysis — Think Deeper applies here."
- "Several decisions were made in side channels over the past month. The team's default is to communicate locally and inform the group late — this is a Build Trust Through Communication pattern."
- "The team's open question resolution rate shows most items are resolved only after escalation. As a group, we're waiting too long to push — Act Like an Owner."
- "Goal-setting in [area] has been incremental for N cycles. Think Bigger — is the team accepting constraints that could be challenged?"

---

## Design Decisions Worth Noting

- The agent assigns deadlines when humans don't. It explains why, and owners can change them.
- The agent writes to Confluence. Humans shouldn't need to. The database is the real source of truth; Confluence is just the readable view.
- Individual feedback stays with the individual. The team sees process patterns, not people patterns.
- The restatement check is the core mechanism for catching misunderstandings. Everything else can be observed passively; misunderstandings require active probing.
