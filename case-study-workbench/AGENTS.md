# CAR-WASH repository rules

## Product boundary
This system assists discovery, evidence extraction, review, and export.
It must never publish content automatically.

## Evidence
Every public sentence must reference one or more approved claim IDs.
Never infer completion, operation, effectiveness, or measured outcomes from
funding, planning, intent, or generic program language.

## Tribal/Nation sources
Nation-authored sources control public wording for Tribal/Nation-led cases.
Do not use supporting sources to override public-use boundaries.
All such cases require mandatory human review.

## Engineering
Run `ruff check .`, `mypy src`, and `pytest` before completing a task when those
tools are available. Add regression fixtures for every corrected extraction or
classification error. Use small commits and do not silently change schemas.

## Accessibility
Do not rely on color alone. Support keyboard navigation and reduced motion.
Public artifacts require image rights, credit, caption, and alt text fields.

## Work planning
For changes spanning multiple modules or requiring schema migration, create
or update `PLANS.md` before implementation.

