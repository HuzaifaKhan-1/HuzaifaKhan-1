"""Writes the profile stats card from live GitHub data (standard library only).

Usage:  GH_TOKEN=... python stats_card.py <user> <output.svg>
"""
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

SANS = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount } }
      }
    }
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 6, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def graphql(variables):
    req = urllib.request.Request(
        'https://api.github.com/graphql',
        data=json.dumps({'query': QUERY, 'variables': variables}).encode(),
        headers={'Authorization': f"bearer {os.environ['GH_TOKEN']}", 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as res:
        payload = json.load(res)
    if payload.get('errors'):
        raise RuntimeError(payload['errors'])
    return payload['data']['user']


def fetch(login):
    after, stars, langs, colors = None, 0, {}, {}
    while True:
        user = graphql({'login': login, 'after': after})
        repos = user['repositories']
        for repo in repos['nodes']:
            stars += repo['stargazerCount']
            for edge in repo['languages']['edges']:
                name = edge['node']['name']
                langs[name] = langs.get(name, 0) + edge['size']
                colors[name] = edge['node']['color'] or '#94A3B8'
        if not repos['pageInfo']['hasNextPage']:
            break
        after = repos['pageInfo']['endCursor']
    calendar = user['contributionsCollection']['contributionCalendar']
    days = [d['contributionCount'] for w in calendar['weeks'] for d in w['contributionDays']]
    streak = longest = 0
    for count in days:
        streak = streak + 1 if count else 0
        longest = max(longest, streak)
    return {
        'contributions': calendar['totalContributions'], 'streak': longest,
        'repos': repos['totalCount'], 'stars': stars,
        'weeks': [sum(d['contributionCount'] for d in w['contributionDays']) for w in calendar['weeks']],
        'langs': [(n, s, colors[n]) for n, s in sorted(langs.items(), key=lambda kv: -kv[1])[:5]],
    }


def render(data):
    W, H, T = 1000, 256, 12
    css = [
        f'.s{{animation:s {T}s ease-out infinite both}}'
        '@keyframes s{0%{opacity:0;transform:translateY(8px)}8%,92%{opacity:1;transform:translateY(0)}98%,100%{opacity:0;transform:translateY(0)}}',
        f'.b{{animation:b {T}s cubic-bezier(.2,.7,.2,1) infinite both;transform-box:fill-box;transform-origin:50% 100%}}'
        '@keyframes b{0%{transform:scaleY(0)}10%,92%{transform:scaleY(1)}98%,100%{transform:scaleY(0)}}',
        f'.l{{animation:l {T}s ease-out infinite both;transform-box:fill-box;transform-origin:0 50%}}'
        '@keyframes l{0%{transform:scaleX(0)}14%,92%{transform:scaleX(1)}98%,100%{transform:scaleX(0)}}',
        '.sw{animation:sw 6s ease-in-out infinite}'
        '@keyframes sw{0%{transform:translateX(0);opacity:0}15%,85%{opacity:.8}100%{transform:translateX(546px);opacity:0}}',
        '@media (prefers-reduced-motion: reduce){*{animation:none!important}}',
    ]
    out = [
        '<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#22C55E"/><stop offset=".35" stop-color="#06B6D4"/><stop offset=".7" stop-color="#2563EB"/><stop offset="1" stop-color="#7C3AED"/></linearGradient>'
        '<linearGradient id="sky" gradientUnits="userSpaceOnUse" x1="430" x2="976" y1="0" y2="0"><stop offset="0" stop-color="#4ADE80"/><stop offset=".55" stop-color="#22D3EE"/><stop offset="1" stop-color="#3B82F6"/></linearGradient>'
        '<clipPath id="bar"><rect x="24" y="196" width="952" height="10" rx="5"/></clipPath></defs>',
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="#0B1020" stroke="url(#g)" stroke-opacity=".45"/>',
        f'<text x="24" y="30" font-family="{MONO}" font-size="12" fill="#4ADE80">// git log --stats --since=1.year</text>',
    ]

    stats = [('contributions', f"{data['contributions']:,}", '#4ADE80'), ('longest streak', f"{data['streak']}d", '#22D3EE'),
             ('repositories', f"{data['repos']:,}", '#A78BFA'), ('stars earned', f"{data['stars']:,}", '#F472B6')]
    for i, (label, value, col) in enumerate(stats):
        x, y = 24 + (i % 2) * 190, 90 + (i // 2) * 76
        out.append(f'<g class="s" style="animation-delay:{i * .15:.2f}s"><text x="{x}" y="{y}" font-family="{SANS}" font-weight="800" font-size="36" fill="#F8FAFC">{value}</text>'
                   f'<text x="{x}" y="{y + 20}" font-family="{MONO}" font-size="12" fill="{col}">|{label}⟩</text></g>')

    # contribution skyline: one bar per week, real data
    weeks = data['weeks'][-52:]
    top = max(weeks) or 1
    x0, base, tall, step = 430, 170, 126, 546 / max(len(weeks), 1)
    out.append(f'<line x1="{x0}" y1="{base + .5}" x2="976" y2="{base + .5}" stroke="#1E293B"/>')
    for i, count in enumerate(weeks):
        h = max(2, count / top * tall)
        out.append(f'<rect class="b" style="animation-delay:{i * .025:.3f}s" x="{x0 + i * step:.1f}" y="{base - h:.1f}" width="{step - 2:.1f}" height="{h:.1f}" rx="1.5" fill="url(#sky)" opacity="{.45 + .55 * count / top:.2f}"/>')
    out.append(f'<rect class="sw" x="{x0}" y="{base - tall}" width="2" height="{tall}" fill="#86EFAC" opacity="0"/>')
    out.append(f'<text x="976" y="30" text-anchor="end" font-family="{MONO}" font-size="12" fill="#64748B">52 weeks · peak {top}/week</text>')

    # languages: real byte share across public, non-fork repositories
    total = sum(s for _, s, _ in data['langs']) or 1
    x = 24.0
    bar, legend = [], []
    lx = 24
    for name, size, color in data['langs']:
        w = size / total * 952
        pct = size / total * 100
        bar.append(f'<rect x="{x:.1f}" y="196" width="{w:.1f}" height="10" fill="{escape(color)}"/>')
        label = f'{escape(name)} {pct:.1f}%'
        legend.append(f'<circle cx="{lx + 5}" cy="229" r="4.5" fill="{escape(color)}"/><text x="{lx + 15}" y="233.5" font-family="{SANS}" font-size="12.5" fill="#CBD5E1">{label}</text>')
        lx += 190
        x += w
    out.append(f'<g clip-path="url(#bar)"><g class="l" style="animation-delay:.3s">{"".join(bar)}</g></g>{"".join(legend)}')

    summary = (f"GitHub stats: {data['contributions']:,} contributions in the past year, longest streak {data['streak']} days, "
               f"{data['repos']} public repositories, stars earned: {data['stars']}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(summary)}" fill="none">'
            f'<title>{escape(summary)}</title><style>{"".join(css)}</style>{"".join(out)}</svg>')


if __name__ == '__main__':
    with open(sys.argv[2], 'w', encoding='utf-8') as fh:
        fh.write(render(fetch(sys.argv[1])))
