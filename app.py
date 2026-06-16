import streamlit as st
from openai import OpenAI
import sqlite3
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ── PAGE CONFIG ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Project Intelligence Agent",
    page_icon="🧠",
    layout="wide"
)

# ── DATABASE ──────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect("project_state.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        what TEXT, owner TEXT, rationale TEXT,
        assumptions TEXT, source_quote TEXT,
        participants TEXT, created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS assumptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        what TEXT, verified INTEGER DEFAULT 0,
        source_quote TEXT, created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS open_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT, owner TEXT, deadline TEXT,
        source_quote TEXT, status TEXT DEFAULT 'open', created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS tensions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT, source_a TEXT,
        source_b TEXT, resolved INTEGER DEFAULT 0, created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        what TEXT, owner TEXT, status TEXT DEFAULT 'unknown',
        source_quote TEXT, created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS kickoffs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT, description TEXT,
        scope_json TEXT, stakeholders_json TEXT,
        checklist_json TEXT, created_at TEXT
    )""")
    conn.commit()
    return conn

def get_state_summary(conn):
    c = conn.cursor()
    decisions = c.execute("SELECT id, what, owner FROM decisions ORDER BY id DESC LIMIT 20").fetchall()
    assumptions = c.execute("SELECT id, what, verified FROM assumptions ORDER BY id DESC LIMIT 20").fetchall()
    questions = c.execute("SELECT id, question, owner, status FROM open_questions ORDER BY id DESC LIMIT 20").fetchall()
    tensions = c.execute("SELECT id, description, resolved FROM tensions ORDER BY id DESC LIMIT 10").fetchall()
    return {
        "decisions": [dict(d) for d in decisions],
        "assumptions": [dict(a) for a in assumptions],
        "open_questions": [dict(q) for q in questions],
        "tensions": [dict(t) for t in tensions],
    }

def save_results(conn, extracted, participants_str):
    c = conn.cursor()
    now = datetime.now().isoformat()
    default_deadline = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

    for d in extracted.get("decisions", []):
        c.execute("INSERT INTO decisions VALUES (NULL,?,?,?,?,?,?,?)", (
            d.get("what", ""), d.get("owner", "Unknown"),
            d.get("rationale", ""), json.dumps(d.get("assumptions", [])),
            d.get("source_quote", ""), participants_str, now
        ))
    for a in extracted.get("assumptions", []):
        c.execute("INSERT INTO assumptions VALUES (NULL,?,0,?,?)", (
            a.get("what", ""), a.get("source_quote", ""), now
        ))
    for q in extracted.get("open_questions", []):
        c.execute("INSERT INTO open_questions VALUES (NULL,?,?,?,?,?,?)", (
            q.get("question", ""), q.get("owner", "Unassigned"),
            default_deadline, q.get("source_quote", ""), "open", now
        ))
    for t in extracted.get("tensions", []):
        c.execute("INSERT INTO tensions VALUES (NULL,?,?,?,0,?)", (
            t.get("description", ""), t.get("source_a", ""),
            t.get("source_b", ""), now
        ))
    for r in extracted.get("requirements", []):
        c.execute("INSERT INTO requirements VALUES (NULL,?,?,?,?,?)", (
            r.get("what", ""), r.get("owner", ""),
            r.get("status", "unknown"), r.get("source_quote", ""), now
        ))
    conn.commit()

# ── CLAUDE ────────────────────────────────────────────────────────────
def get_client():
    api_key = os.getenv("GREENNODE_API_KEY")
    if not api_key or api_key == "paste-your-key-here":
        st.error("Add your GreenNode API key to the .env file first.")
        st.stop()
    return OpenAI(
        api_key=api_key,
        base_url="https://aiplatform.console.greennode.ai/v1"
    )

def extract_from_conversation(conversation, existing_state):
    client = get_client()

    existing = json.dumps(existing_state, indent=2, default=str)

    prompt = f"""You are a project intelligence agent. Analyze this conversation and extract structured information.

