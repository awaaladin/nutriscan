"""Illustrations for the website, drawn as SVG so they stay sharp and tiny.

The phone screens mirror the real app (same cards, same wording). They use sample data and the
pages say so. Run via site/build.py, which writes them to download/assets/img/."""
import os

G9, G7, G5 = "#0B2E22", "#0E6B4F", "#1B8A5A"
GOLD, GOLD2, CREAM = "#E1C766", "#B8860B", "#F7F6F2"
AMBER, RED, INK, MUTED = "#C77A00", "#C0392B", "#171C1A", "#5D6A64"
FONT = "system-ui,-apple-system,'Segoe UI',Roboto,sans-serif"


def phone(body: str, title: str, dark: bool = False) -> str:
    screen = "#10211A" if dark else CREAM
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 610" role="img" aria-label="{title}" font-family="{FONT}">
<defs>
  <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{GOLD}"/><stop offset="1" stop-color="{GOLD2}"/></linearGradient>
  <clipPath id="scr"><rect x="10" y="10" width="280" height="590" rx="34"/></clipPath>
</defs>
<rect width="300" height="610" rx="44" fill="#0E1412"/>
<rect x="10" y="10" width="280" height="590" rx="34" fill="{screen}"/>
<g clip-path="url(#scr)">
{body}
</g>
<rect x="124" y="18" width="52" height="14" rx="7" fill="#0E1412"/>
<rect x="110" y="588" width="80" height="4" rx="2" fill="{'#3b4a43' if dark else '#CFD3CC'}"/>
</svg>
'''


def t(x, y, s, size=12, fill=INK, weight=400, anchor="start", extra=""):
    s = s.replace("&", "&amp;")
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}" {extra}>{s}</text>'


def appbar(title):
    return (f'<path d="M30 70 L22 62 L30 54" fill="none" stroke="{INK}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
            + t(46, 68, title, 16, INK, 600))


def result():
    b = [appbar("Product")]
    b += [t(24, 108, "Golden Oat Biscuits", 18, INK, 700), t(24, 126, "Sample Foods", 12, MUTED),
          t(24, 142, "Barcode 6150000000000", 10, MUTED)]
    b += [f'<rect x="24" y="154" width="88" height="26" rx="13" fill="#FBE9C0"/>', t(68, 172, "Moderate", 12, AMBER, 700, "middle"),
          t(124, 173, "5/10", 16, INK, 700), t(168, 172, "Diabetic risk: Medium", 10.5, INK)]
    b += [f'<rect x="20" y="192" width="260" height="80" rx="14" fill="#FFF4DC" stroke="#F0D9A0"/>',
          t(32, 210, "FOR YOU", 9, AMBER, 700, extra='letter-spacing="1"'),
          t(32, 228, "Watch the sugar: 11 g per 100 g is", 11), t(32, 243, "high if you manage diabetes.", 11),
          t(32, 262, "Allergen check: none found", 10, G7, 600)]
    b += [f'<rect x="20" y="282" width="260" height="124" rx="14" fill="#E6F3EC" stroke="#BFE0CE"/>',
          f'<circle cx="40" cy="302" r="8" fill="{G5}"/><path d="M36 302 l3 3 l5 -6" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
          t(54, 307, "Corroborated", 14, G7, 700), t(34, 328, "• 2 independent sources agree", 10.5),
          t(34, 344, "• NAFDAC number captured", 10.5), t(34, 360, "• Source: Open Food Facts", 10.5),
          f'<rect x="32" y="372" width="236" height="24" rx="12" fill="none" stroke="{G7}"/>',
          t(150, 388, "Something wrong? Report a correction", 10, G7, 600, "middle")]
    b += [t(24, 430, "Per 100 g", 12, INK, 700)]
    for i, (label, val, w, col) in enumerate([("Sugar", "11 g", 55, AMBER), ("Saturated fat", "4 g", 35, G5), ("Sodium", "320 mg", 30, G5)]):
        y = 450 + i * 26
        b += [t(24, y + 8, label, 10.5, INK), t(94, y + 8, val, 10.5, MUTED),
              f'<rect x="140" y="{y}" width="130" height="8" rx="4" fill="#E4E7E2"/>',
              f'<rect x="140" y="{y}" width="{130 * w // 100}" height="8" rx="4" fill="{col}"/>']
    b += [f'<rect x="20" y="540" width="124" height="38" rx="19" fill="none" stroke="{G7}" stroke-width="1.5"/>', t(82, 563, "Read aloud", 12, G7, 600, "middle"),
          f'<rect x="152" y="540" width="128" height="38" rx="19" fill="{G7}"/>', t(216, 563, "Ask NutriScan", 12, "#fff", 600, "middle")]
    return phone("\n".join(b), "A product result with health score, personal advice and data trust")


def scan():
    b = ['<rect x="10" y="10" width="280" height="590" fill="#0A130F"/>']
    b += [f'<rect x="10" y="150" width="280" height="300" fill="#16251E"/>']
    # shelf shapes in the background
    for x, h, c in [(24, 120, "#22372D"), (74, 150, "#2A4236"), (200, 110, "#22372D"), (250, 140, "#2A4236")]:
        b.append(f'<rect x="{x}" y="{430 - h}" width="38" height="{h}" rx="5" fill="{c}"/>')
    # frame brackets
    for d in ["M52 190 V168 H74", "M226 168 H248 V190", "M52 410 V432 H74", "M226 432 H248 V410"]:
        b.append(f'<path d="{d}" fill="none" stroke="{GOLD}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>')
    # barcode
    x = 92
    for w in [3, 2, 5, 2, 3, 6, 2, 3, 4, 2, 6, 3, 2, 5, 3, 2, 4, 3, 5]:
        b.append(f'<rect x="{x}" y="260" width="{w}" height="70" fill="#F7F6F2"/>')
        x += w + 2
    b.append(f'<rect x="64" y="298" width="172" height="2.5" rx="1.2" fill="#FF5A4F" opacity=".9"><animate attributeName="y" values="206;392;206" dur="3.4s" repeatCount="indefinite"/></rect>')
    b += [t(150, 112, "Scan a barcode", 17, "#fff", 600, "middle"), t(150, 134, "Hold steady, we'll do the rest", 11, "#9DB1A7", 400, "middle")]
    b += [f'<rect x="60" y="480" width="180" height="40" rx="20" fill="none" stroke="#5B7A6B"/>', t(150, 505, "Type the barcode instead", 11.5, "#CFE0D6", 500, "middle")]
    return phone("\n".join(b), "The barcode scanner", dark=True)


def photo():
    b = [appbar("Help us add this product")]
    b += [t(24, 106, "We couldn't find this one yet.", 13, INK, 700), t(24, 124, "Two quick photos add it for everyone.", 11, MUTED)]
    b += [f'<rect x="20" y="140" width="124" height="150" rx="14" fill="#fff" stroke="#DCE0D8"/>',
          f'<rect x="50" y="160" width="64" height="86" rx="8" fill="#F3E3B6" stroke="{GOLD2}" stroke-width="1.5"/>',
          f'<circle cx="82" cy="196" r="12" fill="url(#gold)"/>', t(82, 270, "1. Front of pack", 10.5, INK, 600, "middle"),
          f'<rect x="156" y="140" width="124" height="150" rx="14" fill="#fff" stroke="#DCE0D8"/>',
          f'<rect x="174" y="158" width="88" height="96" rx="6" fill="#fff" stroke="#9AA59F"/>']
    for i in range(6):
        b.append(f'<rect x="182" y="{168 + i * 13}" width="{58 + (i % 3) * 6}" height="5" rx="2.5" fill="#C9D1CB"/>')
        b.append(f'<rect x="248" y="{168 + i * 13}" width="8" height="5" rx="2.5" fill="#C9D1CB"/>')
    b.append(t(218, 270, "2. Nutrition table", 10.5, INK, 600, "middle"))
    b += [f'<rect x="20" y="306" width="260" height="92" rx="14" fill="#FFF4DC" stroke="#F0D9A0"/>',
          t(32, 326, "WHAT HAPPENS NEXT", 9, AMBER, 700, extra='letter-spacing="1"'),
          t(32, 346, "AI reads the label. You check it.", 11), t(32, 362, "It's marked “Estimated” until it's confirmed,", 11),
          t(32, 378, "and saved so the next scan is instant.", 11)]
    b += [f'<rect x="20" y="420" width="260" height="46" rx="23" fill="{G7}"/>', t(150, 448, "Take photo", 14, "#fff", 600, "middle"),
          t(150, 494, "Or type the nutrition values", 11.5, G7, 600, "middle")]
    return phone("\n".join(b), "Adding an unknown product with two photos")


def chat():
    b = [f'<rect x="10" y="10" width="280" height="76" fill="{G9}"/>',
         f'<circle cx="40" cy="62" r="13" fill="url(#gold)"/>', t(62, 67, "Ask NutriScan", 15, "#fff", 600),
         t(62, 80, "Food, medicine & fake products", 9, "#9DB1A7")]
    b += [f'<rect x="64" y="104" width="206" height="52" rx="16" fill="{G7}"/>',
          t(76, 124, "Can my father with diabetes", 11, "#fff"), t(76, 140, "have this biscuit?", 11, "#fff")]
    b += [f'<rect x="20" y="170" width="236" height="150" rx="16" fill="#fff" stroke="#DCE0D8"/>',
          t(32, 192, "It has about 11 g of sugar per 100 g,", 10.5), t(32, 207, "which is high for someone with diabetes.", 10.5),
          t(32, 226, "A small portion now and then may be", 10.5), t(32, 241, "fine, but a pharmacist or dietitian", 10.5),
          t(32, 256, "can give you advice that fits him.", 10.5),
          f'<rect x="32" y="270" width="140" height="34" rx="10" fill="#E6F3EC"/>', t(42, 285, "Our data: Corroborated", 9.5, G7, 600),
          t(42, 297, "NAFDAC number captured", 9, MUTED)]
    b += [f'<path d="M36 336 q0 -9 8 -9 h12 q8 0 8 9 v6 l-8 0 l-6 6 l0 -6 l-6 0 z" fill="none" stroke="{MUTED}" stroke-width="1.4"/>',
          t(80, 342, "Helpful", 10, MUTED), t(130, 342, "Not helpful", 10, MUTED), t(204, 342, "Read aloud", 10, G7, 600)]
    b += [f'<rect x="20" y="540" width="260" height="40" rx="20" fill="#fff" stroke="#DCE0D8"/>',
          f'<circle cx="44" cy="560" r="9" fill="none" stroke="{MUTED}" stroke-width="1.5"/>', t(66, 564, "Ask about a product…", 11.5, "#8A948E"),
          f'<circle cx="256" cy="560" r="12" fill="{G7}"/><path d="M251 560 h10 m-4 -4 l4 4 l-4 4" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>']
    return phone("\n".join(b), "The Ask NutriScan chat")


def alerts():
    b = [appbar("Fake product alerts")]
    b += [t(24, 100, "Products people reported as fake", 11, MUTED)]
    rows = [("Sample Malt Drink", "Reported fake", RED, "#FBE3E0", "6 reports · open market, Lagos"),
            ("Sample Pain Tablets", "Disputed", AMBER, "#FBE9C0", "3 reports · pharmacy, Kano"),
            ("Sample Tomato Paste", "Reported fake", RED, "#FBE3E0", "4 reports · supermarket, Abuja")]
    for i, (name, tag, col, bg, meta) in enumerate(rows):
        y = 116 + i * 104
        b += [f'<rect x="20" y="{y}" width="260" height="92" rx="14" fill="#fff" stroke="#DCE0D8"/>',
              f'<rect x="32" y="{y + 14}" width="40" height="52" rx="6" fill="#F3E3B6"/>',
              t(84, y + 28, name, 12.5, INK, 700), f'<rect x="84" y="{y + 38}" width="92" height="20" rx="10" fill="{bg}"/>',
              t(130, y + 52, tag, 10, col, 700, "middle"), t(84, y + 78, meta, 9.5, MUTED)]
    b += [f'<rect x="20" y="440" width="260" height="84" rx="14" fill="#E6F3EC" stroke="#BFE0CE"/>',
          t(32, 462, "See a pack that looks wrong?", 12, G7, 700), t(32, 480, "Report it with photos, where you bought", 10.5),
          t(32, 494, "it and the batch number.", 10.5), t(32, 512, "Reports from new accounts count less.", 10, MUTED)]
    b += [f'<rect x="20" y="540" width="260" height="38" rx="19" fill="{G7}"/>', t(150, 563, "Report a product", 13, "#fff", 600, "middle")]
    return phone("\n".join(b), "The fake product alerts list")


def trust():
    b = [appbar("Data trust")]
    b += [f'<rect x="20" y="86" width="260" height="190" rx="14" fill="#E6F3EC" stroke="#BFE0CE"/>',
          f'<circle cx="42" cy="112" r="10" fill="{G5}"/><path d="M37 112 l3.5 3.5 l6 -7" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
          t(60, 118, "Corroborated", 16, G7, 700), t(34, 146, "• Open Food Facts agrees on 3 of 3 values", 10.5),
          t(34, 164, "• Matched by name, brand and country", 10.5), t(34, 182, "• NAFDAC number captured, not yet confirmed", 10.5),
          t(34, 200, "• Values you read from the pack: 1", 10.5),
          f'<rect x="32" y="216" width="236" height="24" rx="12" fill="none" stroke="{G7}"/>', t(150, 232, "Source: Open Food Facts", 10, G7, 600, "middle"),
          t(34, 262, "Last checked today", 9.5, MUTED)]
    b += [t(24, 306, "The four levels", 12, INK, 700)]
    for i, (name, desc, col) in enumerate([("Verified", "NAFDAC number confirmed", G7), ("Corroborated", "Two independent sources agree", G5),
                                          ("Sourced", "One source we can cite", "#2E7DAF"), ("Unverified", "Not enough proof yet", "#7A8680")]):
        y = 322 + i * 44
        b += [f'<rect x="20" y="{y}" width="260" height="36" rx="10" fill="#fff" stroke="#DCE0D8"/>', f'<circle cx="38" cy="{y + 18}" r="6" fill="{col}"/>',
              t(52, y + 16, name, 11.5, INK, 700), t(52, y + 29, desc, 9.5, MUTED)]
    b += [f'<rect x="20" y="510" width="260" height="56" rx="12" fill="#FFF4DC" stroke="#F0D9A0"/>', t(32, 532, "Votes alone never change a value.", 11, INK, 700),
          t(32, 548, "An independent source or our team must agree.", 10, MUTED)]
    return phone("\n".join(b), "How NutriScan shows how far data can be trusted")


def shelf():
    """Story scene: two look-alike packs on a shelf and a phone that checks them."""
    def pack(x, c1, c2, label, flag=False):
        s = (f'<g transform="translate({x} 150)"><rect width="110" height="170" rx="10" fill="{c1}"/><rect y="46" width="110" height="64" fill="{c2}"/>'
             f'<circle cx="55" cy="78" r="18" fill="{GOLD}" opacity=".9"/>'
             f'<text x="55" y="140" font-size="12" font-weight="700" fill="#fff" text-anchor="middle" font-family="{FONT}">{label}</text>'
             f'<rect x="20" y="152" width="70" height="6" rx="3" fill="#fff" opacity=".5"/></g>')
        return s
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 440" role="img" aria-label="Two packs that look identical on a shelf, with a phone checking them" font-family="{FONT}">
<defs><linearGradient id="beam" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{GOLD}" stop-opacity=".55"/><stop offset="1" stop-color="{GOLD}" stop-opacity="0"/></linearGradient>
<linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{GOLD}"/><stop offset="1" stop-color="{GOLD2}"/></linearGradient></defs>
<rect width="840" height="440" rx="24" fill="#123D2C"/>
<circle cx="640" cy="90" r="200" fill="#1B5A41" opacity=".35"/>
<rect x="60" y="320" width="720" height="14" rx="7" fill="#0B2E22"/>
<rect x="60" y="334" width="720" height="60" fill="#0E3626" opacity=".6"/>
{pack(120, "#C77A00", "#E3A52F", "Golden Oat")}
{pack(260, "#C77A00", "#E3A52F", "Golden Oat")}
{pack(400, "#2E7DAF", "#5AA0CC", "Sweet Milk")}
<g transform="translate(560 120)">
  <path d="M60 230 L-40 300 L190 300 Z" fill="url(#beam)" opacity=".0"/>
  <rect x="20" y="40" width="130" height="250" rx="22" fill="#0E1412" stroke="#2c3b34" stroke-width="3"/>
  <rect x="28" y="52" width="114" height="226" rx="16" fill="#F7F6F2"/>
  <circle cx="85" cy="112" r="26" fill="url(#gold)"/>
  <path d="M73 100h8v-4h-12v12h4zM97 100h-8v-4h12v12h-4zM73 124h8v4h-12v-12h4zM97 124h-8v4h12v-12h-4z" fill="{G9}"/>
  <rect x="42" y="158" width="86" height="12" rx="6" fill="#E6F3EC"/>
  <rect x="42" y="180" width="86" height="12" rx="6" fill="#FBE3E0"/>
  <rect x="42" y="202" width="60" height="12" rx="6" fill="#FFF4DC"/>
  <rect x="42" y="236" width="86" height="26" rx="13" fill="{G7}"/>
</g>
<path d="M545 250 C500 220 380 190 320 150" fill="none" stroke="{GOLD}" stroke-width="3" stroke-dasharray="3 9" stroke-linecap="round"/>
<g transform="translate(318 60)"><rect width="150" height="54" rx="27" fill="#FBE3E0"/><circle cx="27" cy="27" r="12" fill="{RED}"/><path d="M27 20v9M27 33v.5" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/><text x="50" y="25" font-size="12" font-weight="700" fill="{RED}">Reported fake</text><text x="50" y="40" font-size="10" fill="#7a3a33">by 4 people near you</text></g>
<g transform="translate(150 60)"><rect width="140" height="54" rx="27" fill="#E6F3EC"/><circle cx="27" cy="27" r="12" fill="{G5}"/><path d="M21 27l4.5 4.5 8-9" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/><text x="50" y="25" font-size="12" font-weight="700" fill="{G7}">NAFDAC number</text><text x="50" y="40" font-size="10" fill="#3d6b58">captured</text></g>
</svg>
'''


ALL = {"phone-result.svg": result, "phone-scan.svg": scan, "phone-photo.svg": photo, "phone-chat.svg": chat,
       "phone-alerts.svg": alerts, "phone-trust.svg": trust, "scene-shelf.svg": shelf}


def write_all(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, fn in ALL.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(fn())
