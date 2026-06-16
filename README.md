# Project Intelligence Agent

**Track: Agentic Assistant**

An AI agent that reads your team's conversations and tells you what's actually happening in a project — who decided what, what's being assumed without being said, who should be in the room but isn't, and where two people think they agreed but didn't.

---

## The Problem

Complex projects fail not because people don't work hard, but because decisions get lost in email threads, assumptions go unchecked, and people walk out of the same meeting with different understandings. Meeting summaries don't fix this — they record what was said, not what was actually decided or left unresolved.

Specific failure modes this agent is built to catch:
- A decision made in a side thread that the group never sees
- Someone says "I can do it" without stating the conditions — the constraint surfaces two weeks later
- A recommendation sits unacknowledged at the end of an email; the sender thinks it was accepted
- A project proceeds without Risk or CS in the room; the gap shows up at launch
- The team is working on a solution that doesn't actually satisfy the underlying requirement

---

## What It Does

### 1. Project Kickoff — stakeholder mapping
Before the project starts, the agent asks scoping questions (does it touch fund flow? external partners? KYC? reconciliation?) and maps which teams must be involved, what needs to be resolved before build starts, and what the team is likely assuming that needs validation.

### 2. Conversation Analysis — structured extraction
Paste any conversation — email thread, meeting transcript, Teams chat. The agent extracts:

| Category | What it catches |
|---|---|
| **Decisions** | Explicit and implied, including things turned off or deferred |
| **Assumptions** | Vague capability claims, competitor-as-proxy reasoning, guesses stated as facts |
| **Open Questions** | Including @mention task assignments that have no formal home |
| **Buried Items** | Decisions hidden inside analytical emails, external deadlines surfaced mid-thread |
| **Phantom Agreements** | "Working on it" ≠ done; silence treated as consent; unacknowledged recommendations |
| **Tensions** | Contradictions, recurring unresolved items ("this was already in the meeting notes") |
| **Requirements** | Stated conditions stakeholders are holding the team to, tracked as met/unmet/unknown |
| **Solution Gaps** | When a decision was made but the underlying requirement remains unmet |
| **Attribution Flags** | Claims attributed to someone who wasn't in the source conversation |

### 3. Restatement Check — catch misalignment before it becomes an incident
After a significant decision is logged, the agent generates a targeted question to send to each stakeholder: "What does this mean for your work?" It compares responses and flags if they diverge.

### 4. Escalation Simulator
Simulate time passing on open questions. The agent shows what reminders and overdue alerts it would send, and to whom.

---

## Demo Scenario

**Setup:** QR Global rollout project at a fintech company.

1. **Kickoff** — scope the project → agent identifies Risk and Reconciliation must be involved
2. **Conversation 1** — planning email thread → agent extracts the decision, flags that Risk was not in the conversation, surfaces an unverified assumption about partner acceptance
3. **Conversation 2** — follow-up thread → agent detects a phantom agreement ("working on it" response to a launch blocker), flags a solution gap (decision made but underlying reconciliation requirement still unmet)
4. **Restatement check** — two stakeholders answer what the decision means for their work → agent surfaces the divergence

---

## Tech Stack

| Layer | Choice |
|---|---|
| LLM | DeepSeek-R1-Distill-Qwen-32B via GreenNode MaaS |
| UI | Streamlit |
| State store | SQLite |
| Deployment | GreenNode AgentBase |

> Note: Uses DeepSeek-R1-Distill-Qwen-32B via GreenNode's external MaaS API. Cost is borne by the team.

---

## Running Locally

```bash
pip install -r requirements.txt
# Add your GreenNode API key to .env:
# GREENNODE_API_KEY=your-key-here
streamlit run app.py
```

---

## Files

| File | Purpose |
|---|---|
| `app.py` | Full Streamlit app — kickoff, extraction, restatement, escalation |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Container config for AgentBase deployment (port 8080) |
| `project-intelligence-agent.md` | Full product design document |
