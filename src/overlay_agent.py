import json
import os
import time
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")

OVERLAY_PIPE = os.path.join(TMP_DIR, "overlay_pipe")
PROGRAM_FILE = os.path.join(TMP_DIR, "current_program.txt")
NEXT_PROGRAM_FILE = os.path.join(TMP_DIR, "next_program.txt")
SCHEDULE_FILE = os.path.join(TMP_DIR, "schedule_next.txt")
STATE_FILE = os.path.join(RUNTIME_DIR, "on-air-state.json")

WIDTH = 1280
HEIGHT = 720
FPS = 1
FRAME_INTERVAL = 1.0 / FPS

COLORS_BY_BLOCK = {
    "breaking_news": (239, 68, 68, 230),
    "trasmissione_straordinaria": (239, 68, 68, 230),
    "flash_60s": (248, 113, 113, 220),
    "news": (56, 189, 248, 220),
    "sport": (34, 197, 94, 220),
    "meteo": (14, 165, 233, 220),
    "wellness": (45, 212, 191, 220),
    "podcast": (251, 146, 60, 220),
    "music_only": (168, 85, 247, 220),
}


def read_text(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return " ".join(f.read().strip().split()) or default
    except OSError:
        return default


def read_schedule_items(max_items=4):
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            raw = f.read().strip()
    except OSError:
        return []

    if not raw:
        return []

    raw = raw.replace("\r\n", "\n").replace("\r", "\n")

    lines = [" ".join(line.split()) for line in raw.splitlines() if line.strip()]

    if lines and lines[0].upper() == "PROSSIMI EVENTI":
        lines = lines[1:]

    entries = []

    for line in lines:
        parts = [part.strip() for part in line.split("|") if part.strip()]
        entries.extend(parts)

    items = []

    for entry in entries[:max_items]:
        parts = entry.split(" ", 1)

        if len(parts) == 2 and ":" in parts[0]:
            time_part = parts[0].strip()
            title_part = parts[1].strip()
        else:
            time_part = "--:--"
            title_part = entry.strip()

        if not title_part:
            continue

        items.append(
            {
                "time": time_part,
                "title": title_part,
            }
        )

    return items


def read_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size, index=1 if bold else 0)
        except OSError:
            continue

    return ImageFont.load_default()


FONT_LABEL = font(14)
FONT_SMALL = font(16)
FONT_BODY = font(20)
FONT_TITLE = font(26, bold=True)
FONT_CLOCK = font(34, bold=True)

FONT_TIMELINE_LABEL = font(14, bold=True)
FONT_TIMELINE_TIME = font(17, bold=True)
FONT_TIMELINE_TITLE = font(15)
FONT_TIMELINE_TITLE_BOLD = font(15, bold=True)


def text_width(draw, text, selected_font):
    box = draw.textbbox((0, 0), text, font=selected_font)
    return box[2] - box[0]


def ellipsize(draw, text, selected_font, max_width):
    if text_width(draw, text, selected_font) <= max_width:
        return text

    suffix = "."
    low = 0
    high = len(text)

    while low < high:
        mid = (low + high + 1) // 2
        candidate = text[:mid].rstrip() + suffix

        if text_width(draw, candidate, selected_font) <= max_width:
            low = mid
        else:
            high = mid - 1

    return text[:low].rstrip() + suffix


def wrap_text_lines(draw, text, selected_font, max_width, max_lines=2):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()

        if text_width(draw, candidate, selected_font) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)

        current = word

        if len(lines) >= max_lines:
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    lines = lines[:max_lines]

    if lines:
        last_index = len(lines) - 1
        lines[last_index] = ellipsize(
            draw,
            lines[last_index],
            selected_font,
            max_width,
        )

    return lines


def draw_panel(draw, xy, fill=(15, 23, 42, 235), accent=(56, 189, 248, 220)):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=2, fill=fill)
    draw.rectangle((x1, y1, x1 + 6, y2), fill=accent)


def draw_on_air_panel(draw, xy, current_program, accent):
    x1, y1, x2, y2 = xy

    draw_panel(draw, xy, accent=accent)

    content_x = x1 + 22
    max_width = (x2 - x1) - 44

    draw.text(
        (content_x, y1 + 12),
        "ON AIR",
        font=FONT_LABEL,
        fill=(252, 165, 165, 255),
    )

    title = current_program.upper().strip()

    title_lines = wrap_text_lines(
        draw,
        title,
        FONT_TITLE,
        max_width,
        max_lines=2,
    )

    title_y = y1 + 38

    for line in title_lines:
        draw.text(
            (content_x, title_y),
            line,
            font=FONT_TITLE,
            fill=(255, 255, 255, 255),
        )
        title_y += 30


