import re


def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def build_fallback_script(character_id, filtered_news):
    if character_id == "sport":
        opening = "Un saluto a tutti gli appassionati di sport! Oggi giornata ricca di emozioni."
        music_launch = "E adesso, carichiamo i motori con un po' di musica! A tra poco."
        reentry = "Di nuovo insieme su NewsicaTV! Continuiamo il nostro viaggio nello sport."
        closing = "Per lo sport è tutto. Restate con noi su NewsicaTV."
    elif character_id == "wellness":
        opening = "È il momento del benessere su NewsicaTV. Piccole idee per stare meglio, ogni giorno."
        music_launch = "Ora una piccola pausa per rilassarci con un buon brano. A tra poco."
        reentry = "Eccoci di nuovo insieme, sintonizzati su NewsicaTV. Proseguiamo."
        closing = "Per ora è tutto. Prendiamoci una piccola pausa, e continuiamo a volerci bene."
    elif character_id == "meteo":
        opening = "Ed eccoci agli aggiornamenti meteo nazionali. Vediamo la situazione sulla nostra Penisola per le prossime ore."
        closing = "Per il meteo nazionale è tutto. Restate con noi per la nostra programmazione musicale."
    else:
        opening = "Benritrovati in diretta su NewsicaTV. Ecco gli aggiornamenti di oggi."
        music_launch = "Ed ora, spazio alla musica su NewsicaTV. Ci risentiamo tra poco."
        reentry = "Rieccoci in diretta su NewsicaTV, continuiamo con le nostre notizie."
        closing = "Per questa edizione è tutto. Restate con noi per la nostra programmazione musicale."

    transitions = {
        "news": ["In apertura,", "Nel frattempo,", "Passiamo ora a un altro aggiornamento,", "Da segnalare anche,"],
        "sport": ["Partiamo dal campo,", "Occhio anche a questa notizia,", "Restiamo sullo sport,", "Chiudiamo con un altro aggiornamento,"],
        "wellness": ["Partiamo da una piccola abitudine,", "C'è poi uno spunto interessante,", "Pensiamo anche alla cura quotidiana,", "Chiudiamo con un'idea semplice,"],
        "meteo": ["Partendo dal Nord Italia,", "Spostiamoci ora al Centro della nostra Penisola,", "E per finire diamo uno sguardo al Meridione e alle Isole,", "In sintesi,"],
    }

    if character_id == "meteo":
        lines = [opening]
        for index, item in enumerate(filtered_news[:4]):
            title = clean_text(item.get("title", ""))
            summary = clean_text(item.get("summary", ""))
            transition = transitions.get(character_id, transitions["news"])[index]
            if title and summary:
                lines.append(f"{transition} {title}. {summary}")
            elif title:
                lines.append(f"{transition} {title}.")
        if len(lines) == 1:
            lines.append("Al momento non ci sono nuovi aggiornamenti verificati per questa rubrica.")
        lines.append(closing)
        return "\n\n".join(lines)

    news_items = filtered_news[:4]
    if not news_items:
        return f"{opening}\n\nAl momento non ci sono nuovi aggiornamenti verificati.\n\n{closing}"

    parts_text = []
    for index, item in enumerate(news_items):
        title = clean_text(item.get("title", ""))
        summary = clean_text(item.get("summary", ""))
        transition = transitions.get(character_id, transitions["news"])[index]
        content = f"{transition} {title}. {summary}" if title and summary else f"{transition} {title}."

        if index == 0:
            parts_text.append(f"{opening}\n\n{content}\n\n{music_launch}")
        elif index == len(news_items) - 1:
            parts_text.append(f"{reentry}\n\n{content}\n\n{closing}")
        else:
            parts_text.append(f"{reentry}\n\n{content}\n\n{music_launch}")

    return "\n\n[MUSIC_BREAK]\n\n".join(parts_text)

