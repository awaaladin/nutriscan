"""Builds the NutriScan website into ../download.

    python site/build.py

Each page is a body fragment in site/pages/<slug>.html whose first line is
<!--title|description|nav-label-->. This script wraps it in the shared header, footer and loading
screen, writes the SVG illustrations, sitemap.xml and robots.txt. Static assets (css/js/logo)
live in download/assets and are served as they are."""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "download")
sys.path.insert(0, HERE)
import illustrations  # noqa: E402

SITE = "https://nutriscan-download.vercel.app"
# Public support address. Leave None until one has been chosen: the Contact page then says
# so honestly instead of showing a made-up address.
SUPPORT_EMAIL = None

NAV = [("index", "Home"), ("how-it-works", "How it works"), ("features", "Features"), ("our-data", "Our data & AI"),
       ("safety", "Safety"), ("about", "About"), ("contact", "Contact")]

# The QR-scanner glyph, the same geometry as the app's loading screen.
_RINGS = [((5, 5, 11, 11), (6.5, 6.5, 9.5, 9.5)), ((13, 5, 19, 11), (14.5, 6.5, 17.5, 9.5)), ((5, 13, 11, 19), (6.5, 14.5, 9.5, 17.5))]
_DOTS = [(13, 13, 14.5, 14.5), (14.5, 14.5, 16, 16), (16, 13, 17.5, 14.5), (13, 16, 14.5, 17.5), (14.5, 17.5, 16, 19), (16, 16, 17.5, 17.5),
         (17.5, 14.5, 19, 16), (17.5, 17.5, 19, 19)]
_CORNERS = [[(22, 7), (20, 7), (20, 4), (17, 4), (17, 2), (22, 2)], [(22, 22), (17, 22), (17, 20), (20, 20), (20, 17), (22, 17)],
            [(2, 22), (2, 17), (4, 17), (4, 20), (7, 20), (7, 22)], [(2, 2), (7, 2), (7, 4), (4, 4), (4, 7), (2, 7)]]


def _icon():
    rp = lambda r: f"M{r[0]},{r[1]}H{r[2]}V{r[3]}H{r[0]}Z"
    p = "".join(rp(o) + rp(i) for o, i in _RINGS) + "".join(rp(d) for d in _DOTS)
    return p + "".join("M" + "L".join(f"{x},{y}" for x, y in poly) + "Z" for poly in _CORNERS)


LOADER = f'''<div class="loader" aria-hidden="true">
  <div class="disc"><svg viewBox="0 0 96 96"><defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#E1C766"/><stop offset="1" stop-color="#B8860B"/></linearGradient></defs>
  <circle cx="48" cy="48" r="48" fill="url(#lg)"/><path transform="translate(48 48) scale(2) translate(-12 -12)" fill="#0B2E22" fill-rule="evenodd" d="{_icon()}"/></svg></div>
  <div class="word">Nutri<span>Scan</span></div>
  <div class="tag-line">Know what you eat</div>
</div>'''

HEAD_SCRIPT = ('<script>(function(){var d=document.documentElement;d.className+=" js";'
               'try{if(!sessionStorage.getItem("ns-seen")&&!matchMedia("(prefers-reduced-motion: reduce)").matches)d.className+=" show-loader";}'
               'catch(e){}})();</script>')


def header(slug):
    links = "".join(
        f'<a href="{s}.html"{" aria-current=\"page\"" if s == slug else ""}>{label}</a>' if s != "index"
        else f'<a href="./"{" aria-current=\"page\"" if slug == "index" else ""}>{label}</a>'
        for s, label in NAV)
    return f'''<a class="skip" href="#main">Skip to content</a>
<header class="site-header"><div class="container nav">
  <a class="brand" href="./" aria-label="NutriScan home"><img src="logo.svg" alt="" width="34" height="34"><span class="wm">Nutri<span>Scan</span></span></a>
  <button class="menu-btn" aria-label="Menu" aria-expanded="false" aria-controls="nav-links"><span></span><span></span><span></span></button>
  <nav class="nav-links" id="nav-links" aria-label="Main">{links}<a class="btn btn-gold btn-sm" href="download.html">Download</a></nav>
</div></header>'''


FOOTER = '''<footer class="site-footer"><div class="container">
  <div class="foot-grid">
    <div><a class="brand" href="./"><img src="logo.svg" alt="" width="34" height="34"><span class="wm">Nutri<span>Scan</span></span></a>
      <p>Scan packaged food and medicine. Understand what is in it, what it means for you, and whether it can be trusted. Built for Nigeria first.</p></div>
    <div><h4>Product</h4><a href="how-it-works.html">How it works</a><a href="features.html">Features</a><a href="our-data.html">Our data &amp; AI</a><a href="download.html">Download</a></div>
    <div><h4>Company</h4><a href="about.html">About</a><a href="contact.html">Contact</a><a href="safety.html">Safety &amp; compliance</a></div>
    <div><h4>Legal</h4><a href="privacy.html">Privacy Policy</a><a href="terms.html">Terms &amp; Conditions</a><a href="safety.html#medical">Medical disclaimer</a><a href="safety.html#ai">How we use AI</a></div>
  </div>
  <div class="foot-note">
    <span>&copy; <span data-year>2026</span> NutriScan. Powered by <strong>JCN</strong>.</span>
    <span>Educational information only. Not medical advice. Not affiliated with NAFDAC, WHO or Google.</span>
  </div>
</div></footer>'''


def page(slug, title, desc, body):
    full_title = "NutriScan: Know what you eat" if slug == "index" else f"{title} · NutriScan"
    url = SITE + ("/" if slug == "index" else f"/{slug}.html")
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{full_title}</title>
<meta name="description" content="{desc}">
<meta name="theme-color" content="#0b2e22">
<link rel="icon" type="image/svg+xml" href="logo.svg">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{full_title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{SITE}/og-image.png">
<meta property="og:url" content="{url}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image">
{HEAD_SCRIPT}
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
{LOADER}
{header(slug)}
<main id="main">
{body}
</main>
{FOOTER}
<script src="assets/site.js" defer></script>
</body>
</html>
'''


def contact_block():
    if SUPPORT_EMAIL:
        return (f'<p><strong>Email:</strong> <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a><br>'
                "We aim to reply within a few working days.</p>")
    return ('<p><strong>Email:</strong> our public support address is being set up for the public launch. Until then, beta testers '
            "can reach the team through whoever shared the app with them.</p>")


def main():
    illustrations.write_all(os.path.join(OUT, "assets", "img"))
    slugs = []
    for name in sorted(os.listdir(os.path.join(HERE, "pages"))):
        if not name.endswith(".html"):
            continue
        slug = name[:-5]
        src = open(os.path.join(HERE, "pages", name), encoding="utf-8").read()
        m = re.match(r"<!--(.*?)\|(.*?)-->\s*", src, re.S)
        assert m, f"{name} needs a <!--title|description--> first line"
        title, desc = m.group(1).strip(), m.group(2).strip()
        body = src[m.end():].replace("{{CONTACT_BLOCK}}", contact_block())
        with open(os.path.join(OUT, f"{slug}.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(page(slug, title, desc, body))
        slugs.append(slug)
    urls = "".join(f"<url><loc>{SITE}{'/' if s == 'index' else f'/{s}.html'}</loc></url>" for s in slugs)
    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
    with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    print("built", len(slugs), "pages")


if __name__ == "__main__":
    main()
