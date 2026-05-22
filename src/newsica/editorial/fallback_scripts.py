import re


def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def wellness_fallback_for_title(title):
    normalized = clean_text(title).lower()
    if "ufficio" not in normalized and "scrivania" not in normalized:
        return None

    return "\n\n[MUSIC_BREAK]\n\n".join([
        (
            "È il momento del benessere su NewsicaTV. Piccole idee per stare meglio, ogni giorno.\n\n"
            "Oggi parliamo di esercizi per l'ufficio: gesti semplici, da fare alla scrivania, "
            "senza trasformare la giornata in una seduta di palestra. Si parte dalle spalle. "
            "Appoggiamo bene i piedi, lasciamo scendere le braccia e facciamo qualche rotazione lenta, "
            "prima in avanti e poi indietro. Il punto non è forzare, ma sciogliere quella rigidità "
            "che arriva dopo tante ore davanti allo schermo.\n\n"
            "Ora lasciamo respirare anche la musica. Tra poco torniamo con una pausa attiva da meno di un minuto."
        ),
        (
            "Eccoci di nuovo insieme. Una pausa attiva in ufficio può essere piccolissima: "
            "alzarsi, fare due passi, aprire il petto e guardare per qualche secondo lontano dal monitor. "
            "Anche il collo ringrazia se lo muoviamo con calma, portando lo sguardo a destra e a sinistra "
            "senza scatti. Sono movimenti quotidiani, non prestazioni.\n\n"
            "Ci prendiamo un altro brano, e poi chiudiamo con un esercizio di respirazione discreto, da fare anche tra una riunione e l'altra."
        ),
        (
            "Rientriamo in studio per l'ultimo consiglio del giorno. Prima di riprendere il lavoro, "
            "proviamo tre respiri lenti: inspiriamo dal naso, lasciamo espandere il torace, poi espiriamo senza fretta. "
            "Se possiamo, aggiungiamo una piccola estensione delle gambe sotto la scrivania, alternando destra e sinistra. "
            "Pochi secondi, ma ripetuti nella giornata fanno la differenza nella percezione di leggerezza.\n\n"
            "Per ora è tutto. Prendiamoci una piccola pausa, e continuiamo a volerci bene."
        ),
    ])


def build_fallback_script(character_id, filtered_news, title=None):
    if character_id == "wellness" and title:
        themed_script = wellness_fallback_for_title(title)
        if themed_script:
            return themed_script

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
    elif character_id == "podcast":
        news_items = filtered_news[:3]
        lines = [
            "[SPEAKER: Giulia] Benvenuti a Newsica Podcast. Oggi ci prendiamo qualche minuto in più per capire meglio alcune storie emerse nelle ultime ore, andando un po' oltre il titolo secco.",
            "[SPEAKER: Marco] Ciao Giulia. Sì, perché spesso la differenza sta proprio lì: non solo sapere che cosa è successo, ma capire il contesto, le conseguenze e il motivo per cui una notizia continua a far discutere.",
        ]
        for index, item in enumerate(news_items):
            title = clean_text(item.get("title", ""))
            summary = clean_text(item.get("summary", ""))
            if not title and not summary:
                continue
            if index % 2 == 0:
                lines.append(f"[SPEAKER: Giulia] Partiamo da questo tema: {title}. {summary} È una notizia che merita attenzione non solo per il fatto in sé, ma anche per quello che racconta del clima più generale in cui si sta muovendo questa vicenda.")
                lines.append("[SPEAKER: Marco] Ed è proprio qui che vale la pena fermarsi un momento. Quando una storia entra così nel dibattito pubblico, spesso significa che tocca abitudini, equilibri o aspettative che riguardano molte più persone di quanto sembri a un primo ascolto.")
            else:
                lines.append(f"[SPEAKER: Marco] Il punto interessante è proprio qui: {title}. {summary} Dietro questa notizia c'è anche una chiave di lettura più ampia, che aiuta a capire perché se ne stia parlando così tanto e che cosa potrebbe cambiare da qui in avanti.")
                lines.append("[SPEAKER: Giulia] E infatti, quando guardiamo questi passaggi con un po' più di calma, emerge meglio il quadro complessivo. Non è solo una sequenza di aggiornamenti, ma un racconto che si costruisce pezzo dopo pezzo e che va seguito con continuità.")
        lines.append("[SPEAKER: Giulia] Per questa conversazione è tutto. Abbiamo provato a mettere in fila i fatti con un po' più di respiro, senza fermarci alla superficie. Restate con noi, la programmazione di NewsicaTV continua.")
        return "\n".join(lines)
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