EXISTING PROJECT STATE (check for conflicts):
{existing}

CONVERSATION TO ANALYZE:
{conversation}

You are analyzing communications from ZaloPay, a Vietnamese fintech company. Content may be in Vietnamese, English, or mixed. Extract everything in English.

ZaloPay context:
- Teams involved: Product (PO), Operations (OP), Accounting (ACC), BD, Engineering
- Common terms: SOF (Source of Funds), TKĐB (special designated account), TKNHBT (settlement account), IBFT (interbank fund transfer), fundflow, reconcile/đối soát, MC/merchant, GD (transaction/giao dịch), STB (settlement bank)
- Core values to flag against: Think Deeper (root cause? does this solution actually meet the requirement?), Act Like an Owner (who owns this?), Build Trust Through Communication (was the group informed?)

REQUIREMENTS: Track any stated requirement from any stakeholder. A requirement is a condition that must be true for the work to be acceptable — not a preference, not a nice-to-have, but a constraint someone is holding the team to. Watch for:
- Compliance/regulatory requirements ("must comply with X")
- Business requirements from specific stakeholders ("Thủy's requirement that Bank3 only has thu hộ/chi hộ")
- Operational requirements ("OP needs X before launch")
- Any statement of the form "we need X to be true" or "X must be the case"
For each:
- what: the requirement in English
- owner: who stated it / who is holding the team to it
- status: met / unmet / unknown (check against decisions in the existing state and in this conversation)
- source_quote: exact quote

SOLUTION_GAPS: This is critical. When a decision is made, check whether it actually satisfies the stated requirements (from this conversation AND from existing state). Flag when:
- A decision solves a narrow problem but the underlying requirement remains unmet
- The team concluded something in a meeting but the conclusion only partially addresses what was needed
- "Even if we do X, Y still remains" — someone (or the analysis) shows the proposed solution is insufficient
- A workaround is proposed to unblock a specific party (e.g. one merchant, one team) without addressing the underlying systemic issue. The workaround may succeed locally while the root problem remains open for everyone else.
- A launch condition is stated ("we launch when X is done") but X has no timeline — the condition is defined but the answer is still effectively unknown.
For each:
- decision: what was decided
- requirement: the stated requirement it was supposed to meet
- gap: what remains unaddressed
- source_quote: exact quote

Extract the following. Be specific — use real names and actual quotes.

PARTICIPANTS: Everyone in this conversation (from, to, cc fields count).

DECISIONS: Explicit or implied decisions. Watch for:
- Things stated as "we will do X" or "team will X"
- Workarounds or short-term fixes agreed on
- Things turned off or shut down
For each:
- what: the decision (in English)
- owner: who is responsible
- rationale: why
- assumptions: what is being taken as true
- source_quote: exact quote (original language ok)

ASSUMPTIONS: Things treated as true without verification. Watch for:
- Fund flow assumptions (which account receives what)
- Timeline assumptions ("PO will complete by X")
- System behavior assumptions ("Napas will do X")
- Capability assumptions: someone says "I can do it" or "we can handle it" without specifying conditions, scale, or constraints — flag every vague capability claim
- Regulatory assumptions: "we need to comply with X" without confirming whether it's mandatory or optional
- Competitor-as-proxy assumptions: "Competitor X does it, therefore our partners/regulators will accept it too" — this is an inference, not confirmation. Flag whenever a competitor's behavior is used as evidence that ZaloPay can or should do the same.
- Guesses presented without flagging: "tụi em đoán" / "we assume" / "probably" — if the word appears in the body but the conclusion section states the guess as a fact, flag it.
For each:
- what: the assumption (in English)
- source_quote: exact quote

