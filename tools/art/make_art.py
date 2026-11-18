"""STORYVERSE art kit generator (original artwork, vector).

Writes SVGs to backend/app/static/sim/art/:
  portraits/<kingdom>.svg   square painted-style bust of each ruler
  medallions/<kingdom>.svg  the same portrait inside an ornate gold ring (used in UI and in VR)
  crests/<kingdom>.svg      heraldic shield (emblems from docs/02_CHARACTERS_AND_KINGDOMS.md)
  icons/<name>.svg          resources, actions, buildings (gold-leaf style)

Run:  python tools/art/make_art.py      (no dependencies)
"""

from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "backend" / "app" / "static" / "sim" / "art"

GOLD_DEFS = """
<linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#fbe9ad"/><stop offset=".45" stop-color="#d6b066"/>
  <stop offset=".7" stop-color="#a87b36"/><stop offset="1" stop-color="#6e4d1d"/></linearGradient>
<linearGradient id="goldH" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#fff2c2"/><stop offset=".5" stop-color="#c99a4a"/><stop offset="1" stop-color="#6e4d1d"/></linearGradient>
<linearGradient id="steel" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#e6e9ee"/><stop offset=".45" stop-color="#9aa1ab"/><stop offset="1" stop-color="#3d434c"/></linearGradient>
"""


# ============================================================================ rulers
RULERS = {
    "aurelia": dict(
        name="King Aldric Solmane", bg=("#3a5aa0", "#16244a"), skin="#e6b18c", skin_shadow="#b47a58",
        lips="#b5655a", eyes="#5a3b22", hair="#5b3a22", hair_hi="#8a5d38", style="short", beard="short",
        brow=4.5, robe=("#2f4f95", "#14244c"), collar="ermine", chain="sunburst", crown="royal",
        age=1, jaw=1.0),
    "drakoria": dict(
        name="Queen Varka Embermane", bg=("#8a2a30", "#2a0b0e"), skin="#e0a983", skin_shadow="#a8694a",
        lips="#a8443c", eyes="#5f7a3a", hair="#8e2f17", hair_hi="#d0652e", style="braid", beard=None,
        brow=3.2, robe=("#6e1f25", "#2a0b0e"), collar="armor", chain=None, crown="iron",
        age=0, jaw=0.9, stern=True),
    "sylvara": dict(
        name="Queen Isolde Fernhallow", bg=("#2f6a4a", "#0d2418"), skin="#f0c8a8", skin_shadow="#b98a6c",
        lips="#b56a62", eyes="#5d7486", hair="#b8bcc4", hair_hi="#eef0f3", style="long", beard=None,
        brow=2.6, robe=("#2e6447", "#0f2a1d"), collar="leaf", chain=None, crown="oak",
        age=1, jaw=0.88),
    "valoria": dict(
        name="High King Cassian Valor", bg=("#4f4392", "#18123a"), skin="#ddb08f", skin_shadow="#a6755a",
        lips="#a8665c", eyes="#4d6478", hair="#ece8df", hair_hi="#ffffff", style="receding", beard="long",
        brow=4.0, robe=("#4b3a82", "#1a1238"), collar="ermine", chain="anchor", crown="high",
        age=2, jaw=1.0),
}


# The Royal Councils (docs/02_CHARACTERS_AND_KINGDOMS.md). Same painter, different hats.
COUNCILLORS = {
    "caius": dict(name="Master Caius Vell", bg=("#3a5aa0", "#16244a"), skin="#e8bf9c", skin_shadow="#b0846a", lips="#a8665c",
                  eyes="#4a3a2a", hair="#9a9590", hair_hi="#d8d4cc", style="receding", beard=None, brow=3.4,
                  robe=("#3b2f22", "#17110b"), collar="plain", chain="anchor", crown="cap", age=2, jaw=0.95),
    "maren": dict(name="Queen Maren Solmane", bg=("#3a5aa0", "#16244a"), skin="#f1c9a9", skin_shadow="#bb8e70", lips="#c06d68",
                  eyes="#3f6a8a", hair="#c99a3e", hair_hi="#f4d685", style="long", beard=None, brow=2.6,
                  robe=("#2f4f95", "#14244c"), collar="ermine", chain=None, crown="circlet_gold", age=0, jaw=0.88),
    "elowen": dict(name="Princess Elowen", bg=("#3a5aa0", "#16244a"), skin="#f2cbac", skin_shadow="#c0927a", lips="#c8746e",
                   eyes="#5a7a3a", hair="#8a5a30", hair_hi="#c48a50", style="long", beard=None, brow=2.4,
                   robe=("#c6a15b", "#6e4d1d"), collar="plain", chain=None, crown="circlet_gold", age=0, jaw=0.86),
    "hrothgar": dict(name="Marshal Hrothgar Ashborn", bg=("#8a2a30", "#2a0b0e"), skin="#d39c7a", skin_shadow="#985f44", lips="#9a5a50",
                     eyes="#4a4a40", hair="#7a7570", hair_hi="#bdb8b0", style="short", beard="short", brow=5,
                     robe=("#4a1a1e", "#1a0608"), collar="armor", chain=None, crown=None, age=2, jaw=1.05, stern=True, eyepatch=True),
    "silka": dict(name="Silka the Smelter", bg=("#8a2a30", "#2a0b0e"), skin="#c9906c", skin_shadow="#8e583e", lips="#a04e44",
                  eyes="#3a2a1a", hair="#2a1a14", hair_hi="#5a3a2a", style="braid", beard=None, brow=3.2,
                  robe=("#5a3a22", "#22150b"), collar="plain", chain=None, crown="hood", age=1, jaw=0.92),
    "torvald": dict(name="Prince Torvald", bg=("#8a2a30", "#2a0b0e"), skin="#e2ab86", skin_shadow="#a86e4e", lips="#a8504a",
                    eyes="#5f7a3a", hair="#9a3418", hair_hi="#d8663a", style="short", beard="short", brow=4,
                    robe=("#6e1f25", "#2a0b0e"), collar="armor", chain=None, crown="circlet_iron", age=0, jaw=1.0, stern=True),
    "wren": dict(name="Lord Wren Fernhallow", bg=("#2f6a4a", "#0d2418"), skin="#e6bd9e", skin_shadow="#a9806a", lips="#a0605a",
                 eyes="#5d7486", hair="#3a3028", hair_hi="#6a5a4a", style="short", beard="short", brow=3.6,
                 robe=("#1d3326", "#08120c"), collar="plain", chain=None, crown="hood", age=1, jaw=0.98),
    "mossa": dict(name="Elder Mossa", bg=("#2f6a4a", "#0d2418"), skin="#d9b392", skin_shadow="#9e7a60", lips="#a46a60",
                  eyes="#4a5a3a", hair="#e8e4dc", hair_hi="#ffffff", style="long", beard=None, brow=2.4,
                  robe=("#3f6a3a", "#142412"), collar="leaf", chain=None, crown="hood", age=2, jaw=0.9),
    "lirael": dict(name="Princess Lirael", bg=("#2f6a4a", "#0d2418"), skin="#f4d0b2", skin_shadow="#c49a80", lips="#c8746e",
                   eyes="#5d7486", hair="#d8cfb0", hair_hi="#fffbe8", style="braid", beard=None, brow=2.2,
                   robe=("#2e6447", "#0f2a1d"), collar="leaf", chain=None, crown="oak", age=0, jaw=0.85),
    "ibbe": dict(name="Harbormistress Ibbe", bg=("#4f4392", "#18123a"), skin="#a8724e", skin_shadow="#6e4630", lips="#7a3e34",
                 eyes="#2a1a12", hair="#1a1210", hair_hi="#4a3a30", style="long", beard=None, brow=3,
                 robe=("#4b3a82", "#1a1238"), collar="plain", chain="anchor", crown="circlet_gold", age=1, jaw=0.9),
    "oren": dict(name="Admiral Oren Tidewell", bg=("#4f4392", "#18123a"), skin="#c98f68", skin_shadow="#8e5a3e", lips="#985a4e",
                 eyes="#4d6478", hair="#8a8580", hair_hi="#cfcac2", style="short", beard="short", brow=4.2,
                 robe=("#1f2a4a", "#0a0f1e"), collar="plain", chain="anchor", crown="tricorn", age=2, jaw=1.02),
    "seraphine": dict(name="Dame Seraphine Valor", bg=("#4f4392", "#18123a"), skin="#ecc3a2", skin_shadow="#b48a70", lips="#b8645c",
                      eyes="#3f5a7a", hair="#d8b060", hair_hi="#fbe6a6", style="braid", beard=None, brow=3,
                      robe=("#4b3a82", "#1a1238"), collar="armor", chain=None, crown="circlet_iron", age=0, jaw=0.9, stern=True),
}
PEOPLE = {**RULERS, **COUNCILLORS}


