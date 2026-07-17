# SOP-NET-019: Rollback Standard Operating Procedure

**Owner:** Network Engineering | **Last reviewed:** 2026-03-30

## Principles
1. No change is approved without a written, step-level rollback plan.
2. Rollback must be executable by a different engineer than the implementer, using only the
   change record and the pre-change backup.
3. Target: rollback initiated within 5 minutes of failed verification, completed within 15 minutes.

## Standard rollback steps
1. Stop further batches immediately on the first failed verification check.
2. Restore affected configuration from the pre-change backup
   (Cisco: `configure replace`; Huawei OLT: re-create service-ports from backup).
3. Re-run the full verification checklist against the *original* state
   (ONU online count, DHCP leases, gateway ping, traffic within 10% of baseline).
4. Notify the NOC and record the rollback in the change record within 30 minutes.

## Verification checklist (post-change and post-rollback)
- All affected ONUs/ports online
- VLAN membership matches intent
- DHCP leases issuing on the segment (test client obtains an IP within 60 s)
- Gateway reachable (ping) from test client
- Interface traffic within 10% of pre-change baseline after 10 minutes
