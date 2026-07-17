# SOP-NET-014: Huawei OLT (MA5800) Service Change Procedure

**Applies to:** Huawei MA5800 series OLTs (OLT-01, OLT-12)
**Owner:** Access Network Team | **Last reviewed:** 2026-04-18

## Purpose
Standard procedure for service-port changes (VLAN moves, profile changes) on Huawei GPON OLTs.

## Key facts
- Customer services on the OLT are bound to **service-ports**; a VLAN migration means deleting and
  re-creating each affected service-port with the new VLAN.
- The uplink port (typically 0/19/0) must carry the target VLAN (`port vlan <vlan> 0/19 0`)
  **before** any service-port is migrated, otherwise customers black-hole immediately.
- Migrations affecting more than 20 subscribers must be batched (max 20 service-ports per batch)
  with a 2-minute observation pause between batches.

## Procedure
1. `display vlan <target>` — confirm VLAN exists on the OLT.
2. `backup configuration tftp <server> <file>` — mandatory pre-change backup.
3. Add target VLAN to uplink: `vlan <target> smart` then `port vlan <target> 0/19 0`.
4. For each ONU service-port: `undo service-port <id>` then re-create with the new VLAN.
5. `display service-port vlan <target>` — confirm counts match expectation.
6. Confirm ONU status: `display ont info summary` — all migrated ONUs online.

## Rollback
Re-create service-ports with the original VLAN from the backup. The aggregation switch keeps the
old SVI up for 7 days after any migration to allow instant rollback.
