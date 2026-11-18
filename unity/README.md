# STORYVERSE: Unity Quest Client

This folder **is** the Unity project. In Unity Hub choose *Add → Add project from disk* and pick `unity/`.
It opens in **Unity 6000.0.85f2**. `Packages/manifest.json` already pins Meta XR SDK **209.0.0** (Core, MRUK and
Interaction) through Meta's scoped registry, plus OpenXR 1.19.0, XR Management and Newtonsoft.

**Verification so far:** all 29 scripts compile with 0 errors and 0 warnings. They were built against the editor's
real UnityEngine DLLs and uGUI/TMP source, both with and without Fusion. Every Meta XR and MRUK call was also checked
against the **real v209 SDK source**.

**One-click setup:** *Storyverse → 1. Configure Project*, then *2. Build KingdomWorld Scene*. That sets Quest features
(hands, passthrough, anchors, scene), the OpenXR and Meta XR feature set, Android IL2CPP/ARM64, HTTP to the LAN backend,
and `Assets/Resources/ApiSettings.asset` (pointed at this laptop's Wi-Fi IP), then builds and wires the whole scene.
*3a* builds a Windows smoke test and *3b* builds the Quest APK.

**Playing together:** in `ApiSettings`, set **SharedWorldName** (e.g. `The Continent`). Every headset built with it
joins that world and takes a free throne. Start one headset first: it creates the world. Leave it empty for Solo Court.
**Answering proposals:** offers other rulers send you (trades, loans, alliances, peace) appear one at a time on the
**Envoy's Scroll** to the right of the map. Palm-hold **Accept** or **Refuse**. The **Hall of Crowns** (back left) shows
prestige ranks and crown holders.
**End Turn** is the hourglass on the desk (palm-hold). In a shared world it marks you ready, and the turn advances when
every human is ready.

**Laptop IP changed?** Nothing to rebuild. When the saved address stops answering, the headset broadcasts on the
LAN (UDP 47800), the backend replies with its current address, and the headset remembers it. Allow UDP 47800 and
TCP 8000 for Python in Windows Firewall on private networks. Docker Desktop doesn't forward broadcasts, so run the
backend with `uvicorn` directly when headsets need discovery.

**Desktop preview (no headset):** run `Builds/Win/Storyverse.exe` (*Storyverse → 3a* builds it). With no headset
connected, the camera sits in the player's chair on the virtual pedestal. **Left-click** = look + pinch (select a kingdom,
open a letter, read the gauge) or palm-hold a seal (desk, envoy, End Turn). **Right-drag** = look around. **E** = end turn,
**A/R** = accept or refuse the envoy's proposal. Screenshots: `-screenshot out.png [-look pitch,yaw]`.
See `docs/screenshots/`.

**Smoke test (no headset):** *Storyverse → 3a*, then `Builds/Win/Storyverse.exe -batchmode -nographics -smoketest`.
It prints `[SmokeTest] PASS/FAIL` lines to the player log and returns exit code 0 when everything passes.

