// Original art kit (tools/art/make_art.py -> tools/art/render_png.mjs -> Assets/Resources/Art).
// Medallion("Sylvara"), Crest("Drakoria"), Icon("farm"); Show() puts a texture on any quad.
using System.Collections.Generic;
using UnityEngine;

namespace Storyverse
{
    public static class ArtLibrary
    {
        static readonly Dictionary<string, Texture2D> Cache = new();
        static Material _template;

        public static Texture2D Medallion(string kingdom) => Load("medallions", kingdom);
        public static Texture2D Crest(string kingdom) => Load("crests", kingdom);
        public static Texture2D Icon(string name) => Load("icons", name);

        static Texture2D Load(string folder, string key)
        {
            if (string.IsNullOrEmpty(key)) return null;
            var path = $"Art/{folder}/{key.ToLowerInvariant()}";
            if (!Cache.TryGetValue(path, out var tex)) Cache[path] = tex = Resources.Load<Texture2D>(path);
            return tex;
        }

        /// <summary>Shows `tex` on the renderer (unlit, alpha-blended); hides it when there is no texture.</summary>
        public static void Show(Renderer target, Texture2D tex)
        {
            if (target == null) return;
            target.gameObject.SetActive(tex != null);
            if (tex == null) return;
            _template ??= Resources.Load<Material>("Art/ArtQuad");
            if (target.sharedMaterial == null || target.sharedMaterial == _template || target.sharedMaterial.shader != _template.shader)
                target.sharedMaterial = new Material(_template);   // one instance per renderer, never the shared asset
            target.sharedMaterial.mainTexture = tex;
        }
    }
}
