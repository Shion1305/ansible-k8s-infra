# WireGuard Overlay Addressing Plan (Zones)

The WireGuard overlay `10.130.5.0/24` is partitioned into role/location **zones**.
Every host and static peer is assigned an IP from exactly one zone and **must
declare which zone it belongs to**. CI verifies that the declared zone and the
assigned IP agree, so the plan can't silently drift.

This keeps the topology self-documenting (you can tell what a node is from its
IP), lets firewall/policy rules target a whole class of nodes as a single CIDR,
and reserves room to grow each class without renumbering.

## Zones

Defined once in `inventory.yml` under `wireguard_zones`:

| Zone | CIDR | Range | Purpose |
|---|---|---|---|
| `oci` | `10.130.5.0/29` | `.1`–`.6` | Cloud nodes (Oracle Cloud) |
| `home-static` | `10.130.5.64/27` | `.65`–`.95` | Always-on home machines (k8s workers) |
| `owned-mobile` | `10.130.5.96/28` | `.97`–`.111` | My own roaming devices (laptops/phones) |
| `external-static` | `10.130.5.128/28` | `.129`–`.143` | Other people's always-on hosts |
| `external-mobile` | `10.130.5.144/28` | `.145`–`.159` | Other people's roaming devices |

Unassigned blocks, reserved for future growth: `.8/29`, `.16/28`, `.32/27`,
`.112/28`, `.160/27`, `.192/26`.

## Current allocation

| Name | Zone | IP | Managed by |
|---|---|---|---|
| `k8s` (control plane) | `oci` | `10.130.5.1` | Ansible |
| `k8s-proxy` | `oci` | `10.130.5.2` | Ansible |
| `cm4` | `home-static` | `10.130.5.65` | Ansible |
| `s2204` | `home-static` | `10.130.5.66` | Ansible |
| `mac-m4-max` | `owned-mobile` | `10.130.5.97` | external device |
| `tomoya-mac` | `external-mobile` | `10.130.5.145` | external device |

`external-static` currently has no members (reserved).

## Rules (enforced by CI)

`tests/test_inventory_zones.py` runs in CI via `just test`. It parses
`inventory.yml` (no live hosts) and **fails** when:

1. a host or static peer is **missing** its `wireguard_zone` (hosts) / `zone`
   (static peers) attribute;
2. the **zone derived from the IP** (the zone whose CIDR contains it) does not
   equal the **declared** zone — i.e. a typo in either field;
3. an IP falls **outside** the overlay (`wireguard_network`);
4. two entries share the **same IP**;
5. two zone CIDRs **overlap**, or a zone is not inside the overlay.

So the declared zone is a redundant, human-readable assertion that CI keeps
honest against the actual IP.

## Adding a cluster node (Ansible-managed)

1. Pick the right zone (`home-static` for a home box, `oci` for a cloud box).
2. Pick a free IP inside that zone's CIDR (see the range column above).
3. Add the host under the right group in `inventory.yml` with both
   `wireguard_ip` and `wireguard_zone`:
   ```yaml
   newbox:
     ansible_host: newbox
     wireguard_ip: 10.130.5.67
     wireguard_zone: home-static
     # ...
   ```
4. `just lint && just test` — the zone test confirms the IP/zone are consistent.
5. Deploy with `just deploy` (run in a maintenance window for renumbers, since a
   worker's WireGuard IP is its kubelet `--node-ip`; see the caveats below).

## Adding a static peer (external device)

1. Generate the device's WireGuard key; set the device's own `Address` to the
   chosen overlay IP.
2. Add it under `wireguard_static_peers` in `inventory.yml`:
   ```yaml
   wireguard_static_peers:
     my-phone:
       public_key: "<device public key>"
       allowed_ips: "10.130.5.98/32"
       zone: owned-mobile
   ```
3. `just lint && just test`, then deploy (control plane picks up the new peer).

## Renumbering caveats

- **Never renumber the control plane (`10.130.5.1`).** It is baked into the
  cluster PKI (API server cert SANs), etcd, and `apiserver_advertise_address`;
  changing it effectively means rebuilding the cluster.
- **Cluster workers**: the WireGuard IP is the kubelet `--node-ip`. Changing it
  changes the node's InternalIP — kubelet restarts, Cilium re-establishes the
  tunnel, brief cross-node blip (pod IPs are unaffected). Do it in a maintenance
  window and deploy all affected nodes together.
- **Static peers are not managed by this repo.** Renumbering one here only
  updates the control-plane-side `allowed_ips`; the device's own `Address` must
  be changed to match at the same time, or that peer drops until it is.
- **Removing a static peer**: the control plane's incremental merge preserves
  peers already present in the running config, so deleting one from
  `inventory.yml` will not remove it from the live control plane. Remove it
  there explicitly (`sudo wg set wg0 peer <pubkey> remove` and drop it from
  `/etc/wireguard/wg0.conf`) or regenerate the config from scratch.

## See also

- `CLAUDE.md` → *WireGuard addressing plan (zones)*
- `docs/WIREGUARD_INCREMENTAL_UPDATES.md` — how control-plane peers are merged
- `tests/test_inventory_zones.py` — the CI guard described above