**HTTP note:** the backend runs over plain HTTP on your LAN, so the setup allows cleartext traffic (Unity's
*Allow downloads over HTTP* and Meta's network-security config turned off). For a public server, use HTTPS and revert both.

**Photon Fusion 2** isn't on a package registry. Import it from Photon (free account), set your App Id, then add
`STORYVERSE_FUSION` under *Project Settings → Player → Scripting Define Symbols*. Until then the game runs normally,
but you won't see the other rulers' hands.

## 1. Packages
| Package | Used by |
|---|---|
| Meta XR Core SDK (`com.meta.xr.sdk.core`) | `OVRHand`, `OVRSkeleton`, `OVREyeGaze`, `OVRSpatialAnchor`, `OVRCameraRig` |
| Meta XR Interaction SDK v207+ (optional, recommended for judging) | gaze/poke/grab interactors. Wire their events to `GazeTarget.Hover/Unhover/Select` |
| Meta MR Utility Kit (`com.meta.xr.mrutilitykit`) | `TableAnchorPlacer`, `ChronicleWall` (tables & walls) |
| Photon Fusion 2 | `MultiplayerManager`, `PlayerSpawner`, `PlayerAvatar` |
| Newtonsoft Json (`com.unity.nuget.newtonsoft-json`) | `ApiClient`, models |
| TextMeshPro | labels |

## 2. Project settings (Quest 3 / 3S)
- Build target **Android**, IL2CPP, ARM64; XR Plug-in: **OpenXR** with Meta Quest feature group (or Oculus XR).
- OVRManager: Hand Tracking **Hands Only** (or Controllers and Hands), Passthrough **enabled**,
  Scene Support **Required**, Anchor Support **enabled**, Eye Tracking **supported** (requests permission at runtime).
- Insecure HTTP to a laptop backend during development: either serve the API over HTTPS or allow cleartext traffic in a
  custom `AndroidManifest.xml` (`android:usesCleartextTraffic="true"`), **development builds only**.
- Fusion Hub: paste your Photon App Id.

## 3. Scene wiring (`KingdomWorld.unity`)
```
OVRCameraRig (passthrough layer on)
├── Hands: OVRHand + OVRSkeleton (L/R) + PinchDetector (L/R) + "Palm" trigger collider (tag "Palm")
GameSystems
├── KingdomManager ─ WorldEventSocket
├── GameBootstrap ─ refs: TableAnchorPlacer, MultiplayerManager, ChronicleWall, OnboardingDirector
├── MultiplayerManager ─ runnerPrefab (NetworkRunner + PlayerSpawner{avatarPrefab})
├── GazeSelector ─ OVREyeGaze (optional), head = CenterEyeAnchor, pinchers = both PinchDetectors
├── Toasts ─ head, TMP template
RealmMapRoot  (empty; TableAnchorPlacer parents & scales it onto the table)
├── RealmMap ─ seatPrefab (KingdomSeat + GazeTarget + collider), building prefabs by type, ribbon materials
TableAnchorPlacer ─ mapRoot = RealmMapRoot, fallbackPedestal, head
DiplomaticDesk ─ StandingGauge, 5 Seals (PalmHoldConfirm each), GiftTray (3 chests + envoy plate)
BuildingTray ─ BuildingCard × N ─ BuildingPlacementManager
WristLedger (on left wrist) ─ onboarding ref
Rookery ─ LetterObject prefab, landing spot, raven Animator ("Land" trigger)
ChronicleWall ─ ChroniclePanel prefab, Herald, free-standing banner
OnboardingDirector ─ Herald, TableAnchorPlacer, pulse highlights
```
Create `Assets/Resources/ApiSettings.asset` (*Create → Storyverse → Api Settings*) and set **BaseUrl** to your laptop's
LAN address (e.g. `http://192.168.1.20:8000`) while testing on the headset.

## 4. Script map (spec §5.2 → files)
| Spec script | File |
|---|---|
| HandInteractionManager / PinchDetector | `XR/PinchDetector.cs`, `XR/GazeSelector.cs`, `XR/GazeTarget.cs`, `XR/PalmHoldConfirm.cs` |
| BuildingPlacementManager / BuildingData | `Buildings/BuildingPlacementManager.cs`, `Buildings/BuildingCard.cs`, `Data/Models.cs` |
| KingdomManager / ResourceDisplay | `Kingdom/KingdomManager.cs`, `Kingdom/WristLedger.cs` |
| WorldMapManager | `World/RealmMap.cs`, `World/KingdomSeat.cs`, `XR/TableAnchorPlacer.cs` |
| MultiplayerManager / PlayerAvatar | `Networking/MultiplayerManager.cs`, `Networking/PlayerSpawner.cs`, `Networking/PlayerAvatar.cs` |
| TradeManager / LoanManager / DiplomacyManager | `Diplomacy/DiplomaticDesk.cs`, `Diplomacy/GiftTray.cs`, `Diplomacy/StandingGauge.cs` |
| BattleManager | battles run from the desk's War seal; results arrive as chronicle + toast |
| StoryEventManager | `Story/ChronicleWall.cs`, `Story/Herald.cs`, `Story/ChroniclePanel.cs` |
| APIClient | `Networking/ApiClient.cs`, `Networking/WorldEventSocket.cs` |
| (new) letters | `Diplomacy/LetterObject.cs`, `Diplomacy/Rookery.cs` |
| (new) onboarding / entry | `OnboardingDirector.cs`, `GameBootstrap.cs` |

## 5. Design rules baked into the code
- **The client never decides results.** Every commit goes through `ApiClient`; the UI refreshes from the server.
- **One gesture, one transaction.** `PinchDetector.GestureId` is sent as the `Idempotency-Key` (test XR-09).
- **Tracking loss is safe.** Losing a hand mid-placement cancels the preview; nothing is committed (XR-06/07).
- **Avatars sync in map space.** Remote rulers appear around *your* table, wherever their own table is.
- **Rooms you never tested.** No scene data, no table or a small table all fall back to a virtual pedestal; no wall falls back to a banner.
