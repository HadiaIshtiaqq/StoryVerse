// One-click project + scene setup for STORYVERSE.
//   Menu:          Storyverse > 1. Configure Project, then Storyverse > 2. Build KingdomWorld Scene
//   Command line:  Unity -batchmode -quit -projectPath unity -executeMethod Storyverse.EditorTools.StoryverseSetup.Step1Project
//                  Unity -batchmode -quit -projectPath unity -executeMethod Storyverse.EditorTools.StoryverseSetup.Step2Scene
// Every reference is wired through SerializedObject, and a misspelled field name throws, so a successful run
// means every field in the scene was found and set.
using System;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using Storyverse.Buildings;
using Storyverse.Diplomacy;
using Storyverse.Kingdom;
using Storyverse.Networking;
using Storyverse.Story;
using Storyverse.World;
using Storyverse.XR;
using TMPro;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.SceneManagement;
using UnityEditor.XR.Management;
using UnityEditor.XR.Management.Metadata;
using UnityEditor.XR.OpenXR.Features;
using UnityEngine;
using UnityEngine.XR.Management;
using UnityEngine.XR.OpenXR;
using UnityEngine.Rendering;
using UnityEngine.UI;
using Object = UnityEngine.Object;

namespace Storyverse.EditorTools
{
    public static class StoryverseSetup
    {
        const string ScenePath = "Assets/Scenes/KingdomWorld.unity";
        const string PrefabDir = "Assets/Prefabs";
        const string MatDir = "Assets/Art/Materials";

        static readonly (string type, string label, Color color)[] Buildings =
        {
            ("farm", "Farm", new Color(0.86f, 0.76f, 0.33f)),
            ("lumber_mill", "Lumber Mill", new Color(0.48f, 0.33f, 0.20f)),
            ("mine", "Mine", new Color(0.45f, 0.45f, 0.48f)),
            ("gold_mine", "Gold Mine", new Color(0.78f, 0.63f, 0.36f)),
            ("market", "Market", new Color(0.85f, 0.52f, 0.22f)),
            ("bank", "Bank", new Color(0.14f, 0.24f, 0.21f)),
            ("barracks", "Barracks", new Color(0.51f, 0.24f, 0.26f)),
            ("watchtower", "Watchtower", new Color(0.62f, 0.60f, 0.55f)),
            ("academy", "Academy", new Color(0.30f, 0.45f, 0.75f)),
            ("hospital", "Hospital", new Color(0.92f, 0.90f, 0.86f)),
            ("houses", "Houses", new Color(0.82f, 0.74f, 0.58f)),
            ("tavern", "Tavern", new Color(0.55f, 0.36f, 0.22f)),
            ("mansions", "Mansions", new Color(0.88f, 0.84f, 0.76f)),
            ("blacksmith", "Blacksmith", new Color(0.36f, 0.33f, 0.32f)),
            ("granary", "Granary", new Color(0.74f, 0.58f, 0.36f)),
        };

        static readonly Color Gold = new(0.78f, 0.63f, 0.36f), Emerald = new(0.14f, 0.24f, 0.21f),
            Parchment = new(0.91f, 0.87f, 0.79f), Crimson = new(0.51f, 0.24f, 0.26f), Midnight = new(0.06f, 0.09f, 0.15f);

        // ------------------------------------------------------------------ step 1: project
        [MenuItem("Storyverse/1. Configure Project")]
        public static void Step1Project()
        {
            ImportTmpEssentials();
            EnsureTag("Palm");
            ConfigureMetaFeatures();
            ConfigureXR();
            ConfigurePlayer();
            CreateApiSettings();
            ConfigureArt();
            AssetDatabase.SaveAssets();
            Debug.Log("[StoryverseSetup] Step 1 complete: TMP essentials, Palm tag, Meta features, player settings, ApiSettings.");
        }

        static void ImportTmpEssentials()
        {
            if (AssetDatabase.IsValidFolder("Assets/TextMesh Pro")) return;
            var ugui = UnityEditor.PackageManager.PackageInfo.FindForAssetPath("Packages/com.unity.ugui");
            var pkg = Path.Combine(ugui.resolvedPath, "Package Resources", "TMP Essential Resources.unitypackage");
            if (!File.Exists(pkg)) throw new FileNotFoundException("TMP Essential Resources not found", pkg);
            AssetDatabase.ImportPackage(pkg, false);
        }

        static void EnsureTag(string tag)
        {
            var tm = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            var tags = tm.FindProperty("tags");
            for (int i = 0; i < tags.arraySize; i++) if (tags.GetArrayElementAtIndex(i).stringValue == tag) return;
            tags.InsertArrayElementAtIndex(tags.arraySize);
            tags.GetArrayElementAtIndex(tags.arraySize - 1).stringValue = tag;
            tm.ApplyModifiedPropertiesWithoutUndo();
        }

        static void ConfigureMetaFeatures()
        {
            var cfg = OVRProjectConfig.CachedProjectConfig;
            cfg.handTrackingSupport = OVRProjectConfig.HandTrackingSupport.ControllersAndHands;
            cfg.anchorSupport = OVRProjectConfig.AnchorSupport.Enabled;
            cfg.sceneSupport = OVRProjectConfig.FeatureSupport.Required;
            cfg.insightPassthroughSupport = OVRProjectConfig.FeatureSupport.Required;
            cfg.eyeTrackingSupport = OVRProjectConfig.FeatureSupport.Supported;
            // Meta's default network_sec_config.xml sets cleartextTrafficPermitted="false", which blocks the game's
            // http:// backend on the headset. Unity's own "Allow downloads over HTTP" (ConfigurePlayer) then adds
            // android:usesCleartextTraffic. Switch both off/on together if you move the backend to HTTPS.
            cfg.enableNSCConfig = false;
            OVRProjectConfig.CommitProjectConfig(cfg);
        }

        /// <summary>XR Plug-in Management: OpenXR loader + Meta XR feature set. Android initialises XR on start;
        /// Standalone does not (no PC VR target, and it keeps the headless Windows smoke test deterministic).</summary>
        static void ConfigureXR()
        {
            if (!EditorBuildSettings.TryGetConfigObject(XRGeneralSettings.k_SettingsKey, out XRGeneralSettingsPerBuildTarget perTarget))
            {
                EnsureFolder("Assets/XR");
                perTarget = ScriptableObject.CreateInstance<XRGeneralSettingsPerBuildTarget>();
                AssetDatabase.CreateAsset(perTarget, "Assets/XR/XRGeneralSettingsPerBuildTarget.asset");
                EditorBuildSettings.AddConfigObject(XRGeneralSettings.k_SettingsKey, perTarget, true);
            }
            foreach (var group in new[] { BuildTargetGroup.Standalone, BuildTargetGroup.Android })
            {
                if (!perTarget.HasSettingsForBuildTarget(group)) perTarget.CreateDefaultSettingsForBuildTarget(group);
                if (!perTarget.HasManagerSettingsForBuildTarget(group)) perTarget.CreateDefaultManagerSettingsForBuildTarget(group);
                var assigned = XRPackageMetadataStore.AssignLoader(perTarget.ManagerSettingsForBuildTarget(group), "UnityEngine.XR.OpenXR.OpenXRLoader", group);
                perTarget.SettingsForBuildTarget(group).InitManagerOnStart = group == BuildTargetGroup.Android;
                OpenXRSettings.GetSettingsForBuildTargetGroup(group);   // creates the OpenXR settings asset if missing
                var metaSet = OpenXRFeatureSetManager.GetFeatureSetWithId(group, "com.meta.openxr.featureset.metaxr");
                if (metaSet != null) { metaSet.isEnabled = true; OpenXRFeatureSetManager.SetFeaturesFromEnabledFeatureSets(group); }
                Debug.Log($"[StoryverseSetup] XR {group}: OpenXR loader {(assigned ? "assigned" : "already assigned")}, Meta XR feature set {(metaSet != null ? "enabled" : "NOT FOUND")}");
            }
            EditorUtility.SetDirty(perTarget);
        }

