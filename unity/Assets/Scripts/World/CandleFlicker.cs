// Candlelight for the council table (picture 1): the flame and its light breathe with a little noise.
using UnityEngine;

namespace Storyverse.World
{
    public class CandleFlicker : MonoBehaviour
    {
        [SerializeField] Light flameLight;
        [SerializeField] Transform flame;
        [SerializeField] float baseIntensity = 0.6f, flicker = 0.25f, speed = 7f;

        float _seed;
        Vector3 _flameScale;

        void Awake()
        {
            _seed = Random.value * 100f;
            if (flame) _flameScale = flame.localScale;
        }

        void Update()
        {
            var n = Mathf.PerlinNoise(_seed, Time.time * speed);                // 0..1, smooth
            if (flameLight) flameLight.intensity = baseIntensity + (n - 0.5f) * 2f * flicker;
            if (flame) flame.localScale = new Vector3(_flameScale.x, _flameScale.y * (0.85f + 0.3f * n), _flameScale.z);
        }
    }
}
