import json
import os
import time
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

TMP_DIR = os.path.join(BASE_DIR, "tmp")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")

OVERLAY_PIPE = os.path.join(TMP_DIR, "overlay_pipe")
PROGRAM_FILE = os.path.join(TMP_DIR, "current_program.txt")
NEXT_PROGRAM_FILE = os.path.join(TMP_DIR, "next_program.txt")
SCHEDULE_FILE = os.path.join(TMP_DIR, "schedule_next.txt")

WIDTH = int(os.getenv("STREAM_WIDTH", "1280"))
HEIGHT = int(os.getenv("STREAM_HEIGHT", "720"))
STREAM_FPS = int(os.getenv("STREAM_FPS", "25"))
OVERLAY_FPS = int(os.getenv("OVERLAY_FPS", "25"))
FRAME_INTERVAL = 1.0 / (OVERLAY_FPS + 5)
TICKER_FILE = os.path.join(TMP_DIR, "ticker.txt")


def env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SHOW_MUSIC_PILL = env_flag("NEWSICA_SHOW_MUSIC_PILL", default=False)
SHOW_ON_AIR_PANEL = env_flag("NEWSICA_SHOW_ON_AIR_PANEL", default=False)
SHOW_CLOCK_PANEL = env_flag("NEWSICA_SHOW_CLOCK_PANEL", default=False)
SHOW_SCHEDULE_TIMELINE = env_flag("NEWSICA_SHOW_SCHEDULE_TIMELINE", default=False)
SHOW_TICKER = env_flag("NEWSICA_SHOW_TICKER", default=False)
ENABLE_COLOR_TICKER = env_flag("NEWSICA_ENABLE_COLOR_TICKER", default=False)
TICKER_ANIMATION_FPS = int(os.getenv("NEWSICA_TICKER_ANIMATION_FPS", "10"))

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


def read_schedule_items(max_items=5):
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
    from newsica.broadcast.runtime_state import get_current_state
    return get_current_state()


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
FONT_LIVESONG = font(10)
FONT_SMALL = font(16)
FONT_BODY = font(20)
FONT_TITLE = font(26, bold=True)
FONT_CLOCK = font(34, bold=True)

FONT_TIMELINE_LABEL = font(14, bold=True)
FONT_TIMELINE_TIME = font(17, bold=True)
FONT_TIMELINE_TITLE = font(15)
FONT_TIMELINE_TITLE_BOLD = font(15, bold=True)

FONT_TICKER = font(20)
FONT_TICKER_BOLD = font(20, bold=True)

MEASURE_DRAW = ImageDraw.Draw(Image.new("RGBA", (1, 1), (0, 0, 0, 0)))

ON_AIR_BOX = (30, 30, 1010, 145)
CLOCK_BOX = (1080, 30, 1250, 132)
MUSIC_BOX = (995, 145, 1250, 187)
TIMELINE_BOX = (30, 535, 1250, 642)
TICKER_BOX = (0, 676, WIDTH, HEIGHT)
CHAT_BOX = (30, 370, 480, 505)

# Chat state machine globals
CHAT_STATE_IDLE = 0
CHAT_STATE_FADE_IN = 1
CHAT_STATE_DISPLAY = 2
CHAT_STATE_FADE_OUT = 3

_chat_state = CHAT_STATE_IDLE
_chat_msg_data = None
_chat_state_start_time = 0.0
_chat_last_checked_msg_timestamp = 0.0
_chat_opacity = 0
_chat_last_disk_read = 0.0

# Request state machine globals
REQUEST_STATE_IDLE = 0
REQUEST_STATE_FADE_IN = 1
REQUEST_STATE_DISPLAY = 2
REQUEST_STATE_FADE_OUT = 3

_request_state = REQUEST_STATE_IDLE
_request_start_time = 0.0
_request_opacity = 0
_last_seen_request = (None, None)