def _face_path(jaw: float) -> str:
    """Forehead to chin; `jaw` < 1 narrows the lower face."""
    lx = lambda x: 200 + (x - 200) * jaw
    return (f"M 142 175 C 140 128 166 104 200 104 C 234 104 260 128 258 175 "
            f"C {lx(257):.0f} 210 {lx(246):.0f} 238 {lx(226):.0f} 254 C {lx(216):.0f} 262 {lx(208):.0f} 266 200 266 "
            f"C {lx(192):.0f} 266 {lx(184):.0f} 262 {lx(174):.0f} 254 C {lx(154):.0f} 238 {lx(143):.0f} 210 142 175 Z")


def _eye(cx: float, iris: str, stern: bool) -> str:
    lid = f"M {cx-15} 176 Q {cx} {167 if stern else 164.5} {cx+15} 176" if cx < 200 else \
          f"M {cx-15} 176 Q {cx} {167 if stern else 164.5} {cx+15} 176"
    return f"""
  <path d="M {cx-14} 176 Q {cx} 166 {cx+14} 176 Q {cx} 183 {cx-14} 176 Z" fill="#f4ede4"/>
  <circle cx="{cx}" cy="175.6" r="6.6" fill="{iris}"/>
  <circle cx="{cx}" cy="175.6" r="6.6" fill="url(#irisShade)"/>
  <circle cx="{cx}" cy="175.6" r="3.1" fill="#140d0a"/>
  <circle cx="{cx-2.2}" cy="173.4" r="1.6" fill="#fff" opacity=".9"/>
  <path d="{lid}" fill="none" stroke="#2a1a12" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M {cx-12} 180 Q {cx} 184 {cx+12} 180" fill="none" stroke="#7a4a36" stroke-width=".9" opacity=".5"/>"""


def _eyepatch() -> str:
    return ('<path d="M 140 150 L 260 128" stroke="#1a1410" stroke-width="3"/>'
            '<path d="M 162 168 Q 178 160 194 170 Q 192 188 178 190 Q 164 188 162 168 Z" fill="#1a1410"/>'
            '<path d="M 170 150 L 186 200" stroke="#8a4a3a" stroke-width="2" opacity=".6"/>')


def _hood_back(r: dict) -> str:
    if r["crown"] != "hood":
        return ""
    return ('<path d="M 118 190 C 104 100 150 62 200 62 C 250 62 296 100 282 190 C 292 250 314 300 340 400 '
            'L 60 400 C 86 300 108 250 118 190 Z" fill="url(#robe)"/>'
            '<path d="M 118 190 C 104 100 150 62 200 62 C 250 62 296 100 282 190" fill="none" stroke="#000" stroke-width="3" opacity=".25"/>')


def _hair_back(r: dict) -> str:
    s = r["style"]
    if s in ("long", "braid"):
        return (f'<path d="M 128 172 C 116 96 160 74 200 74 C 240 74 284 96 272 172 C 280 240 292 300 306 372 '
                f'L 94 372 C 108 300 120 240 128 172 Z" fill="url(#hair)"/>')
    if s == "receding":
        return '<path d="M 136 190 C 128 150 140 120 160 112 L 240 112 C 260 120 272 150 264 190 C 262 210 254 222 246 226 L 154 226 C 146 222 138 210 136 190 Z" fill="url(#hair)"/>'
    return ""


def _hair_front(r: dict) -> str:
    s = r["style"]
    if s == "short":
        return ('<path d="M 139 176 C 128 116 160 86 200 86 C 240 86 272 116 261 176 C 257 150 250 132 238 122 '
                'C 222 130 178 130 162 122 C 150 132 143 150 139 176 Z" fill="url(#hair)"/>'
                '<path d="M 160 112 C 180 104 220 104 240 112" fill="none" stroke="url(#hairHi)" stroke-width="3" opacity=".55"/>')
    if s == "braid":
        braid = "".join(f'<ellipse cx="{262 + i*2}" cy="{236 + i*20}" rx="13" ry="12" fill="url(#hair)" stroke="#5a1c0c" stroke-width="1.2"/>'
                        for i in range(6))
        return (braid + '<path d="M 140 172 C 136 116 168 92 206 94 C 240 96 262 120 260 160 C 246 132 222 120 192 124 '
                'C 170 128 152 144 140 172 Z" fill="url(#hair)"/>'
                '<path d="M 170 104 C 196 98 230 104 248 124" fill="none" stroke="url(#hairHi)" stroke-width="3" opacity=".6"/>')
    if s == "long":
        return ('<path d="M 140 178 C 134 116 164 92 200 92 C 236 92 266 116 260 178 C 254 146 240 120 204 114 '
                'C 200 128 196 128 196 114 C 160 120 146 146 140 178 Z" fill="url(#hair)"/>'
                '<path d="M 200 96 C 176 104 156 130 150 170 M 200 96 C 224 104 244 130 250 170" fill="none" '
                'stroke="url(#hairHi)" stroke-width="2.4" opacity=".7"/>')
    if s == "receding":
        return '<path d="M 146 150 C 150 118 176 104 200 104 C 224 104 250 118 254 150 C 246 132 232 122 200 120 C 168 122 154 132 146 150 Z" fill="url(#hair)" opacity=".85"/>'
    return ""


