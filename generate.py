#!/usr/bin/env python3
"""Generate self-hosted GitHub profile SVG cards for @jontstaz.

Everything is baked in at generation time: contribution grid, streaks,
language mix, repo list, pixel-art portrait. No external API images,
no third-party watermarks. GitHub-safe SVG: <style>/<animate>/<animateTransform>
only, no scripts, no external fetches.
"""

import base64
import collections
import datetime as dt
import html
import io
import json
import math
import os
import subprocess
import sys
import urllib.request

OUT = os.path.dirname(os.path.abspath(__file__))
LOGIN = "jontstaz"

# ---------------------------------------------------------------- theme
CYAN = "#22d3ee"
CYAN_DIM = "#0e7490"
GREEN = "#4ade80"
GREEN_BRIGHT = "#86efac"
YELLOW = "#fbbf24"
PURPLE = "#c084fc"
BLUE = "#60a5fa"
PINK = "#f472b6"
RED = "#f87171"
INK = "#0a0e14"          # page background
PANEL = "#0d1420"        # card background
PANEL2 = "#101a2a"       # subtle alt panel
LINE = "#1c2b3f"         # hairline borders
GRID_OFF = "#131c2b"     # empty grid cell
FADE = "#6b829e"         # secondary text
FADE2 = "#8ba3bd"        # primary secondary text
BRIGHT = "#e8f1fb"       # brightest text
MONO = "ui-monospace, 'JetBrains Mono', 'Cascadia Code', Menlo, Consolas, monospace"

LANG_COLOR = {
    "TypeScript": "#3178c6", "Python": "#3572A5", "Lua": "#000080",
    "JavaScript": "#f1e05a", "C": "#555555", "Less": "#1d365d",
    "HTML": "#e34c26", "CSS": "#663399", "Shell": "#89e051",
    "Dockerfile": "#384d54", "Go": "#00ADD8", "CMake": "#DA3434",
    "Rust": "#dea584", "Nix": "#7e7eff", "Vue": "#41b883", "Other": "#5b6b80",
}


# ================================================================ helpers
def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def fetch_gh_data():
    """GraphQL: calendar + repos with language edges (paginated)."""
    query = """
    query($login:String!,$cursor:String){
      user(login:$login){
        avatarUrl
        createdAt
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
        repositories(first:100, after:$cursor, ownerAffiliations:OWNER,
                     isFork:false, orderBy:{field:STARGAZERS, direction:DESC}) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes {
            name description stargazerCount isPrivate isFork pushedAt
            primaryLanguage { name color }
            languages(first:12, orderBy:{field:SIZE, direction:DESC}) {
              edges { size node { name color } }
            }
        }
      }
    }
    }
    """
    # strip trailing brace glitch safety: rebuild query cleanly
    query = """
    query($login:String!,$cursor:String){
      user(login:$login){
        avatarUrl
        createdAt
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
        repositories(first:100, after:$cursor, ownerAffiliations:OWNER,
                     isFork:false, orderBy:{field:STARGAZERS, direction:DESC}) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes {
            name description stargazerCount isPrivate isFork pushedAt
            primaryLanguage { name color }
            languages(first:12, orderBy:{field:SIZE, direction:DESC}) {
              edges { size node { name color } }
            }
          }
        }
      }
    }
    """
    cursor = None
    repos = []
    avatar_url = None
    created = None
    cal_total = 0
    weeks = None
    for _ in range(5):
        cmd = ["gh", "api", "graphql", "-f", f"query={query}", "-F", f"login={LOGIN}"]
        if cursor:
            cmd += ["-f", f"cursor={cursor}"]
        d = json.loads(sh(cmd))
        u = d["data"]["user"]
        avatar_url = u["avatarUrl"]
        created = u["createdAt"]
        cc = u["contributionsCollection"]["contributionCalendar"]
        cal_total = cc["totalContributions"]
        weeks = cc["weeks"]
        page = u["repositories"]
        repos.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return {"avatar_url": avatar_url, "created": created, "cal_total": cal_total,
            "weeks": weeks, "repos": repos}


