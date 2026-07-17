# SOP-NET-011: Cisco VLAN Migration Procedure

**Applies to:** Cisco Catalyst / ASR aggregation and core devices
**Owner:** Network Engineering | **Last reviewed:** 2026-05-02

## Purpose
Standard procedure for moving customer-facing traffic from one VLAN to another on Cisco aggregation switches.

## Preconditions
1. Target VLAN must already exist in the IPAM/NetBox VLAN plan and on the device.
2. SVI for the target VLAN must be configured with the correct gateway IP **and DHCP relay
   (`ip helper-address`)** if the customer segment uses DHCP.
3. A configuration backup must be taken immediately before the change.
4. Change must run inside the approved maintenance window unless classified as emergency.

## Procedure
1. `show vlan id <target>` — confirm VLAN exists and is active.
2. `show run interface Vlan<target>` — confirm SVI, gateway, and `ip helper-address` are present.
3. `copy running-config tftp:` — backup.
4. Move access/trunk port membership: `switchport access vlan <target>` or update trunk allowed list.
5. Verify: MAC table population, DHCP lease issuance on the new VLAN, gateway ping from a test client.

## Rollback
Re-apply the previous VLAN membership from the backup config. Rollback must complete within
15 minutes of a failed verification. See SOP-NET-019 (Rollback SOP).