OPEN_QUESTIONS: Raised but unanswered. Watch for:
- Requests for timelines with no response ("anh/chị cho timeline giùm")
- Requests for data/numbers with no response
- Risks named but no resolution plan
- "Will discuss later" without owner or date
- "Follow up with X to see if we should do Y" — sounds like action but has no decision mandate or deadline
- Compliance items with unclear ownership: who decides whether to implement?
- @mention task assignments inside email threads or chat replies — when someone assigns a task via "@Name em làm X giùm chị" inline in a message, not as a formal action item. These are real tasks that will disappear when the thread goes quiet.
- "Sẽ confirm sau" / "will follow up later" / "sẽ xác thực sau" with no named owner and no deadline attached — floating promises inside research or analysis that were never converted to tracked actions.
For each:
- question: what needs to be answered (in English)
- owner: who should answer (name, not team)
- source_quote: exact quote

BURIED_ITEMS: Important things hidden inside emails about something else. Watch for:
- Unilateral decisions stated as conclusions inside analytical or informational emails (e.g. "I decided we don't need to do X" buried in a data summary)
- Compliance or regulatory items introduced with "ngoài ra" / "also" / "additionally" at the end of a longer email
- Information shared bilaterally (person A told person B) before the group — flag that the group may not have full context
- Mandatory vs optional ambiguity: "cần" (need/must) used when it's unclear if it's a regulatory requirement or a recommendation
- External deadlines surfaced mid-thread: a stakeholder reveals that an outside party (merchant, regulator, partner) is waiting with a specific deadline that was not previously visible to the group. This changes the pressure on the current decision and may have been unknown to the decision-maker.
- Bilateral negotiation results relayed in group email: someone reports that they spoke with an external party and got agreement/rejection — the outcome was reached outside the group and is now being reported as fait accompli.
For each:
- what: what was buried (in English)
- risk: why it matters if it drifts
- source_quote: exact quote

TENSIONS: This is critical. Detect ALL of these:
1. Contradictions with existing project state
2. Two people proposing different solutions to the same problem
3. Anyone saying a recap/summary doesn't match what they remember ("không giống như mình nhớ", "that's not what we discussed")
4. A decision made in one email contradicted by another email in the same thread
5. Compliance or risk flags with no agreed resolution
6. Someone's stated capability contradicts technical reality ("I can do it" but the system constraints suggest otherwise)
7. "This was already discussed / it's in the meeting notes" — when a participant asserts that an unresolved issue was raised and documented in a prior meeting. This means the group has been circling the same problem across multiple meetings without resolving it. Flag as a recurring unresolved item, not just a current tension.
For each:
- description: what contradicts what (in English)
- source_a: first position + who said it
- source_b: conflicting position + who said it

PHANTOM_AGREEMENTS: Someone appeared to agree but actually didn't, or understanding differs. Watch for:
- Recap emails where the writer says "correct me if wrong" — these are alignment checks, not confirmed decisions
- Someone restating a decision differently from how it was originally stated
- Silence from key stakeholders on critical items
- Vague capability claims ("I can do it", "we can handle it", "no problem") without specifying conditions — the unstated condition is where misalignment hides
- A decision that was clear to the decision-makers but may not have been understood the same way by others in the room
- A recommendation or proposal made at the end of an email with no response from the decision-maker — the thread ended without the person who needs to say yes/no actually saying it. The proposer may believe it was accepted; the decision-maker may not have registered it as requiring a response.
- "Working on it" vs "done" misalignment: one party interprets active work or acknowledged commitment as satisfying a blocker ("we're building it, why is this still a concern?"), while the stakeholder holding the requirement means the work must be fully complete before proceeding. Neither side makes the difference explicit. Flag whenever someone responds to a launch blocker by describing their work-in-progress rather than a completion date or condition.
For each:
- description: what the potential misalignment is
- who_may_misunderstand: name(s)
- source_quote: exact quote

ATTRIBUTION_FLAGS: Claims attributing a statement/decision to someone — verify they were in the conversation.
- claim: what was attributed
- attributed_to: who
- in_conversation: true/false
- note: explanation

