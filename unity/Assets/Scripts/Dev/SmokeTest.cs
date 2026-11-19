// Headless end-to-end check, development builds only:  Storyverse.exe -batchmode -nographics -smoketest
// Drives the real components (no gestures needed): enter the realm -> end turns -> an NPC court sends a proposal ->
// the Envoy's Scroll accepts it -> resources move on the server -> the market stall trades -> the ultimatum lectern is wired. Prints [SmokeTest] PASS/FAIL lines and quits.
using System;
using System.Linq;
using System.Threading.Tasks;
using Storyverse.Diplomacy;
using Storyverse.Kingdom;
using Storyverse.Story;
using Storyverse.World;
using UnityEngine;

namespace Storyverse.Dev
{
    public class SmokeTest : MonoBehaviour
    {
        public static bool Requested => Debug.isDebugBuild && Environment.GetCommandLineArgs().Contains("-smoketest");

        int _failures;

        async void Start()
        {
            try { await Run(); }
            catch (Exception e) { Fail($"exception: {e.GetType().Name}: {e.Message}"); }
            Debug.Log(_failures == 0 ? "[SmokeTest] ALL PASSED" : $"[SmokeTest] {_failures} FAILED");
            Application.Quit(_failures == 0 ? 0 : 1);
        }

        async Task Run()
        {
            var km = KingdomManager.Instance;
            if (!await Until(() => km.Dashboard != null && km.Map != null, 40)) { Fail("never entered the realm"); return; }
            Pass($"entered as {km.Dashboard.Kingdom.Name}, turn {km.Dashboard.World.Turn}");

            Check(FindFirstObjectByType<RealmMap>() != null && km.Map.Kingdoms.Count == 4, $"map has {km.Map.Kingdoms.Count} kingdoms");
            Check(FindObjectsByType<KingdomSeat>(FindObjectsSortMode.None).Length == 4, "four kingdom seats rendered");
            var board = FindFirstObjectByType<CrownBoard>();
            Check(board != null, "Hall of Crowns present");

            var tray = FindFirstObjectByType<ProposalTray>();
            if (tray == null) { Fail("Envoy's Scroll missing"); return; }

            var startTurn = km.Dashboard.World.Turn;
            // Always end at least one turn: a resumed world may already have envoys waiting.
            for (int i = 0; i < 4 && (i == 0 || tray.PendingCount == 0); i++)
            {
                var r = await km.AdvanceTurn();
                Check(r.Advanced, $"End Turn advanced to {r.Turn}");
                await Until(() => tray.PendingCount > 0, 3);
            }
            Check(km.Dashboard.World.Turn > startTurn, $"world turn moved {startTurn} -> {km.Dashboard.World.Turn}");
            if (tray.PendingCount == 0) { Fail("no NPC court sent a proposal in 4 turns"); return; }
            Pass($"{tray.PendingCount} proposal(s) on the Envoy's Scroll");

            var before = km.Dashboard.Inbox.Trades.Count + km.Dashboard.Inbox.Loans.Count + km.Dashboard.Inbox.Alliances.Count + km.Dashboard.Inbox.Peace.Count;
            var gold = km.Dashboard.Kingdom.Resources.Gold;
            await tray.AnswerFirst(true);
            var after = km.Dashboard.Inbox.Trades.Count + km.Dashboard.Inbox.Loans.Count + km.Dashboard.Inbox.Alliances.Count + km.Dashboard.Inbox.Peace.Count;
            Check(after == before - 1, $"accepted one proposal ({before} -> {after} waiting)");
            Pass($"gold {gold} -> {km.Dashboard.Kingdom.Resources.Gold} after accepting");

            // Royal Market stall: a palm-hold buys a lot of wood, and the server's treasury moves.
            var stall = FindFirstObjectByType<MarketStall>();
            Check(stall != null, "Royal Market stall present");
            var market = km.Dashboard.Market;
            Check(market != null && km.Dashboard.Ultimatums != null, "dashboard carries the market and ultimatums");
            if (stall != null && market != null && market.Open && market.UnitsLeft > 0)
            {
                var wood = km.Dashboard.Kingdom.Resources.Wood;
                var bought = await stall.Trade("buy", "wood");
                var now = km.Dashboard.Kingdom.Resources.Wood;
                Check(bought != null && now == wood + bought.Amount, $"market bought {bought?.Amount} wood ({wood} -> {now})");
            }
            else Pass("market closed for this kingdom (it has no Market building)");

            // Ultimatum lectern: always in the scene; it rises only while a court demands tribute.
            var lectern = FindFirstObjectByType<UltimatumLectern>();
            Check(lectern != null, "Ultimatum lectern present");
            if (lectern != null)
                Pass(lectern.Current != null ? $"ultimatum shown: {lectern.Current.From} demands {lectern.Current.Amount} by turn {lectern.Current.DeadlineTurn}"
                                             : "no demand yet: the lectern stays hidden");
        }

        static async Task<bool> Until(Func<bool> condition, float seconds)
        {
            var end = Time.realtimeSinceStartup + seconds;
            while (!condition()) { if (Time.realtimeSinceStartup > end) return false; await Task.Delay(100); }
            return true;
        }

        void Check(bool ok, string what) { if (ok) Pass(what); else Fail(what); }
        static void Pass(string what) => Debug.Log($"[SmokeTest] PASS {what}");
        void Fail(string what) { _failures++; Debug.LogError($"[SmokeTest] FAIL {what}"); }
    }
}