# Ticker caching globals
_last_ticker_content = None
_last_accent_color = None
_cached_layout = None
_cached_total_width = 0
_cached_static_key = None
_cached_static_frame = None
_cached_clock_key = None
_cached_clock_panel = None
_cached_ticker_strip = None

TAG_COLORS = {
    "ULTIMORA": (239, 68, 68, 255),          # Rosso brillante
    "ULTIM'ORA": (239, 68, 68, 255),
    "SPORT": (34, 197, 94, 255),             # Verde brillante
    "CRONACA": (251, 146, 60, 255),          # Arancione
    "MONDO": (56, 189, 248, 255),            # Celeste
    "ESTERI": (56, 189, 248, 255),
    "POLITICA": (168, 85, 247, 255),         # Viola
    "ECONOMIA": (234, 179, 8, 255),          # Oro/Giallo
    "CULTURA": (236, 72, 153, 255),          # Rosa
    "TECNOLOGIA": (45, 212, 191, 255),        # Turchese/Teal
    "SALUTE": (16, 185, 129, 255),           # Smeraldo
    "LIFESTYLE": (244, 63, 94, 255),         # Rosa scuro/Rose
    "NEWS": (14, 165, 233, 255),             # Blu oceano
    "METEO": (14, 165, 233, 255),
}


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

    bot_msg = "Invia un memo vocale o richiedi un brano al bot Telegram: @NewsicaTV_Bot"
    draw.text(
        (content_x, title_y + 4),
        bot_msg,
        font=FONT_LABEL,
        fill=(148, 163, 184, 255),
    )


def draw_music_pill(draw, xy, music_title, accent):
    if not music_title:
        return

    x1, y1, x2, y2 = xy
    panel_fill = (15, 23, 42, 205)
    label_color = accent[:3] + (245,)
    text_color = (226, 232, 240, 255)

    draw_panel(draw, xy, fill=panel_fill, accent=accent)

    content_x = x1 + 22
    max_width = (x2 - x1) - 38

    draw.text(
        (content_x, y1 + 8),
        "IN RIPRODUZIONE",
        font=FONT_LIVESONG,
        fill=label_color,
    )

    title = ellipsize(draw, music_title, FONT_SMALL, max_width)
    draw.text(
        (content_x, y1 + 24),
        title,
        font=FONT_SMALL,
        fill=text_color,
    )


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
    timeline_end_x = x2 - 100
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


def get_ticker_layout(draw, ticker_text, accent):
    blocks = ticker_text.split("•")
    layout_segments = []
    highlight_font = FONT_TICKER_BOLD if ENABLE_COLOR_TICKER else FONT_TICKER
    
    for b_idx, block in enumerate(blocks):
        block_str = block.strip()
        if not block_str:
            continue
            
        if "In onda:" in block_str or "Tra poco:" in block_str:
            layout_segments.append({
                "text": block_str,
                "font": highlight_font,
                "color": (253, 224, 71, 255) # soft gold/yellow
            })
        else:
            # Raggruppa gli elementi di notizie all'interno di questo blocco
            news_parts = block_str.split("●")
            valid_items = [p.strip() for p in news_parts if p.strip()]
            
            for i, item in enumerate(valid_items):
                subparts = item.split("|")
                clean_subparts = [sp.strip() for sp in subparts if sp.strip()]
                
                if len(clean_subparts) >= 2:
                    tag = clean_subparts[0]
                    title = " | ".join(clean_subparts[1:])
                    
                    tag_upper = tag.upper().strip()
                    tag_color = TAG_COLORS.get(tag_upper, accent) if ENABLE_COLOR_TICKER else (255, 255, 255, 255)
                    
                    layout_segments.append({
                        "text": "● ",
                        "font": highlight_font,
                        "color": tag_color
                    })
                    layout_segments.append({
                        "text": f"{tag} ",
                        "font": highlight_font,
                        "color": tag_color
                    })
                    layout_segments.append({
                        "text": "| ",
                        "font": FONT_TICKER,
                        "color": (148, 163, 184, 255)
                    })
                    layout_segments.append({
                        "text": title,
                        "font": FONT_TICKER,
                        "color": (255, 255, 255, 255)
                    })
                else:
                    layout_segments.append({
                        "text": item,
                        "font": FONT_TICKER,
                        "color": (255, 255, 255, 255)
                    })
                    
                # Separatore interno alle notizie
                if i < len(valid_items) - 1:
                    layout_segments.append({
                        "text": "   •   ",
                        "font": FONT_TICKER,
                        "color": (148, 163, 184, 180)
                    })
                    
        # Separatore tra blocchi principali
        if b_idx < len(blocks) - 1:
            layout_segments.append({
                "text": "   •   ",
                "font": FONT_TICKER,
                "color": (148, 163, 184, 180)
            })
            
    # Misura le larghezze totali dei segmenti
    total_width = 0
    measured_segments = []
    for seg in layout_segments:
        w = text_width(draw, seg["text"], seg["font"])
        measured_segments.append({
            "text": seg["text"],
            "font": seg["font"],
            "color": seg["color"],
            "width": w
        })
        total_width += w
        
    return measured_segments, total_width


