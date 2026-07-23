# Spirits Calling Release Readiness

- **Package acceptance:** `blocked`
- **Package version:** `0.9.0`
- **Source revision:** `b0d0f46`
- **Engine/platform/configuration:** `5.8` / `Win64` / `Shipping`
- **IoStore:** `True`
- **Package path:** `Builds/Windows`
- **Launch log:** `evidence/launch.log`

## Smoke Matrix

| Case | Status | Evidence |
|---|---|---|
| smoke.b1 | not_run | `evidence/missing/smoke.b1.missing` |
| smoke.b2 | not_run | `evidence/missing/smoke.b2.missing` |
| smoke.b3 | not_run | `evidence/missing/smoke.b3.missing` |
| smoke.b4-lan-host-join | not_run | `evidence/missing/smoke.b4-lan-host-join.missing` |
| smoke.b5-pc-vr | not_run | `evidence/missing/smoke.b5-pc-vr.missing` |
| smoke.b6-30 | not_run | `evidence/missing/smoke.b6-30.missing` |
| pcvr.quest_link.menu | not_run | `evidence/missing/pcvr.quest_link.menu.missing` |
| pcvr.quest_link.possession | not_run | `evidence/missing/pcvr.quest_link.possession.missing` |
| pcvr.quest_link.summon | not_run | `evidence/missing/pcvr.quest_link.summon.missing` |
| pcvr.quest_link.heavy_attack | not_run | `evidence/missing/pcvr.quest_link.heavy_attack.missing` |
| pcvr.quest_link.return_to_spirit | not_run | `evidence/missing/pcvr.quest_link.return_to_spirit.missing` |

## Gates

| ID | Owner | Priority | Status | Evidence | Failure / resolution |
|---|---|---|---|---|---|
| preflight.build | release-engineering | P0 | pass | `build` |  |
| preflight.audio | release-engineering | P0 | pass | `RawAssets/Audio` |  |
| preflight.generated_assets | release-engineering | P0 | pass | `RawAssets/AI` |  |
| preflight.map | release-engineering | P0 | pass | `Content/Maps/DemoMap.umap` |  |
| preflight.config | release-engineering | P0 | pass | `Config/DefaultGame.ini` |  |
| preflight.a5 | release-engineering | P0 | pass | `evidence/missing/preflight.a5.missing` |  |
| preflight.package | release-engineering | P0 | not_run | `evidence/missing/preflight.package.missing` | 尚未打包（P0-5 待做） (open) |
| preflight.release_scope | release-engineering | P0 | pass | `evidence/missing/preflight.release_scope.missing` |  |
| smoke.b1 | release-engineering | P0 | not_run | `evidence/missing/smoke.b1.missing` | not measured (open) |
| smoke.b2 | release-engineering | P0 | not_run | `evidence/missing/smoke.b2.missing` | not measured (open) |
| smoke.b3 | release-engineering | P0 | not_run | `evidence/missing/smoke.b3.missing` | not measured (open) |
| smoke.b4-lan-host-join | release-engineering | P0 | not_run | `evidence/missing/smoke.b4-lan-host-join.missing` | not measured (open) |
| smoke.b5-pc-vr | release-engineering | P0 | not_run | `evidence/missing/smoke.b5-pc-vr.missing` | not measured (open) |
| smoke.b6-30 | release-engineering | P0 | not_run | `evidence/missing/smoke.b6-30.missing` | not measured (open) |
| release.steam.account_app_id | steam-release-owner | P0 | not_run | `evidence/missing/release.steam.account_app_id.missing` | release owner evidence not supplied (open) |
| release.store.capsule_art | store-art-owner | P0 | not_run | `evidence/missing/release.store.capsule_art.missing` | release owner evidence not supplied (open) |
| release.store.screenshots | store-capture-owner | P0 | not_run | `evidence/missing/release.store.screenshots.missing` | release owner evidence not supplied (open) |
| release.store.trailer | trailer-owner | P0 | not_run | `evidence/missing/release.store.trailer.missing` | release owner evidence not supplied (open) |
| release.legal.content_rating | legal-owner | P0 | not_run | `evidence/missing/release.legal.content_rating.missing` | release owner evidence not supplied (open) |
| release.legal.eula_privacy | legal-owner | P0 | not_run | `evidence/missing/release.legal.eula_privacy.missing` | release owner evidence not supplied (open) |
| release.store.early_access_scope | release-owner | P0 | not_run | `Docs/Release/Release_Materials/scope.md` | release owner evidence not supplied (open) |
| release.audio.imports | audio-import-owner | P0 | not_run | `evidence/missing/release.audio.imports.missing` | release owner evidence not supplied (open) |

