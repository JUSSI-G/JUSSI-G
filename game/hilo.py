"""Community Higher/Lower card game for a GitHub profile README.

Each guess is made against a freshly shuffled full deck, so every draw is random.
Triggered by a GitHub Action when someone opens an issue titled "hilo|higher"
or "hilo|lower". The guess is read from environment variables (never the
command line, so issue text can't inject anything).

Writes:
  game/state.json   - the scoreboard
  game/table.svg    - animated shuffle + deal of the new card
  README.md         - the block between the HILO markers

Run with `--reset` to start over, or `--render` to only redraw.
"""

import json
import os
import random
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "game" / "state.json"
SVG_FILE = ROOT / "game" / "table.svg"
README_FILE = ROOT / "README.md"
REPO = os.environ.get("GITHUB_REPOSITORY", "JUSSI-G/JUSSI-G")

START = "<!-- HILO:START -->"
END = "<!-- HILO:END -->"

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["♠", "♥", "♦", "♣"]
DECK = [r + s for s in SUITS for r in RANKS]
RNG = random.SystemRandom()


def value(card):
    return RANKS.index(card[:-1])  # 2 low ... A high


# ---------------------------------------------------------------- state ----

def new_state():
    return {"current": RNG.choice(DECK), "previous": None,
            "wins": 0, "losses": 0, "ties": 0, "last": None}


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return new_state()


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def play(state, guess, user):
    old = state["current"]
    deck = [c for c in DECK if c != old]
    RNG.shuffle(deck)          # fresh shuffle every single guess
    new = deck[0]

    a, b = value(old), value(new)
    if a == b:
        result, state["ties"] = "tie", state["ties"] + 1
        msg = f"🤝 {old} → **{new}**. Same rank, it's a tie."
    elif (guess == "higher") == (b > a):
        result, state["wins"] = "win", state["wins"] + 1
        msg = f"✅ {old} → **{new}**. You called it!"
    else:
        result, state["losses"] = "loss", state["losses"] + 1
        msg = f"❌ {old} → **{new}**. Not this time."

    state["previous"], state["current"] = old, new
    state["last"] = {"user": user, "guess": guess, "from": old, "to": new, "result": result}
    return msg


# ----------------------------------------------------------------- svg -----

CARD_W, CARD_H = 100, 133


FONT_B64 = __import__("base64").b64encode((Path(__file__).parent / "cards.woff").read_bytes()).decode()
FS = 174                      # font size where the glyph is ~100x133 px (Noto Sans Symbols 2)
GX = 51 / 1000 * FS          # glyph left bearing
GY = 766 / 1000 * FS         # glyph top above baseline
SUIT_BASE = {"♠": 0x1F0A0, "♥": 0x1F0B0, "♦": 0x1F0C0, "♣": 0x1F0D0}
RANK_OFF = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
            "10": 10, "J": 11, "Q": 13, "K": 14}   # 12 is the Knight, skipped


def glyph(card):
    return chr(SUIT_BASE[card[-1]] + RANK_OFF[card[:-1]])


def _card(ch, x, y):
    # The Unicode glyph on a fill that matches GitHub's page background, so it
    # looks see-through but hides the cards underneath while shuffling.
    return (f'<rect class="bg" x="{x+1}" y="{y+1}" width="{CARD_W-2}" height="{CARD_H-2}" rx="7"/>'
            f'<text class="c" x="{x-GX:.1f}" y="{y+GY:.1f}">{ch}</text>')


def card_face(card, x, y):
    return _card(glyph(card), x, y)


def card_back(x, y):
    return _card(chr(0x1F0A0), x, y)