def draw_schedule_timeline(draw, xy, items, accent):
    if not items:
        return

    x1, y1, x2, y2 = xy

    panel_fill = (15, 23, 42, 235)
    text_primary = (255, 255, 255, 255)
    text_secondary = (203, 213, 225, 255)
    line_color = (148, 163, 184, 150)
    label_color = (125, 211, 252, 255)

    draw_panel(draw, xy, fill=panel_fill, accent=accent)

    label_x = x1 + 22
    label_y = y1 + 18

    draw.text(
        (label_x, label_y),
        "A SEGUIRE",
        font=FONT_TIMELINE_LABEL,
        fill=label_color,
    )

    timeline_start_x = x1 + 175
    timeline_end_x = x2 - 42
    timeline_y = y1 + 24

    event_count = len(items)

    if event_count == 1:
        marker_positions = [(timeline_start_x + timeline_end_x) // 2]
    else:
        available_width = timeline_end_x - timeline_start_x
        marker_positions = [
            int(timeline_start_x + (available_width * index / (event_count - 1)))
            for index in range(event_count)
        ]

    draw.line(
        (timeline_start_x, timeline_y, timeline_end_x, timeline_y),
        fill=line_color,
        width=3,
    )

    for index, item in enumerate(items):
        marker_x = marker_positions[index]
        is_next = index == 0

        marker_radius = 7 if is_next else 5
        marker_fill = accent if is_next else (226, 232, 240, 230)

        if is_next:
            glow = accent[:3] + (70,)
            draw.ellipse(
                (
                    marker_x - 15,
                    timeline_y - 15,
                    marker_x + 15,
                    timeline_y + 15,
                ),
                fill=glow,
            )

        draw.ellipse(
            (
                marker_x - marker_radius,
                timeline_y - marker_radius,
                marker_x + marker_radius,
                timeline_y + marker_radius,
            ),
            fill=marker_fill,
        )

        slot_width = 200

        time_text = item.get("time", "--:--")
        title_text = item.get("title", "").strip()

        time_w = text_width(draw, time_text, FONT_TIMELINE_TIME)

        draw.text(
            (marker_x - time_w // 2, y1 + 38),
            time_text,
            font=FONT_TIMELINE_TIME,
            fill=text_primary,
        )

        title_font = FONT_TIMELINE_TITLE_BOLD if is_next else FONT_TIMELINE_TITLE

        title_lines = wrap_text_lines(
            draw,
            title_text,
            title_font,
            slot_width,
            max_lines=3,
        )

        line_y = y1 + 60

        for line in title_lines:
            line_w = text_width(draw, line, title_font)

            draw.text(
                (marker_x - line_w // 2, line_y),
                line,
                font=title_font,
                fill=text_secondary,
            )

            line_y += 16


def render_frame():
    now = datetime.now()
    state = read_state()

    block_type = state.get("current_block") or state.get("type") or ""

    if state.get("status") == "SPECIAL_BROADCAST":
        block_type = "trasmissione_straordinaria"

    accent = COLORS_BY_BLOCK.get(block_type, (56, 189, 248, 220))

    current_program = read_text(PROGRAM_FILE, "NEWSICA TV")
    schedule_items = read_schedule_items()

    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw_on_air_panel(
        draw,
        (30, 30, 1010, 132),
        current_program,
        accent,
    )

    draw_panel(draw, (1080, 30, 1250, 132), accent=(255, 255, 255, 155))

    draw.text(
        (1100, 42),
        now.strftime("%H:%M"),
        font=FONT_CLOCK,
        fill=(255, 255, 255, 255),
    )

    draw.text(
        (1100, 84),
        now.strftime("%d/%m/%Y"),
        font=FONT_LABEL,
        fill=(203, 213, 225, 255),
    )

    if schedule_items:
        draw_schedule_timeline(
            draw,
            (30, 535, 1250, 642),
            schedule_items,
            accent,
        )

    return image


def write_frames():
    os.makedirs(TMP_DIR, exist_ok=True)

    if not os.path.exists(OVERLAY_PIPE):
        os.mkfifo(OVERLAY_PIPE)

    while True:
        try:
            with open(OVERLAY_PIPE, "wb", buffering=0) as pipe:
                while True:
                    start = time.monotonic()

                    pipe.write(render_frame().tobytes("raw", "RGBA"))

                    elapsed = time.monotonic() - start
                    time.sleep(max(0.0, FRAME_INTERVAL - elapsed))
        except BrokenPipeError:
            time.sleep(0.5)


def check_singleton(name):
    import fcntl

    os.makedirs(RUNTIME_DIR, exist_ok=True)

    lock_file_path = os.path.join(RUNTIME_DIR, f"{name}.lock")

    try:
        f = open(lock_file_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.write(str(os.getpid()))
        f.flush()
        return f
    except (IOError, OSError):
        print(f"ERRORE: Un'altra istanza di {name} e' gia' in esecuzione.")
        return None


if __name__ == "__main__":
    lock = check_singleton("overlay_agent")

    if not lock:
        raise SystemExit(1)

    print("Overlay Agent avviato. Scrittura frame RGBA su tmp/overlay_pipe.")
    write_frames()