Return ONLY valid JSON, no other text:
{{
  "participants": ["name1", "name2"],
  "decisions": [],
  "assumptions": [],
  "open_questions": [],
  "tensions": [],
  "phantom_agreements": [],
  "buried_items": [],
  "requirements": [],
  "solution_gaps": [],
  "attribution_flags": []
}}"""

    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.choices[0].message.content.strip()
    start = text.find('{')
    end = text.rfind('}') + 1
    return json.loads(text[start:end])


def generate_restatement_questions(decisions):
    client = get_client()
    dec_text = "\n".join([f"- {d['what']} (owner: {d['owner']})" for d in decisions])

    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        max_tokens=600,
        messages=[{"role": "user", "content": f"""For each decision below, write one short question to ask stakeholders to check if they really understood it. The question should ask: "what does this mean for your specific work?"

Decisions:
{dec_text}

Return ONLY JSON array:
[{{"decision": "...", "question": "..."}}]"""}]
    )
    text = response.choices[0].message.content.strip()
    start = text.find('[')
    end = text.rfind(']') + 1
    return json.loads(text[start:end])


def compare_restatements(decision, answer_a, person_a, answer_b, person_b):
    client = get_client()

    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        max_tokens=400,
        messages=[{"role": "user", "content": f"""Two people responded to the same decision. Do they understand it the same way?

Decision: {decision}

{person_a} said: "{answer_a}"
{person_b} said: "{answer_b}"

Return JSON:
{{"aligned": true/false, "summary": "one sentence: are they aligned or what's different"}}"""}]
    )
    text = response.choices[0].message.content.strip()
    start = text.find('{')
    end = text.rfind('}') + 1
    return json.loads(text[start:end])

def run_kickoff(project_name, description, scope):
    client = get_client()

    scope_text = "\n".join([f"- {k}: {'Yes' if v else 'No'}" for k, v in scope.items()])

    prompt = f"""You are a project intelligence agent helping a ZaloPay project owner start a new project correctly.

Project name: {project_name}
Description: {description}

Project scope (answered by the project owner):
{scope_text}

ZaloPay context: Teams that may be involved in any project include:
- Tech FE: front-end app changes, user-facing UI
- Tech BE: backend APIs, services, deployments
- Risk: fraud detection, risk scoring, user risk checks, key management
- CS (Customer Support): training materials, FAQs, support procedures, complaint handling
- Operations/Biz: business processes, merchant contracts, partner alignment, quy trình
- Legal: contract review, FAQs legal review, compliance
- Data Platform: dashboards, event tracking, data pipelines, reporting
- Reconciliation/Accounting (AC): fund flow, đối soát, settlement, payment reconciliation
- External Partners: banks (CIMB, NAPAS), merchants, third-party integrations
- UM (User Management): user profiles, KYC, eKYC
- Product (PO): PRD, user journey, sequence diagrams, technical doc sign-off

Based on the scope, return a JSON with:
1. required_stakeholders: list of teams that MUST be involved, each with:
   - team: team name
   - role: what they need to do in this project
   - why: specific reason based on the scope answers
2. open_questions: list of critical questions that must be answered before build starts (based on scope)
3. assumptions_to_validate: list of things the team is likely assuming that need verification
4. checklist_items: key launch readiness items for this project scope (draw from ZaloPay product launch patterns: fund flow check, load test, CS training, golive announcement, reconciliation flow, etc.)
5. risk_areas: what could go wrong if the wrong people are excluded

