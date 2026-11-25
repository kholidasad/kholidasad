#!/usr/bin/env python3
"""Steam-profile-style SVG cards for a GitHub profile README, built from live GitHub data.

Usage:
  python gen_steam.py --login kholidasad --out assets          # fetch live data (needs GITHUB_TOKEN)
  python gen_steam.py --data sample.json --out assets          # render from a saved JSON (offline)
  python gen_steam.py --login kholidasad --dump data.json      # just save fetched data

Standard library only, so it runs on a plain GitHub Actions runner.
"""
import argparse, base64, json, os, sys, urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape

# ----------------------------------------------------------------- CONFIG ---
CONFIG = {
    "headline": "Backend-leaning Full-stack Engineer",
    "fallback_bio": "a wannabe back-end developer",
    "website": "kholidasad.web.id",
    "featured_repo": "multi-tenant-starter-kit",   # shown in "Favorite Project Showcase"
    "featured_tagline": "SAAS FOUNDATION",
    "status_line": "Open to new builds & teams",
    "recent_count": 3,                             # rows in "Recent Activity"
    "exclude_recent": [],                          # repo names to hide from Recent Activity
}

# ------------------------------------------------------------------ FETCH ---
QUERY = """
query($login: String!) {
  user(login: $login) {
    login name bio avatarUrl(size: 320)
    followers { totalCount }
    allRepos: repositories(privacy: PUBLIC, ownerAffiliations: OWNER) { totalCount }
    repos: repositories(privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false, first: 100,
                        orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name description stargazerCount pushedAt
        primaryLanguage { name }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
      }
    }
    contributionsCollection {
      contributionCalendar { totalContributions weeks { contributionDays { contributionCount } } }
    }
  }
}"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "steam-profile-readme"})
    res = json.load(urllib.request.urlopen(req, timeout=30))
    if res.get("errors"):
        sys.exit(f"GitHub API error: {res['errors']}")
    u = res["data"]["user"]

    lang_bytes = {}
    for r in u["repos"]["nodes"]:
        for e in r["languages"]["edges"]:
            lang_bytes[e["node"]["name"]] = lang_bytes.get(e["node"]["name"], 0) + e["size"]
    total = sum(lang_bytes.values()) or 1
    langs = sorted(((k, round(v * 100 / total)) for k, v in lang_bytes.items()), key=lambda x: -x[1])

    cal = u["contributionsCollection"]["contributionCalendar"]
    active = sum(1 for w in cal["weeks"] for d in w["contributionDays"] if d["contributionCount"] > 0)

    avatar = ""
    try:
        with urllib.request.urlopen(u["avatarUrl"], timeout=30) as a:
            ctype = a.headers.get_content_type() or "image/png"
            avatar = f"data:{ctype};base64," + base64.b64encode(a.read()).decode()
    except Exception as ex:  # avatar is cosmetic; keep going
        print("avatar download failed:", ex)

    return {
        "login": u["login"], "name": u["name"] or u["login"], "bio": (u["bio"] or "").strip(),
        "avatar": avatar, "followers": u["followers"]["totalCount"],
        "repo_count": u["allRepos"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in u["repos"]["nodes"]),
        "contributions": cal["totalContributions"], "active_days": active,
        "languages": langs,
        "repos": [{"name": r["name"], "description": r["description"] or "",
                   "stars": r["stargazerCount"], "pushed_at": r["pushedAt"],
                   "language": (r["primaryLanguage"] or {}).get("name") or "Code"}
                  for r in u["repos"]["nodes"]],
    }

# ----------------------------------------------------------------- RENDER ---
FONT = "'Motiva Sans','Segoe UI',Arial,Helvetica,sans-serif"
TXT, MUTED, BLUE, ONLINE, GREEN = "#c7d5e0", "#8f98a0", "#66c0f4", "#57cbde", "#a4d007"
W = 900
LANG_COLORS = {"PHP": "#777bb4", "JavaScript": "#c9a400", "TypeScript": "#3178c6", "Swift": "#f05138",
               "CSS": "#663399", "HTML": "#e34c26", "Python": "#3572a5", "Go": "#00add8", "Blade": "#f7523f",
               "Vue": "#41b883", "Shell": "#4eaa25", "Kotlin": "#a97bff", "Dart": "#00b4ab"}
PROG = ('<linearGradient id="prog" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#47bfff"/>'
        '<stop offset="1" stop-color="#1a44c2"/></linearGradient>')


def x(s):
    return escape(str(s))


def svg(h, body, defs=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1b2838"/><stop offset="1" stop-color="#0e141b"/></linearGradient>
<linearGradient id="sec" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2c4b63" stop-opacity=".9"/><stop offset="1" stop-color="#1b2838" stop-opacity="0"/></linearGradient>
{defs}
</defs>
<style>text{{font-family:{FONT};}}</style>
<rect width="{W}" height="{h}" rx="4" fill="url(#bg)"/>
{body}
</svg>'''


def section(title, right=""):
    r = f'<text x="{W-20}" y="27" text-anchor="end" font-size="12" fill="{MUTED}">{x(right)}</text>' if right else ""
    return (f'<rect x="0" y="0" width="{W}" height="40" fill="url(#sec)"/>'
            f'<text x="20" y="26" font-size="15" fill="{TXT}" letter-spacing=".5">{x(title)}</text>{r}')


def wrap(text, width, lines=2):
    words, out, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            out.append(cur); cur = w
            if len(out) == lines:
                break
        else:
            cur = f"{cur} {w}".strip()
    else:
        out.append(cur)
    if len(out) == lines and len(" ".join(out)) < len(text):
        out[-1] = out[-1][: width - 1].rstrip() + "…"
    return [l for l in out if l]


def initials(name):
    parts = [p for p in name.replace("_", " ").replace("-", " ").split() if p]
    return ("".join(p[0] for p in parts[:2]) if len(parts) > 1 else name[:2]).upper()


def days_ago(iso):
    d = (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
    return "today" if d <= 0 else "yesterday" if d == 1 else f"{d} days ago"


def achievements(d):
    langs = dict(d["languages"])
    top = d["languages"][0][0] if d["languages"] else "Code"
    return [
        ("First Commit", "#66c0f4", d["contributions"] > 0, '<path d="M-10 0h20M0-10v20" stroke="#fff" stroke-width="4"/>'),
        (f'{d["repo_count"]} Repos', "#a4d007", d["repo_count"] >= 10,
         '<rect x="-12" y="-12" width="24" height="24" fill="none" stroke="#fff" stroke-width="3"/><path d="M-12 -4h24" stroke="#fff" stroke-width="3"/>'),
        (f"{top} Main", LANG_COLORS.get(top, "#8892bf"), bool(d["languages"]),
         f'<text y="6" text-anchor="middle" font-size="13" font-weight="800" fill="#fff">{x(top[:4].lower())}</text>'),
        (f'Polyglot ×{len(langs)}', "#e5c07b", len(langs) >= 3,
         '<circle r="12" fill="none" stroke="#fff" stroke-width="3"/><path d="M-12 0h24M0-12c-8 8-8 16 0 24M0-12c8 8 8 16 0 24" stroke="#fff" stroke-width="2" fill="none"/>'),
        ("Streak 30d", "#f05138", d["active_days"] >= 30, '<path d="M0-13c6 8 10 12 6 20-2 4-10 4-12 0-3-6 2-8 2-13 2 3 3 4 4 6z" fill="#fff"/>'),
        ("First Star", "#57cbde", d["stars"] > 0, '<path d="M0-13l4 9 9 1-7 6 2 9-8-5-8 5 2-9-7-6 9-1z" fill="#fff"/>'),
        ("Century", "#c02942", d["contributions"] >= 100, '<text y="6" text-anchor="middle" font-size="16" font-weight="800" fill="#fff">100</text>'),
        ("Rising Star", "#d4af37", d["stars"] >= 10, '<path d="M-12 8 L0 -12 L12 8 Z" fill="#fff"/>'),
    ]


def render(d, out):
    os.makedirs(out, exist_ok=True)
    cfg = CONFIG
    write = lambda n, s: open(os.path.join(out, n), "w", encoding="utf-8").write(s)
    langs = d["languages"]
    top, top_pct = (langs[0] if langs else ("Code", 0))
    bio = d["bio"] or cfg["fallback_bio"]
    level = d["repo_count"]

    # 1. header
    if d.get("avatar"):
        avatar = (f'<clipPath id="av"><rect x="34" y="42" width="156" height="156"/></clipPath>'
                  f'<image x="34" y="42" width="156" height="156" href="{d["avatar"]}" clip-path="url(#av)" preserveAspectRatio="xMidYMid slice"/>')
    else:
        avatar = (f'<rect x="34" y="42" width="156" height="156" fill="#2a475e"/>'
                  f'<text x="112" y="140" text-anchor="middle" font-size="60" font-weight="700" fill="{BLUE}">{x(initials(d["name"]))}</text>')
    lang_line = " · ".join(l for l, _ in langs[:5])
    write("header.svg", svg(240, f'''
<rect x="0" y="0" width="{W}" height="240" rx="4" fill="url(#hero)" opacity=".55"/>
<rect x="28" y="36" width="168" height="168" fill="url(#frame)"/>
<rect x="31" y="39" width="162" height="162" fill="#0e141b"/>
{avatar}
<text x="222" y="72" font-size="28" fill="#ffffff">{x(d["name"])}</text>
<text x="222" y="98" font-size="14" fill="{MUTED}">{x(d["login"])} · {x(cfg["headline"])}</text>
<text x="222" y="140" font-size="14" fill="{TXT}" font-style="italic">"{x(bio[:60])}"</text>
<text x="222" y="166" font-size="13" fill="{MUTED}">{x(lang_line)}</text>
<text x="222" y="196" font-size="13" fill="{BLUE}">{x(cfg["website"])}</text>
<text x="700" y="64" font-size="22" fill="{TXT}">Level</text>
<circle cx="806" cy="57" r="22" fill="none" stroke="#c02942" stroke-width="2.5"/>
<text x="806" y="64" text-anchor="middle" font-size="18" fill="{TXT}">{level}</text>
<rect x="690" y="92" width="190" height="52" rx="3" fill="#000" fill-opacity=".25"/>
<polygon points="714,100 732,110 732,130 714,140 696,130 696,110" fill="url(#badge)" stroke="#e5c07b" stroke-width="1"/>
<text x="714" y="125" text-anchor="middle" font-size="13" font-weight="700" fill="#1b2838">&lt;/&gt;</text>
<text x="744" y="114" font-size="13" fill="{TXT}">Built in Public</text>
<text x="744" y="132" font-size="12" fill="{MUTED}">{d["contributions"]} XP</text>
<text x="690" y="178" font-size="17" fill="{ONLINE}">Currently Online</text>
<text x="690" y="198" font-size="12" fill="{MUTED}">{x(cfg["status_line"])}</text>
''', defs='''<linearGradient id="hero" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#3a6e94"/><stop offset=".6" stop-color="#1b2838"/><stop offset="1" stop-color="#2a1b3d"/></linearGradient>
<linearGradient id="frame" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#53a4c4"/><stop offset="1" stop-color="#2b6f8a"/></linearGradient>
<linearGradient id="badge" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f5d78e"/><stop offset="1" stop-color="#c8963e"/></linearGradient>'''))

    # 2. stats strip
    stats = [("Repositories", d["repo_count"]), ("Contributions", d["contributions"]),
             ("Active Days", d["active_days"]), ("Languages", len(langs)), ("Followers", d["followers"])]
    cw, cells = W / len(stats), ""
    for i, (k, v) in enumerate(stats):
        cx = cw * i + cw / 2
        cells += f'<text x="{cx}" y="36" text-anchor="middle" font-size="24" fill="{BLUE}">{v}</text>'
        cells += f'<text x="{cx}" y="58" text-anchor="middle" font-size="12" fill="{MUTED}">{k}</text>'
        if i:
            cells += f'<line x1="{cw*i}" y1="14" x2="{cw*i}" y2="62" stroke="#2a475e"/>'
    write("stats.svg", svg(76, cells))

    # 3. featured project
    repos = {r["name"]: r for r in d["repos"]}
    f = repos.get(cfg["featured_repo"]) or (d["repos"][0] if d["repos"] else
                                             {"name": cfg["featured_repo"], "description": "", "language": top, "stars": 0})
    words = f["name"].replace("_", "-").upper().split("-")
    l1 = "-".join(words[:2]) if len(words) > 2 else words[0]
    l2 = " ".join(words[2:]) if len(words) > 2 else " ".join(words[1:])
    desc = wrap(f["description"] or "A selected public project.", 52)
    f_share = dict(langs).get(f["language"], 0)
    write("showcase.svg", svg(250, section("Favorite Project Showcase") + f'''
<rect x="20" y="56" width="400" height="176" fill="url(#cap)"/>
<g opacity=".18" fill="#fff">
  <rect x="320" y="80" width="80" height="26" rx="3"/><rect x="320" y="114" width="80" height="26" rx="3"/><rect x="320" y="148" width="80" height="26" rx="3"/>
  <rect x="296" y="88" width="30" height="10"/><rect x="296" y="122" width="30" height="10"/><rect x="296" y="156" width="30" height="10"/>
</g>
<text x="40" y="150" font-size="{27 if len(l1) <= 13 else 21}" font-weight="800" fill="#fff">{x(l1)}</text>
<text x="40" y="184" font-size="22" font-weight="800" fill="{BLUE}" letter-spacing="3">{x(l2)}</text>
<text x="40" y="214" font-size="11" fill="{TXT}" letter-spacing="2">{x(f["language"].upper())} · {x(cfg["featured_tagline"])}</text>
<text x="450" y="84" font-size="20" fill="#fff">{x(f["name"])}</text>
''' + "".join(f'<text x="450" y="{108+18*i}" font-size="13" fill="{MUTED}">{x(l)}</text>' for i, l in enumerate(desc)) + f'''
<text x="450" y="172" font-size="26" fill="{TXT}">{f_share}%</text>
<text x="450" y="192" font-size="12" fill="{MUTED}">of my public code is {x(f["language"])}</text>
<text x="640" y="172" font-size="26" fill="{TXT}">★ {f["stars"]}</text>
<text x="640" y="192" font-size="12" fill="{MUTED}">Stars</text>
<text x="450" y="222" font-size="12" fill="{GREEN}">▶ View repository</text>
''', defs='<linearGradient id="cap" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0f3b57"/><stop offset=".55" stop-color="#14567a"/><stop offset="1" stop-color="#3b1f5c"/></linearGradient>'))

    # 4. achievements — show 6, unlocked first
    ach = achievements(d)
    unlocked = sum(1 for a in ach if a[2])
    shown = sorted(ach, key=lambda a: not a[2])[:6]
    icons = ""
    for i, (label, col, ok, glyph) in enumerate(shown):
        ax = 20 + i * 76
        fill, op = (col, ".85") if ok else ("#3d4450", "1")
        icons += f'''<g opacity="{1 if ok else .45}">
<rect x="{ax}" y="58" width="64" height="64" rx="3" fill="{fill}" fill-opacity="{op}"/>
<rect x="{ax}" y="58" width="64" height="64" rx="3" fill="url(#shine)"/>
<g transform="translate({ax+32},90)">{glyph}</g></g>
<text x="{ax+32}" y="140" text-anchor="middle" font-size="10" fill="{MUTED}">{x(label)}</text>'''
    rate = round(unlocked * 100 / len(ach))
    nxt = [a[0] for a in ach if not a[2]][:2]
    write("achievements.svg", svg(220, section("Achievement Showcase", f"{unlocked} of {len(ach)} unlocked") + icons + f'''
<line x1="490" y1="60" x2="490" y2="200" stroke="#2a475e"/>
<text x="560" y="96" text-anchor="middle" font-size="30" fill="{TXT}">{d["contributions"]}</text>
<text x="560" y="118" text-anchor="middle" font-size="12" fill="{MUTED}">Contributions</text>
<text x="690" y="96" text-anchor="middle" font-size="30" fill="{TXT}">{d["active_days"]}</text>
<text x="690" y="118" text-anchor="middle" font-size="12" fill="{MUTED}">Active Days</text>
<text x="820" y="96" text-anchor="middle" font-size="30" fill="{TXT}">{rate}%</text>
<text x="820" y="118" text-anchor="middle" font-size="12" fill="{MUTED}">Completion Rate</text>
<rect x="20" y="168" width="450" height="8" rx="4" fill="#0e141b"/>
<rect x="20" y="168" width="{int(450*rate/100)}" height="8" rx="4" fill="url(#prog)"/>
<text x="20" y="200" font-size="12" fill="{MUTED}">{x("Next unlock: " + " · ".join(nxt) if nxt else "All achievements unlocked!")}</text>
''', defs='<linearGradient id="shine" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".25"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/></linearGradient>' + PROG))

    # 5. recent activity — most recently pushed repos
    skip = {d["login"].lower(), cfg["featured_repo"].lower(), *map(str.lower, cfg["exclude_recent"])}
    recent = [r for r in d["repos"] if r["name"].lower() not in skip][: cfg["recent_count"]]
    write("activity-header.svg", svg(40, section("Recent Activity", f'{d["contributions"]} contributions in the last year')))
    palettes = [("#14567a", "#3b1f5c"), ("#2d5f2e", "#1b2838"), ("#a83a24", "#3b1f5c"), ("#5c3b8a", "#1b2838"), ("#0f3b57", "#2d5f2e")]
    for i in range(cfg["recent_count"]):
        if i >= len(recent):  # keep a valid file so README never shows a broken image
            write(f"activity-{i+1}.svg", svg(114, f'<text x="{W/2}" y="62" text-anchor="middle" font-size="13" fill="{MUTED}">No more recent activity</text>'))
            continue
        r = recent[i]
        c1, c2 = palettes[i % len(palettes)]
        share = dict(langs).get(r["language"], 0)
        sub = r["description"] or "Public repository"
        sub = sub if len(sub) <= 70 else sub[:69] + "…"
        write(f"activity-{i+1}.svg", svg(114, f'''
<rect x="16" y="14" width="184" height="86" fill="url(#g)"/>
<text x="108" y="66" text-anchor="middle" font-size="28" font-weight="800" fill="#fff" opacity=".9">{x(initials(r["name"]))}</text>
<text x="108" y="88" text-anchor="middle" font-size="10" fill="#fff" letter-spacing="2" opacity=".75">{x(r["language"].upper())}</text>
<text x="220" y="42" font-size="18" fill="#fff">{x(r["name"])}</text>
<text x="220" y="64" font-size="12" fill="{MUTED}">{x(sub)}</text>
<text x="{W-20}" y="42" text-anchor="end" font-size="12" fill="{MUTED}">last played {days_ago(r["pushed_at"])}</text>
<text x="{W-20}" y="62" text-anchor="end" font-size="12" fill="{GREEN}">★ {r["stars"]} · ▶ open</text>
<text x="220" y="90" font-size="11" fill="{MUTED}">{x(r["language"])} share of my code</text>
<rect x="400" y="82" width="300" height="8" rx="4" fill="#0e141b"/>
<rect x="400" y="82" width="{max(4, int(300*share/100))}" height="8" rx="4" fill="url(#prog)"/>''',
            defs=f'<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>' + PROG))

    # 6. comments
    write("comments.svg", svg(150, section("Comments") + f'''
<rect x="20" y="56" width="{W-40}" height="44" rx="2" fill="#0e141b" stroke="#2a475e"/>
<text x="34" y="83" font-size="13" fill="{MUTED}">Let’s talk about the next build — open to thoughtful teams, ambitious products, useful engineering work.</text>
<rect x="{W-130}" y="110" width="110" height="28" rx="2" fill="url(#btn)"/>
<text x="{W-75}" y="129" text-anchor="middle" font-size="13" fill="#d2efa9">Say hello</text>
''', defs='<linearGradient id="btn" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#75b022"/><stop offset="1" stop-color="#588a1b"/></linearGradient>'))

    # recent repo names for README links
    return [r["name"] for r in recent]


def update_readme_links(readme, login, recent):
    """Point each Recent Activity card at the right repo."""
    if not os.path.exists(readme):
        return
    import re
    s = open(readme, encoding="utf-8").read()
    for i, name in enumerate(recent, 1):
        s = re.sub(rf'<a href="[^"]*"><img src="\./assets/activity-{i}\.svg"',
                   f'<a href="https://github.com/{login}/{name}"><img src="./assets/activity-{i}.svg"', s)
    open(readme, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--login")
    ap.add_argument("--data")
    ap.add_argument("--out", default="assets")
    ap.add_argument("--dump")
    ap.add_argument("--readme", default="README.md")
    a = ap.parse_args()
    if a.data:
        data = json.load(open(a.data))
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not (a.login and token):
            sys.exit("Need --login and a GITHUB_TOKEN/GH_TOKEN env var (or --data file).")
        data = fetch(a.login, token)
    if a.dump:
        json.dump(data, open(a.dump, "w"), indent=2)
    recent = render(data, a.out)
    update_readme_links(a.readme, data["login"], recent)
    print("rendered:", sorted(os.listdir(a.out)), "| recent:", recent)
