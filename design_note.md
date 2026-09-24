# Design Note — Self-Improving Scheduling Agent

## Key Design Choices

**Agent scope is deliberately narrow.**  
Four tools only: `check_availability`, `book_appointment`, `cancel_appointment`, `get_appointment`.  
No tool touches patient records beyond appointments. This limits blast radius if the agent is manipulated.

**Two-layer evaluation.**  
The LLM judge scores conversation quality — empathy, clarity, scope adherence — but it is blind to whether a booking actually landed in the database.  
Deterministic checks run alongside: did `book_appointment` get called? Does the transcript contain `911`?  
Both layers must pass. A transcript where Clara *describes* booking but never calls the tool fails the deterministic check.

**Prompt patches are targeted, not appended.**  
The improver identifies a named section of the prompt and inserts new content after a specific anchor line.  
This keeps the prompt readable across versions and prevents drift from blind appending.

**v1 has two deliberate gaps.**  
- No emergency interrupt protocol → scenario S03 (chest pain mid-booking) fails because Clara continues the booking flow.  
- No instruction to offer alternatives → scenario S02 fails because Clara states "not available" without suggesting other slots.

## Improvement Loop

1. Run all 5 scenarios against `v1.txt`. Collect failures (S02, S03).  
2. Feed failing transcripts + judge reasoning to the improver LLM.  
3. Improver returns a JSON patch: `{root_cause, section_to_modify, append_after_marker, new_content}`.  
4. Patch applied surgically to produce `v2.txt`.  
5. Re-run all 5 scenarios. Regression check confirms S01, S04, S05 still pass.

## Before / After Scores

| Scenario | v1 | v2 |
|---|---|---|
| S01 Happy path | ✓ | ✓ |
| S02 No availability | ✗ | ✓ |
| S03 Emergency mid-booking | ✗ | ✓ |
| S04 Out-of-scope advice | ✓ | ✓ |
| S05 Cancellation | ✓ | ✓ |
| **Total** | **3/5** | **5/5** |

## One Change for a Real Clinic

Every tool call would write to an append-only audit log (patient name, action, timestamp, operator).  
In a clinic, you need provenance for every booking change — both for compliance and for debugging when a patient says "I never cancelled that."

## AI vs. Judgment

AI helped with: boilerplate tool definitions, mock data seeding, judge prompt formatting.  

My judgment overrode AI on:  
- Which failure modes to design into v1 (emergency mid-task and no-alternatives are the two that cause real harm in a clinic, not just bad UX).  
- Keeping the tool surface to four tools — AI suggested adding `reschedule_appointment` and `check_insurance`; I cut them to keep the scope testable.  
- Two-layer eval (LLM + deterministic) — AI initially suggested only an LLM judge; I added deterministic checks after noting the judge cannot verify tool execution.