def build_ticker_strip(layout_segments, total_width):
    strip_height = TICKER_BOX[3] - TICKER_BOX[1]
    strip = Image.new("RGBA", (max(1, total_width), strip_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(strip)
    x = 0
    y = (strip_height - 24) // 2

    for seg in layout_segments:
        draw.text((x, y), seg["text"], font=seg["font"], fill=seg["color"])
        x += seg["width"]

    return strip


def composite_ticker_slice(image, ticker_strip, dest_x, dest_y):
    src_x1 = max(0, -dest_x)
    src_x2 = min(ticker_strip.width, WIDTH - dest_x)
    if src_x2 <= src_x1:
        return

    slice_image = ticker_strip.crop((src_x1, 0, src_x2, ticker_strip.height))
    image.alpha_composite(slice_image, dest=(max(0, dest_x), dest_y))


def draw_scrolling_ticker(image, accent, ticker_text):
    global _last_ticker_content, _last_accent_color, _cached_layout, _cached_total_width, _cached_ticker_strip

    if not ticker_text:
        return
        
    # Full opacity for text accent color
    accent_text_color = accent[:3] + (255,)
    
    # 3. Check cache invalidation
    if (ticker_text != _last_ticker_content or 
         accent != _last_accent_color or 
         getattr(draw_scrolling_ticker, "_last_color_mode", None) != ENABLE_COLOR_TICKER or
         _cached_layout is None):
        _last_ticker_content = ticker_text
        _last_accent_color = accent
        draw_scrolling_ticker._last_color_mode = ENABLE_COLOR_TICKER
        _cached_layout, _cached_total_width = get_ticker_layout(MEASURE_DRAW, ticker_text, accent_text_color)
        _cached_ticker_strip = build_ticker_strip(_cached_layout, _cached_total_width)
        
    if not _cached_layout or _cached_total_width <= 0 or _cached_ticker_strip is None:
        return
        
    # 4. Compute scroll offset
    speed = 160
    total_cycle = _cached_total_width + WIDTH
    scroll_x = int(time.monotonic() * speed) % total_cycle
    
    # Start coordinate (drawing from right to left)
    start_x = WIDTH - scroll_x
    y = TICKER_BOX[1]

    composite_ticker_slice(image, _cached_ticker_strip, start_x, y)
    wrapped_x = start_x + total_cycle
    if wrapped_x < WIDTH:
        composite_ticker_slice(image, _cached_ticker_strip, wrapped_x, y)


def build_static_overlay_frame(accent, current_program, music_visible, current_music_title, schedule_items):
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    if SHOW_ON_AIR_PANEL:
        draw_on_air_panel(draw, ON_AIR_BOX, current_program, accent)
    if SHOW_CLOCK_PANEL:
        draw_panel(draw, CLOCK_BOX, accent=(255, 255, 255, 155))

    if music_visible:
        draw_music_pill(draw, MUSIC_BOX, current_music_title, accent)

    if SHOW_SCHEDULE_TIMELINE and schedule_items:
        draw_schedule_timeline(draw, TIMELINE_BOX, schedule_items, accent)

    if SHOW_TICKER:
        draw.rectangle(TICKER_BOX, fill=(15, 23, 42, 184))
    return image


def get_static_overlay_frame(accent, current_program, music_visible, current_music_title, schedule_items):
    global _cached_static_key, _cached_static_frame

    schedule_key = tuple(
        (item.get("time", "--:--"), item.get("title", ""))
        for item in schedule_items
    )
    static_key = (
        accent,
        current_program,
        music_visible,
        current_music_title if music_visible else "",
        schedule_key,
    )

    if _cached_static_key != static_key or _cached_static_frame is None:
        _cached_static_key = static_key
        _cached_static_frame = build_static_overlay_frame(
            accent,
            current_program,
            music_visible,
            current_music_title,
            schedule_items,
        )

    return _cached_static_frame.copy()


def get_clock_panel(now):
    global _cached_clock_key, _cached_clock_panel

    if not SHOW_CLOCK_PANEL:
        return None

    clock_key = now.strftime("%H:%M:%S")
    if _cached_clock_key != clock_key or _cached_clock_panel is None:
        x1, y1, x2, y2 = CLOCK_BOX
        panel = Image.new("RGBA", (x2 - x1, y2 - y1), (0, 0, 0, 0))
        draw = ImageDraw.Draw(panel)

        draw.text(
            (20, 12),
            now.strftime("%H:%M"),
            font=FONT_CLOCK,
            fill=(255, 255, 255, 255),
        )
        draw.text(
            (20, 54),
            now.strftime("%d/%m/%Y"),
            font=FONT_LABEL,
            fill=(203, 213, 225, 255),
        )

        _cached_clock_key = clock_key
        _cached_clock_panel = panel

    return _cached_clock_panel


_last_disk_read_time = 0.0
_cached_state = {}
_cached_program = "NEWSICA TV"
_cached_schedule_items = []
_cached_ticker_text = ""


def draw_chat_overlay(image, accent):
    global _chat_state, _chat_state_start_time, _chat_opacity, _chat_msg_data, _chat_last_checked_msg_timestamp, _chat_last_disk_read
    
    now_mono = time.monotonic()
    
    # 1. Rilevamento nuovi messaggi
    if now_mono - _chat_last_disk_read >= 0.5:
        _chat_last_disk_read = now_mono
        from newsica.storage.repositories.editorial_memory_repository import get_memory
        try:
            val = get_memory("latest_chat")
            if val:
                data = json.loads(val)
                msg_timestamp = data.get("timestamp", 0.0)
                if msg_timestamp > _chat_last_checked_msg_timestamp:
                    _chat_last_checked_msg_timestamp = msg_timestamp
                    _chat_msg_data = data
                    _chat_state = CHAT_STATE_FADE_IN
                    _chat_state_start_time = now_mono
        except Exception:
            pass
                
    # 2. Aggiornamento macchina a stati
    if _chat_state == CHAT_STATE_IDLE:
        _chat_opacity = 0
        return
        
    elapsed = now_mono - _chat_state_start_time
    
    if _chat_state == CHAT_STATE_FADE_IN:
        duration = 0.5
        if elapsed >= duration:
            _chat_state = CHAT_STATE_DISPLAY
            _chat_state_start_time = now_mono
            _chat_opacity = 235
        else:
            _chat_opacity = int(235 * (elapsed / duration))
            
    elif _chat_state == CHAT_STATE_DISPLAY:
        duration = 6.0
        _chat_opacity = 235
        if elapsed >= duration:
            _chat_state = CHAT_STATE_FADE_OUT
            _chat_state_start_time = now_mono
            
    elif _chat_state == CHAT_STATE_FADE_OUT:
        duration = 0.5
        if elapsed >= duration:
            _chat_state = CHAT_STATE_IDLE
            _chat_opacity = 0
            _chat_msg_data = None
        else:
            _chat_opacity = int(235 * (1.0 - (elapsed / duration)))
            
    # 3. Rendering della card
    if _chat_opacity > 0 and _chat_msg_data:
        x1, y1, x2, y2 = CHAT_BOX
        w = x2 - x1
        h = y2 - y1
        
        chat_card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(chat_card)
        
        # Disegna il box glassmorphic
        card_draw.rounded_rectangle((0, 0, w, h), radius=2, fill=(15, 23, 42, _chat_opacity))
        card_draw.rectangle((0, 0, 6, h), fill=accent[:3] + (_chat_opacity,))
        
        # Disegna il badge "CHAT LIVE"
        card_draw.text((22, 12), "CHAT LIVE", font=FONT_LABEL, fill=(244, 63, 94, _chat_opacity))
        
        # Scegli colore autore in base al ruolo
        author = _chat_msg_data.get("author", "Anonimo")
        is_mod = _chat_msg_data.get("is_moderator", False)
        is_own = _chat_msg_data.get("is_owner", False)
        is_spon = _chat_msg_data.get("is_sponsor", False)
        
        if is_own:
            author_color = (248, 113, 113, _chat_opacity)  # Rosso chiaro
            role_label = " (Owner)"
        elif is_mod:
            author_color = (74, 222, 128, _chat_opacity)   # Verde chiaro
            role_label = " (Mod)"
        elif is_spon:
            author_color = (192, 132, 252, _chat_opacity)  # Viola chiaro
            role_label = " (Sponsor)"
        else:
            author_color = (56, 189, 248, _chat_opacity)   # Celeste chiaro
            role_label = ""
            
        author_text = f"{author}{role_label}"
        
        # Disegna autore
        card_draw.text((22, 32), author_text, font=FONT_TIMELINE_LABEL, fill=author_color)
        
        # Messaggio wrapped
        message = _chat_msg_data.get("message", "")
        max_text_width = w - 44
        lines = wrap_text_lines(card_draw, message, FONT_SMALL, max_text_width, max_lines=2)
        
        msg_y = 58
        for line in lines:
            card_draw.text((22, msg_y), line, font=FONT_SMALL, fill=(255, 255, 255, _chat_opacity))
            msg_y += 20
            
        # Componi
        image.alpha_composite(chat_card, dest=(x1, y1))


def draw_request_overlay(image, accent, state):
    global _request_state, _request_start_time, _request_opacity, _last_seen_request
    
    requested_by = state.get("requested_by", "")
    requested_title = state.get("requested_title", "")
    
    if not requested_by or not requested_title:
        if _request_state != REQUEST_STATE_IDLE and _request_state != REQUEST_STATE_FADE_OUT:
            _request_state = REQUEST_STATE_FADE_OUT
            _request_start_time = time.monotonic()
    else:
        current_req = (requested_by, requested_title)
        if current_req != _last_seen_request:
            _last_seen_request = current_req
            _request_state = REQUEST_STATE_FADE_IN
            _request_start_time = time.monotonic()
            
    if _request_state == REQUEST_STATE_IDLE:
        _request_opacity = 0
        return
        
    now_mono = time.monotonic()
    elapsed = now_mono - _request_start_time
    
    if _request_state == REQUEST_STATE_FADE_IN:
        duration = 0.8
        if elapsed >= duration:
            _request_state = REQUEST_STATE_DISPLAY
            _request_start_time = now_mono
            _request_opacity = 240
        else:
            _request_opacity = int(240 * (elapsed / duration))
            
    elif _request_state == REQUEST_STATE_DISPLAY:
        duration = 12.0
        _request_opacity = 240
        if elapsed >= duration:
            _request_state = REQUEST_STATE_FADE_OUT
            _request_start_time = now_mono
            
    elif _request_state == REQUEST_STATE_FADE_OUT:
        duration = 0.8
        if elapsed >= duration:
            _request_state = REQUEST_STATE_IDLE
            _request_opacity = 0
        else:
            _request_opacity = int(240 * (1.0 - (elapsed / duration)))
            
    if _request_opacity > 0:
        CARD_WIDTH = 750
        CARD_HEIGHT = 130
        x1 = (WIDTH - CARD_WIDTH) // 2
        y1 = 260
        
        card = Image.new("RGBA", (CARD_WIDTH, CARD_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(card)
        
        draw.rounded_rectangle((0, 0, CARD_WIDTH, CARD_HEIGHT), radius=6, fill=(15, 23, 42, _request_opacity))
        
        # Bordo accent magenta/rosa brillante
        stripe_color = (236, 72, 153, _request_opacity)
        draw.rounded_rectangle((0, 0, 8, CARD_HEIGHT), radius=6, fill=stripe_color)
        
        # Label "NEWSICA TI ASCOLTA!"
        draw.text((25, 15), "NEWSICA TI ASCOLTA!", font=FONT_TIMELINE_LABEL, fill=(244, 63, 94, _request_opacity))
        
        # Testo principale wrapped
        if state.get("current_block") == "telegram_voice" or requested_title == "Messaggio Vocale":
            main_text = f"Stiamo ascoltando un messaggio vocale inviato da {requested_by}"
        else:
            main_text = f"Questo brano \"{requested_title}\" è stato richiesto da {requested_by}"
        max_text_width = CARD_WIDTH - 50
        lines = wrap_text_lines(draw, main_text, FONT_BODY, max_text_width, max_lines=2)
        
        text_y = 42
        for line in lines:
            draw.text((25, text_y), line, font=FONT_BODY, fill=(255, 255, 255, _request_opacity))
            text_y += 28
            
        image.alpha_composite(card, dest=(x1, y1))


def render_frame():
    global _last_disk_read_time, _cached_state, _cached_program, _cached_schedule_items, _cached_ticker_text
    
    now = datetime.now()
    now_mono = time.monotonic()
    
    # Leggiamo dal disco al massimo una volta ogni 1.0 secondo
    if now_mono - _last_disk_read_time >= 1.0:
        _last_disk_read_time = now_mono
        _cached_state = read_state()
        _cached_program = read_text(PROGRAM_FILE, "NEWSICA TV")
        _cached_schedule_items = read_schedule_items()
        _cached_ticker_text = read_text(TICKER_FILE)
        
    state = _cached_state
    current_program = _cached_program
    schedule_items = _cached_schedule_items
    ticker_text = _cached_ticker_text

    block_type = state.get("current_block") or state.get("type") or ""

    if state.get("status") == "SPECIAL_BROADCAST":
        block_type = "trasmissione_straordinaria"

    accent = COLORS_BY_BLOCK.get(block_type, (56, 189, 248, 220))

    current_music_title = " ".join((state.get("current_music_title") or "").split())

    current_segment = state.get("current_segment", "") or ""
    music_visible = SHOW_MUSIC_PILL and current_music_title and (
        block_type == "music_only"
        or current_segment == "music_rotation_until_deadline"
        or current_segment.startswith("music_")
    )

    image = get_static_overlay_frame(
        accent,
        current_program,
        music_visible,
        current_music_title,
        schedule_items,
    )
    clock_panel = get_clock_panel(now)
    if clock_panel is not None:
        image.alpha_composite(clock_panel, dest=(CLOCK_BOX[0], CLOCK_BOX[1]))

    if SHOW_TICKER:
        draw_scrolling_ticker(image, accent, ticker_text)

    draw_chat_overlay(image, accent)
    draw_request_overlay(image, accent, state)

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

    print(f"Overlay Agent avviato. Scrittura frame RGBA su tmp/overlay_pipe a {OVERLAY_FPS}fps (stream {STREAM_FPS}fps).")
    write_frames()