def pixelate_avatar(url, size=48, box=48):
    """Download avatar and return a data URI of a downscaled pixel version.
    48px keeps the retro chunky-pixel feel (3px blocks at 150px display)
    while staying recognisable; raise `size` to 150 for a fully sharp avatar."""
    png, _ = urllib.request.urlretrieve(url)
    try:
        from PIL import Image
        img = Image.open(png).convert("RGB").resize((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
        # (palette extraction skipped — full 169-color mini image embedded)
    finally:
        os.unlink(png)


def esc(s):
    return html.escape(str(s), quote=True)


def trunc(s, n):
    s = (s or "").replace("\r", " ").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


# ================================================================ card chrome
def card_open(w, h, x=1.5, y=1.5, title="", label="", rx=14, right=None, cls=""):
    """Open a card: dark panel, hairline border, optional header row.
    Returns (svg_header_string, content_origin(x,y))."""
    head = []
    head.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{PANEL}" stroke="{LINE}" stroke-width="1"/>')
    if title:
        tx = x + 22
        ty = y + 30
        # corner accents
        head.append(f'<path d="M {x+1.5} {y+26} V {y+1.5+rx*0.35} Q {x+1.5} {y+1.5} {x+1.5+rx*0.35} {y+1.5} H {x+26}" '
                    f'fill="none" stroke="{CYAN}" stroke-width="1.5" opacity="0.9"/>')
        head.append(f'<rect x="{x+22}" y="{ty-6.5}" width="3.5" height="13" fill="{CYAN}" opacity="0.85"/>')
        head.append(f'<text x="{tx+9}" y="{ty}" font-family="{MONO}" font-size="11.5" font-weight="700" '
                    f'letter-spacing="2.2" fill="{CYAN}">{esc(title.upper())}</text>')
        if label:
            head.append(f'<text x="{tx+9+len(title)*7.55+len(title.upper())*2.2}" y="{ty}" font-family="{MONO}" font-size="10.5" '
                        f'letter-spacing="1.5" fill="{FADE}">{esc(label.upper())}</text>')
    if right:
        head.append(f'<text x="{x+w-20}" y="{y+30}" text-anchor="end" font-family="{MONO}" font-size="10.5" '
                    f'letter-spacing="1.8" fill="{FADE}">{esc(right)}</text>')
    return "\n".join(head), (x, y)


def chip(x, y, label, color, w=None, h=20, pad=8):
    if w is None:
        w = len(label) * 6.6 + pad * 2 + 4
    body = [f'<g class="chip ch-{esc(label).lower()}" >']
    body.append(f'<rect x="{x}" y="{y}" width="{w:.0f}" height="{h}" rx="{h/2}" fill="{color}" opacity="0.13"/>')
    body.append(f'<rect x="{x}" y="{y}" width="{w:.0f}" height="{h}" rx="{h/2}" fill="none" stroke="{color}" stroke-width="1" opacity="0.8"/>')
    body.append(f'<circle cx="{x+12.5}" cy="{y+h/2}" r="3" fill="{color}"/>')
    body.append(f'<text x="{x+21}" y="{y+h/2+3.8}" font-family="{MONO}" font-size="10.5" font-weight="600" '
                f'letter-spacing="0.5" fill="{color}">{esc(label)}</text>')
    body.append("</g>")
    return "\n".join(body), w


def sparkline(x, y, w, h, values, color, dur, begin, stroke=2, fill=True, maxv=None):
    n = len(values)
    if maxv is None:
        maxv = max(values) or 1
    pts = [((x + i * (w / (n - 1))), y + h - (v / maxv) * (h - 4) - 2) for i, v in enumerate(values)]
    d_line = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in pts)
    d_area = d_line + f" L {x+w} {y+h} L {x} {y+h} Z"
    parts = []
    if fill:
        parts.append(f'<path d="{d_area}" fill="{color}" opacity="0.12"/>')
    parts.append(f'<path class="spk" d="{d_line}" fill="none" stroke="{color}" stroke-width="{stroke}" '
                 f'stroke-linecap="round" stroke-linejoin="round" pathLength="100" stroke-dasharray="100" stroke-dashoffset="100" '
                 f'style="--i:{begin}"/>')
    return "\n".join(parts)


def mini_grid(x, y, cell, values, maxv, prefix):
    """Small static grid; cells above threshold pulse in sequence."""
    out = []
    cols = len(values)
    for i, v in enumerate(values):
        t = v / (maxv or 1)
        if v <= 0:
            fill = GRID_OFF
            op = 0.9
        elif t < 0.25:
            fill = "#14532d"
        elif t < 0.5:
            fill = "#166534"
        elif t < 0.75:
            fill = "#22c55e"
        else:
            fill = GREEN_BRIGHT
        out.append(f'<rect id="{prefix}{i}" x="{x + i * (cell+2):.0f}" y="{y}" width="{cell}" height="{cell}" '
                   f'rx="{cell*0.22:.1f}" fill="{fill}" opacity="{op}"/>')
    out.append(
        f'<animate xlink:href="#{prefix}0" attributeName="opacity" values="0.25;1;0.25" dur="{dur_s(2.4)}" '
        f'repeatCount="indefinite" begin="0s" calcMode="linear"/>'
        if False else "")
    return "\n".join(x for x in out if x)


def dur_s(x):
    return f"{x}s"


# ================================================================ CARD 1: SIGNAL RUN
def build_hero(data, stats):
    days = sorted((d["date"], d["contributionCount"])
                  for w in data["weeks"] for d in w["contributionDays"])  # noqa: unused local
    W, H = 840, 400
    grid_x, grid_y = 24, 52
    cols = 53
    cell = 11.5
    gap = 3.4
    pitch = cell + gap
    maxv = max(c for _, c in days) or 1

    # current streak computed in stats dict
    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
             f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{MONO}">')
    p.append(f'''<style>
      .fadeup{{animation:fu .7s cubic-bezier(.2,.7,.3,1) both;animation-delay:var(--i)}}
      @keyframes fu{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
      .scan{{animation:scan 7s linear infinite;opacity:.5}}
      @keyframes scan{{0%{{transform:translateY(-4px)}}50%{{transform:translateY({H-90}px)}}100%{{transform:translateY(-4px)}}}}
      .glow{{animation:glow 2.6s ease-in-out infinite}}
      @keyframes glow{{0%,100%{{opacity:.55}}50%{{opacity:1}}}}
      .blip{{animation:blip 2.2s ease-in-out infinite}}
      @keyframes blip{{0%,100%{{opacity:.35}}50%{{opacity:1}}}}
      .d{{animation:drop .35s cubic-bezier(.2,.9,.3,1.2) both;animation-delay:var(--i)}}
      @keyframes drop{{from{{opacity:0;transform:translateY(-10px)}}to{{opacity:1;transform:none}}}}
      .ring{{animation:ring 3s ease-in-out infinite}}
      @keyframes ring{{0%,100%{{stroke-opacity:.25}}50%{{stroke-opacity:.9}}}}
      .core{{animation:core 2s ease-in-out infinite}}
      @keyframes core{{0%,100%{{opacity:.6}}50%{{opacity:1}}}}
    </style>''')
    p.append(f'<rect width="{W}" height="{H}" rx="14" fill="{INK}"/>')
    # faint texture: dot matrix
    p.append('<defs>'
             '<pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse">'
             '<circle cx="1.2" cy="1.2" r="1.2" fill="#1a2536"/></pattern>'
             '<linearGradient id="hdr" x1="0" y1="0" x2="1" y2="0">'
             f'<stop offset="0" stop-color="{PANEL}"/><stop offset="1" stop-color="{PANEL2}"/></linearGradient>'
             '<linearGradient id="scanl" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{CYAN}" stop-opacity="0.14"/>'
             '<stop offset="1" stop-color="' + CYAN + '" stop-opacity="0"/></linearGradient>'
             '<radialGradient id="gl" cx="0.5" cy="0.35" r="0.9">'
             f'<stop offset="0" stop-color="{CYAN}" stop-opacity="0.12"/>'
             f'<stop offset="0.55" stop-color="{CYAN}" stop-opacity="0.03"/>'
             '<stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></radialGradient>'
             '</defs>')
    p.append(f'<rect width="{W}" height="{H}" rx="14" fill="url(#dots)" opacity="0.5"/>')
    p.append(f'<rect width="{W}" height="{H}" rx="14" fill="url(#gl)"/>')

    # ---------------- header
    p.append(card_open(W - 3, H - 3, 1.5, 1.5, "SIGNAL RUN", "@jontstaz", right=f"HI-SCORE {stats['cal_total']:,}")[0])

    # ---------------- the grid
    quarter = {"0": "#14532d", "1": "#166534", "2": "#22c55e", "3": GREEN_BRIGHT}
    months = []
    last_month = None
    for ci, w in enumerate(data["weeks"]):
        ds = sorted(w["contributionDays"], key=lambda d: d["date"])
        if ds:
            m = ds[0]["date"][:7]
            if m != last_month:
                months.append((ci, m))
                last_month = m
    for lbl_y, mi in (("grid", 0),):
        pass
    for ci, w in enumerate(data["weeks"]):
        ds = sorted(w["contributionDays"], key=lambda d: d["date"])
        for ri, day in enumerate(ds):
            c = day["contributionCount"]
            x = grid_x + ci * pitch
            y = grid_y + ri * pitch
            lvl = 0 if c <= 0 else (1 if c <= maxv * 0.25 else (2 if c <= maxv * 0.5 else (3 if c <= maxv * 0.75 else 4)))
            if c <= 0:
                fill, op = GRID_OFF, 0.9
            elif lvl == 1:
                fill, op = "#14532d", 1
            elif lvl == 2:
                fill, op = "#166534", 1
            elif lvl == 3:
                fill, op = "#22c5e" if False else "#22c55e", 1
            else:
                fill, op = GREEN_BRIGHT, 1
            # ship eats busy days: heavily busy cells pulse
            hot = c >= maxv * 0.55
            anim = (f'<animate attributeName="opacity" values="1;0.35;1" dur="{2.2+0.4*(ri%3)}s" '
                    f'begin="{(ci%7)*0.18:.2f}s" repeatCount="indefinite"/>') if hot else ""
            p.append(f'<g class="d" style="--i:{0.03*ci:.2f}s"><rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" '
                     f'rx="2.5" fill="{fill}" opacity="{op}">{anim}</rect></g>')


    # ---------------- month labels
    mon_names = {1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
                 7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"}
    for ci, m in months:
        if ci == 0:
            continue
        mm = int(m[5:7])
        p.append(f'<text x="{grid_x + ci*pitch:.0f}" y="{grid_y - 8}" font-size="9" fill="{FADE}" '
                 f'letter-spacing="1">{mon_names[mm]}</text>')

    # ---------------- stat blocks under grid
    row_y = 232
    items = [
        ("LEVEL", f"{stats['year']}", CYAN),
        ("STREAK", f"{stats['current']} DAY", GREEN),
        ("BEST RUN", f"{stats['best']} DAYS", GREEN_BRIGHT),
        ("STARS", f"{stats['stars']:,}", YELLOW),
        ("FOLLOWERS", f"{stats['followers']:,}", PURPLE),
    ]
    bw = (W - 48 - 4 * 10) / 5
    for i, (label, val, colr) in enumerate(items):
        bx = 24 + i * (bw + 10)
        p.append(f'<g class="fadeup" style="--i:{0.9+0.12*i:.2f}s">'
                 f'<rect x="{bx:.1f}" y="{row_y}" width="{bw:.1f}" height="54" rx="9" fill="{PANEL}" stroke="{LINE}"/>'
                 f'<rect x="{bx:.1f}" y="{row_y}" width="{bw:.1f}" height="54" rx="9" fill="none" stroke="{colr}" stroke-opacity="0.16"/>'
                 f'<text x="{bx+14}" y="{row_y+21}" font-size="9" letter-spacing="1.6" fill="{FADE}">{label}</text>'
                 f'<text x="{bx+14}" y="{row_y+43}" font-size="19" font-weight="700" fill="{BRIGHT}">{esc(val)}</text>'
                 f'<rect x="{bx:.1f}" y="{row_y+51}" width="{bw:.1f}" height="3" rx="1.5" fill="{colr}" opacity="0.35"/></g>')

    # ---------------- power-up chips (languages)
    chips_y = 312
    p.append(f'<text x="24" y="{chips_y - 10}" font-size="9" letter-spacing="1.6" fill="{FADE}">POWER-UPS</text>')
    cx = 24
    for name, pct, colr in stats["langs"][:4]:
        c, w = chip(cx, chips_y, f"{name.upper()} {pct:.0f}%", colr, h=22)
        p.append(f'<g class="fadeup" style="--i:{1.4+0.1*len(p)%7:.2f}s">{c}</g>')
        cx += w + 10

    # ---------------- sparkline right side? kept clean. footer
    p.append(f'<text x="24" y="{H-18}" font-size="10" fill="{FADE}">every lit cell is a real commit day · the busier the day, the brighter it burns</text>')
    p.append(f'<text x="{W-24}" y="{H-18}" text-anchor="end" font-size="10" fill="{FADE2}">· {stats["active_days"]} active days · {stats["max_day"]} peak ·</text>')
    p.append("</svg>")
    return "\n".join(p)


# ================================================================ CARD 2: PILOT (neofetch)
def build_pilot(data, stats):
    W, H = 840, 330
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{MONO}">']
    p.append(f'''<style>
      .caret{{animation:crt 1.05s steps(1) infinite}}
      @keyframes crt{{0%,49%{{opacity:1}}50%,100%{{opacity:0}}}}
      .fadeup{{animation:fu .7s cubic-bezier(.2,.7,.3,1) both;animation-delay:var(--i)}}
      @keyframes fu{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
      .ringspin{{animation:rs 14s linear infinite;transform-origin:center}}
      @keyframes rs{{to{{transform:rotate(360deg)}}}}
    </style>''')
    p.append(f'<rect width="{W}" height="{H}" rx="14" fill="{INK}"/>')
    # window chrome
    p.append(f'<rect x="1.5" y="1.5" width="{W-3}" height="{H-3}" rx="13" fill="{PANEL}" stroke="{LINE}"/>')
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        p.append(f'<circle cx="{24+i*18}" cy="24" r="5.5" fill="{c}"/>')
    p.append(f'<text x="{W/2}" y="28" text-anchor="middle" font-size="10.5" fill="{FADE}" letter-spacing="1">jontstaz@github: ~ neofetch</text>')

    # pixel portrait: alternating color rows over the b64 mini image
    portrait_x, portrait_y, ps = 34, 66, 150
    palette = []
    b64 = data.get("portrait_b64")
    if b64:
        p.append(f'<g class="fadeup" style="--i:0.15s"><image x="{portrait_x}" y="{portrait_y}" width="{ps}" height="{ps}" '
                 f'xlink:href="{b64}" image-rendering="optimizeSpeed" /></g>')
        # scanline overlay
        p.append(f'<g class="fadeup" style="--i:0.2s">')
        p.append(f'<clipPath id="pc"><rect x="{portrait_x}" y="{portrait_y}" width="{ps}" height="{ps}" rx="10"/></clipPath>')
        p.append(f'<g clip-path="url(#pc)">')
        p.append(f'<rect x="{portrait_x}" y="{portrait_y}" width="{ps}" height="{ps}" fill="url(#ptint)" opacity="0"/>')
        for yy in range(0, ps, 3):
            p.append(f'<rect x="{portrait_x}" y="{portrait_y+yy}" width="{ps}" height="1.4" fill="{INK}" opacity="0.25"/>')
        p.append(f'<rect x="{portrait_x}" y="{portrait_y}" width="{ps}" height="{ps}" rx="10" fill="none" stroke="{CYAN}" stroke-opacity="0.5"/>')
        p.append(f'<rect x="{portrait_x-5}" y="{portrait_y-5}" width="{ps+10}" height="{ps+10}" rx="12" fill="none" '
                 f'stroke="{CYAN}" stroke-opacity="0.25" stroke-dasharray="3 6" class="ringspin" style="transform-origin:{portrait_x+ps/2}px {portrait_y+ps/2}px"/>')
        p.append('</g>')
        p.append('</g>')

    # ---- right column: identity
    tx = portrait_x + ps + 36
    ty = 78
    L1 = 17.5
    p.append(f'<g class="fadeup" style="--i:0.25s"><text x="{tx}" y="{ty}" font-size="24" font-weight="700" fill="{BRIGHT}" letter-spacing="0.5">jontstaz'
             f'<tspan fill="{CYAN}">@</tspan><tspan fill="{FADE2}">github</tspan></text>')
    p.append(f'<text x="{tx}" y="{ty+40}" font-size="11" fill="{FADE}">SOFTWARE ENGINEER · AI-POWERED DEV TOOLS · AUTOMATION</text>')
    p.append('</g>')
    ty += 56

    def row(label, value_html, extra=""):
        nonlocal ty
        p.append(f'<text x="{tx}" y="{ty+L1}" font-size="12" fill="{CYAN}" font-weight="700">{esc(label)}<tspan fill="{FADE}"> ·</tspan></text>')
        p.append(f'<text x="{tx+118}" y="{ty+L1}" font-size="12" fill="{FADE2}">{value_html}</text>')
        ty += L1 + 3

    row("OS", f"<tspan fill='{BRIGHT}'>TypeScript</tspan><tspan fill='{FADE}'> · </tspan><tspan fill='{BRIGHT}'>Python</tspan><tspan fill='{FADE}'> · Linux</tspan>")
    row("UPTIME", f"<tspan fill='{BRIGHT}'>12 yrs</tspan><tspan fill='{FADE}'> in dev · {stats['git_years']} yrs in git</tspan>")
    row("NOW", f"<tspan fill='{GREEN_BRIGHT}'>agentic workflows</tspan><tspan fill='{FADE}'> · local AI · DX tooling</tspan>")
    row("WORK", f"<tspan fill='{FADE2}'>work account</tspan> <tspan fill='{CYAN}' text-decoration='underline'>@jonte-z</tspan>")
    # npub row (wrap manually)
    npub = stats["npub"]
    p.append(f'<text x="{tx}" y="{ty+L1}" font-size="12" fill="{CYAN}" font-weight="700">NPUB<tspan fill="{FADE}"> ·</tspan></text>')
    p.append(f'<text x="{tx+118}" y="{ty+L1}" font-size="10.5" fill="{FADE}" letter-spacing="0.3">{esc(npub[:34])}</text>')
    p.append(f'<text x="{tx+118}" y="{ty+L1+15}" font-size="10.5" fill="{FADE}" letter-spacing="0.3">{esc(npub[34:])}</text>')
    ty += L1 + 26

    # ---- bottom stats strip
    strip_y = H - 78
    p.append(f'<rect x="24" y="{strip_y}" width="{W-48}" height="1" fill="{LINE}"/>')
    cols = [
        ("REPOS", f"{stats['repos']}", CYAN),
        ("STARS", f"{stats['stars']:,}", YELLOW),
        ("FOLLOWERS", f"{stats['followers']:,}", PURPLE),
        ("CONTRIBS/YR", f"{stats['cal_total']:,}", GREEN),
        ("ACTIVE DAYS", f"{stats['active_days']}", GREEN_BRIGHT),
        ("BEST RUN", f"{stats['best']}d", BLUE),
    ]
    cw = (W - 48) / 6
    for i, (label, val, colr) in enumerate(cols):
        x = 24 + i * cw
        p.append(f'<g class="fadeup" style="--i:{0.4+0.1*i:.2f}s">'
                 f'<text x="{x}" y="{strip_y+26}" font-size="8.5" letter-spacing="1.4" fill="{FADE}">{label}</text>'
                 f'<text x="{x}" y="{strip_y+47}" font-size="16" font-weight="700" fill="{colr}">{esc(val)}</text></g>')
    # caret line
    p.append(f'<text x="34" y="{H-18}" font-size="11" fill="{GREEN}">➜<tspan fill="{FADE}"> ~ </tspan>'
             f'<tspan fill="{BRIGHT}">echo "ship fast, build things"</tspan>'
             f'<tspan class="caret" fill="{CYAN}">▊</tspan></text>')
    p.append("</svg>")
    return "\n".join(p)


# ================================================================ CARD 3: MISSIONS
def build_missions(data, stats):
    repos = [r for r in data["repos"] if not r["isPrivate"] and r["stargazerCount"] > 0
             and r["name"].lower() != LOGIN.lower()][:6]
    W = 840
    row_h = 44
    H = 78 + row_h * len(repos) + 26
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{MONO}">']
    p.append(f'''<style>
      .fadeup{{animation:fu .6s cubic-bezier(.2,.7,.3,1) both;animation-delay:var(--i)}}
      @keyframes fu{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
      .hovr{{transition:opacity .2s}}
      .star{{animation:st 3.5s ease-in-out infinite}}
      @keyframes st{{0%,100%{{opacity:.75}}50%{{opacity:1}}}}
    </style>''')
    p.append(f'<rect width="{W}" height="{H}" rx="14" fill="{INK}"/>')
    p.append(card_open(W - 3, H - 3, 1.5, 1.5, "MISSIONS", "BY STARS", right=f"{stats['stars']:,} TOTAL")[0])

    y0 = 64
    for i, r in enumerate(repos):
        y = y0 + i * row_h
        idx = f"{i+1:02d}"
        lang = (r.get("primaryLanguage") or {}).get("name")
        colr = LANG_COLOR.get(lang, "#5b6b80") if lang else "#5b6b80"
        url = f"https://github.com/{LOGIN}/{r['name']}"
        # row hover strip
        p.append(f'<g class="fadeup" style="--i:{0.05*i:.2f}s">')
        p.append(f'<a href="{esc(url)}" xlink:href="{esc(url)}" target="_blank">')
        p.append(f'<rect x="14" y="{y}" width="{W-28}" height="{row_h-6}" rx="8" fill="{PANEL}" opacity="0.55"/>')
        p.append(f'<text x="30" y="{y+row_h/2+4.5}" font-size="13" font-weight="700" fill="{CYAN}" opacity="0.85">{idx}</text>')
        p.append(f'<circle cx="60" cy="{y+row_h/2-1}" r="4" fill="{colr}"/>')
        p.append(f'<text x="74" y="{y+row_h/2+1}" font-size="13" font-weight="600" fill="{BRIGHT}">{esc(r["name"])}</text>')
        desc = trunc(r.get("description"), 74)
        if desc:
            p.append(f'<text x="74" y="{y+row_h/2+16}" font-size="10.5" fill="{FADE}">{esc(desc)}</text>')
        p.append(f'<text x="{W-30}" y="{y+row_h/2+1.5}" text-anchor="end" font-size="12" font-weight="700" fill="{YELLOW}" class="star">'
                 f'★ {r["stargazerCount"]}</text>')
        # fork-ish secondary: pushedAt year
        yr = (r.get("pushedAt") or "")[:4]
        if yr:
            p.append(f'<text x="{W-30}" y="{y+row_h/2+16}" text-anchor="end" font-size="9.5" fill="{FADE}">PUSH {yr}</text>')
        p.append('</a>')
        p.append('</g>')
    p.append("</svg>")
    return "\n".join(p)


# ================================================================ CARD 4: POWER-UPS (languages)
def build_langs(data, stats):
    W, H = 840, 252
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{MONO}">']
    p.append(f'''<style>
      .fadeup{{animation:fu .6s cubic-bezier(.2,.7,.3,1) both;animation-delay:var(--i)}}
      @keyframes fu{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
      .bar{{stroke-dasharray:var(--w);stroke-dashoffset:var(--w);animation:bw 1s cubic-bezier(.25,.8,.3,1) both;animation-delay:var(--i)}}
      @keyframes bw{{to{{stroke-dashoffset:0}}}}
      .fillin{{transform:scaleX(0);transform-origin:left;animation:fi .9s cubic-bezier(.25,.8,.3,1) both;animation-delay:var(--i)}}
      @keyframes fi{{to{{transform:scaleX(1)}}}}
    </style>''')
    p.append(f'<rect width="{W}" height="{H}" rx="14" fill="{INK}"/>')
    p.append(card_open(W - 3, H - 3, 1.5, 1.5, "POWER-UPS", "LANGUAGE MIX", right=f"{stats['total_bytes']/1e6:.1f}MB SCANNED")[0])

    langs = stats["langs"]
    x0, y0 = 30, 70
    bw = W - 260
    for i, (name, pct, colr) in enumerate(langs[:5]):
        y = y0 + i * 33
        p.append(f'<g class="fadeup" style="--i:{0.08*i:.2f}s">')
        p.append(f'<circle cx="{x0+6}" cy="{y+4}" r="4" fill="{colr}"/>')
        p.append(f'<text x="{x0+20}" y="{y+8}" font-size="12.5" font-weight="600" fill="{BRIGHT}">{esc(name)}</text>')
        # track
        p.append(f'<rect x="{x0+150}" y="{y-2}" width="{bw}" height="9" rx="4.5" fill="{GRID_OFF}"/>')
        # fill
        wid = bw * pct / 100
        p.append(f'<rect x="{x0+150}" y="{y-2}" width="{wid:.1f}" height="9" rx="4.5" fill="{colr}" opacity="0.95"/>')
        p.append(f'<rect x="{x0+150}" y="{y-2}" width="{wid:.1f}" height="9" rx="4.5" fill="url(#lg sheen)" opacity="0"/>')
        # animated sheen sweep over the filled part
        p.append(f'<rect x="{x0+150}" y="{y-2}" width="{wid:.1f}" height="9" rx="4.5" fill="url(#sheen)"/>'
                 f'<g opacity="0.55"><rect x="{x0+150}" y="{y-2}" width="{wid:.1f}" height="9" rx="4.5" fill="none" stroke="{colr}" stroke-opacity="0.5"/></g>')
        p.append(f'<text x="{x0+150+bw+14}" y="{y+7}" font-size="12" font-weight="700" fill="{colr}" text-anchor="start">{pct:.0f}%</text>')
        p.append('</g>')
    # legend of the rest
    rest = langs[5:8]
    if rest:
        ty = y0 + 5 * 33 + 12
        line = "  ·  ".join(f"{n} {q:.0f}%" for n, q, _ in rest)
        p.append(f'<text x="{x0}" y="{ty}" font-size="10" fill="{FADE}">+ {esc(line)}</text>')
    p.append('<defs><linearGradient id="sheen" x1="0" y1="0" x2="1" y2="0">'
             '<stop offset="0" stop-color="#ffffff" stop-opacity="0.25"/>'
             '<stop offset="0.5" stop-color="#ffffff" stop-opacity="0.05"/>'
             '<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient></defs>')
    p.append("</svg>")
    return "\n".join(p)


# ================================================================ CARD 5: FLIGHT LOG
def build_flight(data, stats):
    """26-week radar: weekly sparkbars + monthly heat tiles."""
    weeks = data["weeks"]
    weekly = []
    for w in weeks[-26:]:
        ds = sorted(w["contributionDays"], key=lambda d: d["date"])
        weekly.append(sum(d["contributionCount"] for d in ds))
    W, H = 840, 260
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{MONO}">']
    p.append(f'''<style>
      .fadeup{{animation:fu .6s cubic-bezier(.2,.7,.3,1) both;animation-delay:var(--i)}}
      @keyframes fu{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
      .beam{{animation:bm 2.8s ease-in-out infinite}}
      @keyframes bm{{0%,100%{{opacity:.4}}50%{{opacity:1}}}}
    </style>''')
    p.append(f'<rect width="{W}" height="{H}" rx="14" fill="{INK}"/>')
    p.append(card_open(W - 3, H - 3, 1.5, 1.5, "FLIGHT LOG", "26 WEEKS", right=f"SCORE {stats['cal_total']:,}")[0])

    # left: weekly bar chart
    chart_x, chart_y, chart_w, chart_h = 30, 78, 470, 130
    n = len(weekly)
    bw = chart_w / n
    maxw = max(weekly) or 1
    for i, v in enumerate(weekly):
        hgt = max(2.5, (v / maxw) * (chart_h - 14))
        x = chart_x + i * bw
        # color by intensity
        t = v / maxw
        colr = GRID_OFF if v == 0 else ("#166534" if t < 0.33 else ("#22c55e" if t < 0.66 else GREEN_BRIGHT))
        ybase = chart_y + chart_h
        # SMIL grow (2.5px stub -> full height, freeze) so rsvg shows full bars and browsers see the grow
        anim = (f'<animate attributeName="height" values="2.5;{hgt:.1f}" dur="0.7s" begin="{0.04*i:.2f}s" fill="freeze"/>'
                f'<animate attributeName="y" values="{ybase-2.5:.1f};{ybase-hgt:.1f}" dur="0.7s" begin="{0.04*i:.2f}s" fill="freeze"/>') if v > 0 else ""
        p.append(f'<g class="fadeup" style="--i:{0.03*i:.2f}s">'
                 f'<rect x="{x+1:.1f}" y="{ybase-hgt:.1f}" width="{bw-2.5:.1f}" height="{hgt:.1f}" rx="2" '
                 f'fill="{colr}" opacity="{0.95 if v>0 else 0.7}">{anim}</rect></g>')
    # baseline + max marker
    p.append(f'<line x1="{chart_x}" y1="{chart_y+chart_h}" x2="{chart_x+chart_w}" y2="{chart_y+chart_h}" stroke="{LINE}" stroke-width="1"/>')
    p.append(f'<text x="{chart_x}" y="{chart_y-6}" font-size="9" fill="{FADE}" letter-spacing="1">COMMITS / WEEK</text>')
    p.append(f'<text x="{chart_x+chart_w}" y="{chart_y-6}" text-anchor="end" font-size="9" fill="{FADE}">peak {maxw}</text>')

    # right: telemetry stack
    rx = 560
    telem = [
        ("CURRENT RUN", f"{stats['current']} DAYS", GREEN),
        ("BEST RUN", f"{stats['best']} DAYS", GREEN_BRIGHT),
        ("ACTIVE DAYS", f"{stats['active_days']}", CYAN),
        ("PEAK DAY", f"{stats['max_day']}", YELLOW),
    ]
    for i, (label, val, colr) in enumerate(telem):
        y = 84 + i * 36
        p.append(f'<g class="fadeup" style="--i:{0.15+0.1*i:.2f}s">'
                 f'<text x="{rx}" y="{y}" font-size="9" letter-spacing="1.5" fill="{FADE}">{label}</text>'
                 f'<text x="{rx}" y="{y+17}" font-size="16" font-weight="700" fill="{colr}">{val}</text></g>')
    # tiny radar decoration
    p.append(f'<g class="fadeup" style="--i:0.6s" transform="translate({rx+200},118)">'
             f'<circle r="34" fill="none" stroke="{CYAN}" stroke-opacity="0.2"/>'
             f'<circle r="22" fill="none" stroke="{CYAN}" stroke-opacity="0.14"/>'
             f'<circle r="10" fill="none" stroke="{CYAN}" stroke-opacity="0.1"/>'
             f'<g class="beam"><path d="M0 0 L34 0" stroke="{CYAN}" stroke-width="1.5" opacity="0.7">'
             f'<animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="4s" repeatCount="indefinite"/>'
             f'</path></g>'
             f'<circle r="2.2" fill="{CYAN}" class="core"/></g>')

    # footer strip: busiest month
    p.append(f'<line x1="30" y1="{H-42}" x2="{W-30}" y2="{H-42}" stroke="{LINE}"/>')
    p.append(f'<text x="30" y="{H-20}" font-size="10" fill="{FADE}">heaviest month · {esc(stats["top_month_lbl"])} with {stats["top_month_val"]:,} contributions</text>')
    p.append(f'<text x="{W-30}" y="{H-20}" text-anchor="end" font-size="10" fill="{FADE2}">weekdays grind · {esc(stats["top_wd"])}</text>')
    p.append("</svg>")
    return "\n".join(p)


# ================================================================ main
def main():
    data = fetch_gh_data()

    # ---- stats
    days = sorted((d["date"], d["contributionCount"])
                  for w in data["weeks"] for d in w["contributionDays"])
    counts = [c for _, c in days]
    cur = best = 0
    bestlen = 0
    for _, c in days:
        cur = cur + 1 if c > 0 else 0
        bestlen = max(bestlen, cur)
    curstreak = 0
    for i, (date, c) in enumerate(reversed(days)):
        if c > 0:
            curstreak += 1
        elif i == 0:
            continue
        else:
            break
    bymonth = collections.Counter()
    for d, c in days:
        bymonth[d[:7]] += c
    top_month, top_mval = (bymonth.most_common(1)[0] if bymonth else ("—", 0))
    bywd = collections.Counter()
    for d, c in days:
        bywd[dt.date.fromisoformat(d).weekday()] += c
    wd_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    top_wd = wd_names[bywd.most_common(1)[0][0]] if bywd else "—"

    lang_bytes = collections.Counter()
    for r in data["repos"]:
        if r.get("isPrivate") or r.get("isFork"):
            continue
        for e in r["languages"]["edges"]:
            lang_bytes[e["node"]["name"]] += e["size"]
    total_bytes = sum(lang_bytes.values())
    custom = {"Lua": "#7c3aed"}  # legible purple instead of GitHub navy
    langs = []
    for name, b in lang_bytes.most_common(8):
        pct = b / total_bytes * 100
        langs.append((name, pct, custom.get(name) or LANG_COLOR.get(name) or "#5b6b80"))

    stars = sum(r["stargazerCount"] for r in data["repos"] if not r["isPrivate"])
    user_rest = json.loads(sh(["gh", "api", "users/jontstaz"]))
    followers = int(user_rest["followers"])
    public_repos = int(user_rest["public_repos"])
    year = dt.date.today().year
    npub = ""
    bio = user_rest.get("bio") or ""
    for tok in bio.split():
        if tok.startswith("npub1"):
            npub = tok
            break

    stats = {
        "year": year,
        "cal_total": data["cal_total"],
        "stars": stars,
        "followers": followers,
        "repos": public_repos,
        "active_days": sum(1 for c in counts if c > 0),
        "max_day": max(counts) if counts else 0,
        "current": curstreak,
        "best": bestlen,
        "top_month_lbl": top_month,
        "top_month_val": top_mval,
        "top_wd": top_wd,
        "langs": langs,
        "total_bytes": total_bytes,
        "npub": npub,
        "git_years": round((dt.date.today() - dt.date(2014, 1, 12)).days / 365.25, 1),
    }

    try:
        data["portrait_b64"] = pixelate_avatar(data["avatar_url"])
    except Exception as e:
        print(f"warn: portrait skipped ({e})", file=sys.stderr)

    os.makedirs(OUT, exist_ok=True)
    cards = {
        "hero.svg": build_hero(data, stats),
        "pilot.svg": build_pilot(data, stats),
        "missions.svg": build_missions(data, stats),
        "langs.svg": build_langs(data, stats),
        "flight.svg": build_flight(data, stats),
    }
    for fname, svg in cards.items():
        with open(os.path.join(OUT, fname), "w") as f:
            f.write(svg)
        print(f"wrote {fname} ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()
