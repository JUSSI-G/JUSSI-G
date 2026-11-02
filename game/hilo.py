import json
import os
import random
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

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
    return RANKS.index(card[:-1])


def new_state():
    return {"current": RNG.choice(DECK), "previous": None, "recent": [],
            "wins": 0, "losses": 0, "ties": 0, "last": None}


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return new_state()


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def quantum_index(n):
    key = os.environ.get("QRNG_API_KEY", "").strip()
    if not key:
        return None
    try:
        req = Request("https://api.quantumnumbers.anu.edu.au?length=16&type=uint16",
                      headers={"x-api-key": key})
        with urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        if not data.get("success"):
            return None
        limit = 65536 - 65536 % n
        for v in data["data"]:
            if 0 <= v < limit:
                return v % n
    except Exception:
        return None
    return None


def play(state, guess, user):
    old = state["current"]
    deck = [c for c in DECK if c != old]
    idx = quantum_index(len(deck))
    if idx is None:
        RNG.shuffle(deck)
        new, source = deck[0], "classical"
    else:
        new, source = deck[idx], "quantum"

    a, b = value(old), value(new)
    if a == b:
        result, state["ties"] = "tie", state["ties"] + 1
        msg = f"## 🤝 It's a tie!\n\n{old} → **{new}**. Same rank, nobody wins this one."
    elif (guess == "higher") == (b > a):
        result, state["wins"] = "win", state["wins"] + 1
        msg = f"## ✅ You won!\n\nYou guessed **{guess}**: {old} → **{new}**."
    else:
        result, state["losses"] = "loss", state["losses"] + 1
        msg = f"## ❌ You lost\n\nYou guessed **{guess}**: {old} → **{new}**. Better luck next time!"

    state["previous"], state["current"] = old, new
    state["recent"] = ([old] + state.get("recent", []))[:3]
    state["last"] = {"guess": guess, "from": old, "to": new, "result": result, "source": source}
    if source == "quantum":
        msg += "\n\nThis card was drawn using quantum vacuum fluctuations measured by the [ANU Quantum Random Numbers](https://quantumnumbers.anu.edu.au) lab."
    return msg


CARD_W, CARD_H = 100, 133


FONT_B64 = __import__("base64").b64encode((Path(__file__).parent / "cards.woff").read_bytes()).decode()
FS = 174
GX = 51 / 1000 * FS
GY = 766 / 1000 * FS
SUIT_BASE = {"♠": 0x1F0A0, "♥": 0x1F0B0, "♦": 0x1F0C0, "♣": 0x1F0D0}
RANK_OFF = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
            "10": 10, "J": 11, "Q": 13, "K": 14}


def glyph(card):
    return chr(SUIT_BASE[card[-1]] + RANK_OFF[card[:-1]])


def _card(ch, x, y):


    return (f'<rect class="bg" x="{x+1}" y="{y+1}" width="{CARD_W-2}" height="{CARD_H-2}" rx="7"/>'
            f'<text class="c" x="{x-GX:.1f}" y="{y+GY:.1f}">{ch}</text>')


def card_face(card, x, y):
    return _card(glyph(card), x, y)


def card_back(x, y):
    return _card(chr(0x1F0A0), x, y)