def _beard(r: dict) -> str:
    b = r["beard"]
    if b == "short":
        return ('<path d="M 148 202 C 150 244 172 274 200 278 C 228 274 250 244 252 202 C 246 226 236 242 226 248 '
                'Q 200 260 174 248 C 164 242 154 226 148 202 Z" fill="url(#hair)"/>'
                '<path d="M 176 224 Q 200 213 224 224 Q 212 229 200 226 Q 188 229 176 224 Z" fill="url(#hair)"/>')
    if b == "long":
        return ('<path d="M 146 198 C 144 252 166 306 200 338 C 234 306 256 252 254 198 C 248 232 234 250 222 254 '
                'Q 200 262 178 254 C 166 250 152 232 146 198 Z" fill="url(#hair)"/>'
                '<path d="M 172 226 Q 200 210 228 226 Q 214 233 200 229 Q 186 233 172 226 Z" fill="url(#hair)"/>'
                '<path d="M 186 262 C 190 292 196 312 200 330 M 214 262 C 210 292 204 312 200 330 M 170 250 C 176 280 186 300 194 318" '
                'fill="none" stroke="url(#hairHi)" stroke-width="1.6" opacity=".55"/>')
    return ""


def _age_lines(r: dict) -> str:
    if not r["age"]:
        return ""
    o = .22 * r["age"]
    lines = (f'<path d="M 160 194 Q 168 199 172 196 M 240 194 Q 232 199 228 196" fill="none" stroke="#7a4a36" stroke-width="1" opacity="{o+.1}"/>'
             f'<path d="M 184 208 Q 178 222 182 236 M 216 208 Q 222 222 218 236" fill="none" stroke="#7a4a36" stroke-width="1.2" opacity="{o}"/>')
    if r["age"] > 1:
        lines += '<path d="M 168 132 Q 200 126 232 132 M 172 142 Q 200 137 228 142" fill="none" stroke="#7a4a36" stroke-width="1" opacity=".35"/>'
    return lines


def _clothing(r: dict) -> str:
    out = ['<path d="M 34 400 C 48 328 108 298 170 290 Q 200 300 230 290 C 292 298 352 328 366 400 Z" fill="url(#robe)"/>',
           '<path d="M 170 290 Q 200 300 230 290 L 214 400 L 186 400 Z" fill="#000" opacity=".18"/>']
    c = r["collar"]
    if c == "plain":
        out.append('<path d="M 150 296 Q 200 322 250 296 L 256 312 Q 200 342 144 312 Z" fill="#000" opacity=".22"/>')
    elif c == "ermine":
        spots = "".join(f'<path d="M {x} {y} l -3 9 l 3 -2 l 3 2 Z" fill="#1a1410"/>'
                        for x, y in [(96, 340), (130, 318), (164, 306), (236, 306), (270, 318), (304, 340), (112, 372), (288, 372)])
        out.append('<path d="M 46 400 C 60 340 112 308 172 298 Q 200 312 228 298 C 288 308 340 340 354 400 L 316 400 '
                   'C 300 356 262 330 226 322 Q 200 334 174 322 C 138 330 100 356 84 400 Z" fill="#f2efe8"/>' + spots)
    elif c == "armor":
        out.append('<path d="M 40 400 C 44 340 82 304 138 296 C 150 318 150 350 136 400 Z" fill="url(#steel)" stroke="#2a2f36" stroke-width="2"/>'
                   '<path d="M 360 400 C 356 340 318 304 262 296 C 250 318 250 350 264 400 Z" fill="url(#steel)" stroke="#2a2f36" stroke-width="2"/>'
                   '<path d="M 56 360 Q 96 330 140 326 M 344 360 Q 304 330 260 326" fill="none" stroke="#2a2f36" stroke-width="2"/>'
                   + "".join(f'<circle cx="{x}" cy="{y}" r="3" fill="#cfd4da" stroke="#2a2f36"/>' for x, y in [(80, 346), (112, 334), (320, 346), (288, 334)])
                   + '<path d="M 150 300 Q 200 322 250 300 L 252 320 Q 200 344 148 320 Z" fill="#2b1a14"/>')
    elif c == "leaf":
        out.append('<path d="M 150 296 Q 200 330 250 296 L 262 318 Q 200 356 138 318 Z" fill="#1d4532"/>'
                   '<g transform="translate(200 330)"><ellipse rx="16" ry="9" fill="url(#steel)" transform="rotate(-30)"/>'
                   '<ellipse rx="16" ry="9" fill="url(#steel)" transform="rotate(30)"/><circle r="5" fill="#9fd3b0"/></g>')
    ch = r["chain"]
    if ch:
        links = "".join(f'<circle cx="{x}" cy="{y}" r="5.5" fill="url(#gold)" stroke="#6e4d1d" stroke-width="1"/>'
                        for x, y in [(142, 318), (154, 334), (168, 348), (184, 358), (216, 358), (232, 348), (246, 334), (258, 318)])
        pend = ('<circle cx="200" cy="372" r="14" fill="url(#gold)" stroke="#6e4d1d" stroke-width="1.5"/>'
                + ("".join(f'<path d="M 200 372 L {200 + 20*__import__("math").cos(a*0.785):.1f} {372 + 20*__import__("math").sin(a*0.785):.1f}" stroke="url(#gold)" stroke-width="3"/>' for a in range(8))
                   if ch == "sunburst" else
                   '<path d="M 200 362 V 382 M 192 368 H 208 M 190 378 Q 200 388 210 378" fill="none" stroke="#3a2a10" stroke-width="2.2"/>'))
        out.append(links + pend)
    return "".join(out)


