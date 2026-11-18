using UnityEngine;

namespace Storyverse.Networking
{
    /// <summary>Create via Assets > Create > Storyverse > Api Settings, save as Resources/ApiSettings.asset.</summary>
    [CreateAssetMenu(menuName = "Storyverse/Api Settings")]
    public class ApiSettings : ScriptableObject
    {
        [Tooltip("e.g. http://192.168.1.20:8000 when testing on Quest against a laptop backend")]
        public string BaseUrl = "http://localhost:8000";
        public int TimeoutSeconds = 10;

        [Tooltip("Empty = Solo Court (you + three NPC rulers). Set a name (e.g. \"The Continent\") and every headset " +
                 "built with it joins that same world, each taking a free throne; the first one creates it.")]
        public string SharedWorldName = "";
    }
}
