# Commit/Push Discipline

This repository follows milestone-oriented commit discipline.

## Commit only at meaningful checkpoints
- after completing a blueprint phase (A, B, C, D, ...)
- after finishing a coherent component (for example execution engine or state persistence)
- after smoke tests or validation pass

## Never commit
- incomplete logic fragments
- unvalidated code
- random/context-free edits

## Every commit must include
- WHAT: what was implemented
- WHY: why this change was made
- STATUS: what is done and what is still pending

## Repository handling standard
- treat this repository as a production system, not an experiment
- keep commit history clean and actionable
- each commit must be a reliable checkpoint to return to
