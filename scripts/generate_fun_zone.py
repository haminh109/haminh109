from pathlib import Path
import urllib.request
import datetime as dt
import re
import os
import sys

ROWS = 7
CELL = 12
GAP = 3
PAD_X = 18
PAD_Y = 18
TITLE_H = 26
def fetch_contributions(username: str):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("Thiếu GITHUB_TOKEN trong environment.")

    today = dt.date.today()
    start = today - dt.timedelta(days=371)

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                weekday
                contributionCount
                contributionLevel
              }
            }
          }
        }
      }
    }
    """

    payload = {
        "query": query,
        "variables": {
            "login": username,
            "from": f"{start.isoformat()}T00:00:00Z",
            "to": f"{today.isoformat()}T23:59:59Z",
        },
    }

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "fun-zone-generator",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    if "errors" in raw:
        raise RuntimeError(f"GraphQL error: {raw['errors']}")

    user = raw.get("data", {}).get("user")
    if not user:
        raise RuntimeError("Không lấy được user từ GraphQL response.")

    weeks = (
        user["contributionsCollection"]["contributionCalendar"]["weeks"]
    )
    if not weeks:
        raise RuntimeError("Contribution calendar rỗng.")

    level_map = {
        "NONE": 0,
        "FIRST_QUARTILE": 1,
        "SECOND_QUARTILE": 2,
        "THIRD_QUARTILE": 3,
        "FOURTH_QUARTILE": 4,
    }

    cols = len(weeks)
    grid = [[0 for _ in range(cols)] for _ in range(ROWS)]

    for c, week in enumerate(weeks):
        for day in week["contributionDays"]:
            r = int(day["weekday"])
            lvl = level_map.get(day["contributionLevel"], 0)
            if 0 <= r < ROWS:
                grid[r][c] = lvl

    return grid, cols

def theme(mode: str):
    if mode == "dark":
        return {
            "bg": "#0d1117",
            "title": "#c9d1d9",
            "empty": "#161b22",
            "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
            "sep": "#30363d",
            "breakout_ball": "#58a6ff",
            "breakout_paddle": "#1f6feb",
            "brick_fill": "#2ea043",
            "brick_stroke": "#7ee787",
            "maze": "#8b949e",
            "pacman": "#f7df1e",
            "ghost1": "#ff5f56",
            "ghost2": "#ff79c6",
            "ghost3": "#8be9fd",
            "pellet": "#f0f6fc",
        }
    return {
        "bg": "#ffffff",
        "title": "#24292f",
        "empty": "#ebedf0",
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "sep": "#d0d7de",
        "breakout_ball": "#2f81f7",
        "breakout_paddle": "#1f6feb",
        "brick_fill": "#2da44e",
        "brick_stroke": "#1a7f37",
        "maze": "#57606a",
        "pacman": "#bf8700",
        "ghost1": "#cf222e",
        "ghost2": "#bf3989",
        "ghost3": "#0969da",
        "pellet": "#57606a",
    }

def cell_x(col):
    return PAD_X + col * (CELL + GAP)

def cell_y(row):
    return PAD_Y + TITLE_H + row * (CELL + GAP)

def cx(col):
    return cell_x(col) + CELL / 2

def cy(row):
    return cell_y(row) + CELL / 2

def p(col, row):
    return f"{cx(col):.1f},{cy(row):.1f}"

def build_motion_path(points):
    if not points:
        return ""
    s = f"M {p(points[0][0], points[0][1])} "
    for col, row in points[1:]:
        s += f"L {p(col, row)} "
    return s.strip()

def breakout_bricks(left_cols):
    bricks = []
    for r in range(0, 4):
        for c in range(1, max(2, left_cols - 2)):
            if (r + c) % 5 != 0:
                bricks.append((c, r))
    return bricks

def pacman_points(cols, left_cols):
    start = left_cols + 2
    end = cols - 2
    span = max(8, end - start)

    def cc(frac):
        return int(round(start + frac * span))

    return [
        (cc(0.00), 1),
        (cc(0.12), 1),
        (cc(0.12), 4),
        (cc(0.26), 4),
        (cc(0.26), 2),
        (cc(0.41), 2),
        (cc(0.41), 5),
        (cc(0.56), 5),
        (cc(0.56), 1),
        (cc(0.72), 1),
        (cc(0.72), 3),
        (cc(0.87), 3),
        (cc(0.87), 6),
        (cc(1.00), 6),
    ]

def breakout_ball_points(left_cols):
    m = max(8, left_cols - 3)
    return [
        (1, 5),
        (3, 3),
        (6, 1),
        (9, 3),
        (12, 1),
        (m, 4),
        (11, 5),
        (8, 2),
        (5, 4),
        (2, 6),
        (4, 5),
    ]

def paddle_positions(left_cols):
    base_y = cell_y(6) + 1
    w = CELL * 2.8 + GAP * 1.8
    xs = [
        cell_x(1),
        cell_x(4),
        cell_x(7),
        cell_x(max(2, left_cols - 6)),
        cell_x(max(1, left_cols - 9)),
        cell_x(5),
        cell_x(2),
    ]
    return xs, base_y, w

def ghost_shape(x, y, color):
    return f"""
    <g transform="translate({x-6},{y-6})">
      <path d="M 6 0
               C 2.7 0 0 2.7 0 6
               L 0 11
               L 2 9
               L 4 11
               L 6 9
               L 8 11
               L 10 9
               L 12 11
               L 12 6
               C 12 2.7 9.3 0 6 0 Z"
            fill="{color}"/>
      <circle cx="4.2" cy="5" r="1.3" fill="white"/>
      <circle cx="7.8" cy="5" r="1.3" fill="white"/>
      <circle cx="4.5" cy="5.2" r="0.55" fill="#111"/>
      <circle cx="8.1" cy="5.2" r="0.55" fill="#111"/>
    </g>
    """

def pacman_shape(x, y, color, bg):
    return f"""
    <g transform="translate({x},{y})">
      <circle cx="0" cy="0" r="5.6" fill="{color}"/>
      <polygon points="0,0 5.8,-2.7 5.8,2.7" fill="{bg}">
        <animateTransform
          attributeName="transform"
          attributeType="XML"
          type="rotate"
          values="0 0 0;18 0 0;0 0 0;-18 0 0;0 0 0"
          dur="0.45s"
          repeatCount="indefinite"/>
      </polygon>
    </g>
    """

def render_svg(grid, cols, mode: str):
    t = theme(mode)
    left_cols = min(18, max(14, cols // 3))
    width = PAD_X * 2 + cols * (CELL + GAP) - GAP
    height = PAD_Y * 2 + TITLE_H + ROWS * (CELL + GAP) - GAP

    parts = []
    parts.append(f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" role="img" aria-label="Unified GitHub fun zone">""")
    parts.append(f"""<rect width="{width}" height="{height}" fill="{t["bg"]}"/>""")
    parts.append(f"""<text x="{PAD_X}" y="{PAD_Y + 12}" fill="{t["title"]}" font-family="system-ui,Segoe UI,Arial" font-size="14" font-weight="700">Fun Zone — Breakout × Pac-Man</text>""")

    parts.append("<g>")
    for r in range(ROWS):
        for c in range(cols):
            level = grid[r][c]
            color = t["levels"][max(0, min(level, 4))]
            parts.append(
                f"""<rect x="{cell_x(c)}" y="{cell_y(r)}" width="{CELL}" height="{CELL}" rx="3" fill="{color}"/>"""
            )
    parts.append("</g>")

    sep_x = cell_x(left_cols) - GAP // 2
    parts.append(f"""<line x1="{sep_x}" y1="{cell_y(0)-4}" x2="{sep_x}" y2="{cell_y(6)+CELL+4}" stroke="{t["sep"]}" stroke-width="1"/>""")

    parts.append(f"""<text x="{cell_x(0)}" y="{cell_y(0)-8}" fill="{t["title"]}" font-family="system-ui,Segoe UI,Arial" font-size="10" opacity="0.9">BREAKOUT</text>""")
    parts.append(f"""<text x="{cell_x(left_cols+1)}" y="{cell_y(0)-8}" fill="{t["title"]}" font-family="system-ui,Segoe UI,Arial" font-size="10" opacity="0.9">PAC-MAN</text>""")

    bricks = breakout_bricks(left_cols)
    parts.append("<g>")
    for i, (c, r) in enumerate(bricks):
        x = cell_x(c) + 1.2
        y = cell_y(r) + 1.2
        parts.append(
            f"""<rect x="{x}" y="{y}" width="{CELL-2.4}" height="{CELL-2.4}" rx="2" fill="{t["brick_fill"]}" fill-opacity="0.18" stroke="{t["brick_stroke"]}" stroke-opacity="0.55" stroke-width="1"/>"""
        )
    parts.append("</g>")

    paddle_xs, paddle_y, paddle_w = paddle_positions(left_cols)
    values = ";".join(f"{x:.1f}" for x in paddle_xs)
    parts.append(f"""
    <rect x="{paddle_xs[0]:.1f}" y="{paddle_y:.1f}" width="{paddle_w:.1f}" height="5.2" rx="2.6" fill="{t["breakout_paddle"]}">
      <animate attributeName="x" values="{values}" dur="5.8s" repeatCount="indefinite"/>
    </rect>
    """)

    ball_path = build_motion_path(breakout_ball_points(left_cols))
    parts.append(f"""
    <g>
      <circle cx="0" cy="0" r="5.2" fill="{t["breakout_ball"]}">
        <animateMotion dur="5.8s" repeatCount="indefinite" path="{ball_path}"/>
      </circle>
    </g>
    """)

    pp = pacman_points(cols, left_cols)
    maze_d = "M " + " L ".join(p(c, r) for c, r in pp)
    parts.append(f"""<path d="{maze_d}" stroke="{t["maze"]}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none" opacity="0.9"/>""")

    pellets = []
    for c, r in pp[1:-1]:
        pellets.append(f"""<circle cx="{cx(c)}" cy="{cy(r)}" r="1.7" fill="{t["pellet"]}" opacity="0.85"/>""")
    parts.append("<g>" + "".join(pellets) + "</g>")

    pac_path = build_motion_path(pp)
    parts.append(f"""
    <g>
      {pacman_shape(0, 0, t["pacman"], t["bg"])}
      <animateMotion dur="11s" repeatCount="indefinite" path="{pac_path}" rotate="auto"/>
    </g>
    """)

    parts.append(f"""
    <g>
      {ghost_shape(0, 0, t["ghost1"])}
      <animateMotion dur="11s" begin="-1.5s" repeatCount="indefinite" path="{pac_path}" rotate="auto"/>
    </g>
    """)
    parts.append(f"""
    <g>
      {ghost_shape(0, 0, t["ghost2"])}
      <animateMotion dur="11s" begin="-3.2s" repeatCount="indefinite" path="{pac_path}" rotate="auto"/>
    </g>
    """)
    parts.append(f"""
    <g>
      {ghost_shape(0, 0, t["ghost3"])}
      <animateMotion dur="11s" begin="-4.8s" repeatCount="indefinite" path="{pac_path}" rotate="auto"/>
    </g>
    """)

    parts.append("</svg>")
    return "".join(parts)

def main():
    username = sys.argv[1] if len(sys.argv) > 1 else "haminh109"
    grid, cols = fetch_contributions(username)

    out = Path("generated")
    out.mkdir(exist_ok=True)

    (out / "fun-zone-light.svg").write_text(render_svg(grid, cols, "light"), encoding="utf-8")
    (out / "fun-zone-dark.svg").write_text(render_svg(grid, cols, "dark"), encoding="utf-8")

    print(f"Generated SVGs for {username} in ./generated")

if __name__ == "__main__":
    main()
