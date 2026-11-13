## Test environments and languages

The team skills (`qa-agent`, `triage`, `incident`, `release`) read this section instead of guessing.

- Test environments:
  - **Simulator** (with camera replay) — runs in CI and on every developer machine; reproduce bugs and run the
    regression here first.
  - **Test bench** (real machine at Enclave) — motion, timing and safety behaviour; changes in the *Machine control*
    risk area are tested here **by someone other than the author** before review. TODO: who books it, where results go.
  - **Customer machine (WKKM)** — acceptance only, by the customer's engineer; never change software there.
- Languages the user interface supports: Chinese (zh) and English (en) — every user-visible text in both.
- Project skills: `mateo-machine-review` (test design, review and release checks for machine-control changes),
  `mateo-logs` (field evidence for incidents and bug reproduction).