def _crown(r: dict) -> str:
    c = r["crown"]
    if c is None:
        return ""
    if c == "hood":       # the front rim of a hood framing the face
        return ('<path d="M 132 200 C 124 120 160 92 200 92 C 240 92 276 120 268 200 C 262 150 246 110 200 108 '
                'C 154 110 138 150 132 200 Z" fill="url(#robe)"/>'
                '<path d="M 136 196 C 132 128 164 102 200 102 C 236 102 268 128 264 196" fill="none" stroke="#000" stroke-width="2" opacity=".35"/>')
    if c == "cap":        # scholar's velvet cap with a gold tassel
        return ('<path d="M 146 122 C 146 84 176 70 200 70 C 224 70 254 84 254 122 Q 200 110 146 122 Z" fill="#2a1f3a"/>'
                '<path d="M 140 124 Q 200 108 260 124 L 258 134 Q 200 120 142 134 Z" fill="#3e2f52"/>'
                '<path d="M 230 80 Q 262 96 262 132" fill="none" stroke="url(#gold)" stroke-width="3"/><circle cx="262" cy="136" r="5" fill="url(#gold)"/>')
    if c == "tricorn":    # admiral's hat
        return ('<path d="M 110 128 C 140 70 260 70 290 128 C 260 110 230 104 200 104 C 170 104 140 110 110 128 Z" fill="#141a2e"/>'
                '<path d="M 110 128 C 140 112 170 106 200 106 C 230 106 260 112 290 128" fill="none" stroke="url(#gold)" stroke-width="4"/>'
                '<circle cx="200" cy="92" r="9" fill="url(#gold)" stroke="#6e4d1d"/>')
    if c.startswith("circlet"):
        fill = "url(#steel)" if c == "circlet_iron" else "url(#gold)"
        gem = "#b3202a" if c == "circlet_iron" else "#3b6fd6"
        return (f'<path d="M 146 128 Q 200 112 254 128 L 254 136 Q 200 120 146 136 Z" fill="{fill}" stroke="#3a2a10" stroke-width="1"/>'
                f'<path d="M 200 112 l 6 7 l -6 9 l -6 -9 Z" fill="{gem}" stroke="#2a1a0a"/>')
    if c == "royal":
        points = "".join(f'<path d="M {x-11} 106 L {x} 66 L {x+11} 106 Z" fill="url(#gold)" stroke="#6e4d1d" stroke-width="1.5"/>'
                         f'<circle cx="{x}" cy="64" r="5" fill="#f4efe6" stroke="#6e4d1d"/>' for x in (154, 177, 200, 223, 246))
        gems = "".join(f'<ellipse cx="{x}" cy="112" rx="5" ry="6" fill="{g}" stroke="#4a2a0a"/>'
                       for x, g in [(160, "#2f6fd0"), (200, "#c0262f"), (240, "#2f6fd0")])
        return points + '<path d="M 144 104 Q 200 92 256 104 L 258 122 Q 200 110 142 122 Z" fill="url(#gold)" stroke="#6e4d1d" stroke-width="1.5"/>' + gems
    if c == "iron":
        spikes = "".join(f'<path d="M {x-6} 112 L {x} {y} L {x+6} 112 Z" fill="url(#steel)" stroke="#2a2f36"/>'
                         for x, y in [(160, 92), (180, 84), (200, 74), (220, 84), (240, 92)])
        return spikes + ('<path d="M 146 110 Q 200 100 254 110 L 255 122 Q 200 112 145 122 Z" fill="url(#steel)" stroke="#2a2f36" stroke-width="1.5"/>'
                         '<path d="M 200 104 l 6 8 l -6 8 l -6 -8 Z" fill="#b3202a" stroke="#3a0a0a"/>')
    if c == "oak":
        leaves = "".join(f'<ellipse cx="{x}" cy="{y}" rx="12" ry="6" fill="url(#leaf)" stroke="#173a26" transform="rotate({rot} {x} {y})"/>'
                         for x, y, rot in [(152, 120, -60), (166, 106, -40), (184, 98, -15), (200, 95, 0), (216, 98, 15), (234, 106, 40), (248, 120, 60)])
        acorns = "".join(f'<ellipse cx="{x}" cy="{y}" rx="3.5" ry="4.5" fill="#a07a3a"/>' for x, y in [(175, 104), (225, 104)])
        return '<path d="M 148 122 Q 200 102 252 122" fill="none" stroke="url(#steel)" stroke-width="4"/>' + leaves + acorns
    if c == "high":
        return ('<path d="M 156 112 C 156 70 180 50 200 50 C 220 50 244 70 244 112 Z" fill="#3a2a6a"/>'
                '<path d="M 156 110 C 158 74 180 54 200 52 M 244 110 C 242 74 220 54 200 52 M 200 52 V 110" fill="none" stroke="url(#gold)" stroke-width="5"/>'
                '<path d="M 200 30 l 4 10 l 10 0 l -8 7 l 3 10 l -9 -6 l -9 6 l 3 -10 l -8 -7 l 10 0 Z" fill="url(#gold)" stroke="#6e4d1d"/>'
                '<path d="M 140 106 Q 200 92 260 106 L 262 126 Q 200 114 138 126 Z" fill="url(#gold)" stroke="#6e4d1d" stroke-width="1.5"/>'
                + "".join(f'<circle cx="{x}" cy="116" r="4.5" fill="{g}" stroke="#2a1a4a"/>'
                          for x, g in [(158, "#3b6fd6"), (180, "#f4efe6"), (200, "#9b2fd0"), (220, "#f4efe6"), (242, "#3b6fd6")]))
    return ""


def portrait(key: str) -> str:
    r = PEOPLE[key]
    stern = r.get("stern", False)
    brow_l = "M 158 160 Q 176 154 193 163" if stern else "M 160 162 Q 176 153 192 159"
    brow_r = "M 242 160 Q 224 154 207 163" if stern else "M 240 162 Q 224 153 208 159"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">
<title>{r['name']}</title>
<defs>{GOLD_DEFS}
  <radialGradient id="bg" cx=".35" cy=".3" r=".9"><stop offset="0" stop-color="{r['bg'][0]}"/><stop offset="1" stop-color="{r['bg'][1]}"/></radialGradient>
  <radialGradient id="skin" cx=".38" cy=".36" r=".75"><stop offset="0" stop-color="{r['skin']}"/><stop offset=".75" stop-color="{r['skin']}"/><stop offset="1" stop-color="{r['skin_shadow']}"/></radialGradient>
  <linearGradient id="faceShade" x1="0" y1="0" x2="1" y2="0"><stop offset=".45" stop-color="#3a1d10" stop-opacity="0"/><stop offset="1" stop-color="#3a1d10" stop-opacity=".38"/></linearGradient>
  <linearGradient id="neckShade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2a140a" stop-opacity=".55"/><stop offset=".5" stop-color="#2a140a" stop-opacity="0"/></linearGradient>
  <linearGradient id="robe" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{r['robe'][0]}"/><stop offset="1" stop-color="{r['robe'][1]}"/></linearGradient>
  <linearGradient id="hair" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{r['hair_hi']}"/><stop offset=".35" stop-color="{r['hair']}"/><stop offset="1" stop-color="#1a0f08"/></linearGradient>
  <linearGradient id="hairHi" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{r['hair_hi']}"/><stop offset="1" stop-color="{r['hair_hi']}" stop-opacity="0"/></linearGradient>
  <linearGradient id="leaf" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#bfe3c4"/><stop offset="1" stop-color="#3f7d55"/></linearGradient>
  <radialGradient id="irisShade" cx=".5" cy=".3" r=".7"><stop offset=".5" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".45"/></radialGradient>
  <radialGradient id="candle" cx=".2" cy=".3" r=".8"><stop offset="0" stop-color="#ffcf7a" stop-opacity=".22"/><stop offset="1" stop-color="#ffcf7a" stop-opacity="0"/></radialGradient>
  <radialGradient id="vignette" cx=".5" cy=".45" r=".72"><stop offset=".6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".6"/></radialGradient>
