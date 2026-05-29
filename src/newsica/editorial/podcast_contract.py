import re

PODCAST_MIN_WORDS = 420
PODCAST_MIN_SEGMENTS = 8
PODCAST_MAX_SEGMENTS = 18
PODCAST_ALLOWED_ENDING_PUNCTUATION = (".", "!", "?", "…")
PODCAST_CLOSING_MARKERS = (
    "grazie",
    "alla prossima",
    "al prossimo appuntamento",
    "ci ritroviamo",
    "ci risentiamo",
    "buona musica",
    "newsicatv",
    "chi ci ha seguito",
    "chi ci ha ascoltato",
)


def parse_podcast_segments(script_text):
    script_text = script_text or ""
    pattern = re.compile(r"\[SPEAKER:\s*([^\]]+)\]")
    matches = list(pattern.finditer(script_text))
    segments = []

    for idx, match in enumerate(matches):
        speaker = match.group(1).strip()
        start_idx = match.end()
        end_idx = matches[idx + 1].start() if idx + 1 < len(matches) else len(script_text)
        text_content = (script_text[start_idx:end_idx] or "").strip()
        if text_content:
            segments.append((speaker, text_content))

    return segments


def validate_podcast_script(script_text):
    issues = []
    normalized_text = (script_text or "").strip()

    if not normalized_text:
        return False, ["copione vuoto"]

    if "[MUSIC_BREAK]" in normalized_text:
        issues.append("il podcast contiene [MUSIC_BREAK], ma la pipeline live gestisce una puntata unica continua")

    segments = parse_podcast_segments(normalized_text)
    if len(segments) < PODCAST_MIN_SEGMENTS:
        issues.append(
            f"turni insufficienti: trovati {len(segments)}, richiesti almeno {PODCAST_MIN_SEGMENTS}"
        )
    if len(segments) > PODCAST_MAX_SEGMENTS:
        issues.append(
            f"turni eccessivi: trovati {len(segments)}, massimo consigliato {PODCAST_MAX_SEGMENTS}"
        )

    words = re.findall(r"\b[\wÀ-ÿ']+\b", normalized_text, flags=re.UNICODE)
    if len(words) < PODCAST_MIN_WORDS:
        issues.append(
            f"copione troppo corto: trovate {len(words)} parole, richieste almeno {PODCAST_MIN_WORDS}"
        )

    if segments:
        closing_window = " ".join(text for _, text in segments[-3:]).lower()
    else:
        closing_window = normalized_text.lower()

    if not closing_window.endswith(PODCAST_ALLOWED_ENDING_PUNCTUATION):
        issues.append("il copione non termina con una frase completa")

    if not any(marker in closing_window for marker in PODCAST_CLOSING_MARKERS):
        issues.append("manca una chiusura naturale con saluto o passaggio finale alla musica")

    return not issues, issues


def build_podcast_revision_prompt(validation_issues):
    issues_text = "; ".join(validation_issues)
    return (
        "CORREZIONE OBBLIGATORIA DEL PODCAST:\n"
        f"- Il precedente output non e' valido: {issues_text}.\n"
        "- Riscrivi da zero un podcast completo, non un'aggiunta o una continuazione.\n"
        "- Mantieni il formato a turni con i tag [SPEAKER: Giulia] e [SPEAKER: Marco].\n"
        "- Sviluppa un vero dialogo di almeno 420 parole e almeno 8 turni.\n"
        "- Non inserire [MUSIC_BREAK] e non promettere una ripresa dopo la musica.\n"
        "- Negli ultimi 2-3 turni accompagna l'ascoltatore verso una chiusura naturale e un lancio finale alla musica di NewsicaTV."
    )