## Unresolved Issues

| ID | Gate | Reason | Evidence | Resolution |
|---|---|---|---|---|
| preflight.a5.issue | preflight.a5 | DefaultGame.ini ProjectVersion | `evidence/missing/preflight.a5.missing` | open |
| preflight.package.issue | preflight.package | 尚未打包（P0-5 待做） | `evidence/missing/preflight.package.missing` | open |
| preflight.release_scope.issue | preflight.release_scope | PC single-player/LAN-friend/PCVR 宣告與非出貨能力排除已通過 | `evidence/missing/preflight.release_scope.missing` | open |
| smoke.b1.issue | smoke.b1 | gate did not pass | `evidence/missing/smoke.b1.missing` | open |
| smoke.b2.issue | smoke.b2 | gate did not pass | `evidence/missing/smoke.b2.missing` | open |
| smoke.b3.issue | smoke.b3 | gate did not pass | `evidence/missing/smoke.b3.missing` | open |
| smoke.b4-lan-host-join.issue | smoke.b4-lan-host-join | gate did not pass | `evidence/missing/smoke.b4-lan-host-join.missing` | open |
| smoke.b5-pc-vr.issue | smoke.b5-pc-vr | gate did not pass | `evidence/missing/smoke.b5-pc-vr.missing` | open |
| smoke.b6-30.issue | smoke.b6-30 | gate did not pass | `evidence/missing/smoke.b6-30.missing` | open |
| release.steam.account_app_id.issue | release.steam.account_app_id | release owner evidence not supplied | `evidence/missing/release.steam.account_app_id.missing` | open |
| release.store.capsule_art.issue | release.store.capsule_art | release owner evidence not supplied | `evidence/missing/release.store.capsule_art.missing` | open |
| release.store.screenshots.issue | release.store.screenshots | release owner evidence not supplied | `evidence/missing/release.store.screenshots.missing` | open |
| release.store.trailer.issue | release.store.trailer | release owner evidence not supplied | `evidence/missing/release.store.trailer.missing` | open |
| release.legal.content_rating.issue | release.legal.content_rating | release owner evidence not supplied | `evidence/missing/release.legal.content_rating.missing` | open |
| release.legal.eula_privacy.issue | release.legal.eula_privacy | release owner evidence not supplied | `evidence/missing/release.legal.eula_privacy.missing` | open |
| release.store.early_access_scope.issue | release.store.early_access_scope | release owner evidence not supplied | `Docs/Release/Release_Materials/scope.md` | open |
| release.audio.imports.issue | release.audio.imports | release owner evidence not supplied | `evidence/missing/release.audio.imports.missing` | open |

## Earliest Reproducible Failure

```json
null
```

## Validator Findings

- `stability.memory.atFiveMinutes.privateWorkingSetBytes` **missing**: private working set bytes are required
- `stability.memory.atEnd.privateWorkingSetBytes` **missing**: private working set bytes are required
- `gates[5].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[6].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[7].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[8].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[9].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[10].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[11].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[12].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[13].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[14].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[15].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[16].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[17].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[18].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[19].evidencePath` **unlocatable**: gate evidence path does not exist
- `gates[21].evidencePath` **unlocatable**: gate evidence path does not exist
- `evidence[5].path` **unlocatable**: evidence path does not exist
- `evidence[6].path` **unlocatable**: evidence path does not exist
- `evidence[7].path` **unlocatable**: evidence path does not exist
- `evidence[8].path` **unlocatable**: evidence path does not exist
- `evidence[9].path` **unlocatable**: evidence path does not exist
- `evidence[10].path` **unlocatable**: evidence path does not exist
- `evidence[11].path` **unlocatable**: evidence path does not exist
- `evidence[12].path` **unlocatable**: evidence path does not exist
- `evidence[13].path` **unlocatable**: evidence path does not exist
- `evidence[14].path` **unlocatable**: evidence path does not exist
- `evidence[15].path` **unlocatable**: evidence path does not exist
- `evidence[16].path` **unlocatable**: evidence path does not exist
- `evidence[17].path` **unlocatable**: evidence path does not exist
- `evidence[18].path` **unlocatable**: evidence path does not exist
- `evidence[19].path` **unlocatable**: evidence path does not exist
- `evidence[21].path` **unlocatable**: evidence path does not exist