def render_svg(state):
    W, H = 340, 230
    deck_x, deal_x, top = 60, 220, 40
    last = state.get("last")
    verdict = ""
    if last:
        word, cls = {"win": ("CORRECT!", "win"), "loss": ("WRONG", "loss"), "tie": ("TIE", "tie")}[last["result"]]
        verdict = (f'<text class="guess" x="{W/2}" y="212" text-anchor="middle">LAST GUESS {last["guess"].upper()} THAN {last["from"]}'
                   f'<tspan class="verdict {cls}" dx="10">{word}</tspan></text>')
    shuffle_cards = ""
    for i in range(5):
        shuffle_cards += f'<g class="sh sh{i}">{card_back(deck_x, top)}</g>'

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
    .guess {{ font: 600 13px -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; fill: #8b949e; letter-spacing: .06em; }}
    .verdict {{ font-size: 17px; font-weight: 800; animation: pop .3s ease-out 2.8s both; }}
    .win {{ fill: #2da44e; }} .loss {{ fill: #cf222e; }} .tie {{ fill: #8b949e; }}
    @media (prefers-color-scheme: dark) {{ .win {{ fill: #3fb950; }} .loss {{ fill: #f85149; }} }}
    @keyframes pop {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    .label {{ font: 600 12px -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; fill: #8b949e; letter-spacing: .08em; }}
  </style>
  <text class="label" x="{deck_x + CARD_W/2}" y="24" text-anchor="middle">DECK</text>
  <text class="label" x="{deal_x + CARD_W/2}" y="24" text-anchor="middle">ON THE TABLE</text>
  {shuffle_cards}
  <g class="deal">
    <g class="flip-back">{card_back(deck_x, top)}</g>
    <g class="flip-front">{card_face(state['current'], deck_x, top)}</g>
  </g>
  {verdict}
</svg>
"""


def pct(n, total):
    return f"{round(100 * n / total)}%" if total else "–"


def issue_link(guess):
    title = quote(f"hilo|{guess}")
    body = quote("Just press **Create** below, no need to write anything.\n\nYour result appears here as a comment in about a minute. You can also refresh the profile page to see the new card.")
    return f"https://github.com/{REPO}/issues/new?title={title}&body={body}"


def render_readme_block(state):
    w, l, t = state["wins"], state["losses"], state["ties"]
    total = w + l + t
    return "\n".join([
        START,
        "## Higher or Lower?",
        "",
        "Anyone can play. Will the next card be **higher** or **lower** than the one on the table?",
        "The deck is reshuffled before every draw. Aces are high.",
        "",
        "<picture>",
        f'  <source media="(prefers-color-scheme: dark)" srcset="game/{state["board"]}.svg">',
        f'  <source media="(prefers-color-scheme: light)" srcset="game/{state["board"]}.svg">',
        f'  <img src="game/{state["board"]}.png" alt="Card on the table: {state["current"]}" width="340">',
        "</picture>",
        "",
        *([f"<sub>Recent: {' · '.join(state['recent'])}</sub>", ""] if state.get("recent") else []),
        f"### [▲ Higher]({issue_link('higher')}) &nbsp;&nbsp;·&nbsp;&nbsp; [▼ Lower]({issue_link('lower')})",
        "",
        "<sub><img src=\"icons/cirq.svg\" width=\"14\" height=\"14\" alt=\"\"> Each month's first 100 draws are made using quantum vacuum fluctuations measured by the <a href=\"https://quantumnumbers.anu.edu.au\">ANU Quantum Random Numbers</a> lab, because it creates true randomness (and it's cool).</sub>",
        "",
        f"**Community win rate: {pct(w, total)}**",
        "",
        "**Just played? Give it up to a minute, then refresh the page to see your card.**",
        "",
        "<sub>Clicking opens a pre-filled GitHub issue. Press <b>Create</b> and a GitHub Action shuffles and deals the next card.</sub>",
        END,
    ])


def render_png(state, path):
    from PIL import Image, ImageDraw, ImageFont
    k = 2
    W, H = 340 * k, 230 * k
    deck_x, deal_x, top = 60, 220, 40
    ink = (139, 148, 158, 255)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cards = ImageFont.truetype(str(Path(__file__).parent / "cards.woff"), FS * k)
    label = ImageFont.load_default(12 * k)
    guess_font = ImageFont.load_default(13 * k)
    verdict_font = ImageFont.load_default(17 * k)
    d.text(((deck_x + CARD_W / 2) * k, 24 * k), "DECK", font=label, fill=ink, anchor="ms")
    d.text(((deal_x + CARD_W / 2) * k, 24 * k), "ON THE TABLE", font=label, fill=ink, anchor="ms")
    d.text(((deck_x - GX) * k, (top + GY) * k), chr(0x1F0A0), font=cards, fill=ink, anchor="ls")
    d.text(((deal_x - GX) * k, (top + GY) * k), glyph(state["current"]), font=cards, fill=ink, anchor="ls")
    last = state.get("last")
    if last:
        word, col = {"win": ("CORRECT!", (45, 164, 78, 255)), "loss": ("WRONG", (207, 34, 46, 255)),
                     "tie": ("TIE", ink)}[last["result"]]
        suit_font = ImageFont.truetype(str(Path(__file__).parent / "cards.woff"), 14 * k)
        left = f"GUESSED {last['guess'].upper()} THAN {last['from'][:-1]}"
        suit = last["from"][-1]
        lw = d.textlength(left, font=guess_font)
        sw = d.textlength(suit + " ", font=suit_font)
        vw = d.textlength(word, font=verdict_font)
        gap = 8 * k
        x0 = (W - lw - sw - gap - vw) / 2
        d.text((x0, 212 * k), left, font=guess_font, fill=ink, anchor="ls")
        d.text((x0 + lw, 212 * k), suit, font=suit_font, fill=ink, anchor="ls")
        d.text((x0 + lw + sw + gap, 212 * k), word, font=verdict_font, fill=col, anchor="ls")
    im.save(path, optimize=True)


def write_outputs(state):
    board = f"board-{RNG.getrandbits(32):08x}"
    for old in list(SVG_FILE.parent.glob("board-*")) + [SVG_FILE]:
        old.unlink(missing_ok=True)
    (SVG_FILE.parent / f"{board}.svg").write_text(render_svg(state), encoding="utf-8")
    render_png(state, SVG_FILE.parent / f"{board}.png")
    state["board"] = board
    text = README_FILE.read_text(encoding="utf-8")
    block = render_readme_block(state)
    if START in text and END in text:
        text = text.split(START)[0] + block + text.split(END, 1)[1]
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    README_FILE.write_text(text, encoding="utf-8")


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
        msg, ok = "I couldn't read that guess. Use the **Higher** or **Lower** link on the profile and don't edit the title.", False
    else:
        state = load_state()
        msg = play(state, guess, user)
        save_state(state)
        write_outputs(state)
        ok = True

    msg += f"\n\n[Back to the table](https://github.com/{REPO.split('/')[0]})"
    if os.environ.get("RESULT_FILE"):
        Path(os.environ["RESULT_FILE"]).write_text(msg, encoding="utf-8")
    print(msg)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
