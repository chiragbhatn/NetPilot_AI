# POL-CHG-001: Maintenance Window Policy

**Owner:** Change Advisory Board | **Effective:** 2025-11-01

## Standard window
All service-affecting changes to production network devices must execute inside the standard
maintenance window: **Sunday 02:00–04:00 local time**.

## Rules
1. Changes affecting more than 10 customers are always classified as service-affecting.
2. Service-affecting changes outside the window are **prohibited** unless declared an emergency
   by the on-call incident manager (severity P1/P2 only).
3. Read-only/diagnostic activity is exempt from the window.
4. Every windowed change requires: an approved change record, a tested rollback plan, and a named
   approver who is **not** the implementer.
5. The change must be abandoned (rolled back) if it is not verified complete by 03:45, leaving a
   15-minute safety buffer before the window closes.

## Blast-radius limits
A single change record may affect at most **100 customers**. Larger migrations must be split into
multiple change records across multiple windows.