Return ONLY valid JSON:
{{
  "required_stakeholders": [{{"team": "", "role": "", "why": ""}}],
  "open_questions": [""],
  "assumptions_to_validate": [""],
  "checklist_items": [{{"area": "", "item": ""}}],
  "risk_areas": [""]
}}"""

    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.choices[0].message.content.strip()
    start = text.find('{')
    end = text.rfind('}') + 1
    return json.loads(text[start:end])


# ── UI ────────────────────────────────────────────────────────────────
conn = get_db()

st.title("🧠 Project Intelligence Agent")
st.caption("Tracks decisions, assumptions, open questions, and tensions across conversations.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🚀 Project Kickoff", "📥 Analyze Conversation", "📋 Project State", "🔁 Restatement Check", "⏰ Escalation Simulator"])

# ── TAB 1: KICKOFF ────────────────────────────────────────────────────
with tab1:
    st.subheader("Project Kickoff")
    st.caption("Answer a few questions about your project. The agent will map who needs to be involved and what to resolve before build starts.")

    with st.form("kickoff_form"):
        project_name = st.text_input("Project name", placeholder="e.g. PayLater QR Global Rollout")
        description = st.text_area("What is this project doing?", height=100,
            placeholder="Describe the feature, change, or initiative in 1-3 sentences.")

        st.markdown("**Scope questions**")
        col1, col2 = st.columns(2)
        with col1:
            fund_flow = st.checkbox("Involves changes to payment processing or fund flow")
            external_partner = st.checkbox("Involves a new external partner, bank, or merchant")
            kyc = st.checkbox("Involves user data, KYC, or eKYC")
            ui_changes = st.checkbox("Involves user-facing UI or app changes")
        with col2:
            reconciliation = st.checkbox("Affects reconciliation or settlement (đối soát)")
            risk = st.checkbox("Involves risk scoring or fraud detection")
            cs_impact = st.checkbox("Requires CS training or new support procedures")
            new_apis = st.checkbox("Requires new APIs or third-party integrations")

        submitted = st.form_submit_button("🔍 Map this project", type="primary")

    if submitted and project_name and description:
        scope = {
            "Payment processing / fund flow": fund_flow,
            "New external partner / bank / merchant": external_partner,
            "User data / KYC / eKYC": kyc,
            "User-facing UI changes": ui_changes,
            "Reconciliation / settlement": reconciliation,
            "Risk scoring / fraud detection": risk,
            "CS training / support procedures": cs_impact,
            "New APIs / third-party integrations": new_apis,
        }

        with st.spinner("Mapping stakeholders and checklist..."):
            try:
                result = run_kickoff(project_name, description, scope)
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

        st.success(f"Kickoff map for: **{project_name}**")

        # Required stakeholders
        stakeholders = result.get("required_stakeholders", [])
        if stakeholders:
            st.subheader(f"👥 Required stakeholders ({len(stakeholders)})")
            for s in stakeholders:
                with st.expander(f"**{s.get('team')}** — {s.get('role')}"):
                    st.write(f"**Why:** {s.get('why')}")

        col1, col2 = st.columns(2)

        with col1:
            questions = result.get("open_questions", [])
            if questions:
                st.subheader(f"❓ Must answer before build ({len(questions)})")
                for q in questions:
                    st.warning(q)

            risks = result.get("risk_areas", [])
            if risks:
                st.subheader("⚠️ Risk if wrong people excluded")
                for r in risks:
                    st.error(r)

        with col2:
            assumptions = result.get("assumptions_to_validate", [])
            if assumptions:
                st.subheader(f"💭 Assumptions to validate ({len(assumptions)})")
                for a in assumptions:
                    st.info(a)

            checklist = result.get("checklist_items", [])
            if checklist:
                st.subheader(f"✅ Launch readiness checklist ({len(checklist)})")
                for item in checklist:
                    st.write(f"**{item.get('area')}:** {item.get('item')}")

        if st.button("💾 Save kickoff to project state"):
            c = conn.cursor()
            c.execute("INSERT INTO kickoffs VALUES (NULL,?,?,?,?,?,?)", (
                project_name, description,
                json.dumps(scope), json.dumps(stakeholders),
                json.dumps(result.get("checklist_items", [])),
                datetime.now().isoformat()
            ))
            conn.commit()
            st.success("Saved.")

    # Show previous kickoffs
    saved = conn.execute("SELECT * FROM kickoffs ORDER BY id DESC LIMIT 5").fetchall()
    if saved:
        st.divider()
        st.markdown("**Previous kickoffs**")
        for k in saved:
            with st.expander(f"{k['project_name']} — {k['created_at'][:10]}"):
                stakeholders = json.loads(k['stakeholders_json'])
                st.write("**Required teams:** " + ", ".join([s['team'] for s in stakeholders]))


# ── TAB 2: ANALYZE ────────────────────────────────────────────────────
with tab2:
    st.subheader("Paste a conversation")
    st.caption("Can be a Teams thread, email, meeting notes — any text.")

    conversation = st.text_area(
        "Conversation",
        height=280,
        placeholder="""Example:
Alice: OK so we've decided to go with Vendor A for the payment gateway.
Bob: Agreed. I'll own that. We're assuming the integration takes 2 weeks max.
Carol: What about the fallback if they can't meet the deadline?
Alice: We'll cross that bridge. CEO approved the budget by the way.
Bob: Good. Carol, can you confirm the API docs are ready?"""
    )

    if st.button("🔍 Analyze", type="primary", disabled=not conversation.strip()):
        with st.spinner("Reading the conversation..."):
            existing = get_state_summary(conn)
            try:
                result = extract_from_conversation(conversation, existing)
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

        participants = result.get("participants", [])
        participants_str = ", ".join(participants)

        st.success(f"Done. Participants detected: **{participants_str or 'none found'}**")

        # Solution gaps — most critical, show first
        gaps = result.get("solution_gaps", [])
        if gaps:
            st.error("🕳️ Solution gaps — decision made but requirement still unmet")
            for g in gaps:
                st.error(
                    f"**Decision:** {g.get('decision')}\n\n"
                    f"**Was supposed to meet:** {g.get('requirement')}\n\n"
                    f"**Gap:** {g.get('gap')}\n\n"
                    f"📎 \"{g.get('source_quote')}\""
                )

        # Requirements
        reqs = result.get("requirements", [])
        if reqs:
            st.warning(f"📋 Requirements tracked ({len(reqs)})")
            for r in reqs:
                status_icon = "✅" if r.get("status") == "met" else "❌" if r.get("status") == "unmet" else "❓"
                st.info(f"{status_icon} **{r.get('what')}** — owner: {r.get('owner')} | status: {r.get('status')}")

        # Buried items
        buried = result.get("buried_items", [])
        if buried:
            st.error("📦 Buried items — important things hidden in this conversation")
            for b in buried:
                st.warning(
                    f"**{b.get('what')}**\n\n"
                    f"**Risk if ignored:** {b.get('risk')}\n\n"
                    f"📎 \"{b.get('source_quote')}\""
                )

        # Phantom agreements — show first
        phantoms = result.get("phantom_agreements", [])
        if phantoms:
            st.error("🫥 Phantom agreements detected")
            for ph in phantoms:
                st.warning(
                    f"**Possible misalignment:** {ph.get('description')}\n\n"
                    f"**Who may misunderstand:** {ph.get('who_may_misunderstand')}\n\n"
                    f"📎 \"{ph.get('source_quote')}\""
                )

        # Attribution flags
        flags = result.get("attribution_flags", [])
        if flags:
            st.error("⚠️ Attribution flags")
            for f in flags:
                in_conv = f.get("in_conversation", True)
                if not in_conv:
                    st.warning(
                        f"**{f.get('attributed_to')}** was attributed with: *\"{f.get('claim')}\"* "
                        f"— but they were **not in this conversation**. {f.get('note', '')}"
                    )
                else:
                    st.info(f"Attribution of **{f.get('attributed_to')}** verified — they were in this conversation.")

        # Tensions
        tensions = result.get("tensions", [])
        if tensions:
            st.error("⚡ Conflicts with existing project state")
            for t in tensions:
                st.warning(f"**{t.get('description')}**\n\nExisting: {t.get('source_a')}\nNew: {t.get('source_b')}")

        col1, col2 = st.columns(2)

        with col1:
            decisions = result.get("decisions", [])
            if decisions:
                st.subheader(f"✅ Decisions ({len(decisions)})")
                for d in decisions:
                    with st.expander(d.get("what", "—")):
                        st.write(f"**Owner:** {d.get('owner', 'Unknown')}")
                        if d.get("rationale"):
                            st.write(f"**Rationale:** {d.get('rationale')}")
                        if d.get("assumptions"):
                            st.write("**Rests on:**")
                            for a in d.get("assumptions", []):
                                st.write(f"- {a}")
                        if d.get("source_quote"):
                            st.caption(f"📎 \"{d.get('source_quote')}\"")
            else:
                st.info("No decisions found.")

            questions = result.get("open_questions", [])
            if questions:
                st.subheader(f"❓ Open Questions ({len(questions)})")
                for q in questions:
                    with st.expander(q.get("question", "—")):
                        st.write(f"**Should be answered by:** {q.get('owner', 'Unassigned')}")
                        st.write(f"**Auto-deadline:** {(datetime.now() + timedelta(days=3)).strftime('%b %d')}")
                        if q.get("source_quote"):
                            st.caption(f"📎 \"{q.get('source_quote')}\"")

        with col2:
            assumptions = result.get("assumptions", [])
            if assumptions:
                st.subheader(f"💭 Assumptions ({len(assumptions)})")
                for a in assumptions:
                    with st.expander(a.get("what", "—")):
                        st.write("**Status:** Unverified")
                        if a.get("source_quote"):
                            st.caption(f"📎 \"{a.get('source_quote')}\"")
            else:
                st.info("No assumptions found.")

            if tensions:
                st.subheader(f"⚡ Tensions ({len(tensions)})")
                for t in tensions:
                    st.warning(t.get("description", "—"))

        # Save to DB
        if st.button("💾 Save to project state"):
            save_results(conn, result, participants_str)
            st.success("Saved. View in Project State tab.")
            st.session_state["last_decisions"] = result.get("decisions", [])

# ── TAB 3: PROJECT STATE ──────────────────────────────────────────────
with tab3:
    st.subheader("Current Project State")

    if st.button("🔄 Refresh"):
        st.rerun()

    state = get_state_summary(conn)

    col1, col2 = st.columns(2)

    with col1:
        decisions = state["decisions"]
        st.markdown(f"### ✅ Decisions ({len(decisions)})")
        if decisions:
            for d in decisions:
                with st.expander(f"#{d['id']} {d['what']}"):
                    st.write(f"**Owner:** {d['owner']}")
        else:
            st.info("No decisions logged yet.")

        questions = state["open_questions"]
        open_q = [q for q in questions if q["status"] == "open"]
        st.markdown(f"### ❓ Open Questions ({len(open_q)})")
        if open_q:
            for q in open_q:
                with st.expander(f"#{q['id']} {q['question']}"):
                    st.write(f"**Owner:** {q['owner']}")
                    st.write(f"**Deadline:** {q.get('deadline', 'Not set')}")
        else:
            st.info("No open questions.")

    with col2:
        assumptions = state["assumptions"]
        unverified = [a for a in assumptions if not a["verified"]]
        st.markdown(f"### 💭 Unverified Assumptions ({len(unverified)})")
        if unverified:
            for a in unverified:
                with st.expander(f"#{a['id']} {a['what']}"):
                    st.write("Not yet verified")
                    if st.button(f"Mark verified", key=f"verify_{a['id']}"):
                        conn.execute("UPDATE assumptions SET verified=1 WHERE id=?", (a['id'],))
                        conn.commit()
                        st.rerun()
        else:
            st.info("No unverified assumptions.")

        tensions = [t for t in state["tensions"] if not t["resolved"]]
        st.markdown(f"### ⚡ Active Tensions ({len(tensions)})")
        if tensions:
            for t in tensions:
                st.warning(t["description"])
        else:
            st.info("No active tensions.")

    if st.button("🗑️ Clear all data (fresh start)"):
        conn.execute("DELETE FROM decisions")
        conn.execute("DELETE FROM assumptions")
        conn.execute("DELETE FROM open_questions")
        conn.execute("DELETE FROM tensions")
        conn.commit()
        st.success("Cleared.")
        st.rerun()

# ── TAB 4: RESTATEMENT CHECK ──────────────────────────────────────────
with tab4:
    st.subheader("Restatement Check")
    st.caption("After a decision is made, ask people what they think it means. Compare their answers to catch hidden misalignment.")

    state = get_state_summary(conn)
    decisions = state["decisions"]

    if not decisions:
        st.info("No decisions logged yet. Analyze a conversation first.")
    else:
        decision_options = {f"#{d['id']}: {d['what']}": d for d in decisions}
        selected_label = st.selectbox("Pick a decision to check", list(decision_options.keys()))
        selected = decision_options[selected_label]

        with st.expander("Generate restatement question"):
            if st.button("Generate question"):
                with st.spinner("Generating..."):
                    questions = generate_restatement_questions([selected])
                if questions:
                    st.session_state["restatement_q"] = questions[0]["question"]

            if "restatement_q" in st.session_state:
                st.info(f"**Send this to each stakeholder:** {st.session_state['restatement_q']}")

        st.divider()
        st.write("**Enter two people's responses to compare:**")

        col1, col2 = st.columns(2)
        with col1:
            person_a = st.text_input("Person A name", placeholder="e.g. Alice")
            answer_a = st.text_area("Person A's response", height=100)
        with col2:
            person_b = st.text_input("Person B name", placeholder="e.g. Bob")
            answer_b = st.text_area("Person B's response", height=100)

        if st.button("🔍 Compare", type="primary", disabled=not (answer_a and answer_b)):
            with st.spinner("Comparing..."):
                result = compare_restatements(
                    selected["what"], answer_a, person_a or "Person A",
                    answer_b, person_b or "Person B"
                )
            if result.get("aligned"):
                st.success(f"✅ Aligned: {result.get('summary')}")
            else:
                st.error(f"⚠️ Misalignment detected: {result.get('summary')}")

# ── TAB 5: ESCALATION SIMULATOR ──────────────────────────────────────
with tab5:
    st.subheader("Escalation Simulator")
    st.caption("Simulate time passing to see what alerts the agent would send.")

    state = get_state_summary(conn)
    open_questions = [q for q in state["open_questions"] if q["status"] == "open"]

    if not open_questions:
        st.info("No open questions to simulate escalation for.")
    else:
        days = st.slider("Simulate N days passing", 1, 10, 3)

        st.write(f"**What the agent would send after {days} day(s):**")

        for q in open_questions:
            deadline_str = q.get("deadline")
            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
                created = datetime.fromisoformat(q["created_at"])
                simulated_now = created + timedelta(days=days)
                days_until = (deadline - simulated_now).days

                if days_until > 1:
                    st.success(f"✅ **#{q['id']}** \"{q['question']}\" — on track, {days_until} day(s) left.")
                elif days_until == 1 or days_until == 0:
                    st.warning(
                        f"⏰ **Reminder to {q['owner']}:** \"{q['question']}\" is due {'today' if days_until == 0 else 'tomorrow'}. "
                        f"Please resolve or update the group."
                    )
                else:
                    st.error(
                        f"🚨 **OVERDUE — group alert:** \"{q['question']}\" was assigned to {q['owner']} "
                        f"and is {abs(days_until)} day(s) past deadline. No response yet. "
                        f"Who can unblock this?"
                    )
            except Exception:
                st.info(f"#{q['id']} {q['question']} — deadline not set")