        static void ConfigurePlayer()
        {
            PlayerSettings.companyName = "Storyverse";
            PlayerSettings.productName = "Storyverse: Rise of Kingdoms";
            PlayerSettings.colorSpace = ColorSpace.Linear;
            // Unity 6 refuses http:// by default ("Insecure connection not allowed"). The demo backend runs on the
            // laptop over LAN HTTP; for a public deployment serve HTTPS and set this back to NotAllowed.
            PlayerSettings.insecureHttpOption = InsecureHttpOption.AlwaysAllowed;
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, "com.storyverse.riseofkingdoms");
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel32;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel34;   // Quest OS / Meta store level
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.Vulkan, GraphicsDeviceType.OpenGLES3 });
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
        }

        static void CreateApiSettings()
        {
            EnsureFolder("Assets/Resources");
            const string path = "Assets/Resources/ApiSettings.asset";
            var s = AssetDatabase.LoadAssetAtPath<ApiSettings>(path);
            if (s == null) { s = ScriptableObject.CreateInstance<ApiSettings>(); AssetDatabase.CreateAsset(s, path); }
            s.BaseUrl = $"http://{LanAddress()}:8000";   // the headset reaches the laptop backend over Wi-Fi
            EditorUtility.SetDirty(s);
            Debug.Log($"[StoryverseSetup] ApiSettings.BaseUrl = {s.BaseUrl}");
        }

        /// <summary>Original art kit PNGs (tools/art): transparent, clamped, mip-mapped; plus the unlit quad material
        /// ArtLibrary instantiates at runtime (kept in Resources so its shader ships in the build).</summary>
        static void ConfigureArt()
        {
            foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { "Assets/Resources/Art" }))
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                if (AssetImporter.GetAtPath(path) is not TextureImporter ti) continue;
                ti.textureType = TextureImporterType.Default; ti.alphaIsTransparency = true; ti.alphaSource = TextureImporterAlphaSource.FromInput;
                ti.wrapMode = TextureWrapMode.Clamp; ti.mipmapEnabled = true; ti.sRGBTexture = true; ti.maxTextureSize = 512;
                ti.SaveAndReimport();
            }
            const string matPath = "Assets/Resources/Art/ArtQuad.mat";
            if (AssetDatabase.LoadAssetAtPath<Material>(matPath) == null)
                AssetDatabase.CreateAsset(new Material(Shader.Find("Unlit/Transparent")), matPath);
        }

        static Material ArtMaterial(string folder, string key)
        {
            var path = $"{MatDir}/Art_{folder}_{key}.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null) { mat = new Material(AssetDatabase.LoadAssetAtPath<Material>("Assets/Resources/Art/ArtQuad.mat")); AssetDatabase.CreateAsset(mat, path); }
            mat.mainTexture = AssetDatabase.LoadAssetAtPath<Texture2D>($"Assets/Resources/Art/{folder}/{key}.png");
            EditorUtility.SetDirty(mat);
            return mat;
        }

        /// <summary>An unlit, see-through picture quad (portraits, crests, icons). Hidden until code fills it.</summary>
        static Renderer Picture(string name, Transform parent, Vector3 localPos, float size, Material mat, bool flat = false, bool visible = false)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Quad);
            go.name = name; Object.DestroyImmediate(go.GetComponent<Collider>());
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos; go.transform.localScale = new Vector3(size, size, 1);
            if (flat) go.transform.localRotation = Quaternion.Euler(90, 0, 0);
            var r = go.GetComponent<Renderer>(); r.sharedMaterial = mat;
            r.shadowCastingMode = ShadowCastingMode.Off;
            go.SetActive(visible);
            return r;
        }

        static string LanAddress()
        {
            // Only adapters with a default gateway (Wi-Fi/Ethernet). Skips VirtualBox/WSL/Docker virtual adapters,
            // which the headset cannot reach.
            try
            {
                foreach (var nic in NetworkInterface.GetAllNetworkInterfaces())
                {
                    if (nic.OperationalStatus != OperationalStatus.Up) continue;
                    var props = nic.GetIPProperties();
                    if (!props.GatewayAddresses.Any(g => g.Address.AddressFamily == AddressFamily.InterNetwork && !g.Address.Equals(IPAddress.Any))) continue;
                    var ip = props.UnicastAddresses.FirstOrDefault(a => a.Address.AddressFamily == AddressFamily.InterNetwork);
                    if (ip != null) return ip.Address.ToString();
                }
            }
            catch { }
            return "localhost";
        }

        // ------------------------------------------------------------------ step 2: scene
        [MenuItem("Storyverse/2. Build KingdomWorld Scene")]
        public static void Step2Scene()
        {
            if (TMP_Settings.defaultFontAsset == null)
                throw new InvalidOperationException("TMP Essential Resources missing: run Storyverse > 1. Configure Project first.");
            EnsureFolder(PrefabDir); EnsureFolder(MatDir); EnsureFolder("Assets/Scenes");

            var m = new Mats();
            var buildingPrefabs = Buildings.Select(b => (b.type, b.label, prefab: MakeBuildingPrefab(b.type, b.color, m))).ToArray();
            var seatPrefab = MakeSeatPrefab(m);
            var panelPrefab = MakeChroniclePanelPrefab(m);
            var letterPrefab = MakeLetterPrefab(m);

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.55f, 0.55f, 0.6f);
            var sun = new GameObject("Directional Light").AddComponent<Light>();
            sun.type = LightType.Directional; sun.intensity = 1f; sun.transform.rotation = Quaternion.Euler(50, -30, 0);

            // --- XR rig: passthrough camera + both hands -----------------------------------------------------
            var rig = (GameObject)PrefabUtility.InstantiatePrefab(LoadPackageAsset<GameObject>("com.meta.xr.sdk.core", "Prefabs/OVRCameraRig.prefab"));
            var manager = rig.GetComponentInChildren<OVRManager>() ?? rig.AddComponent<OVRManager>();
            SetBool(manager, "isInsightPassthroughEnabled", true);
            rig.AddComponent<OVRPassthroughLayer>();
            var head = Find(rig.transform, "CenterEyeAnchor");
            var cam = head.GetComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0, 0, 0, 0); cam.nearClipPlane = 0.03f;
            var left = MakeHand(Find(rig.transform, "LeftHandAnchor"), true);
            var right = MakeHand(Find(rig.transform, "RightHandAnchor"), false);
            var pinchers = new Object[] { left.pinch, right.pinch };
            var eyeGaze = new GameObject("EyeGaze").AddComponent<OVREyeGaze>();
            eyeGaze.transform.SetParent(head, false);

            PrefabUtility.InstantiatePrefab(LoadPackageAsset<GameObject>("com.meta.xr.mrutilitykit", "Core/Tools/MRUK.prefab"));

            // --- Realm map (TableAnchorPlacer moves & scales this onto the real table) -----------------------
            var mapRoot = new GameObject("RealmMapRoot").transform;
            mapRoot.position = new Vector3(0, 0.75f, 0.55f);
            var board = Prim(PrimitiveType.Cube, "MapBoard", mapRoot, new Vector3(0, -0.006f, 0), new Vector3(1.02f, 0.012f, 1.02f), m.Sea, keepCollider: true);
            DecorateRealm(mapRoot, m);
            MakeCandles(mapRoot, m);
            board.AddComponent<BoxCollider>();
            var realm = new GameObject("RealmMap").AddComponent<RealmMap>();
            realm.transform.SetParent(mapRoot, false);
            Set(realm, "mapRoot", mapRoot);
            Set(realm, "seatPrefab", seatPrefab);
            Set(realm, "allianceRibbon", m.Gold);
            Set(realm, "warRibbon", m.Crimson);
            Set(realm, "passageRibbon", m.Wheat);
            var bp = new SerializedObject(realm).FindProperty("buildingPrefabs");
            bp.arraySize = buildingPrefabs.Length;
            for (int i = 0; i < buildingPrefabs.Length; i++)
            {
                bp.GetArrayElementAtIndex(i).FindPropertyRelative("type").stringValue = buildingPrefabs[i].type;
                bp.GetArrayElementAtIndex(i).FindPropertyRelative("prefab").objectReferenceValue = buildingPrefabs[i].prefab;
            }
            bp.serializedObject.ApplyModifiedPropertiesWithoutUndo();

            // The pedestal's pivot is its TABLETOP (TableAnchorPlacer positions it there); the body hangs below.
            var pedestal = new GameObject("FallbackPedestal");
            pedestal.transform.position = new Vector3(0, 0.72f, 0.55f);
            Prim(PrimitiveType.Cube, "Body", pedestal.transform, new Vector3(0, -0.36f, 0), new Vector3(1.1f, 0.72f, 1.1f), m.Wood, keepCollider: true);
            pedestal.SetActive(false);
            var placer = new GameObject("TableAnchorPlacer").AddComponent<TableAnchorPlacer>();
            Set(placer, "mapRoot", mapRoot); Set(placer, "fallbackPedestal", pedestal); Set(placer, "head", head);

            // --- Game systems ---------------------------------------------------------------------------------
            var systems = new GameObject("GameSystems");
            var socket = systems.AddComponent<WorldEventSocket>();
            var km = systems.AddComponent<KingdomManager>(); Set(km, "socket", socket);
            var multiplayer = systems.AddComponent<MultiplayerManager>();
            var toasts = systems.AddComponent<Toasts>();
            Set(toasts, "head", head);
            Set(toasts, "template", Text("ToastTemplate", systems.transform, Vector3.zero, "Toast", 0.32f, new Vector2(0.6f, 0.12f), Parchment));

            // --- Building tray (left of the player) --------------------------------------------------------------
            var placement = new GameObject("BuildingPlacementManager").AddComponent<BuildingPlacementManager>();
            placement.transform.SetParent(mapRoot, false);
            var reason = Text("PlacementReason", placement.transform, Vector3.zero, "", 0.22f, new Vector2(0.5f, 0.1f), new Color(1f, 0.55f, 0.55f));
            Set(placement, "map", realm); SetArray(placement, "pinchers", pinchers);
            Set(placement, "validMat", m.Valid); Set(placement, "invalidMat", m.Invalid); Set(placement, "reasonLabel", reason);
            Set(placement, "placeSound", Audio(placement.gameObject, "PlaceSound")); Set(placement, "denySound", Audio(placement.gameObject, "DenySound"));

            var tray = new GameObject("BuildingTray").transform;
            tray.SetParent(mapRoot, false); tray.localPosition = new Vector3(-0.76f, 0, -0.26f);
            Prim(PrimitiveType.Cube, "TrayBase", tray, new Vector3(0, -0.005f, 0), new Vector3(0.40f, 0.01f, 0.64f), m.Wood);
            for (int i = 0; i < buildingPrefabs.Length; i++)
            {
                var card = new GameObject($"Card_{buildingPrefabs[i].type}").transform;
                card.SetParent(tray, false);
                card.localPosition = new Vector3((i % 3 - 1) * 0.125f, 0.01f, 0.26f - (i / 3) * 0.122f);
                var body = Prim(PrimitiveType.Cube, "Body", card, Vector3.zero, new Vector3(0.11f, 0.008f, 0.10f), m.Parchment);
                var model = (GameObject)PrefabUtility.InstantiatePrefab(buildingPrefabs[i].prefab, card);
                model.transform.localPosition = new Vector3(0.025f, 0.005f, 0.015f);
                Picture("Icon", card, new Vector3(-0.028f, 0.0055f, 0.014f), 0.042f, ArtMaterial("icons", buildingPrefabs[i].type), flat: true, visible: true);
                var cost = Text("Cost", card, new Vector3(0, 0.006f, -0.03f), buildingPrefabs[i].label, 0.13f, new Vector2(0.11f, 0.04f), Midnight, flat: true);
                var bc = card.gameObject.AddComponent<BuildingCard>();
                SetString(bc, "buildingType", buildingPrefabs[i].type);
                Set(bc, "previewPrefab", buildingPrefabs[i].prefab); Set(bc, "costLabel", cost);
                Set(bc, "body", body.GetComponent<Renderer>()); Set(bc, "placement", placement); SetArray(bc, "pinchers", pinchers);
            }

            // --- Herald, chronicle, onboarding --------------------------------------------------------------------
            var herald = new GameObject("Herald").AddComponent<Herald>();
            herald.transform.SetParent(mapRoot, false); herald.transform.localPosition = new Vector3(0, 0.38f, 0.55f);
            var speech = Text("SpeechBubble", herald.transform, Vector3.zero, "", 0.28f, new Vector2(0.9f, 0.25f), Parchment);
            speech.gameObject.SetActive(false);
            Set(herald, "speechBubble", speech); Set(herald, "fanfare", Audio(herald.gameObject, "Fanfare"));

            var chronicle = new GameObject("ChronicleWall").AddComponent<ChronicleWall>();
            var panelRoot = new GameObject("PanelRoot").transform; panelRoot.SetParent(chronicle.transform, false);
            // A hanging cloth banner (crimson, gold rod) standing to the left, so it never hides the chamber window.
            var banner = new GameObject("FreeStandingBanner");
            banner.transform.SetPositionAndRotation(new Vector3(-1.25f, 1.45f, 1.55f), Quaternion.Euler(0, -35, 0));
            Prim(PrimitiveType.Cube, "Cloth", banner.transform, new Vector3(0, 0, 0.012f), new Vector3(1.75f, 1.05f, 0.012f), m.Crimson);
            Prim(PrimitiveType.Cylinder, "Rod", banner.transform, new Vector3(0, 0.55f, 0.012f), new Vector3(0.03f, 0.95f, 0.03f), m.Gold).transform.localRotation = Quaternion.Euler(0, 0, 90);
            Prim(PrimitiveType.Cube, "Trim", banner.transform, new Vector3(0, -0.53f, 0.012f), new Vector3(1.75f, 0.03f, 0.014f), m.Gold);
            banner.SetActive(false);
            Set(chronicle, "head", head); Set(chronicle, "panelRoot", panelRoot); Set(chronicle, "panelPrefab", panelPrefab.GetComponent<ChroniclePanel>());
            Set(chronicle, "freeStandingBanner", banner); Set(chronicle, "herald", herald);

            // --- Diplomatic desk (player's edge) -----------------------------------------------------------------
            var desk = new GameObject("DiplomaticDesk").transform;
            desk.SetParent(mapRoot, false); desk.localPosition = new Vector3(0, 0, -0.72f);
            Prim(PrimitiveType.Cube, "DeskTop", desk, new Vector3(0, -0.005f, 0), new Vector3(0.9f, 0.01f, 0.32f), m.Wood);
            var gauge = MakeGauge(desk, m);
            var dd = desk.gameObject.AddComponent<DiplomaticDesk>();
            Set(dd, "gauge", gauge);
            Set(dd, "targetTitle", Text("TargetTitle", desk, new Vector3(0.31f, 0.075f, 0.12f), "Look at a kingdom", 0.2f, new Vector2(0.3f, 0.07f), Gold));
            // The ruler you are negotiating with, facing you across the desk.
            Set(dd, "targetPortrait", Picture("TargetPortrait", desk, new Vector3(0.31f, 0.18f, 0.125f), 0.13f, ArtMaterial("medallions", "aurelia")));
            var decisionRoot = new GameObject("DecisionParchment"); decisionRoot.transform.SetParent(desk, false);
            decisionRoot.transform.localPosition = new Vector3(0f, 0.11f, 0.05f);
            Prim(PrimitiveType.Quad, "Paper", decisionRoot.transform, Vector3.zero, new Vector3(0.24f, 0.17f, 1), m.Parchment);   // Quads face -Z: toward the seated player
            Set(dd, "decisionParchment", Text("Text", decisionRoot.transform, new Vector3(0, 0, -0.002f), "", 0.1f, new Vector2(0.22f, 0.15f), Midnight));
            decisionRoot.SetActive(false);
            Set(dd, "decisionRoot", decisionRoot);
            string[] actions = { "alliance", "trade", "loan", "passage", "peace", "declare_war" };
            string[] labels = { "Alliance", "Trade", "Loan", "Passage", "Peace", "War" };
            // Seals sit at x = -0.32 .. +0.20; the End Turn hourglass takes x = +0.36.
            var seals = new SerializedObject(dd).FindProperty("seals");
            seals.arraySize = actions.Length;
            for (int i = 0; i < actions.Length; i++)
            {
                var pos = new Vector3(-0.36f + i * 0.108f, 0, -0.06f);
                var (confirm, cracked, engraving) = MakeSeal(desk, $"Seal_{actions[i]}", labels[i], pos, actions[i] == "declare_war" ? m.Crimson : m.Gold, m);
                var e = seals.GetArrayElementAtIndex(i);
                e.FindPropertyRelative("action").stringValue = actions[i];
                e.FindPropertyRelative("confirm").objectReferenceValue = confirm;
                e.FindPropertyRelative("crackedVisual").objectReferenceValue = cracked;
                e.FindPropertyRelative("engraving").objectReferenceValue = engraving;
            }
            seals.serializedObject.ApplyModifiedPropertiesWithoutUndo();

            // End Turn hourglass: palm-hold to end your turn (shared worlds: marks you ready).
            var (turnConfirm, turnCracked, _) = MakeSeal(desk, "EndTurn", "End Turn", new Vector3(0.36f, 0, -0.06f), m.Emerald, m);
            Object.DestroyImmediate(turnCracked);
            Prim(PrimitiveType.Cylinder, "Hourglass", turnConfirm.transform, new Vector3(0, 0.035f, 0), new Vector3(0.025f, 0.025f, 0.025f), m.Gold);
            var endTurn = turnConfirm.gameObject.AddComponent<EndTurnSeal>();
            Set(endTurn, "confirm", turnConfirm);
            Set(endTurn, "status", Text("TurnStatus", turnConfirm.transform, new Vector3(0, 0.08f, 0), "", 0.07f, new Vector2(0.14f, 0.04f), Parchment));

            // Pinch the gauge to read the reasons behind the standing (StandingGauge.ToggleReasons).
            var dialCol = gauge.gameObject.AddComponent<BoxCollider>(); dialCol.size = new Vector3(0.17f, 0.17f, 0.03f);
            var gaugeTarget = gauge.gameObject.AddComponent<GazeTarget>();
            UnityEditor.Events.UnityEventTools.AddVoidPersistentListener(gaugeTarget.OnSelect, gauge.ToggleReasons);

            // --- Gift tray (right of the player) -----------------------------------------------------------------
            var giftT = new GameObject("GiftTray").transform;
            giftT.SetParent(mapRoot, false); giftT.localPosition = new Vector3(0.72f, 0, -0.30f);
            Prim(PrimitiveType.Cube, "TrayBase", giftT, new Vector3(0, -0.005f, 0), new Vector3(0.30f, 0.01f, 0.5f), m.Wood, keepCollider: true);
            var plate = Prim(PrimitiveType.Cylinder, "EnvoyPlate", giftT, new Vector3(0, 0.002f, -0.14f), new Vector3(0.14f, 0.002f, 0.14f), m.Gold, keepCollider: true);
            Text("PlateLabel", giftT, new Vector3(0, 0.006f, -0.23f), "Envoy", 0.12f, new Vector2(0.14f, 0.03f), Gold, flat: true);
            var chestLabels = new Object[3]; var chests = new Object[3];
            for (int i = 0; i < 3; i++)
            {
                var c = Prim(PrimitiveType.Cube, $"Chest_{i}", giftT, new Vector3((i - 1) * 0.09f, 0.025f, 0.12f), new Vector3(0.06f, 0.045f, 0.045f), m.Gold, keepCollider: true);
                var rb = c.AddComponent<Rigidbody>(); rb.mass = 0.3f;
                SetArray(c.AddComponent<PinchGrab>(), "pinchers", pinchers);
                chests[i] = rb;
                chestLabels[i] = Text("Label", giftT, new Vector3((i - 1) * 0.09f, 0.006f, 0.05f), "", 0.09f, new Vector2(0.09f, 0.04f), Parchment, flat: true);
            }
            var (giftConfirm, _, _) = MakeSeal(giftT, "SendGift", "Send", new Vector3(0, 0, 0.0f), m.Gold, m);
            var gift = giftT.gameObject.AddComponent<GiftTray>();
            Set(gift, "desk", dd); SetArray(gift, "chestLabels", chestLabels); Set(gift, "envoyPlate", plate.GetComponent<Collider>());
            SetArray(gift, "chests", chests); Set(gift, "confirm", giftConfirm);

            // --- Envoy's scroll: proposals sent to you, answered with Accept / Refuse seals ------------------------
            var envoy = new GameObject("EnvoyScroll").transform;
            envoy.SetParent(mapRoot, false); envoy.localPosition = new Vector3(0.74f, 0, 0.18f);
            envoy.localRotation = Quaternion.Euler(0, -25, 0);                     // angled toward the seated player
            Prim(PrimitiveType.Cube, "Stand", envoy, new Vector3(0, 0.005f, 0), new Vector3(0.30f, 0.01f, 0.22f), m.Wood);
            var scroll = new GameObject("Scroll").transform; scroll.SetParent(envoy, false);
            scroll.localPosition = new Vector3(0, 0.13f, 0.06f); scroll.localRotation = Quaternion.Euler(-15, 0, 0);
            Prim(PrimitiveType.Quad, "Paper", scroll, Vector3.zero, new Vector3(0.28f, 0.2f, 1), m.Parchment);
            var envoyText = Text("Text", scroll, new Vector3(0, 0, -0.002f), "", 0.18f, new Vector2(0.26f, 0.18f), Midnight);
            AutoSize(envoyText, 0.08f, 0.2f);
            var glow = Prim(PrimitiveType.Sphere, "WaitingGlow", scroll, new Vector3(0.13f, 0.09f, -0.01f), Vector3.one * 0.02f, m.Highlight);
            glow.SetActive(false);
            var (acceptC, acceptCrack, _) = MakeSeal(envoy, "Accept", "Accept", new Vector3(-0.07f, 0, -0.05f), m.Gold, m);
            var (refuseC, refuseCrack, _) = MakeSeal(envoy, "Refuse", "Refuse", new Vector3(0.07f, 0, -0.05f), m.Crimson, m);
            Object.DestroyImmediate(acceptCrack); Object.DestroyImmediate(refuseCrack);
            var proposals = envoy.gameObject.AddComponent<ProposalTray>();
            Set(proposals, "parchment", envoyText); Set(proposals, "acceptSeal", acceptC); Set(proposals, "refuseSeal", refuseC);
            Set(proposals, "senderPortrait", Picture("SenderPortrait", scroll, new Vector3(0, 0.135f, -0.004f), 0.09f, ArtMaterial("medallions", "aurelia")));
            Set(proposals, "refuseRoot", refuseC.gameObject); Set(proposals, "waitingGlow", glow);

            // --- Hall of Crowns: prestige ranking and the five crowns ---------------------------------------------
            var hall = new GameObject("HallOfCrowns").transform;
            hall.SetParent(mapRoot, false); hall.localPosition = new Vector3(-0.62f, 0.26f, 0.58f);
            hall.localRotation = Quaternion.Euler(0, -20, 0);
            Prim(PrimitiveType.Cube, "Frame", hall, new Vector3(0, 0, 0.006f), new Vector3(0.36f, 0.3f, 0.01f), m.Gold);
            Prim(PrimitiveType.Quad, "Back", hall, Vector3.zero, new Vector3(0.34f, 0.28f, 1), m.Midnight);
            var crownBoard = hall.gameObject.AddComponent<CrownBoard>();
            var boardText = Text("Board", hall, new Vector3(0, 0, -0.002f), "", 0.2f, new Vector2(0.32f, 0.26f), Parchment);
            AutoSize(boardText, 0.08f, 0.22f);
            Set(crownBoard, "board", boardText);
            Set(crownBoard, "leaderPortrait", Picture("LeaderPortrait", hall, new Vector3(0, 0.205f, -0.004f), 0.12f, ArtMaterial("medallions", "aurelia")));

            MakeDecreeBoard(mapRoot, m);
            MakeMarketStall(mapRoot, m);
            MakeUltimatumLectern(mapRoot, m, herald);
            var councilBoard = MakeCouncilBoard(mapRoot, m);

            // --- Rookery (letters) ---------------------------------------------------------------------------------
            var rookery = new GameObject("Rookery").AddComponent<Rookery>();
            rookery.transform.SetParent(mapRoot, false);
            var landing = new GameObject("LandingSpot").transform; landing.SetParent(mapRoot, false); landing.localPosition = new Vector3(0.38f, 0.02f, -0.56f);
            Set(rookery, "letterPrefab", letterPrefab.GetComponent<LetterObject>()); Set(rookery, "landingSpot", landing);

            // --- Onboarding + wrist ledger + gaze ------------------------------------------------------------------
            var onboarding = new GameObject("OnboardingDirector").AddComponent<OnboardingDirector>();
            Set(onboarding, "herald", herald); Set(onboarding, "tablePlacer", placer);
            Set(onboarding, "pulseOnSylvaraLetter", Pulse(landing, m));
            Set(onboarding, "pulseOnBuildTray", Pulse(tray, m));
            Set(onboarding, "pulseOnWrist", Pulse(left.anchor, m));

            var ledgerPanel = new GameObject("LedgerPanel"); ledgerPanel.transform.SetParent(left.anchor, false);
            ledgerPanel.transform.localPosition = new Vector3(0, 0.07f, 0);
            Prim(PrimitiveType.Quad, "Back", ledgerPanel.transform, Vector3.zero, new Vector3(0.14f, 0.12f, 1), m.Midnight);
            var ledgerText = Text("Body", ledgerPanel.transform, new Vector3(0, 0, -0.002f), "", 0.08f, new Vector2(0.13f, 0.11f), Parchment);
            ledgerPanel.SetActive(false);
            var ledger = left.anchor.gameObject.AddComponent<WristLedger>();
            Set(ledger, "hand", left.hand); Set(ledger, "palm", left.anchor); Set(ledger, "head", head);
            Set(ledger, "panel", ledgerPanel); Set(ledger, "body", ledgerText); Set(ledger, "onboarding", onboarding);

            var gaze = systems.AddComponent<GazeSelector>();
            Set(gaze, "eyeGaze", eyeGaze); Set(gaze, "head", head); SetArray(gaze, "pinchers", pinchers); Set(gaze, "placement", placement);

            var preview = systems.AddComponent<Storyverse.Dev.DesktopPreview>();   // PC without a headset only
            Set(preview, "rig", rig.transform); Set(preview, "eye", cam);

            var boot = systems.AddComponent<GameBootstrap>();
            Set(boot, "tablePlacer", placer); Set(boot, "multiplayer", multiplayer); Set(boot, "chronicle", chronicle); Set(boot, "onboarding", onboarding);
            Set(councilBoard, "herald", herald);
            MakeChamber(m);

            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            Debug.Log($"[StoryverseSetup] Step 2 complete: {ScenePath} with {buildingPrefabs.Length} building prefabs, desk, trays, rookery, chronicle, hands.");
        }

        // ------------------------------------------------------------------ builds
        [MenuItem("Storyverse/3a. Build Windows Smoke Test")]
        public static void BuildWindowsSmokeTest() => Build(BuildTarget.StandaloneWindows64, "Builds/Win/Storyverse.exe", BuildOptions.Development);

        [MenuItem("Storyverse/3b. Build Quest APK")]
        // Release build for the headset: no "Development Build" watermark, full IL2CPP optimisation.
        public static void BuildQuestApk() => Build(BuildTarget.Android, "Builds/Quest/Storyverse.apk", BuildOptions.None);

        static void Build(BuildTarget target, string output, BuildOptions options)
        {
            // OpenXR copies this file into the output and errors if a previous build left it there.
            var stale = Path.Combine(Path.GetDirectoryName(output)!, "RuntimeActionBindings.json");
            if (File.Exists(stale)) File.Delete(stale);
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { ScenePath }, target = target, locationPathName = output,
                options = options,
            });
            var s = report.summary;
            Debug.Log($"[StoryverseSetup] Build {target}: {s.result}, {s.totalErrors} errors, {s.totalSize / (1024 * 1024)} MB -> {output}");
            if (s.result != UnityEditor.Build.Reporting.BuildResult.Succeeded) throw new Exception($"Build failed: {s.result}");
        }

        // ------------------------------------------------------------------ hands
        static (Transform anchor, OVRHand hand, PinchDetector pinch) MakeHand(Transform anchor, bool isLeft)
        {
            var go = (GameObject)PrefabUtility.InstantiatePrefab(LoadPackageAsset<GameObject>("com.meta.xr.sdk.core", "Prefabs/OVRHandPrefab.prefab"), anchor);
            go.name = isLeft ? "LeftHand" : "RightHand";
            var hand = go.GetComponent<OVRHand>();
            var skeleton = go.GetComponent<OVRSkeleton>();
            // New v209 projects use the OpenXR hand skeleton.
            SetInt(hand, "HandType", (int)(isLeft ? OVRHand.Hand.HandLeft : OVRHand.Hand.HandRight));
            SetInt(skeleton, "_skeletonType", (int)(isLeft ? OVRSkeleton.SkeletonType.XRHandLeft : OVRSkeleton.SkeletonType.XRHandRight));
            SetInt(go.GetComponent<OVRMesh>(), "_meshType", (int)(isLeft ? OVRMesh.MeshType.XRHandLeft : OVRMesh.MeshType.XRHandRight));

            var pinch = go.AddComponent<PinchDetector>();
            Set(pinch, "hand", hand); Set(pinch, "skeleton", skeleton);

            var palm = new GameObject("Palm") { tag = "Palm" };
            palm.transform.SetParent(anchor, false);
            var sc = palm.AddComponent<SphereCollider>(); sc.isTrigger = true; sc.radius = 0.045f;
            var rb = palm.AddComponent<Rigidbody>(); rb.isKinematic = true; rb.useGravity = false;
            return (anchor, hand, pinch);
        }

        // ------------------------------------------------------------------ prefabs
        // ------------------------------------------------------------------ the realm as a living diorama (picture 2)
        static readonly Vector2[] Capitals = { new(0.28f, 0.32f), new(0.72f, 0.28f), new(0.27f, 0.72f), new(0.73f, 0.71f) };
        static Vector3 MapLocal(float x, float z, float y = 0) => new(x - 0.5f, y, 0.5f - z);
        static float FromCapitals(float x, float z) => Capitals.Min(c => Vector2.Distance(c, new Vector2(x, z)));

        /// <summary>Island continent in a sea, a river, central mountains, forests and grazing sheep. No colliders:
        /// decor never blocks gaze or pinches, and trees stay outside every kingdom's buildable radius.</summary>
        static void DecorateRealm(Transform mapRoot, Mats m)
        {
            var decor = new GameObject("Landscape").transform; decor.SetParent(mapRoot, false);
            Prim(PrimitiveType.Cylinder, "Beach", decor, new Vector3(0, 0.0004f, 0), new Vector3(1.0f, 0.0004f, 1.0f), m.Sand);
            Prim(PrimitiveType.Cylinder, "Land", decor, new Vector3(0, 0.0009f, 0), new Vector3(0.965f, 0.0005f, 0.965f), m.Emerald);
            // River from the mountains to the eastern sea.
            var river = new[] { (0.53f, 0.52f), (0.60f, 0.50f), (0.66f, 0.47f), (0.74f, 0.49f), (0.82f, 0.50f), (0.90f, 0.52f), (0.97f, 0.52f) };
            for (int i = 0; i < river.Length - 1; i++)
            {
                var a = MapLocal(river[i].Item1, river[i].Item2, 0.0016f); var b = MapLocal(river[i + 1].Item1, river[i + 1].Item2, 0.0016f);
                var seg = Prim(PrimitiveType.Cube, "River", decor, (a + b) / 2, new Vector3(0.012f, 0.0006f, Vector3.Distance(a, b) + 0.006f), m.River);
                seg.transform.localRotation = Quaternion.LookRotation(b - a);
            }
            // Mountains in the heart of the continent (nobody's land), snow on the high peaks.
            foreach (var (x, z, h) in new[] { (0.5f, 0.5f, 0.09f), (0.44f, 0.47f, 0.06f), (0.56f, 0.44f, 0.065f), (0.47f, 0.57f, 0.055f), (0.54f, 0.58f, 0.05f) })
            {
                Shape(ConeMesh(), "Mountain", decor, MapLocal(x, z), new Vector3(h * 1.3f, h, h * 1.3f), m.Rock, yaw: x * 400);
                if (h > 0.06f) Shape(ConeMesh(), "Snow", decor, MapLocal(x, z, h * 0.62f), new Vector3(h * 0.5f, h * 0.38f, h * 0.5f), m.Snow);
            }
            // Forests: deterministic scatter outside every capital's buildable radius (0.22) and off the mountains.
            var rnd = new System.Random(11);
            int trees = 0;
            for (int tries = 0; tries < 2000 && trees < 70; tries++)
            {
                float x = (float)rnd.NextDouble(), z = (float)rnd.NextDouble();
                var fromCentre = Vector2.Distance(new Vector2(x, z), new Vector2(0.5f, 0.5f));
                if (fromCentre > 0.45f || fromCentre < 0.12f || FromCapitals(x, z) < 0.25f) continue;
                if (river.Any(p => Vector2.Distance(new Vector2(p.Item1, p.Item2), new Vector2(x, z)) < 0.03f)) continue;
                var tree = new GameObject("Tree").transform; tree.SetParent(decor, false); tree.localPosition = MapLocal(x, z);
                var hgt = 0.018f + (float)rnd.NextDouble() * 0.014f;
                Prim(PrimitiveType.Cylinder, "Trunk", tree, new Vector3(0, hgt * 0.2f, 0), new Vector3(0.003f, hgt * 0.2f, 0.003f), m.Bark);
                if (rnd.NextDouble() < 0.6)
                    Shape(ConeMesh(), "Pine", tree, new Vector3(0, hgt * 0.3f, 0), new Vector3(hgt * 0.65f, hgt * 0.9f, hgt * 0.65f), m.Leaf);
                else
                    Prim(PrimitiveType.Sphere, "Oak", tree, new Vector3(0, hgt * 0.65f, 0), Vector3.one * hgt * 0.75f, m.LeafLight);
                trees++;
            }
            // Sheep in the meadows just beyond the borders.
            for (int i = 0, placed = 0; i < 400 && placed < 14; i++)
            {
                float x = (float)rnd.NextDouble(), z = (float)rnd.NextDouble();
                var d = FromCapitals(x, z);
                if (d < 0.23f || d > 0.3f || Vector2.Distance(new Vector2(x, z), new Vector2(0.5f, 0.5f)) > 0.44f) continue;
                var sheep = new GameObject("Sheep").transform; sheep.SetParent(decor, false);
                sheep.localPosition = MapLocal(x, z); sheep.localRotation = Quaternion.Euler(0, (float)rnd.NextDouble() * 360, 0);
                Prim(PrimitiveType.Sphere, "Fleece", sheep, new Vector3(0, 0.004f, 0), new Vector3(0.008f, 0.006f, 0.011f), m.Wool);
                Prim(PrimitiveType.Sphere, "Head", sheep, new Vector3(0, 0.005f, 0.006f), Vector3.one * 0.004f, m.Midnight);
                placed++;
            }
        }

        /// <summary>Candlelight at the corners of the table (picture 1). Two candles carry real lights (Quest budget).</summary>
        static void MakeCandles(Transform mapRoot, Mats m)
        {
            var spots = new[] { (new Vector3(-0.56f, 0, 0.56f), true), (new Vector3(0.56f, 0, 0.56f), true),
                                (new Vector3(-0.5f, 0, -0.56f), false), (new Vector3(0.5f, 0, -0.56f), false) };
            foreach (var (pos, lit) in spots)
            {
                var c = new GameObject("Candle").transform; c.SetParent(mapRoot, false); c.localPosition = pos;
                Prim(PrimitiveType.Cylinder, "Holder", c, new Vector3(0, 0.003f, 0), new Vector3(0.05f, 0.003f, 0.05f), m.Gold);
                Prim(PrimitiveType.Cylinder, "Wax", c, new Vector3(0, 0.04f, 0), new Vector3(0.022f, 0.036f, 0.022f), m.Parchment);
                var flame = Prim(PrimitiveType.Sphere, "Flame", c, new Vector3(0, 0.084f, 0), new Vector3(0.008f, 0.016f, 0.008f), m.Flame);
                flame.GetComponent<Renderer>().shadowCastingMode = ShadowCastingMode.Off;
                var flicker = c.gameObject.AddComponent<CandleFlicker>();
                Set(flicker, "flame", flame.transform);
                if (!lit) continue;
                var light = new GameObject("Light").AddComponent<Light>();
                light.transform.SetParent(c, false); light.transform.localPosition = new Vector3(0, 0.1f, 0);
                light.type = LightType.Point; light.range = 0.9f; light.intensity = 0.7f; light.color = new Color(1f, 0.74f, 0.45f);
                light.shadows = LightShadows.None;
                Set(flicker, "flameLight", light);
            }
        }

        /// <summary>The council chamber around the table, for the PC preview only (on the Quest your real room is the chamber).</summary>
        static void MakeChamber(Mats m)
        {
            var room = new GameObject("CouncilChamber"); room.AddComponent<DesktopOnly>();
            var stone = m.Make("StoneWall", Color.white);
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>("Assets/Resources/Art/ui/stone.png");
            if (tex) { stone.mainTexture = tex; stone.mainTextureScale = new Vector2(6, 3); }
            var floor = m.Make("Flagstones", new Color(0.24f, 0.22f, 0.2f));
            Prim(PrimitiveType.Cube, "Floor", room.transform, new Vector3(0, -0.01f, 0.6f), new Vector3(6f, 0.02f, 6f), floor);
            Prim(PrimitiveType.Cube, "BackWall", room.transform, new Vector3(0, 1.75f, 2.7f), new Vector3(6f, 3.5f, 0.2f), stone);
            Prim(PrimitiveType.Cube, "LeftWall", room.transform, new Vector3(-2.8f, 1.75f, 0.6f), new Vector3(0.2f, 3.5f, 6f), stone);
            Prim(PrimitiveType.Cube, "RightWall", room.transform, new Vector3(2.8f, 1.75f, 0.6f), new Vector3(0.2f, 3.5f, 6f), stone);
            var glass = ArtMaterial("ui", "stained_glass");
            Picture("Window", room.transform, new Vector3(0, 2.0f, 2.59f), 1f, glass, visible: true).transform.localScale = new Vector3(1.0f, 1.8f, 1);
            var w1 = Picture("WindowL", room.transform, new Vector3(-2.69f, 2.0f, 1.2f), 1f, glass, visible: true).transform;
            w1.localScale = new Vector3(0.8f, 1.44f, 1); w1.localRotation = Quaternion.Euler(0, -90, 0);
            var w2 = Picture("WindowR", room.transform, new Vector3(2.69f, 2.0f, 1.2f), 1f, glass, visible: true).transform;
            w2.localScale = new Vector3(0.8f, 1.44f, 1); w2.localRotation = Quaternion.Euler(0, 90, 0);
            foreach (var x in new[] { -1.2f, 1.2f })
                Prim(PrimitiveType.Cylinder, "Pillar", room.transform, new Vector3(x, 1.75f, 2.45f), new Vector3(0.3f, 1.75f, 0.3f), stone);
        }

        /// <summary>Royal Decrees (picture 2's objectives) as a standing scroll with a claim seal.</summary>
        static void MakeDecreeBoard(Transform mapRoot, Mats m)
        {
            var root = new GameObject("DecreeBoard").transform;
            root.SetParent(mapRoot, false); root.localPosition = new Vector3(-0.8f, 0, 0.32f); root.localRotation = Quaternion.Euler(0, 28, 0);
            Prim(PrimitiveType.Cube, "Stand", root, new Vector3(0, 0.005f, 0), new Vector3(0.3f, 0.01f, 0.14f), m.Wood);
            var scroll = new GameObject("Scroll").transform; scroll.SetParent(root, false);
            scroll.localPosition = new Vector3(0, 0.16f, 0.04f); scroll.localRotation = Quaternion.Euler(-12, 0, 0);
            Prim(PrimitiveType.Quad, "Paper", scroll, Vector3.zero, new Vector3(0.3f, 0.24f, 1), m.Parchment);
            Prim(PrimitiveType.Cylinder, "RodTop", scroll, new Vector3(0, 0.122f, 0.004f), new Vector3(0.012f, 0.165f, 0.012f), m.Wood).transform.localRotation = Quaternion.Euler(0, 0, 90);
            var list = Text("Decrees", scroll, new Vector3(0, -0.005f, -0.002f), "", 0.18f, new Vector2(0.27f, 0.21f), Midnight);
            AutoSize(list, 0.085f, 0.18f);
            var (seal, crack, _) = MakeSeal(root, "ClaimSeal", "Claim", new Vector3(0, 0, -0.035f), m.Gold, m);
            Object.DestroyImmediate(crack);
            var label = Text("ClaimLabel", root, new Vector3(0, 0.03f, -0.07f), "", 0.07f, new Vector2(0.2f, 0.03f), Gold);
            var board = root.gameObject.AddComponent<DecreeBoard>();
            Set(board, "list", list); Set(board, "claimSeal", seal); Set(board, "claimLabel", label);
        }

        /// <summary>The Royal Market: a merchant's stall at the front-left corner. Pinch a crate to choose the goods,
        /// palm-hold Buy or Sell to trade a lot with the crown's merchants (server-priced, per-turn capacity).</summary>
        static void MakeMarketStall(Transform mapRoot, Mats m)
        {
            var root = new GameObject("MarketStall").transform;
            root.SetParent(mapRoot, false); root.localPosition = new Vector3(-0.78f, 0, -0.80f);
            root.localRotation = Quaternion.Euler(0, 25, 0);                         // angled toward the seated player
            Prim(PrimitiveType.Cube, "Stand", root, new Vector3(0, 0.005f, 0), new Vector3(0.32f, 0.01f, 0.18f), m.Wood);
            // The merchant's slate behind the crates: prices, capacity left this turn, what you hold.
            var slate = new GameObject("Slate").transform; slate.SetParent(root, false);
            slate.localPosition = new Vector3(0, 0.15f, 0.085f); slate.localRotation = Quaternion.Euler(-12, 0, 0);
            Prim(PrimitiveType.Quad, "Board", slate, Vector3.zero, new Vector3(0.32f, 0.13f, 1), m.Midnight);
            Prim(PrimitiveType.Cube, "Frame", slate, new Vector3(0, 0, 0.004f), new Vector3(0.335f, 0.145f, 0.006f), m.Gold);
            foreach (var x in new[] { -0.15f, 0.15f })
                Prim(PrimitiveType.Cylinder, "Post", root, new Vector3(x, 0.075f, 0.085f), new Vector3(0.01f, 0.075f, 0.01f), m.Wood);
            var board = Text("Prices", slate, new Vector3(0, 0, -0.002f), "", 0.14f, new Vector2(0.30f, 0.115f), Parchment);
            AutoSize(board, 0.06f, 0.14f);

            string[] goods = { "food", "wood", "stone", "iron" };
            var stall = root.gameObject.AddComponent<MarketStall>();
            var crates = new SerializedObject(stall).FindProperty("crates");
            crates.arraySize = goods.Length;
            for (int i = 0; i < goods.Length; i++)
            {
                var x = -0.111f + i * 0.074f;
                var crate = Prim(PrimitiveType.Cube, $"Crate_{goods[i]}", root, new Vector3(x, 0.035f, 0.03f), new Vector3(0.055f, 0.05f, 0.05f), m.Wood, keepCollider: true);
                var target = crate.AddComponent<GazeTarget>();
                Picture("Icon", root, new Vector3(x, 0.0605f, 0.03f), 0.045f, ArtMaterial("icons", goods[i]), flat: true, visible: true);
                var marker = Prim(PrimitiveType.Cylinder, "Chosen", root, new Vector3(x, 0.011f, 0.03f), new Vector3(0.07f, 0.001f, 0.07f), m.Highlight);
                marker.SetActive(false);
                var tag = Text("Price", root, new Vector3(x, 0.011f, -0.007f), "", 0.06f, new Vector2(0.07f, 0.02f), Parchment, flat: true);
                var e = crates.GetArrayElementAtIndex(i);
                e.FindPropertyRelative("resource").stringValue = goods[i];
                e.FindPropertyRelative("target").objectReferenceValue = target;
                e.FindPropertyRelative("selectedMarker").objectReferenceValue = marker;
                e.FindPropertyRelative("priceTag").objectReferenceValue = tag;
            }
            crates.serializedObject.ApplyModifiedPropertiesWithoutUndo();

            var (buy, buyCrack, buyLabel) = MakeSeal(root, "BuySeal", "Buy", new Vector3(-0.07f, 0, -0.05f), m.Gold, m);
            var (sell, sellCrack, sellLabel) = MakeSeal(root, "SellSeal", "Sell", new Vector3(0.07f, 0, -0.05f), m.Emerald, m);
            Object.DestroyImmediate(buyCrack); Object.DestroyImmediate(sellCrack);
            foreach (var l in new[] { buyLabel, sellLabel }) l.rectTransform.sizeDelta = new Vector2(0.13f, 0.045f);
            Set(stall, "board", board); Set(stall, "buySeal", buy); Set(stall, "sellSeal", sell);
            Set(stall, "buyLabel", buyLabel); Set(stall, "sellLabel", sellLabel); Set(stall, "coins", Audio(root.gameObject, "Coins"));
        }

        /// <summary>Ultimatums: a lectern at the front-right corner that rises only while a court demands tribute.
        /// Shows the demand and the defence race; a crimson seal pays it (palm-hold). The Herald reads it aloud.</summary>
        static void MakeUltimatumLectern(Transform mapRoot, Mats m, Herald herald)
        {
            var root = new GameObject("UltimatumLectern").transform;
            root.SetParent(mapRoot, false); root.localPosition = new Vector3(0.78f, 0, -0.80f);
            root.localRotation = Quaternion.Euler(0, -25, 0);
            var visual = new GameObject("Lectern"); visual.transform.SetParent(root, false);
            var v = visual.transform;
            Prim(PrimitiveType.Cube, "Stand", v, new Vector3(0, 0.005f, 0), new Vector3(0.30f, 0.01f, 0.18f), m.Midnight);
            Prim(PrimitiveType.Cube, "Trim", v, new Vector3(0, 0.011f, -0.088f), new Vector3(0.30f, 0.003f, 0.006f), m.Crimson);
            var scroll = new GameObject("Scroll").transform; scroll.SetParent(v, false);
            scroll.localPosition = new Vector3(0, 0.13f, 0.06f); scroll.localRotation = Quaternion.Euler(-15, 0, 0);
            Prim(PrimitiveType.Quad, "Paper", scroll, Vector3.zero, new Vector3(0.26f, 0.19f, 1), m.Parchment);
            Prim(PrimitiveType.Cylinder, "RodTop", scroll, new Vector3(0, 0.097f, 0.004f), new Vector3(0.012f, 0.145f, 0.012f), m.Crimson).transform.localRotation = Quaternion.Euler(0, 0, 90);
            Prim(PrimitiveType.Cylinder, "RodBottom", scroll, new Vector3(0, -0.097f, 0.004f), new Vector3(0.012f, 0.145f, 0.012f), m.Crimson).transform.localRotation = Quaternion.Euler(0, 0, 90);
            var text = Text("Demand", scroll, new Vector3(0, -0.005f, -0.002f), "", 0.16f, new Vector2(0.24f, 0.17f), Midnight);
            AutoSize(text, 0.06f, 0.16f);
            var portrait = Picture("Threatener", scroll, new Vector3(0, 0.15f, -0.004f), 0.09f, ArtMaterial("medallions", "drakoria"));
            var (pay, crack, payLabel) = MakeSeal(v, "PaySeal", "Tribute", new Vector3(0, 0, -0.05f), m.Crimson, m);
            Object.DestroyImmediate(crack);
            payLabel.rectTransform.sizeDelta = new Vector2(0.14f, 0.03f);
            var lectern = root.gameObject.AddComponent<UltimatumLectern>();
            Set(lectern, "visual", visual); Set(lectern, "scroll", text); Set(lectern, "threatenerPortrait", portrait);
            Set(lectern, "paySeal", pay); Set(lectern, "payLabel", payLabel); Set(lectern, "herald", herald);
            Set(lectern, "drum", Audio(root.gameObject, "WarDrum"));
            visual.SetActive(false);                                              // rises when a demand arrives
        }

        /// <summary>The Royal Council (picture 1): the most urgent adviser's portrait and counsel.</summary>
        static CouncilBoard MakeCouncilBoard(Transform mapRoot, Mats m)
        {
            var root = new GameObject("CouncilBoard").transform;
            root.SetParent(mapRoot, false); root.localPosition = new Vector3(0.62f, 0.26f, 0.58f); root.localRotation = Quaternion.Euler(0, 20, 0);
            Prim(PrimitiveType.Cube, "Frame", root, new Vector3(0, 0, 0.006f), new Vector3(0.36f, 0.3f, 0.01f), m.Gold);
            Prim(PrimitiveType.Quad, "Back", root, Vector3.zero, new Vector3(0.34f, 0.28f, 1), m.Parchment);
            var portrait = Picture("Adviser", root, new Vector3(-0.1f, 0.05f, -0.004f), 0.12f, ArtMaterial("medallions", "caius"));
            var name = Text("Name", root, new Vector3(-0.1f, -0.06f, -0.002f), "", 0.08f, new Vector2(0.15f, 0.06f), Crimson);
            var counsel = Text("Counsel", root, new Vector3(0.065f, -0.01f, -0.002f), "", 0.16f, new Vector2(0.19f, 0.22f), Midnight);
            AutoSize(counsel, 0.09f, 0.16f);
            Text("Title", root, new Vector3(0, 0.125f, -0.002f), "The Royal Council", 0.1f, new Vector2(0.3f, 0.03f), Crimson);
            var board = root.gameObject.AddComponent<CouncilBoard>();
            Set(board, "portrait", portrait); Set(board, "nameplate", name); Set(board, "counsel", counsel);
            return board;
        }


        // ------------------------------------------------------------------ procedural shapes (cone, gable roof)
        static Mesh _cone, _prism;
        const string MeshDir = "Assets/Art/Meshes";

        static Mesh ConeMesh()
        {
            if (_cone) return _cone;
            _cone = AssetDatabase.LoadAssetAtPath<Mesh>($"{MeshDir}/Cone.asset");
            if (_cone) return _cone;
            const int n = 16;
            var v = new System.Collections.Generic.List<Vector3>(); var t = new System.Collections.Generic.List<int>();
            for (int i = 0; i < n; i++)
            {
                float a0 = 2 * Mathf.PI * i / n, a1 = 2 * Mathf.PI * (i + 1) / n;
                var p0 = new Vector3(0.5f * Mathf.Cos(a0), 0, 0.5f * Mathf.Sin(a0)); var p1 = new Vector3(0.5f * Mathf.Cos(a1), 0, 0.5f * Mathf.Sin(a1));
                int b = v.Count; v.Add(p0); v.Add(Vector3.up); v.Add(p1); t.AddRange(new[] { b, b + 1, b + 2 });          // side
                b = v.Count; v.Add(p0); v.Add(p1); v.Add(Vector3.zero); t.AddRange(new[] { b, b + 1, b + 2 });            // base
            }
            _cone = new Mesh { name = "Cone", vertices = v.ToArray(), triangles = t.ToArray() };
            _cone.RecalculateNormals(); _cone.RecalculateBounds();
            EnsureFolder(MeshDir); AssetDatabase.CreateAsset(_cone, $"{MeshDir}/Cone.asset");
            return _cone;
        }

        /// <summary>Gable roof: 1 x 1 footprint, ridge along Z at height 1.</summary>
        static Mesh PrismMesh()
        {
            if (_prism) return _prism;
            _prism = AssetDatabase.LoadAssetAtPath<Mesh>($"{MeshDir}/Prism.asset");
            if (_prism) return _prism;
            Vector3 a = new(-.5f, 0, -.5f), b = new(.5f, 0, -.5f), c = new(0, 1, -.5f), d = new(-.5f, 0, .5f), e = new(.5f, 0, .5f), f = new(0, 1, .5f);
            var v = new[] { a, c, b, d, e, f, a, d, f, a, f, c, b, c, f, b, f, e, a, b, e, a, e, d };
            var t = new int[v.Length]; for (int i = 0; i < t.Length; i++) t[i] = i;
            _prism = new Mesh { name = "Prism", vertices = v, triangles = t };
            _prism.RecalculateNormals(); _prism.RecalculateBounds();
            EnsureFolder(MeshDir); AssetDatabase.CreateAsset(_prism, $"{MeshDir}/Prism.asset");
            return _prism;
        }

        static GameObject Shape(Mesh mesh, string name, Transform parent, Vector3 pos, Vector3 scale, Material mat, float yaw = 0)
        {
            var go = new GameObject(name, typeof(MeshFilter), typeof(MeshRenderer));
            go.transform.SetParent(parent, false); go.transform.localPosition = pos; go.transform.localScale = scale;
            go.transform.localRotation = Quaternion.Euler(0, yaw, 0);
            go.GetComponent<MeshFilter>().sharedMesh = mesh; go.GetComponent<MeshRenderer>().sharedMaterial = mat;
            return go;
        }

        /// <summary>A little house: walls + gable roof (+ chimney with smoke).</summary>
        static void House(Transform root, Vector3 pos, Vector3 size, Material walls, Material roof, Mats m, bool chimney = false, float yaw = 0)
        {
            var h = new GameObject("House").transform; h.SetParent(root, false); h.localPosition = pos; h.localRotation = Quaternion.Euler(0, yaw, 0);
            Prim(PrimitiveType.Cube, "Walls", h, new Vector3(0, size.y / 2, 0), size, walls);
            Shape(PrismMesh(), "Roof", h, new Vector3(0, size.y, 0), new Vector3(size.x * 1.15f, size.y * 0.75f, size.z * 1.1f), roof);
            Prim(PrimitiveType.Cube, "Door", h, new Vector3(0, size.y * 0.25f, -size.z / 2 - 0.0005f), new Vector3(size.x * 0.25f, size.y * 0.5f, 0.001f), m.Midnight);
            if (!chimney) return;
            var ch = Prim(PrimitiveType.Cube, "Chimney", h, new Vector3(size.x * 0.28f, size.y * 1.45f, size.z * 0.2f), new Vector3(0.006f, 0.014f, 0.006f), m.Stone);
            Smoke(ch.transform);
        }

        static void Smoke(Transform chimney, bool dark = false)
        {
            var go = new GameObject("Smoke"); go.transform.SetParent(chimney.parent, false);
            go.transform.localPosition = chimney.localPosition + Vector3.up * 0.009f; go.transform.localRotation = Quaternion.Euler(-90, 0, 0);
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main; main.startLifetime = 2.6f; main.startSpeed = 0.012f; main.startSize = 0.01f; main.maxParticles = 24;
            main.startColor = dark ? new Color(0.25f, 0.25f, 0.27f, 0.6f) : new Color(0.85f, 0.85f, 0.88f, 0.45f);
            main.simulationSpace = ParticleSystemSimulationSpace.World; main.scalingMode = ParticleSystemScalingMode.Hierarchy;
            var em = ps.emission; em.rateOverTime = 4;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Cone; sh.angle = 10; sh.radius = 0.002f;
            var size = ps.sizeOverLifetime; size.enabled = true; size.size = new ParticleSystem.MinMaxCurve(1f, AnimationCurve.Linear(0, 0.6f, 1, 2.4f));
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0), new GradientColorKey(Color.white, 1) },
                      new[] { new GradientAlphaKey(0.9f, 0), new GradientAlphaKey(0f, 1) });
            col.color = g;
            go.GetComponent<ParticleSystemRenderer>().sharedMaterial = AssetDatabase.GetBuiltinExtraResource<Material>("Default-ParticleSystem.mat");
        }

        static GameObject MakeBuildingPrefab(string type, Color color, Mats m)
        {
            var root = new GameObject(type);
            var mat = m.Make($"Building_{type}", color);
            var t = root.transform;
            switch (type)
            {
                case "farm":
                    House(t, new Vector3(0.008f, 0, 0.006f), new Vector3(0.028f, 0.018f, 0.02f), mat, m.Roof, m, chimney: true);
                    Prim(PrimitiveType.Cube, "Field", t, new Vector3(-0.012f, 0.0006f, -0.012f), new Vector3(0.03f, 0.0012f, 0.022f), m.Wheat);
                    break;
                case "lumber_mill":
                    House(t, new Vector3(0.006f, 0, 0.004f), new Vector3(0.03f, 0.016f, 0.02f), mat, m.Roof, m);
                    for (int i = 0; i < 3; i++)
                        Prim(PrimitiveType.Cylinder, "Log", t, new Vector3(-0.016f, 0.003f + (i == 2 ? 0.005f : 0), -0.012f + (i == 2 ? 0.003f : i * 0.006f)),
                             new Vector3(0.005f, 0.012f, 0.005f), m.Wood).transform.localRotation = Quaternion.Euler(0, 0, 90);
                    Prim(PrimitiveType.Cylinder, "Saw", t, new Vector3(0.024f, 0.012f, -0.008f), new Vector3(0.016f, 0.001f, 0.016f), m.Steel).transform.localRotation = Quaternion.Euler(90, 0, 0);
                    break;
                case "mine":
                case "gold_mine":
                    Prim(PrimitiveType.Sphere, "Hill", t, new Vector3(0, 0.006f, 0.004f), new Vector3(0.045f, 0.028f, 0.038f), m.Stone);
                    Prim(PrimitiveType.Cube, "Adit", t, new Vector3(0, 0.007f, -0.012f), new Vector3(0.012f, 0.012f, 0.006f), m.Midnight);
                    Prim(PrimitiveType.Cube, "Lintel", t, new Vector3(0, 0.0135f, -0.0145f), new Vector3(0.016f, 0.002f, 0.002f), m.Wood);
                    var ore = type == "gold_mine" ? m.Gold : m.Iron;
                    for (int i = 0; i < 3; i++) Prim(PrimitiveType.Sphere, "Ore", t, new Vector3(-0.01f + i * 0.009f, 0.003f, -0.024f), Vector3.one * 0.006f, ore);
                    break;
                case "market":
                    foreach (var (x, z) in new[] { (-0.016f, -0.012f), (0.016f, -0.012f), (-0.016f, 0.012f), (0.016f, 0.012f) })
                        Prim(PrimitiveType.Cube, "Post", t, new Vector3(x, 0.009f, z), new Vector3(0.002f, 0.018f, 0.002f), m.Wood);
                    Shape(PrismMesh(), "Awning", t, new Vector3(0, 0.018f, 0), new Vector3(0.04f, 0.01f, 0.03f), mat);
                    Prim(PrimitiveType.Cube, "Counter", t, new Vector3(0, 0.005f, -0.006f), new Vector3(0.03f, 0.01f, 0.01f), m.Wood);
                    Prim(PrimitiveType.Cube, "Crate", t, new Vector3(0.024f, 0.003f, -0.018f), Vector3.one * 0.006f, m.Wheat);
                    break;
                case "bank":
                    Prim(PrimitiveType.Cube, "Steps", t, new Vector3(0, 0.002f, 0), new Vector3(0.042f, 0.004f, 0.032f), m.Stone);
                    for (int i = 0; i < 4; i++) Prim(PrimitiveType.Cylinder, "Column", t, new Vector3(-0.015f + i * 0.01f, 0.012f, -0.012f), new Vector3(0.004f, 0.008f, 0.004f), m.Parchment);
                    Prim(PrimitiveType.Cube, "Hall", t, new Vector3(0, 0.012f, 0.004f), new Vector3(0.036f, 0.016f, 0.02f), mat);
                    Shape(PrismMesh(), "Pediment", t, new Vector3(0, 0.02f, 0), new Vector3(0.044f, 0.01f, 0.034f), m.Parchment, 90);
                    break;
                case "barracks":
                    House(t, new Vector3(0, 0, 0.004f), new Vector3(0.042f, 0.014f, 0.018f), mat, m.Roof, m);
                    Prim(PrimitiveType.Cylinder, "FlagPole", t, new Vector3(0.024f, 0.018f, -0.012f), new Vector3(0.0015f, 0.018f, 0.0015f), m.Wood);
                    Prim(PrimitiveType.Cube, "Flag", t, new Vector3(0.03f, 0.031f, -0.012f), new Vector3(0.012f, 0.008f, 0.0008f), m.Crimson);
                    break;
                case "watchtower":
                    Prim(PrimitiveType.Cylinder, "Tower", t, new Vector3(0, 0.022f, 0), new Vector3(0.016f, 0.022f, 0.016f), m.Stone);
                    Shape(ConeMesh(), "Spire", t, new Vector3(0, 0.044f, 0), new Vector3(0.022f, 0.02f, 0.022f), m.Roof);
                    break;
                case "academy":
                    Prim(PrimitiveType.Cube, "Hall", t, new Vector3(0, 0.009f, 0), new Vector3(0.036f, 0.018f, 0.026f), mat);
                    Prim(PrimitiveType.Sphere, "Dome", t, new Vector3(0, 0.018f, 0), new Vector3(0.022f, 0.016f, 0.022f), m.Gold);
                    Prim(PrimitiveType.Cylinder, "Tower", t, new Vector3(0.016f, 0.016f, 0.01f), new Vector3(0.008f, 0.016f, 0.008f), m.Stone);
                    Shape(ConeMesh(), "Spire", t, new Vector3(0.016f, 0.032f, 0.01f), new Vector3(0.011f, 0.012f, 0.011f), m.Roof);
                    break;
                case "hospital":
                    House(t, Vector3.zero, new Vector3(0.036f, 0.016f, 0.024f), mat, m.Roof, m);
                    Prim(PrimitiveType.Cube, "CrossV", t, new Vector3(0, 0.012f, -0.0125f), new Vector3(0.003f, 0.009f, 0.001f), m.Crimson);
                    Prim(PrimitiveType.Cube, "CrossH", t, new Vector3(0, 0.012f, -0.0125f), new Vector3(0.009f, 0.003f, 0.001f), m.Crimson);
                    break;
                case "houses":
                    House(t, new Vector3(-0.012f, 0, 0.008f), new Vector3(0.016f, 0.012f, 0.014f), mat, m.Roof, m, chimney: true, yaw: 10);
                    House(t, new Vector3(0.013f, 0, 0.01f), new Vector3(0.014f, 0.011f, 0.013f), mat, m.Roof, m, yaw: -15);
                    House(t, new Vector3(0, 0, -0.012f), new Vector3(0.018f, 0.013f, 0.014f), mat, m.Roof, m, chimney: true);
                    break;
                case "tavern":
                    House(t, Vector3.zero, new Vector3(0.032f, 0.02f, 0.024f), mat, m.Roof, m, chimney: true);
                    Prim(PrimitiveType.Cube, "Sign", t, new Vector3(0.019f, 0.013f, -0.013f), new Vector3(0.008f, 0.006f, 0.001f), m.Gold);
                    Prim(PrimitiveType.Cylinder, "Barrel", t, new Vector3(-0.02f, 0.004f, -0.016f), new Vector3(0.007f, 0.004f, 0.007f), m.Wood);
                    break;
                case "mansions":
                    House(t, Vector3.zero, new Vector3(0.044f, 0.022f, 0.026f), mat, m.Roof, m, chimney: true);
                    Prim(PrimitiveType.Cylinder, "Tower", t, new Vector3(0.026f, 0.017f, 0), new Vector3(0.012f, 0.017f, 0.012f), mat);
                    Shape(ConeMesh(), "Spire", t, new Vector3(0.026f, 0.034f, 0), new Vector3(0.016f, 0.016f, 0.016f), m.Roof);
                    break;
                case "blacksmith":
                    House(t, new Vector3(0.006f, 0, 0.006f), new Vector3(0.026f, 0.016f, 0.02f), mat, m.Roof, m);
                    var forge = Prim(PrimitiveType.Cube, "Chimney", t, new Vector3(0.016f, 0.024f, 0.012f), new Vector3(0.007f, 0.016f, 0.007f), m.Stone);
                    Smoke(forge.transform, dark: true);
                    Prim(PrimitiveType.Cube, "Anvil", t, new Vector3(-0.016f, 0.004f, -0.014f), new Vector3(0.01f, 0.006f, 0.005f), m.Steel);
                    Prim(PrimitiveType.Sphere, "ForgeGlow", t, new Vector3(0.006f, 0.005f, -0.0045f), Vector3.one * 0.006f, m.Ember);
                    break;
                case "granary":
                    Prim(PrimitiveType.Cylinder, "Silo", t, new Vector3(0.006f, 0.016f, 0.004f), new Vector3(0.022f, 0.016f, 0.022f), mat);
                    Shape(ConeMesh(), "Cap", t, new Vector3(0.006f, 0.032f, 0.004f), new Vector3(0.026f, 0.014f, 0.026f), m.Roof);
                    Prim(PrimitiveType.Cube, "Sacks", t, new Vector3(-0.016f, 0.003f, -0.014f), new Vector3(0.01f, 0.006f, 0.008f), m.Wheat);
                    break;
                default:
                    House(t, Vector3.zero, new Vector3(0.03f, 0.02f, 0.024f), mat, m.Roof, m);
                    break;
            }
            var col = root.AddComponent<BoxCollider>(); col.center = new Vector3(0, 0.02f, 0); col.size = new Vector3(0.05f, 0.04f, 0.05f);
            return SavePrefab(root, $"{PrefabDir}/Building_{type}.prefab");
        }

        static GameObject MakeSeatPrefab(Mats m)
        {
            var root = new GameObject("KingdomSeat");
            var col = root.AddComponent<BoxCollider>(); col.center = new Vector3(0, 0.04f, 0); col.size = new Vector3(0.1f, 0.09f, 0.1f);
            // Castle (picture 2): curtain walls, four round towers with conical roofs, a square keep and a gate.
            Prim(PrimitiveType.Cube, "Keep", root.transform, new Vector3(0, 0.026f, 0.004f), new Vector3(0.036f, 0.052f, 0.036f), m.Stone);
            for (int i = 0; i < 4; i++)
                Prim(PrimitiveType.Cube, "Merlon", root.transform, new Vector3(-0.014f + i * 0.0093f, 0.055f, -0.0145f), new Vector3(0.005f, 0.006f, 0.005f), m.Stone);
            foreach (var (x, z) in new[] { (-0.04f, -0.04f), (0.04f, -0.04f), (-0.04f, 0.04f), (0.04f, 0.04f) })
            {
                Prim(PrimitiveType.Cylinder, "Tower", root.transform, new Vector3(x, 0.02f, z), new Vector3(0.018f, 0.02f, 0.018f), m.Stone);
                Shape(ConeMesh(), "TowerRoof", root.transform, new Vector3(x, 0.04f, z), new Vector3(0.024f, 0.022f, 0.024f), m.Roof);
            }
            Prim(PrimitiveType.Cube, "WallN", root.transform, new Vector3(0, 0.011f, 0.04f), new Vector3(0.08f, 0.022f, 0.006f), m.Stone);
            Prim(PrimitiveType.Cube, "WallS", root.transform, new Vector3(0, 0.011f, -0.04f), new Vector3(0.08f, 0.022f, 0.006f), m.Stone);
            Prim(PrimitiveType.Cube, "WallE", root.transform, new Vector3(0.04f, 0.011f, 0), new Vector3(0.006f, 0.022f, 0.08f), m.Stone);
            Prim(PrimitiveType.Cube, "WallW", root.transform, new Vector3(-0.04f, 0.011f, 0), new Vector3(0.006f, 0.022f, 0.08f), m.Stone);
            Prim(PrimitiveType.Cube, "Gate", root.transform, new Vector3(0, 0.007f, -0.0435f), new Vector3(0.014f, 0.014f, 0.002f), m.Midnight);
            // Heraldic banner: KingdomSeat puts the kingdom's crest on it (crest art is 200 x 240).
            var bannerR = Prim(PrimitiveType.Quad, "Banner", root.transform, new Vector3(0, 0.095f, -0.016f), new Vector3(0.05f, 0.06f, 1), m.Gold).GetComponent<Renderer>();
            bannerR.shadowCastingMode = ShadowCastingMode.Off;
            var halo = Prim(PrimitiveType.Cylinder, "MyRealmHalo", root.transform, new Vector3(0, 0.001f, 0), new Vector3(0.1f, 0.0005f, 0.1f), m.Gold); halo.SetActive(false);
            // Flat disc (1 mm); KingdomSeat widens X/Z to the build radius and keeps this thickness.
            var ring = Prim(PrimitiveType.Cylinder, "BorderRing", root.transform, new Vector3(0, 0.0017f, 0), new Vector3(0.44f, 0.0005f, 0.44f), m.Border); ring.SetActive(false);   // just above the land layer
            var highlight = Prim(PrimitiveType.Cylinder, "Highlight", root.transform, new Vector3(0, 0.03f, 0), new Vector3(0.11f, 0.032f, 0.11f), m.Highlight); highlight.SetActive(false);
            var name = Text("Name", root.transform, new Vector3(0, 0.15f, 0), "Kingdom", 0.16f, new Vector2(0.2f, 0.04f), Parchment);
            var hint = Text("Hint", root.transform, new Vector3(0, 0.18f, 0), "Pinch to open the desk", 0.1f, new Vector2(0.2f, 0.03f), Gold);
            hint.gameObject.SetActive(false);
            var gt = root.AddComponent<GazeTarget>();
            Set(gt, "highlight", highlight); Set(gt, "label", hint.gameObject);
            var seat = root.AddComponent<KingdomSeat>();
            Set(seat, "nameLabel", name); Set(seat, "bannerRenderer", bannerR); Set(seat, "myRealmHalo", halo); Set(seat, "borderRing", ring.transform);
            return SavePrefab(root, $"{PrefabDir}/KingdomSeat.prefab");
        }

        static GameObject MakeChroniclePanelPrefab(Mats m)
        {
            var root = new GameObject("ChroniclePanel");
            var frame = Prim(PrimitiveType.Cube, "Frame", root.transform, new Vector3(0, 0, 0.006f), new Vector3(0.40f, 0.30f, 0.01f), m.Gold).GetComponent<Renderer>();
            Prim(PrimitiveType.Quad, "Paper", root.transform, Vector3.zero, new Vector3(0.38f, 0.28f, 1), m.Parchment);   // Quads face -Z: toward the seated player
            var panel = root.AddComponent<ChroniclePanel>();
            Set(panel, "title", Text("Title", root.transform, new Vector3(0, 0.1f, -0.002f), "Title", 0.2f, new Vector2(0.36f, 0.05f), Crimson));
            Set(panel, "body", Text("Body", root.transform, new Vector3(0, -0.01f, -0.002f), "", 0.12f, new Vector2(0.36f, 0.16f), Midnight));
            Set(panel, "footer", Text("Footer", root.transform, new Vector3(0, -0.12f, -0.002f), "", 0.09f, new Vector2(0.36f, 0.03f), Emerald));
            Set(panel, "frame", frame);
            return SavePrefab(root, $"{PrefabDir}/ChroniclePanel.prefab");
        }

        static GameObject MakeLetterPrefab(Mats m)
        {
            var root = new GameObject("Letter");
            var col = root.AddComponent<BoxCollider>(); col.size = new Vector3(0.12f, 0.04f, 0.04f);
            var sealedV = new GameObject("Sealed"); sealedV.transform.SetParent(root.transform, false);
            var scroll = Prim(PrimitiveType.Cylinder, "Scroll", sealedV.transform, Vector3.zero, new Vector3(0.025f, 0.05f, 0.025f), m.Parchment);
            scroll.transform.localRotation = Quaternion.Euler(0, 0, 90);
            var wax = Prim(PrimitiveType.Sphere, "Wax", sealedV.transform, new Vector3(0, 0.012f, 0), Vector3.one * 0.015f, m.Crimson).GetComponent<Renderer>();
            var open = new GameObject("Unrolled"); open.transform.SetParent(root.transform, false);
            open.transform.localPosition = new Vector3(0, 0.14f, 0);
            Prim(PrimitiveType.Quad, "Paper", open.transform, Vector3.zero, new Vector3(0.26f, 0.22f, 1), m.Parchment);   // Quads face -Z: toward the seated player
            var from = Text("From", open.transform, new Vector3(0, 0.09f, -0.002f), "", 0.1f, new Vector2(0.24f, 0.03f), Crimson);
            var subject = Text("Subject", open.transform, new Vector3(0, 0.06f, -0.002f), "", 0.14f, new Vector2(0.24f, 0.04f), Midnight);
            var body = Text("Body", open.transform, new Vector3(0, -0.03f, -0.002f), "", 0.09f, new Vector2(0.24f, 0.14f), Midnight);
            open.SetActive(false);
            var gt = root.AddComponent<GazeTarget>();
            var letter = root.AddComponent<LetterObject>();
            Set(letter, "sealedVisual", sealedV); Set(letter, "unrolledVisual", open);
            Set(letter, "subjectText", subject); Set(letter, "bodyText", body); Set(letter, "fromText", from);
            Set(letter, "waxSeal", wax); Set(letter, "unrollSound", Audio(root, "Unroll"));
            return SavePrefab(root, $"{PrefabDir}/Letter.prefab");
        }

        // ------------------------------------------------------------------ desk parts
        static StandingGauge MakeGauge(Transform desk, Mats m)
        {
            var g = new GameObject("StandingGauge").transform;
            g.SetParent(desk, false); g.localPosition = new Vector3(-0.33f, 0.07f, 0.06f);
            Prim(PrimitiveType.Cylinder, "Dial", g, Vector3.zero, new Vector3(0.16f, 0.004f, 0.16f), m.Parchment).transform.localRotation = Quaternion.Euler(-90, 0, 0);
            var pivot = new GameObject("NeedlePivot").transform; pivot.SetParent(g, false); pivot.localPosition = new Vector3(0, -0.05f, -0.005f);
            Prim(PrimitiveType.Cube, "Needle", pivot, new Vector3(0, 0.05f, 0), new Vector3(0.006f, 0.1f, 0.004f), m.Crimson);
            var up = Text("TrendUp", g, new Vector3(0.07f, 0.06f, -0.005f), "▲", 0.2f, new Vector2(0.03f, 0.03f), new Color(0.31f, 0.70f, 0.54f));
            var down = Text("TrendDown", g, new Vector3(0.07f, 0.06f, -0.005f), "▼", 0.2f, new Vector2(0.03f, 0.03f), new Color(0.71f, 0.29f, 0.32f));
            up.gameObject.SetActive(false); down.gameObject.SetActive(false);
            var sg = g.gameObject.AddComponent<StandingGauge>();
            Set(sg, "needle", pivot);
            Set(sg, "bandLabel", Text("Band", g, new Vector3(0, -0.065f, -0.005f), "", 0.14f, new Vector2(0.16f, 0.03f), Gold));
            Set(sg, "reasonsLabel", Text("Reasons", g, new Vector3(0, -0.10f, -0.005f), "", 0.07f, new Vector2(0.2f, 0.05f), Parchment));
            Set(sg, "trendUp", up.gameObject); Set(sg, "trendDown", down.gameObject); Set(sg, "tick", Audio(g.gameObject, "Tick"));
            return sg;
        }

        static (PalmHoldConfirm confirm, GameObject cracked, TMP_Text engraving) MakeSeal(Transform parent, string name, string label, Vector3 pos, Material mat, Mats m)
        {
            var root = new GameObject(name).transform;
            root.SetParent(parent, false); root.localPosition = pos;
            Prim(PrimitiveType.Cylinder, "Wax", root, new Vector3(0, 0.006f, 0), new Vector3(0.07f, 0.006f, 0.07f), mat);
            var trigger = root.gameObject.AddComponent<BoxCollider>(); trigger.isTrigger = true;
            trigger.center = new Vector3(0, 0.05f, 0); trigger.size = new Vector3(0.09f, 0.1f, 0.09f);
            var cracked = Prim(PrimitiveType.Cube, "Cracked", root, new Vector3(0, 0.013f, 0), new Vector3(0.075f, 0.002f, 0.008f), m.Midnight);
            cracked.transform.localRotation = Quaternion.Euler(0, 35, 0); cracked.SetActive(false);
            Text("Label", root, new Vector3(0, 0.0135f, 0), label, 0.1f, new Vector2(0.07f, 0.02f), Midnight, flat: true);
            var engraving = Text("Engraving", root, new Vector3(0, 0.035f, -0.03f), "", 0.06f, new Vector2(0.12f, 0.03f), Parchment);

            var canvasGo = new GameObject("ProgressCanvas", typeof(Canvas));
            canvasGo.transform.SetParent(root, false);
            canvasGo.transform.localPosition = new Vector3(0, 0.015f, 0); canvasGo.transform.localRotation = Quaternion.Euler(90, 0, 0);
            canvasGo.GetComponent<Canvas>().renderMode = RenderMode.WorldSpace;
            var crt = (RectTransform)canvasGo.transform; crt.sizeDelta = new Vector2(80, 80); crt.localScale = Vector3.one * 0.001f;
            var ringGo = new GameObject("Ring", typeof(RectTransform), typeof(Image)); ringGo.transform.SetParent(canvasGo.transform, false);
            ((RectTransform)ringGo.transform).sizeDelta = new Vector2(80, 80);
            var ring = ringGo.GetComponent<Image>();
            ring.sprite = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/Knob.psd");
            ring.type = Image.Type.Filled; ring.fillMethod = Image.FillMethod.Radial360; ring.fillAmount = 0; ring.color = new Color(1f, 0.85f, 0.5f, 0.85f);

            var confirm = root.gameObject.AddComponent<PalmHoldConfirm>();
            Set(confirm, "progressRing", ring); Set(confirm, "waxSound", Audio(root.gameObject, "Wax"));
            return (confirm, cracked, engraving);
        }

        static GameObject Pulse(Transform parent, Mats m)
        {
            var p = Prim(PrimitiveType.Sphere, "OnboardingPulse", parent, new Vector3(0, 0.05f, 0), Vector3.one * 0.05f, m.Highlight);
            p.SetActive(false);
            return p;
        }

        // ------------------------------------------------------------------ helpers
        class Mats
        {
            public readonly Material Gold, Emerald, Parchment, Crimson, Midnight, Wood, Stone, Roof, Valid, Invalid, Highlight, Border,
                Wheat, Steel, Iron, Ember, Sea, Sand, Leaf, LeafLight, Bark, Wool, Snow, Rock, Flame, River;
            public Mats()
            {
                Gold = Make("Gold", StoryverseSetup.Gold); Emerald = Make("Emerald", StoryverseSetup.Emerald);
                Parchment = Make("Parchment", StoryverseSetup.Parchment); Crimson = Make("Crimson", StoryverseSetup.Crimson);
                Midnight = Make("Midnight", StoryverseSetup.Midnight); Wood = Make("Wood", new Color(0.36f, 0.25f, 0.16f));
                Stone = Make("Stone", new Color(0.66f, 0.64f, 0.6f)); Roof = Make("Roof", new Color(0.45f, 0.2f, 0.18f));
                Valid = Make("PlacementValid", new Color(0.31f, 0.70f, 0.54f, 0.6f), transparent: true);
                Invalid = Make("PlacementInvalid", new Color(0.71f, 0.29f, 0.32f, 0.6f), transparent: true);
                Highlight = Make("GazeHighlight", new Color(1f, 0.85f, 0.5f, 0.35f), transparent: true);
                Border = Make("BorderTint", new Color(0.31f, 0.70f, 0.54f, 0.16f), transparent: true);
                Wheat = Make("Wheat", new Color(0.86f, 0.74f, 0.36f)); Steel = Make("Steel", new Color(0.62f, 0.64f, 0.68f));
                Iron = Make("IronOre", new Color(0.36f, 0.34f, 0.36f)); Ember = Make("Ember", new Color(1f, 0.45f, 0.1f));
                Sea = Make("Sea", new Color(0.16f, 0.33f, 0.48f)); Sand = Make("Sand", new Color(0.78f, 0.70f, 0.50f));
                Leaf = Make("Leaf", new Color(0.13f, 0.32f, 0.17f)); LeafLight = Make("LeafLight", new Color(0.30f, 0.50f, 0.22f));
                Bark = Make("Bark", new Color(0.30f, 0.20f, 0.12f)); Wool = Make("Wool", new Color(0.93f, 0.92f, 0.88f));
                Snow = Make("Snow", new Color(0.95f, 0.96f, 0.98f)); Rock = Make("Rock", new Color(0.42f, 0.41f, 0.40f));
                River = Make("River", new Color(0.24f, 0.46f, 0.62f));
                Flame = new Material(Shader.Find("Unlit/Color")) { color = new Color(1f, 0.78f, 0.35f) };
                var flamePath = $"{MatDir}/Flame.mat";
                if (AssetDatabase.LoadAssetAtPath<Material>(flamePath) is Material existing) { existing.color = Flame.color; Flame = existing; }
                else AssetDatabase.CreateAsset(Flame, flamePath);
            }

            public Material Make(string name, Color color, bool transparent = false)
            {
                var path = $"{MatDir}/{name}.mat";
                var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
                // Transparent tints use the dedicated alpha-blended shader: the Standard shader's mode/keyword pairing
                // rendered them opaque in builds.
                var shader = Shader.Find(transparent ? "Legacy Shaders/Transparent/Diffuse" : "Standard");
                if (mat == null) { mat = new Material(shader); AssetDatabase.CreateAsset(mat, path); }
                mat.shader = shader;
                mat.color = color;
                if (transparent) mat.renderQueue = (int)RenderQueue.Transparent;
                EditorUtility.SetDirty(mat);
                return mat;
            }
        }

        static GameObject Prim(PrimitiveType type, string name, Transform parent, Vector3 localPos, Vector3 scale, Material mat, bool keepCollider = false)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            if (parent) go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos; go.transform.localScale = scale;
            go.GetComponent<Renderer>().sharedMaterial = mat;
            if (!keepCollider) Object.DestroyImmediate(go.GetComponent<Collider>());
            return go;
        }

        /// <summary>World-space TextMeshPro. size is the line height in decimetres (0.1 = 1 cm); rect is in metres.</summary>
        static TMP_Text Text(string name, Transform parent, Vector3 localPos, string text, float size, Vector2 rect, Color color, bool flat = false)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var t = go.AddComponent<TextMeshPro>();
            t.text = text; t.fontSize = size; t.color = color;
            t.alignment = TextAlignmentOptions.Center; t.textWrappingMode = TextWrappingModes.Normal;
            t.rectTransform.sizeDelta = rect;
            go.transform.localPosition = localPos;
            go.transform.localRotation = flat ? Quaternion.Euler(90, 0, 0) : Quaternion.identity;
            return t;
        }

        static void AutoSize(TMP_Text t, float min, float max)
        {
            t.enableAutoSizing = true; t.fontSizeMin = min; t.fontSizeMax = max;
            t.alignment = TextAlignmentOptions.Top;
        }

        static AudioSource Audio(GameObject host, string name)
        {
            var go = new GameObject(name); go.transform.SetParent(host.transform, false);
            var a = go.AddComponent<AudioSource>(); a.playOnAwake = false; a.spatialBlend = 1f;
            return a;
        }

        static GameObject SavePrefab(GameObject root, string path)
        {
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, path);
            Object.DestroyImmediate(root);
            return prefab;
        }

        static T LoadPackageAsset<T>(string package, string relative) where T : Object
        {
            var path = $"Packages/{package}/{relative}";
            var asset = AssetDatabase.LoadAssetAtPath<T>(path);
            if (asset == null) throw new FileNotFoundException($"Package asset not found: {path}");
            return asset;
        }

        static Transform Find(Transform root, string name)
        {
            var t = root.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == name);
            if (t == null) throw new InvalidOperationException($"'{name}' not found under {root.name}");
            return t;
        }

        static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            var parent = Path.GetDirectoryName(path)!.Replace('\\', '/');
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
        }

        static SerializedProperty Prop(SerializedObject so, string field)
        {
            var p = so.FindProperty(field);
            if (p == null) throw new InvalidOperationException($"{so.targetObject.GetType().Name} has no serialized field '{field}'");
            return p;
        }

        static void Set(Object target, string field, Object value)
        {
            if (value == null) throw new ArgumentNullException(field, $"Null reference for {target.GetType().Name}.{field}");
            var so = new SerializedObject(target); Prop(so, field).objectReferenceValue = value; so.ApplyModifiedPropertiesWithoutUndo();
        }

        static void SetArray(Object target, string field, Object[] values)
        {
            var so = new SerializedObject(target); var p = Prop(so, field);
            p.arraySize = values.Length;
            for (int i = 0; i < values.Length; i++) p.GetArrayElementAtIndex(i).objectReferenceValue = values[i];
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        static void SetString(Object target, string field, string value) { var so = new SerializedObject(target); Prop(so, field).stringValue = value; so.ApplyModifiedPropertiesWithoutUndo(); }
        static void SetInt(Object target, string field, int value) { var so = new SerializedObject(target); Prop(so, field).intValue = value; so.ApplyModifiedPropertiesWithoutUndo(); }
        static void SetBool(Object target, string field, bool value) { var so = new SerializedObject(target); Prop(so, field).boolValue = value; so.ApplyModifiedPropertiesWithoutUndo(); }
    }
}
