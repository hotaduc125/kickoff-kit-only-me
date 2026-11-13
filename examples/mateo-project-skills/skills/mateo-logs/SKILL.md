---
name: mateo-logs
description: Use when a Mateo problem at the customer (WKKM) needs evidence — an incident, a bug report or a triage that needs reproduction. Lists the exact logs and data to request from the machine in one go, so the site is visited only once. Complements avflow's incident and triage skills.
---

# Mateo — field evidence

The evidence for a field problem is on the customer's machine, and every extra site visit costs days. Ask for
everything **once**. Use this inside avflow's `incident` skill (step 2, *Ask for the right evidence*) and `triage`.

## The log request

Write it for the person who contacts WKKM; never contact the customer yourself.

- Mateo version on the machine, and what changed recently: software update, configuration, **recipe**, hardware.
- The exact time of the problem (each occurrence) and what the operator saw on the screen.
- **Application log** and **alarm / event log** for that period. TODO: folder on the machine and file names.
- **SPC / production data** for the affected batches. TODO: where it is exported from.
- Crash dumps, if the application stopped. TODO: location.
- The configuration files and the **recipe** in use.
- Photos of the screen and of the **affected panel** (the physical result).
- Whether it can be made to happen again, and how.

## Using the evidence

- Timeline: alarms, events, recipe and configuration changes, versions — on which machine, when.
- Replay recorded camera data on the simulator to reproduce (see `mateo-machine-review`).
- Do not commit customer logs or data to the repository; keep anonymised samples only.
