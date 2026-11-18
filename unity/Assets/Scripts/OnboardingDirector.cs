// The 3-minute guided start (judging alignment §2.3): one sentence, one action, then the next.
// Each step completes on a real game event, so the tutorial *is* the game, not a separate mode.
using System;
using System.Collections.Generic;
using Storyverse.Data;
using Storyverse.Kingdom;
using Storyverse.Story;
using Storyverse.World;
using Storyverse.XR;
using UnityEngine;

namespace Storyverse
{
    public class OnboardingDirector : MonoBehaviour
    {
        [SerializeField] Herald herald;
        [SerializeField] TableAnchorPlacer tablePlacer;
        [SerializeField] GameObject pulseOnSylvaraLetter, pulseOnBuildTray, pulseOnWrist;

        class Step { public string Line; public Func<bool> Done; public Action Enter; }

        readonly List<Step> _steps = new();
        int _index = -1;
        bool _placed, _seatSelected, _built, _palmShown, _decided;
        int _startBuildings;

        public void Begin()
        {
            // The placer usually finished before login did, so read its state as well as listening.
            _placed = tablePlacer.IsPlaced;
            tablePlacer.OnPlaced += _ => _placed = true;
            KingdomSeat.OnSelected += _ => _seatSelected = true;
            KingdomManager.Instance.OnDashboard += Track;
            _startBuildings = KingdomManager.Instance.Dashboard?.Buildings.Count ?? 0;

            _steps.Add(new Step { Line = "Your Majesty, place your realm upon the table.", Done = () => _placed });
            _steps.Add(new Step { Line = "Look at a neighbouring kingdom, then pinch to call its envoy.", Done = () => _seatSelected,
                                  Enter = () => Pulse(pulseOnSylvaraLetter) });
            _steps.Add(new Step { Line = "Pinch a farm from the tray and set it down inside your borders.", Done = () => _built,
                                  Enter = () => Pulse(pulseOnBuildTray) });
            _steps.Add(new Step { Line = "Turn your palm upward to read the royal ledger.", Done = () => _palmShown,
                                  Enter = () => Pulse(pulseOnWrist) });
            _steps.Add(new Step { Line = "A proposal awaits on your desk. The decision is yours.", Done = () => _decided });
            Next();
        }

        public void ReportPalmLedgerShown() => _palmShown = true;   // call from WristLedger when it first opens

        void Track(Dashboard d)
        {
            _built |= d.Buildings.Count > _startBuildings;
            _decided |= _index == _steps.Count - 1 && d.Inbox.Trades.Count + d.Inbox.Loans.Count == 0;
        }

        void Update()
        {
            if (_index >= 0 && _index < _steps.Count && _steps[_index].Done()) Next();
        }

        void Next()
        {
            _index++;
            Pulse(null);
            if (_index >= _steps.Count)
            {
                herald.Say("The court is yours. History will remember what you do next.");
                PlayerPrefs.SetInt("sv_onboarded", 1);
                enabled = false;
                return;
            }
            herald.Say(_steps[_index].Line);
            _steps[_index].Enter?.Invoke();
        }

        void Pulse(GameObject target)
        {
            foreach (var g in new[] { pulseOnSylvaraLetter, pulseOnBuildTray, pulseOnWrist })
                if (g) g.SetActive(g == target);
        }
    }
}
