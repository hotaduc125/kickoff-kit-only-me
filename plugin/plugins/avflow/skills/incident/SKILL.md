---
name: incident
description: Use when software in the field misbehaves at a customer site — a production problem, a recurring defect, a stopped system, data loss or a safety concern. Runs the team's incident flow: severity, the exact logs to collect, a timeline, evidence-based hypotheses, reproduction, the fix with a regression test, and a blameless review. Works with either workflow.
---

# Incident

A field incident is handled differently from an ordinary ticket: the customer is affected now, the evidence is in
their environment, and a wrong guess costs a second round of collecting it. **Conclusions need evidence.**

## Rules

- Tickets and notes only through the `tickets` skill; every note is private. **A person** talks to the customer.
- Never state a cause the evidence does not show. Write *suspect* until it is confirmed.
- Never change software in the customer's environment. Fixes go through the normal merge request and release flow.
- If the project has its own incident or log skill (for example `<project>-logs`), use it for log locations, formats and
  the project's own evidence.

## 1. Severity (first hour)

| Severity | Meaning | Response |
|---|---|---|
| **S1** | Production stopped, safety risk, or data loss | Person informed at once; work starts the same day |
| **S2** | Production impaired, workaround exists | Start within one working day |
| **S3** | Minor, cosmetic, or rare | Normal planning |

Record the severity, the affected customer and system(s) or installation(s), the software version, and when it started, as a private note.

## 2. Ask for the right evidence — once

Write a **log request** the person can send to the customer's or the field engineer's contact, so the evidence is collected **only once**. Include:

- the software version and what changed recently (update, configuration, data, infrastructure or hardware);
- the exact time of the problem (or of each occurrence) and what the operator saw;
- the application, error and event logs for that period, crash logs if any, and the relevant data the system produced;
- the configuration in use;
- screenshots of what the user saw (and photos of any physical result);
- whether it can be made to happen again, and how.

## 3. Timeline

From the evidence, build a timeline: *what happened, when, on which system* — events, alarms, configuration changes, versions. Mark gaps where evidence is missing.

## 4. Hypotheses with evidence

List possible causes. For each: the **evidence for**, the **evidence against**, and **how to confirm or exclude it** (a log line, a test, a run in a test environment). Rule causes out against the most specific facts instead of collecting support for a favourite. Earlier fixes in the same area are hypotheses too, not conclusions.

## 5. Reproduce

Reproduce in a test environment as close to the customer's as possible. Use the workflow's debugging skill (`systematic-debugging` with Superpowers, `diagnosing-bugs` with Matt Pocock's skills). No fix before the cause is shown.

## 6. Fix

- Work ticket with the risk area of the code it touches (or *Other high risk*), so the fix gets that area's checks.
- A **regression test** that fails before the fix and passes after it.
- Release through the normal flow (`release` skill), with the incident named in the release notes.

## 7. Blameless review (within 5 working days)

```markdown
## Incident review — <title>
Severity · customer / system · version · dates (started, detected, fixed, released)
What happened (timeline)
Cause (confirmed) — and how it was confirmed
Why it was not caught earlier (tests, review, release checks)
What we change (tests, checks, monitoring, process) — owner and date for each
```

Focus on the system, never on a person.