def render_svg(state):
    W, H = 470, 200
    prev_x, deck_x, deal_x, top = 20, 170, 340, 40
    shuffle_cards = ""
    for i in range(5):
        shuffle_cards += f'<g class="sh sh{i}">{card_back(deck_x, top)}</g>'

    prev = card_face(state["previous"], prev_x, top) if state["previous"] else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Card on the table: {state['current']}">
  <style>
    @font-face {{ font-family: Cards; src: url(data:font/woff;base64,{FONT_B64}) format("woff"); }}
    .c {{ font-family: Cards; font-size: {FS}px; fill: #1f2328; }}
    .bg {{ fill: #ffffff; }}
    @media (prefers-color-scheme: dark) {{ .c {{ fill: #e6edf3; }} .bg {{ fill: #0d1117; }} }}
    .sh, .deal, .flip-back, .flip-front {{ transform-box: fill-box; transform-origin: center; }}
    .sh {{ animation: riffle .55s ease-in-out 3 both; }}
    .sh0 {{ --dx: -46px; --r: -9deg; animation-delay: 0s; }}
    .sh1 {{ --dx: 46px;  --r: 8deg;  animation-delay: .06s; }}
    .sh2 {{ --dx: -30px; --r: -5deg; animation-delay: .12s; }}
    .sh3 {{ --dx: 30px;  --r: 6deg;  animation-delay: .18s; }}
    .sh4 {{ --dx: -14px; --r: -3deg; animation-delay: .24s; }}
    @keyframes riffle {{
      0%, 100% {{ transform: translate(0, 0) rotate(0); }}
      50% {{ transform: translate(var(--dx), -6px) rotate(var(--r)); }}
    }}
    .deal {{ animation: deal .5s cubic-bezier(.3,.7,.3,1) 1.9s both; }}
    @keyframes deal {{ from {{ transform: translateX(0); }} to {{ transform: translateX({deal_x - deck_x}px); }} }}
    .flip-back {{ animation: hide .18s ease-in 2.4s both; }}
    .flip-front {{ animation: show .18s ease-out 2.58s both; }}
    @keyframes hide {{ from {{ transform: scaleX(1); }} to {{ transform: scaleX(0); }} }}
    @keyframes show {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
    .label {{ font: 600 12px -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; fill: #8b949e; letter-spacing: .08em; }}
  </style>
  <text class="label" x="{prev_x + CARD_W/2}" y="24" text-anchor="middle">{'PREVIOUS' if state['previous'] else ''}</text>
  <text class="label" x="{deck_x + CARD_W/2}" y="24" text-anchor="middle">DECK</text>
  <text class="label" x="{deal_x + CARD_W/2}" y="24" text-anchor="middle">ON THE TABLE</text>
  <g class="prev">{prev}</g>
  {shuffle_cards}
  <g class="deal">
    <g class="flip-back">{card_back(deck_x, top)}</g>
    <g class="flip-front">{card_face(state['current'], deck_x, top)}</g>
  </g>
</svg>
"""


# -------------------------------------------------------------- readme -----

def pct(n, total):
    return f"{round(100 * n / total)}%" if total else "–"


def issue_link(guess):
    title = quote(f"hilo|{guess}")
    body = quote("Just press **Create** below, no need to write anything. 🃏\n\nThe deck gets shuffled and the board updates in about a minute.")
    return f"https://github.com/{REPO}/issues/new?title={title}&body={body}"


def render_readme_block(state):
    w, l, t = state["wins"], state["losses"], state["ties"]
    total = w + l + t
    last = state["last"]
    last_line = ""
    if last:
        icon = {"win": "✅", "loss": "❌", "tie": "🤝"}[last["result"]]
        last_line = (f"<sub>Last play: <a href=\"https://github.com/{last['user']}\">@{last['user']}</a> "
                     f"said <b>{last['guess']}</b> on {last['from']} → {last['to']} {icon}</sub>")
    return "\n".join([
        START,
        "## 🃏 Higher or Lower?",
        "",
        "Anyone can play. Will the next card be **higher** or **lower** than the one on the table?",
        "The deck is reshuffled before every draw. Aces are high.",
        "",
        f'<img src="game/table.svg?v={total}" alt="Card on the table: {state["current"]}" width="470">',
        "",
        f"### 👉 [⬆️ Higher]({issue_link('higher')}) &nbsp;&nbsp; [⬇️ Lower]({issue_link('lower')})",
        "",
        "| Wins | Losses | Ties | Games |",
        "|:---:|:---:|:---:|:---:|",
        f"| **{pct(w, total)}** ({w}) | **{pct(l, total)}** ({l}) | {pct(t, total)} ({t}) | {total} |",
        "",
        last_line,
        "",
        "<sub>Clicking opens a pre-filled GitHub issue. Press <b>Create</b> and a GitHub Action shuffles and deals the next card.</sub>",
        END,
    ])


def write_outputs(state):
    SVG_FILE.write_text(render_svg(state), encoding="utf-8")
    text = README_FILE.read_text(encoding="utf-8")
    block = render_readme_block(state)
    if START in text and END in text:
        text = text.split(START)[0] + block + text.split(END, 1)[1]
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    README_FILE.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- main -----

def main():
    if "--reset" in sys.argv:
        state = new_state()
        save_state(state)
        write_outputs(state)
        print("New game started.")
        return
    if "--render" in sys.argv:
        write_outputs(load_state())
        print("Redrawn.")
        return

    title = os.environ.get("ISSUE_TITLE", "").strip().lower()
    user = os.environ.get("ISSUE_USER", "").strip()
    guess = title.split("|", 1)[1].strip() if "|" in title else ""

    if guess not in ("higher", "lower") or not user:
        msg, ok = "🤔 I couldn't read that guess. Use the **Higher** or **Lower** link on the profile and don't edit the title.", False
    else:
        state = load_state()
        msg = play(state, guess, user)
        save_state(state)
        write_outputs(state)
        ok = True

    msg += f"\n\n[Back to the table 🃏](https://github.com/{REPO.split('/')[0]})"
    if os.environ.get("RESULT_FILE"):
        Path(os.environ["RESULT_FILE"]).write_text(msg, encoding="utf-8")
    print(msg)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
