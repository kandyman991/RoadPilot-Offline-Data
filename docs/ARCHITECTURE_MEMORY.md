# Architecture memory: rejected approaches and failed experiments

**Purpose:** Preserve *why* an architecture was abandoned or rejected, so future ChatGPT sessions do not repeat it. This supplements, rather than replaces, `CHAT_HANDOFF.md`, the accepted architecture/decision records and live GitHub evidence.

## What to read
- Verify the real code, main SHA, open PRs and CI first; a handoff or plan is not proof of implementation.
- Read relevant current architecture and `docs/ENGINEERING_DECISIONS.md` (plus any binding architecture contract).
- Read `docs/FAILED_APPROACHES.md` before proposing or reviving a significant design.

## Classification (never conflate these)
- **CONFIRMED_FAILURE:** executed attempt whose negative result has reproduction evidence.
- **REJECTED_BY_DESIGN:** consciously declined option based on constraints, not necessarily built or tested.
- **SUPERSEDED:** an old proposal/implementation replaced by a decision; this does *not* prove it failed.
- **INCONCLUSIVE:** experiment with insufficient evidence; document the next discriminating test.

## Register entry template (append to docs/FAILED_APPROACHES.md)

```md
## F-### — Approach / symptom
- Status: CONFIRMED_FAILURE | REJECTED_BY_DESIGN | SUPERSEDED | INCONCLUSIVE
- Date, scope and versions: YYYY-MM-DD; commit, platform, graph/data fingerprints as applicable
- Problem and hypothesis: goal; why the proposed approach looked promising
- Implementation vs proposal: what actually ran and what was only considered
- Reproduction / evidence: input, command, environment, expected vs observed; tests, logs, issue/PR links
- Root cause: proven / suspected / unknown; supporting data and confidence
- Decision / replacement: current direction and linked accepted ADR or decision
- Reconsider only if: falsifiable condition, concrete comparison and regression tests
- Owner / next experiment: actionable step or none
```

Keep historical entries and immutable proof links; append corrections/supersession notes rather than silently rewriting negative evidence. Cite the actual PR/test instead of fabricating one. Remove personal or secret information from logs.

## Required workflow / PR gate
1. **Before design:** search the failure register and accepted decisions for similar attempts.
2. **During experiments:** capture hypotheses, exact inputs, outputs and limitations; distinguish synthetic CI, desktop, emulator and device testing.
3. **After material failure/architectural choice:** update the register in the same PR; for incomplete evidence link a tracking issue. Not every transient build error is an architectural failure.
4. **Before merge:** PR must answer whether the proposed change revives any rejected approach. If yes, cite the old entry, changed assumptions, explicit approval for architectural deviations, and regression tests addressing the original failure.
5. Update `CHAT_HANDOFF.md` when a milestone changes current status or the next exact action. Do not churn it for documentation-only housekeeping.

This is a **process check**, not a claim that CI automatically enforces every item. Add objective CI assertions when possible. Don't replace an existing binding architecture contract.
