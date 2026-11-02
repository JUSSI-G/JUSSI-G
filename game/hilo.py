import json
import os
import random
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "game" / "state.json"
GAME_DIR = ROOT / "game"
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


FS = 174
GX = 51 / 1000 * FS
GY = 766 / 1000 * FS
SUIT_BASE = {"♠": 0x1F0A0, "♥": 0x1F0B0, "♦": 0x1F0C0, "♣": 0x1F0D0}
RANK_OFF = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
            "10": 10, "J": 11, "Q": 13, "K": 14}


def glyph(card):
    return chr(SUIT_BASE[card[-1]] + RANK_OFF[card[:-1]])


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
        "The deck is reshuffled before every draw. Aces are high. Each month's first 100 draws are made using quantum vacuum fluctuations measured by the <a href=\"https://quantumnumbers.anu.edu.au\">ANU Quantum Random Numbers</a> lab, because it creates true randomness (and it's cool).",
        "",
        f'<img src="game/{state["board"]}.png" alt="Card on the table: {state["current"]}" width="340">',
        "",
        *([f"<sub>Recent: {' · '.join(state['recent'])}</sub>", ""] if state.get("recent") else []),
        f"### [▲ Higher]({issue_link('higher')}) &nbsp;&nbsp;·&nbsp;&nbsp; [▼ Lower]({issue_link('lower')})",
        f"**Community win rate: {pct(w, total)}**",
        "",
        "**Just played? Give it up to a minute, then refresh the page to see your card.**",
        "",
        "<sub>Clicking opens a pre-filled GitHub issue. Press <b>Create</b> and a GitHub Action shuffles and deals the next card.</sub>",
        END,
    ])


K = 2
BOARD_W, BOARD_H = 340, 230
DECK_X, DEAL_X, TOP = 60, 220, 40
INK = (139, 148, 158, 255)
VERDICT = {"win": ("CORRECT!", (45, 164, 78, 255)), "loss": ("WRONG", (207, 34, 46, 255)), "tie": ("TIE", INK)}
SHUFFLE = [(-46, -9, 0.0), (46, 8, 0.06), (-30, -5, 0.12), (30, 6, 0.18), (-14, -3, 0.24)]


def _fonts():
    from PIL import ImageFont
    woff = str(Path(__file__).parent / "cards.woff")
    return {
        "cards": ImageFont.truetype(woff, FS * K),
        "suit": ImageFont.truetype(woff, 14 * K),
        "label": ImageFont.load_default(12 * K),
        "guess": ImageFont.load_default(13 * K),
        "verdict": ImageFont.load_default(17 * K),
    }


def _card_layer(ch, fonts):
    from PIL import Image, ImageDraw
    pad = 4 * K
    w, h = CARD_W * K + 2 * pad, CARD_H * K + 2 * pad
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((pad - GX * K, pad + GY * K), ch, font=fonts["cards"], fill=INK, anchor="ls")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((pad + K, pad + K, w - pad - K, h - pad - K), radius=7 * K, fill=255)
    return layer, mask


def _place(canvas, card, x, y, angle=0.0, scale_x=1.0):
    from PIL import Image
    layer, mask = card
    if scale_x < 0.02:
        return
    if scale_x != 1.0:
        size = (max(1, round(layer.width * scale_x)), layer.height)
        layer, mask = layer.resize(size, Image.BICUBIC), mask.resize(size, Image.BICUBIC)
    if angle:
        layer = layer.rotate(-angle, Image.BICUBIC, expand=True)
        mask = mask.rotate(-angle, Image.BICUBIC, expand=True)
    cx, cy = (x + CARD_W / 2) * K, (y + CARD_H / 2) * K
    canvas.paste(layer, (round(cx - layer.width / 2), round(cy - layer.height / 2)), mask)


def _frame(state, fonts, back, face, t):
    import math
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (BOARD_W * K, BOARD_H * K), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text(((DECK_X + CARD_W / 2) * K, 24 * K), "DECK", font=fonts["label"], fill=INK, anchor="ms")
    d.text(((DEAL_X + CARD_W / 2) * K, 24 * K), "ON THE TABLE", font=fonts["label"], fill=INK, anchor="ms")

    for dx, rot, delay in SHUFFLE:
        local = t - delay
        f = 0.0
        if 0 < local < 1.65:
            f = (1 - math.cos(2 * math.pi * (local % 0.55) / 0.55)) / 2
        _place(im, back, DECK_X + dx * f, TOP - 6 * f, rot * f)

    p = min(max((t - 1.9) / 0.5, 0), 1)
    x = DECK_X + (DEAL_X - DECK_X) * (1 - (1 - p) ** 3)
    if t < 2.58:
        _place(im, back, x, TOP, scale_x=1 - min(max((t - 2.4) / 0.18, 0), 1))
    else:
        _place(im, face, x, TOP, scale_x=min(max((t - 2.58) / 0.18, 0), 1))

    last = state.get("last")
    if last:
        word, col = VERDICT[last["result"]]
        alpha = min(max((t - 2.8) / 0.3, 0), 1)
        left = f"LAST GUESS {last['guess'].upper()} THAN {last['from'][:-1]}"
        suit = last["from"][-1]
        lw = d.textlength(left, font=fonts["guess"])
        sw = d.textlength(suit + " ", font=fonts["suit"])
        vw = d.textlength(word, font=fonts["verdict"])
        gap = 8 * K
        x0 = (BOARD_W * K - lw - sw - gap - vw) / 2
        y0 = 212 * K
        d.text((x0, y0), left, font=fonts["guess"], fill=INK, anchor="ls")
        d.text((x0 + lw, y0), suit, font=fonts["suit"], fill=INK, anchor="ls")
        if alpha > 0:
            d.text((x0 + lw + sw + gap, y0), word, font=fonts["verdict"], fill=col[:3] + (round(255 * alpha),), anchor="ls")
    return im


def render_board(state, path):
    fonts = _fonts()
    back = _card_layer(chr(0x1F0A0), fonts)
    face = _card_layer(glyph(state["current"]), fonts)
    step = 0.08
    times = [i * step for i in range(int(3.1 / step) + 2)]
    frames = [_frame(state, fonts, back, face, t) for t in times]
    still = _frame(state, fonts, back, face, 10)
    durations = [0] + [step * 1000] * (len(frames) - 1) + [10000]
    from PIL import Image
    allf = [still] + frames
    w, h = still.size
    sheet = Image.new("RGBA", (w, h * len(allf)))
    for i, f in enumerate(allf):
        sheet.paste(f, (0, i * h))
    sheet = sheet.quantize(colors=64, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    small = [sheet.crop((0, i * h, w, (i + 1) * h)) for i in range(len(allf))]
    small[0].save(path, save_all=True, append_images=small[1:], default_image=True,
                  duration=durations, loop=1, optimize=True)


def write_outputs(state):
    board = f"board-{RNG.getrandbits(32):08x}"
    for old in list(GAME_DIR.glob("board-*")) + [GAME_DIR / "table.svg"]:
        old.unlink(missing_ok=True)
    render_board(state, GAME_DIR / f"{board}.png")
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