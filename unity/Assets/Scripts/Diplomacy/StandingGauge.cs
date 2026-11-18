// The brass Standing Gauge (feature B14): a needle swings across Hostile..Trusted with a trend arrow.
// Pinch the needle (GazeTarget.OnSelect) to read the last reasons aloud on the parchment.
using Storyverse.Data;
using TMPro;
using UnityEngine;

namespace Storyverse.Diplomacy
{
    public class StandingGauge : MonoBehaviour
    {
        [SerializeField] Transform needle;
        [SerializeField] float minAngle = -80f, maxAngle = 80f, swingSpeed = 90f;
        [SerializeField] TMP_Text bandLabel, reasonsLabel;
        [SerializeField] GameObject trendUp, trendDown;
        [SerializeField] AudioSource tick;

        float _target, _current;

        public void Show(RelationData r)
        {
            _target = Mathf.Lerp(minAngle, maxAngle, (r.Standing + 100) / 200f);
            bandLabel.text = $"{r.Name}: {r.Band} ({r.Standing:+#;-#;0})";
            trendUp.SetActive(r.Trend > 0); trendDown.SetActive(r.Trend < 0);
            var sb = new System.Text.StringBuilder();
            if (r.RecentReasons != null)
                foreach (var x in r.RecentReasons) sb.AppendLine($"{x.Delta:+#;-#;0}  {x.Reason}  (turn {x.Turn})");
            reasonsLabel.text = sb.ToString();
            reasonsLabel.gameObject.SetActive(false);
        }

        public void ToggleReasons() => reasonsLabel.gameObject.SetActive(!reasonsLabel.gameObject.activeSelf);

        void Update()
        {
            if (Mathf.Approximately(_current, _target)) return;
            _current = Mathf.MoveTowards(_current, _target, swingSpeed * Time.deltaTime);
            needle.localRotation = Quaternion.Euler(0, 0, -_current);
            if (tick && !tick.isPlaying && Mathf.Abs(_current - _target) > 2f) tick.Play();
        }
    }
}
