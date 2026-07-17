# STD-NET-003: VLAN Numbering Plan and Standards

**Owner:** Network Architecture | **Last reviewed:** 2026-01-12

## VLAN ranges
| Range | Purpose |
|-------|---------|
| 100–149 | Residential data |
| 150–199 | Residential voice |
| 200–299 | Premium (FTTH) data |
| 300–399 | Enterprise services |
| 400–449 | Management |
| 450–998 | Reserved for future use — **not provisioned** |
| 999 | Quarantine placeholder — **must never carry customer traffic and is not provisioned on any device** |

## Rules
1. A VLAN may only be used if it exists in NetBox **and** on every device in the traffic path.
2. Customer-facing VLANs that use DHCP must have a DHCP relay (`ip helper-address` on Cisco)
   configured on their SVI before any customer is placed on them.
3. VLAN deletions on production devices require Architecture sign-off; VLANs 100, 150, 200, 300
   are protected production VLANs.
4. New premium segments are allocated from 210–229. VLAN 220 (PREMIUM-DATA-NEW) is the current
   target segment for premium growth and migrations.
