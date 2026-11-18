// Anything you can look at: kingdom seats, letters, seals, coin chests.
// Input-agnostic: wire ISDK (v207+) gaze interactor events to Hover/Unhover/Select in the Inspector,
// or let GazeSelector drive it (eye gaze with head-gaze fallback).
using UnityEngine;
using UnityEngine.Events;

namespace Storyverse.XR
{
    [RequireComponent(typeof(Collider))]
    public class GazeTarget : MonoBehaviour
    {
        [SerializeField] GameObject highlight;          // soft outline / glow
        [SerializeField] GameObject label;              // name tag that appears on look
        public UnityEvent OnHover = new(), OnUnhover = new(), OnSelect = new();

        public bool Hovered { get; private set; }

        void Awake() { SetVisual(false); }

        public void Hover() { if (Hovered) return; Hovered = true; SetVisual(true); OnHover.Invoke(); }
        public void Unhover() { if (!Hovered) return; Hovered = false; SetVisual(false); OnUnhover.Invoke(); }
        public void Select() => OnSelect.Invoke();

        void SetVisual(bool on)
        {
            if (highlight) highlight.SetActive(on);
            if (label) label.SetActive(on);
        }
    }
}