</defs>
<rect width="400" height="400" fill="url(#bg)"/>
<path d="M 0 400 L 0 250 Q 60 200 120 230 L 120 400 Z M 400 400 L 400 250 Q 340 200 280 230 L 280 400 Z" fill="#000" opacity=".15"/>
{_hood_back(r)}
{_hair_back(r)}
{_clothing(r)}
<path d="M 176 240 L 176 302 Q 200 312 224 302 L 224 240 Z" fill="url(#skin)"/>
<path d="M 176 240 L 176 302 Q 200 312 224 302 L 224 240 Z" fill="url(#neckShade)"/>
<ellipse cx="141" cy="182" rx="9" ry="17" fill="{r['skin_shadow']}"/><ellipse cx="259" cy="182" rx="9" ry="17" fill="{r['skin_shadow']}"/>
<path d="{_face_path(r['jaw'])}" fill="url(#skin)"/>
<path d="{_face_path(r['jaw'])}" fill="url(#faceShade)"/>
<ellipse cx="170" cy="206" rx="14" ry="8" fill="#e07a6a" opacity=".12"/><ellipse cx="230" cy="206" rx="14" ry="8" fill="#e07a6a" opacity=".1"/>
{_eye(178, r['eyes'], stern) if not r.get('eyepatch') else _eyepatch()}
{_eye(222, r['eyes'], stern)}
<path d="{brow_l}" fill="none" stroke="{r['hair']}" stroke-width="{r['brow']}" stroke-linecap="round"/>
<path d="{brow_r}" fill="none" stroke="{r['hair']}" stroke-width="{r['brow']}" stroke-linecap="round"/>
<path d="M 197 176 C 196 192 191 204 190 210 Q 200 217 210 210" fill="none" stroke="#5a2e1e" stroke-width="1.8" opacity=".35"/>
<path d="M 203 178 C 204 190 205 198 206 204" fill="none" stroke="#fff" stroke-width="2" opacity=".18"/>
<ellipse cx="194" cy="210" rx="3.2" ry="1.7" fill="#3a1a10" opacity=".4"/><ellipse cx="206" cy="210" rx="3.2" ry="1.7" fill="#3a1a10" opacity=".4"/>
{_age_lines(r)}
<path d="M 184 231 Q 193 226 200 228.5 Q 207 226 216 231 Q 200 233.5 184 231 Z" fill="{r['lips']}"/>
<path d="M 186 232 Q 200 242 214 232 Q 200 236 186 232 Z" fill="{r['lips']}" opacity=".8"/>
<path d="M 185 231.5 Q 200 234 215 231.5" fill="none" stroke="#4a1a14" stroke-width="1.3"/>
{_beard(r)}
{_hair_front(r)}
{_crown(r)}
<rect width="400" height="400" fill="url(#candle)"/>
<rect width="400" height="400" fill="url(#vignette)"/>
</svg>"""


def medallion(key: str) -> str:
    """Portrait inside an ornate gold ring with rivets, ready to drop into any UI."""
    inner = portrait(key).split("\n", 1)[1].rsplit("</svg>", 1)[0]
    studs = "".join(
        f'<circle cx="{200 + 186*__import__("math").cos(i*0.3927):.1f}" cy="{200 + 186*__import__("math").sin(i*0.3927):.1f}" '
        f'r="5" fill="url(#gold)" stroke="#5a3d14"/>' for i in range(16))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">
<defs><clipPath id="disc"><circle cx="200" cy="200" r="168"/></clipPath></defs>
<g clip-path="url(#disc)"><svg viewBox="0 0 400 400" width="400" height="400">{inner}</svg></g>
<circle cx="200" cy="200" r="182" fill="none" stroke="#3a2608" stroke-width="30"/>
<circle cx="200" cy="200" r="182" fill="none" stroke="url(#gold)" stroke-width="22"/>
<circle cx="200" cy="200" r="170" fill="none" stroke="#fff2c2" stroke-width="2" opacity=".6"/>
<circle cx="200" cy="200" r="194" fill="none" stroke="#5a3d14" stroke-width="3"/>
{studs}
</svg>"""


# ============================================================================ crests
SHIELD = "M 22 18 H 178 V 108 C 178 168 140 204 100 226 C 60 204 22 168 22 108 Z"
CRESTS = {
    "aurelia": ("#2c4a8a", "sunburst"), "drakoria": ("#8a2a30", "wyvern"),
    "sylvara": ("#2f6a45", "stag"), "valoria": ("#4a3a7a", "star_anchor"),
}


def _charge(kind: str) -> str:
    import math
    if kind == "sunburst":
        rays = "".join(
            f'<path d="M {100 + 30*math.cos(a - .12):.1f} {108 + 30*math.sin(a - .12):.1f} '
            f'L {100 + (62 if i % 2 == 0 else 48)*math.cos(a):.1f} {108 + (62 if i % 2 == 0 else 48)*math.sin(a):.1f} '
            f'L {100 + 30*math.cos(a + .12):.1f} {108 + 30*math.sin(a + .12):.1f} Z" fill="url(#gold)"/>'
            for i, a in enumerate([k * math.pi / 8 for k in range(16)]))
        return rays + '<circle cx="100" cy="108" r="28" fill="url(#gold)" stroke="#6e4d1d" stroke-width="2"/>' \
                      '<path d="M 88 104 Q 92 100 96 104 M 104 104 Q 108 100 112 104 M 90 118 Q 100 126 110 118" fill="none" stroke="#6e4d1d" stroke-width="2"/>'
    if kind == "wyvern":
        return ('<g fill="#141014" stroke="#000" stroke-width="1">'
                '<path d="M 70 150 C 60 128 72 104 96 100 C 106 98 112 90 112 80 C 118 70 132 66 140 72 L 152 70 L 142 80 '
                'C 138 84 130 84 126 88 C 124 104 120 118 110 128 C 128 132 140 146 136 164 C 132 178 116 184 104 176 '
                'C 116 176 124 168 120 156 C 116 144 100 142 90 152 C 84 158 80 168 84 180 C 70 176 66 160 70 150 Z"/>'
                '<path d="M 96 104 C 80 82 52 70 32 76 C 46 82 50 92 44 100 C 56 98 62 106 58 114 C 70 110 78 116 78 124 Z"/>'
                '<path d="M 108 102 C 124 78 150 60 170 62 C 158 72 158 82 166 88 C 152 90 150 100 156 106 C 142 104 134 112 132 120 Z"/>'
                '</g><circle cx="134" cy="76" r="2.4" fill="#e8c35a"/>')
    if kind == "stag":
        antler = ('M 94 94 C 82 72 62 64 44 64 M 72 70 C 64 56 62 46 66 34 M 56 66 C 46 56 42 48 42 40 M 84 80 C 80 68 82 60 88 52 '
                  'M 106 94 C 118 72 138 64 156 64 M 128 70 C 136 56 138 46 134 34 M 144 66 C 154 56 158 48 158 40 M 116 80 C 120 68 118 60 112 52')
        return (f'<path d="{antler}" fill="none" stroke="url(#steel)" stroke-width="8" stroke-linecap="round"/>'
                '<path d="M 100 88 C 116 88 124 100 122 118 C 120 140 110 160 100 172 C 90 160 80 140 78 118 C 76 100 84 88 100 88 Z" fill="url(#steel)" stroke="#2a3a30" stroke-width="2"/>'
                '<path d="M 78 104 L 62 96 L 74 114 Z M 122 104 L 138 96 L 126 114 Z" fill="url(#steel)" stroke="#2a3a30" stroke-width="1.5"/>'
                '<circle cx="92" cy="118" r="3" fill="#1a2a20"/><circle cx="108" cy="118" r="3" fill="#1a2a20"/>'
                '<ellipse cx="100" cy="164" rx="7" ry="5" fill="#1a2a20"/>'
                '<path d="M 76 40 Q 100 26 124 40" fill="none" stroke="url(#gold)" stroke-width="5"/>'
                + "".join(f'<ellipse cx="{x}" cy="{y}" rx="8" ry="4" fill="#7fb98f" transform="rotate({rt} {x} {y})"/>'
                          for x, y, rt in [(82, 36, -40), (100, 30, 0), (118, 36, 40)]))
    if kind == "star_anchor":
        return ('<g fill="none" stroke="#f4f1ea" stroke-width="9" stroke-linecap="round">'
                '<circle cx="100" cy="84" r="11"/><path d="M 100 95 V 190 M 72 110 H 128 M 56 156 C 60 186 84 196 100 196 C 116 196 140 186 144 156"/>'
                '</g><path d="M 48 150 L 56 140 L 66 154 Z M 152 150 L 144 140 L 134 154 Z" fill="#f4f1ea"/>'
                '<path d="M 100 34 l 6 14 l 15 1 l -12 9 l 4 15 l -13 -8 l -13 8 l 4 -15 l -12 -9 l 15 -1 Z" fill="url(#gold)" stroke="#6e4d1d"/>')
    return ""


