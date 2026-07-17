# Incident Report INC-2419: VLAN migration failed — DHCP relay missing on VLAN 220

**Date:** 2026-06-14 (last month) | **Severity:** P2 | **Duration:** 41 minutes
**Affected:** 38 premium customers on OLT-07

## Summary
A planned migration of premium customers from VLAN 200 to VLAN 220 on OLT-07 failed during the
Sunday maintenance window. Service-ports were migrated successfully on the OLT, but customers
could not obtain IP addresses on the new VLAN.

## Root cause
The SVI for VLAN 220 on the aggregation switch had been created **without a DHCP relay
(`ip helper-address`)**. The pre-change checklist verified that VLAN 220 existed but did not
verify the relay configuration. All migrated ONUs came online at layer 2 but DHCP DISCOVER
packets were never forwarded to the DHCP server, causing a total service outage for the
migrated customers.

## Timeline
- 02:10 — Migration batch 1 (20 subscribers) executed, verification "ONU online" passed.
- 02:16 — NOC alarms: DHCP lease count for premium pool dropping.
- 02:24 — Batch 2 halted; troubleshooting began.
- 02:41 — Root cause identified (missing `ip helper-address` on Vlan220 SVI).
- 02:51 — Rollback to VLAN 200 completed; all customers restored.

## Corrective actions
1. DHCP relay was added to the VLAN 220 SVI on 2026-06-15 (verified in NetBox).
2. Pre-change checklist for **any migration to VLAN 220 or a newly created VLAN** must now
   explicitly verify DHCP relay configuration and include a live DHCP lease test with a test ONU
   before migrating customer batches.
3. Verification plans must include "test client obtains DHCP lease" as a hard gate after the
   first batch, before continuing.

## Lesson
"VLAN exists" is not sufficient evidence for a migration. Layer-3 services on the VLAN
(gateway, DHCP relay) must be independently verified. Any similar migration to VLAN 220 should be
treated as **elevated risk** until the DHCP lease test passes.