def crest(key: str) -> str:
    field, charge = CRESTS[key]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240">
<defs>{GOLD_DEFS}
  <linearGradient id="sheen" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".22"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".3"/></linearGradient>
  <clipPath id="sh"><path d="{SHIELD}"/></clipPath>
</defs>
<path d="{SHIELD}" fill="{field}"/>
<g clip-path="url(#sh)">{_charge(charge)}<rect width="200" height="240" fill="url(#sheen)"/></g>
<path d="{SHIELD}" fill="none" stroke="#2a1a06" stroke-width="12"/>
<path d="{SHIELD}" fill="none" stroke="url(#gold)" stroke-width="8"/>
</svg>"""


# ============================================================================ icons (64 x 64, gold leaf)
ICONS = {
    # resources & stats
    "gold": '<ellipse cx="32" cy="46" rx="20" ry="7"/><rect x="12" y="34" width="40" height="12"/><ellipse cx="32" cy="34" rx="20" ry="7"/>'
            '<ellipse cx="32" cy="26" rx="16" ry="6"/><rect x="16" y="18" width="32" height="8"/><ellipse cx="32" cy="18" rx="16" ry="6" class="hi"/>',
    "food": '<path d="M32 58 V20"/><g class="fill">' + "".join(
        f'<ellipse cx="{32 + dx}" cy="{y}" rx="5" ry="9" transform="rotate({rot} {32 + dx} {y})"/>'
        for dx, y, rot in [(-7, 30, -25), (7, 30, 25), (-7, 42, -25), (7, 42, 25), (0, 16, 0)]) + '</g>',
    "wood": '<rect x="8" y="36" width="44" height="14" rx="7"/><rect x="14" y="20" width="44" height="14" rx="7"/>'
            '<circle cx="52" cy="43" r="6" class="dark"/><circle cx="58" cy="27" r="6" class="dark"/>',
    "stone": '<path d="M8 52 L14 30 L32 26 L38 44 L28 56 Z"/><path d="M34 40 L40 18 L56 22 L58 46 L44 54 Z" class="hi"/>',
    "iron": '<path d="M6 46 L16 28 H48 L58 46 Z"/><path d="M16 28 L22 18 H42 L48 28 Z" class="hi"/>',
    "people": '<circle cx="22" cy="20" r="8"/><path d="M8 54 C8 36 36 36 36 54 Z"/><circle cx="44" cy="22" r="7" class="hi"/><path d="M32 54 C34 40 58 40 58 54 Z" class="hi"/>',
    "soldiers": '<path d="M12 36 C12 14 52 14 52 36 L52 50 L40 50 L40 40 L24 40 L24 50 L12 50 Z"/><path d="M30 14 V40 M34 14 V40" class="dark"/>',
    "prestige": '<path d="M10 46 L14 18 L24 32 L32 12 L40 32 L50 18 L54 46 Z"/><rect x="10" y="46" width="44" height="8"/>'
                '<circle cx="32" cy="12" r="4" class="hi"/><circle cx="14" cy="18" r="3" class="hi"/><circle cx="50" cy="18" r="3" class="hi"/>',
    "turn": '<path d="M16 8 H48 M16 56 H48"/><path d="M20 10 C20 26 30 28 32 32 C34 28 44 26 44 10 Z"/><path d="M20 54 C20 40 30 36 32 32 C34 36 44 40 44 54 Z" class="hi"/>',
    # actions
    "ally": '<circle cx="24" cy="32" r="14" class="ring"/><circle cx="40" cy="32" r="14" class="ring hi"/>',
    "trade": '<path d="M32 8 V54 M16 56 H48 M10 18 H54"/><path d="M4 36 L10 18 L16 36 Z M48 36 L54 18 L60 36 Z"/>'
             '<path d="M2 36 Q10 46 18 36 Z M46 36 Q54 46 62 36 Z" class="hi"/>',
    "loan": '<circle cx="28" cy="34" r="18"/><text x="28" y="41" text-anchor="middle" font-size="20" font-family="Georgia" class="dark">G</text>'
            '<path d="M44 12 A 22 22 0 0 1 56 30 L 60 24 M 56 30 L 49 28" class="line"/>',
    "gift": '<rect x="8" y="26" width="48" height="30" rx="3"/><path d="M8 26 C8 14 56 14 56 26 Z" class="hi"/><rect x="28" y="20" width="8" height="36" class="dark"/>',
    "war": '<path d="M10 54 L46 18 M18 54 L54 18" class="blade"/><path d="M6 50 L14 58 M42 14 L50 22 M50 50 L58 58" class="line"/>'
           '<path d="M54 54 L18 18 M46 54 L10 18" class="blade"/>',
    "peace": '<path d="M8 36 C18 20 34 22 40 30 C46 22 54 22 58 18 C56 30 50 38 40 42 C30 50 16 48 8 36 Z"/><circle cx="48" cy="26" r="2" class="dark"/>'
             '<path d="M20 44 L28 54 M28 46 L38 54" class="line"/>',
    "letter": '<rect x="8" y="16" width="48" height="34" rx="2"/><path d="M8 18 L32 36 L56 18" class="line"/><circle cx="32" cy="40" r="7" class="seal"/>',
    # buildings
    "farm": '<path d="M8 30 L32 12 L56 30 V56 H8 Z"/><rect x="24" y="36" width="16" height="20" class="dark"/><path d="M24 36 L40 56 M40 36 L24 56" class="line"/>',
    "lumber_mill": '<rect x="6" y="40" width="40" height="12" rx="6"/><circle cx="44" cy="24" r="14" class="hi"/>'
                   + "".join(f'<path d="M44 24 L{44 + 15*__import__("math").cos(a*0.785):.0f} {24 + 15*__import__("math").sin(a*0.785):.0f}" class="line"/>' for a in range(8)),
    "mine": '<path d="M6 56 L22 30 L34 44 L44 32 L58 56 Z"/><path d="M14 22 C24 10 42 10 52 22" class="blade"/><path d="M32 14 L22 42" class="line"/>',
    "gold_mine": '<path d="M6 56 L22 30 L34 44 L44 32 L58 56 Z" class="dark"/><path d="M24 50 L32 38 L44 42 L40 54 Z" class="hi"/>'
                 '<path d="M14 22 C24 10 42 10 52 22" class="blade"/><path d="M32 14 L22 42" class="line"/>',
    "market": '<rect x="10" y="30" width="44" height="26"/><path d="M6 30 L12 14 H52 L58 30 Z" class="hi"/>'
              '<path d="M16 14 L14 30 M26 14 L26 30 M38 14 L38 30 M48 14 L50 30" class="line"/>',
    "bank": '<path d="M6 22 L32 8 L58 22 Z" class="hi"/><rect x="8" y="22" width="48" height="5"/><rect x="8" y="50" width="48" height="6"/>'
            + "".join(f'<rect x="{x}" y="28" width="6" height="22"/>' for x in (12, 23, 35, 46)),
    "barracks": '<path d="M32 6 L54 14 V32 C54 46 44 54 32 58 C20 54 10 46 10 32 V14 Z"/><path d="M20 44 L44 20 M44 44 L20 20" class="line"/>',
    "watchtower": '<path d="M18 58 L22 22 H42 L46 58 Z"/><path d="M16 22 V10 H22 V16 H28 V10 H36 V16 H42 V10 H48 V22 Z" class="hi"/><rect x="28" y="30" width="8" height="12" class="dark"/>',
    "academy": '<path d="M4 18 C16 12 26 14 32 20 C38 14 48 12 60 18 V52 C48 46 38 48 32 54 C26 48 16 46 4 52 Z"/><path d="M32 20 V54" class="line"/>'
               '<path d="M10 26 H26 M10 32 H26 M38 26 H54 M38 32 H54" class="line"/>',
    "hospital": '<path d="M8 28 L32 10 L56 28 V56 H8 Z"/><path d="M28 30 H36 V38 H44 V46 H36 V54 H28 V46 H20 V38 H28 Z" class="seal"/>',
    # settlement buildings
    "houses": '<path d="M4 34 L18 22 L32 34 V56 H4 Z"/><path d="M30 30 L46 16 L62 30 V56 H30 Z" class="hi"/>'
              '<rect x="14" y="42" width="8" height="14" class="dark"/><rect x="42" y="40" width="8" height="16" class="dark"/>'
              '<rect x="50" y="18" width="5" height="10" class="dark"/>',
    "tavern": '<path d="M14 18 H42 V54 C42 58 38 60 34 60 H22 C18 60 14 58 14 54 Z"/><path d="M42 26 H50 C56 26 56 44 50 44 H42" class="line"/>'
              '<path d="M12 18 C12 8 44 8 44 18 C40 14 16 14 12 18 Z" class="hi"/><path d="M22 26 V52 M30 26 V52" class="line"/>',
    "mansions": '<rect x="6" y="28" width="52" height="28"/><path d="M2 30 L32 12 L62 30 Z" class="hi"/><rect x="26" y="6" width="12" height="20"/>'
                '<path d="M24 8 L32 0 L40 8 Z" class="hi"/>' + "".join(f'<rect x="{x}" y="36" width="6" height="8" class="dark"/>' for x in (12, 22, 36, 46))
                + '<rect x="28" y="44" width="8" height="12" class="dark"/>',
    "blacksmith": '<path d="M10 34 H54 L48 42 H40 V52 H48 V58 H16 V52 H24 V42 H16 Z"/><path d="M40 8 L52 20 M30 18 L44 4 L50 10 L36 24 Z" class="hi"/>'
                  '<path d="M22 28 C26 22 30 22 34 28" class="line"/>',
    "granary": '<path d="M14 58 V24 C14 12 50 12 50 24 V58 Z"/><path d="M14 24 C14 12 50 12 50 24" class="hi"/><rect x="26" y="40" width="12" height="18" class="dark"/>'
               '<path d="M18 30 H46 M18 36 H46" class="line"/>',
    # diplomacy & court
    "passage": '<path d="M2 56 L18 24 L28 38 L40 16 L62 56 Z"/><path d="M26 58 C30 48 36 44 34 36 C32 30 36 26 40 22" class="line"/>'
               '<path d="M18 24 L22 30 L14 30 Z M40 16 L45 24 L35 24 Z" fill="#f4f1ea" stroke="none"/>',
    "decree": '<rect x="12" y="8" width="40" height="48" rx="3"/><path d="M8 10 C8 4 18 4 18 10 V14 H8 Z M46 54 C46 60 56 60 56 54 V50 H46 Z" class="hi"/>'
              '<path d="M20 20 H44 M20 28 H44 M20 36 H36" class="line"/><circle cx="40" cy="46" r="7" class="seal"/>',
    "council": '<ellipse cx="32" cy="44" rx="26" ry="10"/><circle cx="14" cy="26" r="6" class="hi"/><circle cx="32" cy="20" r="6.5" class="hi"/>'
               '<circle cx="50" cy="26" r="6" class="hi"/><path d="M20 44 L44 44" class="line"/>',
    "candle": '<rect x="24" y="24" width="16" height="32" rx="2"/><path d="M32 6 C40 14 38 22 32 22 C26 22 24 14 32 6 Z" fill="#ffcf5a" stroke="#a0581a"/>'
              '<path d="M32 22 V26" class="line"/><path d="M14 58 H50" class="line"/>',
}

ICON_STYLE = """<style>
  * { fill: url(#gold); stroke: #3a2608; stroke-width: 1.6; stroke-linejoin: round; }
  .hi { fill: url(#goldH); }
  .dark { fill: #3a2608; stroke: none; }
  .line { fill: none; stroke: #3a2608; stroke-width: 2.6; stroke-linecap: round; }
  .blade { fill: none; stroke: url(#steel); stroke-width: 6; stroke-linecap: round; }
  .ring { fill: none; stroke: url(#gold); stroke-width: 7; }
  .seal { fill: #9b2330; }
  path[d^="M32 58 V20"], path[d^="M32 8 V54"], path[d^="M16 8 H48"] { fill: none; stroke: url(#gold); stroke-width: 4; }
</style>"""


def icon(name: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs>{GOLD_DEFS}</defs>{ICON_STYLE}'
            f'{ICONS[name]}</svg>')


# ============================================================================ UI chrome
def corner(rot: int) -> str:
    """Gold filigree corner (top-left orientation, rotated for the other corners)."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs>{GOLD_DEFS}</defs>
<g transform="rotate({rot} 32 32)" fill="none" stroke-linecap="round">
<path d="M 4 60 V 10 Q 4 4 10 4 H 60" stroke="#2a1a06" stroke-width="6"/>
<path d="M 4 60 V 10 Q 4 4 10 4 H 60" stroke="url(#gold)" stroke-width="3.5"/>
<path d="M 12 52 V 16 Q 12 12 16 12 H 52" stroke="url(#gold)" stroke-width="1.4" opacity=".8"/>
<path d="M 10 10 C 22 10 30 18 26 26 C 22 32 14 28 18 22 C 21 18 26 20 24 24" stroke="url(#gold)" stroke-width="2.6"/>
<path d="M 30 8 C 36 14 42 14 48 8 M 8 30 C 14 36 14 42 8 48" stroke="url(#gold)" stroke-width="2"/>
<circle cx="10" cy="10" r="3.6" fill="url(#gold)" stroke="#2a1a06"/></g></svg>"""


def stone_tile() -> str:
    """Seamless dark castle-stone wall (240 x 120)."""
    import random
    rnd = random.Random(7)
    bricks = []
    for row in range(4):
        y, off = row * 30, (row % 2) * 30
        for col in range(-1, 5):
            x = col * 60 + off
            shade = rnd.randint(22, 34)
            bricks.append(f'<rect x="{x + 1.5}" y="{y + 1.5}" width="57" height="27" rx="3" '
                          f'fill="rgb({shade},{shade + 2},{shade + 7})"/>')
            bricks.append(f'<rect x="{x + 3}" y="{y + 3}" width="54" height="6" rx="3" fill="#fff" opacity=".025"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 120" width="240" height="120">'
            f'<rect width="240" height="120" fill="#0e1117"/>{"".join(bricks)}</svg>')


def stained_glass() -> str:
    """Original heraldic rose window (geometric panes and a crown), lit from behind. 200 x 360."""
    import math
    import random
    rnd = random.Random(3)
    cols = ["#2a5aa8", "#a8323d", "#2f7a52", "#d6a03a", "#5b3a8a", "#2a8aa0", "#c8642e"]
    panes = []
    for ring, (r0, r1, n) in enumerate([(14, 34, 8), (34, 58, 12), (58, 82, 16)]):
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            pts = [(100 + r0 * math.cos(a0), 112 + r0 * math.sin(a0)), (100 + r1 * math.cos(a0), 112 + r1 * math.sin(a0)),
                   (100 + r1 * math.cos(a1), 112 + r1 * math.sin(a1)), (100 + r0 * math.cos(a1), 112 + r0 * math.sin(a1))]
            panes.append(f'<path d="M {" L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)} Z" fill="{cols[(i + ring * 2) % len(cols)]}"/>')
    lancets = "".join(f'<rect x="{x}" y="{y}" width="26" height="34" fill="{rnd.choice(cols)}"/>'
                      for x in (22, 52, 87, 122, 152) for y in (214, 252, 290))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 360"><defs>{GOLD_DEFS}
<radialGradient id="glow" cx=".5" cy=".3" r=".8"><stop offset="0" stop-color="#fff6d8" stop-opacity=".28"/><stop offset="1" stop-color="#fff6d8" stop-opacity="0"/></radialGradient>
<clipPath id="arch"><path d="M 10 350 V 110 C 10 50 50 14 100 14 C 150 14 190 50 190 110 V 350 Z"/></clipPath></defs>
<g clip-path="url(#arch)"><rect width="200" height="360" fill="#1a2440"/>{"".join(panes)}
<circle cx="100" cy="112" r="14" fill="#f3d06a"/>
<path d="M 88 118 L 90 104 L 95 111 L 100 100 L 105 111 L 110 104 L 112 118 Z" fill="#7a4a10"/>
{lancets}<rect width="200" height="360" fill="url(#glow)"/>
<g fill="none" stroke="#141010" stroke-width="3">
{"".join(f'<circle cx="100" cy="112" r="{r}"/>' for r in (14, 34, 58, 82))}
{"".join(f'<path d="M {100 + 14*math.cos(a):.1f} {112 + 14*math.sin(a):.1f} L {100 + 82*math.cos(a):.1f} {112 + 82*math.sin(a):.1f}"/>' for a in [2*math.pi*k/16 for k in range(16)])}
<path d="M 10 200 H 190 M 10 248 H 190 M 10 286 H 190 M 10 324 H 190"/>
{"".join(f'<path d="M {x} 200 V 350"/>' for x in (48, 83, 117, 152))}</g></g>
<path d="M 10 350 V 110 C 10 50 50 14 100 14 C 150 14 190 50 190 110 V 350 Z" fill="none" stroke="#3a3530" stroke-width="12"/>
<path d="M 10 350 V 110 C 10 50 50 14 100 14 C 150 14 190 50 190 110 V 350 Z" fill="none" stroke="#6e665c" stroke-width="5"/>
</svg>"""


def divider() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 16"><defs>{GOLD_DEFS}</defs>
<path d="M 4 8 H 100 M 140 8 H 236" stroke="url(#gold)" stroke-width="1.5"/>
<path d="M 120 1 L 127 8 L 120 15 L 113 8 Z" fill="url(#gold)" stroke="#2a1a06"/>
<circle cx="104" cy="8" r="2.5" fill="url(#gold)"/><circle cx="136" cy="8" r="2.5" fill="url(#gold)"/></svg>"""


# ============================================================================ main
def main() -> None:
    (OUT / "ui").mkdir(parents=True, exist_ok=True)
    for name, rot in (("corner_tl", 0), ("corner_tr", 90), ("corner_br", 180), ("corner_bl", 270)):
        (OUT / "ui" / f"{name}.svg").write_text(corner(rot), encoding="utf-8")
    (OUT / "ui" / "stone.svg").write_text(stone_tile(), encoding="utf-8")
    (OUT / "ui" / "divider.svg").write_text(divider(), encoding="utf-8")
    (OUT / "ui" / "stained_glass.svg").write_text(stained_glass(), encoding="utf-8")
    for sub in ("portraits", "medallions", "crests", "icons"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    for key in PEOPLE:
        (OUT / "portraits" / f"{key}.svg").write_text(portrait(key), encoding="utf-8")
        (OUT / "medallions" / f"{key}.svg").write_text(medallion(key), encoding="utf-8")
    for key in RULERS:
        (OUT / "crests" / f"{key}.svg").write_text(crest(key), encoding="utf-8")
    for name in ICONS:
        (OUT / "icons" / f"{name}.svg").write_text(icon(name), encoding="utf-8")
    print(f"wrote {len(PEOPLE) * 2 + len(RULERS) + len(ICONS)} SVGs to {OUT}")


if __name__ == "__main__":
    main()
