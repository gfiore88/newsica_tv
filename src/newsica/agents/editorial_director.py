import os
import json
import random
import logging
import requests
from datetime import date
from newsica.editorial.memory import add_music_title, get_recent_music_titles
from newsica.utils.audit_logger import log_decision

logger = logging.getLogger(__name__)


class EditorialDirectorAgent:
    """
    Il "Cervello Pensante" di NewsicaTV.
    Usa Ollama per inventare un palinsesto giornaliero imprevedibile e dinamico
    e per generare prompt musicali avanzati per ACE-Step.
    """

    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = os.getenv("OLLAMA_MODEL", "gemma3:12b")

        # Palinsesto di emergenza in caso di crash dell'LLM.
        self.fallback_schedule = {
            "00:00": {"title": "Newsica Night", "type": "music_only"},
            "06:00": {"title": "Morning News", "type": "news"},
            "08:00": {"title": "Sport Flash", "type": "sport"},
            "09:00": {"title": "Mondo in 60 Secondi", "type": "flash_60s"},
            "10:00": {"title": "Meteo Update", "type": "meteo"},
            "12:00": {"title": "Pranzo News", "type": "news"},
            "14:00": {"title": "Pomeriggio Sport", "type": "sport"},
            "15:00": {"title": "Newsica Podcast", "type": "podcast"},
            "16:00": {"title": "Tech in 60 Secondi", "type": "flash_60s"},
            "18:00": {"title": "Riepilogo Giornata", "type": "news"},
            "20:00": {"title": "Newsica Sera", "type": "news"},
            "21:00": {"title": "Newsica Podcast", "type": "podcast"},
            "22:00": {"title": "Meteo Notte", "type": "meteo"},
        }

        # Fallback ACE-Step più solido del vecchio prompt a tag.
        self.fallback_music_prompt = """
Create a modern 60-second instrumental electro pop song.

Mood: clean, energetic, optimistic, radio-friendly.
Tempo: 118 BPM.
Style: modern electro pop with polished synths, punchy drums, deep bass and a catchy instrumental hook.
Production: streaming-ready mix, clean low end, wide stereo image, bright synth layers, smooth transitions and polished mastering.
Instruments: electronic drums, synth bass, bright pluck synths, warm pads, subtle risers.

Structure:
0:00 - 0:08 short intro with filtered synth and soft percussion.
0:08 - 0:25 main groove with drums, bass and melodic synth pattern.
0:25 - 0:38 build with rising energy and additional rhythmic layers.
0:38 - 0:52 main hook with full beat and catchy lead synth melody.
0:52 - 1:00 final hook continues while fading out smoothly.

Vocals:
No vocals. Instrumental only. No spoken words.

Lyrics:
No lyrics.

Ending:
The final 8 seconds must fade out smoothly and naturally. No abrupt ending. No spoken outro.

Negative prompt:
low quality, distorted vocals, out of tune vocals, bad timing, messy mix, muddy bass, harsh highs, old-fashioned arrangement, theatrical singing, opera vocals, excessive vibrato, abrupt ending, spoken outro, crackle, noise, clipping, overcompressed, random tempo changes, long silence
""".strip()

    def get_daily_pillars(self) -> dict:
        return {
            "07:00": {"title": "Morning News: Il Risveglio", "type": "news"},
            "13:00": {"title": "Pranzo News: Il Punto delle 13", "type": "news"},
            "20:00": {"title": "Newsica Sera: Il TG Principale", "type": "news"},
        }

    def get_weekly_appointments(self, current_date: date) -> dict:
        weekday = current_date.weekday()
        appointments = {}

        # 0=Lunedì, 1=Martedì, 2=Mercoledì, 3=Giovedì, 4=Venerdì, 5=Sabato, 6=Domenica
        if weekday == 4:
            appointments["21:00"] = {
                "title": "Speciale Tecnologia (Settimanale)",
                "type": "podcast",
            }
        elif weekday == 6:
            appointments["10:00"] = {
                "title": "Domenica Sport e Benessere",
                "type": "wellness",
            }

        return appointments

    @staticmethod
    def _normalize_music_title(title: str) -> str:
        return " ".join((title or "").strip().lower().split())

    @staticmethod
    def _music_title_tokens(title: str) -> set[str]:
        stopwords = {
            "the", "a", "an", "of", "and", "for", "to", "in", "on",
            "radio", "mix", "edit", "version", "song", "track",
        }
        tokens = {
            token
            for token in EditorialDirectorAgent._normalize_music_title(title).replace("-", " ").split()
            if len(token) > 2 and token not in stopwords
        }
        return tokens

    def _is_music_title_too_similar(self, title: str, recent_titles: list[str]) -> bool:
        normalized = self._normalize_music_title(title)
        if not normalized:
            return True

        title_tokens = self._music_title_tokens(title)
        dominant_words = {
            "pulse", "beat", "beats", "neon", "electric", "vibes",
            "groove", "rhythm", "dream", "dreams", "motion", "club",
            "dance", "night", "light", "lights",
        }
        for recent_title in recent_titles:
            recent_normalized = self._normalize_music_title(recent_title)
            if normalized == recent_normalized:
                return True

            recent_tokens = self._music_title_tokens(recent_title)
            overlap = title_tokens & recent_tokens
            if overlap & dominant_words:
                return True
            if overlap and len(overlap) >= 2:
                return True

        return False

    def generate_dynamic_schedule(self) -> dict:
        logger.info("🧠 [EditorialDirectorAgent] Inizio brainstorming per il palinsesto dinamico...")

        today = date.today()
        pillars = self.get_daily_pillars()
        weekly = self.get_weekly_appointments(today)
        fixed_slots = {**pillars, **weekly}
        fixed_slots_str = json.dumps(fixed_slots, indent=2, ensure_ascii=False)

        system_prompt = f"""Sei l'Agente Direttore Editoriale di NewsicaTV, una WebTV automatizzata 24/7.
Il tuo compito è generare un palinsesto giornaliero DINAMICO e IMPREVEDIBILE in formato JSON.

REGOLE TASSATIVE:
1. L'output DEVE ESSERE ESCLUSIVAMENTE codice JSON valido, senza blocchi markdown (no ```json), senza preamboli né spiegazioni.
2. Le chiavi del JSON devono essere orari nel formato "HH:00" e coprire l'intera giornata in ordine cronologico.
3. Le ore di inizio devono includere sempre "00:00" e spaziare fino alle "22:00" o "23:00". Fai slot di 1 o 2 ore. Non saltare troppe ore.
4. I valori devono essere oggetti con le chiavi: "title" (titolo accattivante del programma), "type" (categoria) ed un'opzionale "theme" (tema musicale).

FORMAT DISPONIBILI (Usa solo questi in "type"):
- "news": Notiziario generale esteso
- "sport": Notiziario sportivo
- "meteo": Aggiornamento meteo
- "wellness": Rubrica su salute/benessere
- "podcast": Dialogo a due voci su un tema specifico
- "flash_60s": Bollettino rapidissimo di 60 secondi (usalo come pillola a orari sparsi per dare imprevedibilità)
- "music_only": Solo musica in background (utile di notte o in pausa pranzo o in diretta continuata)

RUBRICHE TEMATICHE E COPERTURE MUSICALI:
- Per gli show di tipo "music_only", o anche in blocchi musicali specifici, puoi organizzare delle "rubriche" tematiche inserendo una chiave opzionale "theme" nell'oggetto del programma.
- Valori possibili per "theme": "rock", "dance/disco", "latin/reggaeton/dembow", "synthwave", "lofi chill", "pop ballad".
- Sii creativo! Ad esempio, puoi dedicare uno slot pomeridiano o serale di musica a un tema specifico (es. "theme": "rock" con titolo "Rock & Roll Arena", "theme": "dance/disco" con titolo "Newsica Club Fever", oppure "theme": "latin/reggaeton/dembow" con titolo "Baila Newsica").

LINEE GUIDA EDITORIALI PER IMPREVEDIBILITÀ:
- Varia i titoli. Invece di "Pranzo News", inventa "Oggi alle 13", "Newsica Live", "Ultim'ora Flash".
- Non mettere mai due "podcast" di fila.
- Spargi 3-4 slot "flash_60s" in momenti inaspettati (es. "11:00", "16:00", "23:00").
- Garantisci almeno un "meteo" al mattino e uno la sera.
- Rendi ogni giorno diverso dal precedente, alternando rubriche tematiche e stili musicali.

5. DEVI INCLUDERE OBBLIGATORIAMENTE i seguenti slot prefissati (Colonne Portanti e Appuntamenti Settimanali).
Copiali esattamente e aggiungi il resto del palinsesto creativo attorno ad essi:
{fixed_slots_str}

Esempio di struttura richiesta:
{{
  "00:00": {{"title": "Night Vibes", "type": "music_only", "theme": "synthwave"}},
  "07:00": {{"title": "Buongiorno Newsica", "type": "news"}},
  "14:00": {{"title": "Newsica Club Fever", "type": "music_only", "theme": "dance/disco"}},
  "17:00": {{"title": "Baila Newsica", "type": "music_only", "theme": "latin/reggaeton/dembow"}},
  "19:00": {{"title": "Rock & Roll Arena", "type": "music_only", "theme": "rock"}}
}}
"""

        user_prompt = f"Oggi è {today.isoformat()}. Genera il palinsesto creativo per oggi. Rispondi SOLO in JSON puro."

        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": 0.8,
                "top_p": 0.9,
            },
        }

        try:
            res = requests.post(self.ollama_url, json=payload, timeout=60)
            res.raise_for_status()

            response_text = res.json().get("response", "").strip()
            result = self._extract_json_object(response_text)
            parsed_schedule = json.loads(result)

            # Verifica che tutte le chiavi fisse siano presenti.
            for key, val in fixed_slots.items():
                parsed_schedule[key] = val

            # Riordina il dizionario per orario.
            sorted_schedule = {
                k: parsed_schedule[k]
                for k in sorted(parsed_schedule.keys())
            }

            log_decision(
                "EditorialDirector",
                f"Generato nuovo palinsesto dinamico per oggi con {len(sorted_schedule)} programmi.",
                level="SCHEDULING",
            )

            return sorted_schedule

        except Exception as e:
            logger.error(f"❌ Errore durante la generazione LLM del palinsesto: {e}")
            log_decision(
                "EditorialDirector",
                f"Fallback attivato: Errore di esecuzione: {e}",
                level="ERROR",
            )

        return self.fallback_schedule

    def choose_music_mode(self) -> str:
        """
        Distribuzione consigliata per una web radio:
        - prevalenza preponderante di brani con testi (lyrics/vocal hooks) rispetto a strumentali.
        - full_lyrics: 45%
        - vocal_hook: 30%
        - vocal_chops: 15%
        - instrumental: 10%
        """
        return random.choices(
            population=[
                "full_lyrics",
                "vocal_hook",
                "vocal_chops",
                "instrumental",
            ],
            weights=[
                50,
                25,
                15,
                10,
            ],
            k=1,
        )[0]

    def generate_music_prompt(
        self,
        time_of_day: str,
        fallback_prompt: str | None = None,
        music_mode: str | None = None,
        theme: str | None = None,
    ) -> dict:
        """
        Genera un prompt completo per ACE-Step, includendo una durata randomica e un tema.
        """
        logger.info(f"🧠 [EditorialDirectorAgent] Generazione prompt musicale ACE-Step per {time_of_day} (tema: {theme})...")

        # Selezioniamo casualmente la durata del brano tra 150 e 210 secondi (2.5 - 3.5 minuti)
        duration_seconds = random.randint(150, 210)
        
        # Calcoliamo la struttura del brano
        intro_end = int(duration_seconds * 0.08)       # ~12-16s
        verse1_end = int(duration_seconds * 0.28)      # ~42-58s
        build_end = int(duration_seconds * 0.38)       # ~57-80s
        chorus1_end = int(duration_seconds * 0.58)     # ~87-121s
        verse2_end = int(duration_seconds * 0.78)      # ~117-163s
        chorus2_end = duration_seconds - 8             # La fine del chorus 2 e inizio fade out

        def format_time(sec: int) -> str:
            return f"{sec // 60}:{sec % 60:02d}"

        t_intro = f"0:00 - {format_time(intro_end)}"
        t_verse1 = f"{format_time(intro_end)} - {format_time(verse1_end)}"
        t_build = f"{format_time(verse1_end)} - {format_time(build_end)}"
        t_chorus1 = f"{format_time(build_end)} - {format_time(chorus1_end)}"
        t_verse2 = f"{format_time(chorus1_end)} - {format_time(verse2_end)}"
        t_chorus2 = f"{format_time(verse2_end)} - {format_time(chorus2_end)}"
        t_fade = f"{format_time(chorus2_end)} - {format_time(duration_seconds)}"

        # Default fallback prompt con durata e struttura corretta
        fallback_prompt = fallback_prompt or self.fallback_music_prompt
        # Se stiamo usando il fallback_prompt, ma con una durata diversa, aggiorniamo il suo testo per sicurezza
        if f"{duration_seconds} seconds" not in fallback_prompt:
            fallback_prompt = f"""
Create a modern {duration_seconds}-second instrumental song for a web radio / web TV broadcast.

Mood: clean, energetic, optimistic, radio-friendly.
Tempo: 118 BPM.
Style: modern pop with polished synths, punchy drums, deep bass.
Production: streaming-ready mix, clean low end, wide stereo image.
Instruments: electronic drums, synth bass, bright pluck synths, warm pads.

Structure:
{t_intro} short intro.
{t_verse1} main groove with drums, bass.
{t_build} build with rising energy.
{t_chorus1} main hook with full beat.
{t_verse2} soft bridge.
{t_chorus2} final hook.
{t_fade} outro fading out smoothly.

Vocals:
No vocals. Instrumental only.

Lyrics:
No lyrics.

Ending:
The final 8 seconds must fade out smoothly and naturally. No abrupt ending.

Negative prompt:
low quality, distorted vocals, out of tune vocals, bad timing, messy mix, muddy bass, harsh highs, old-fashioned arrangement, theatrical singing, opera vocals, excessive vibrato, abrupt ending, spoken outro, crackle, noise, clipping, overcompressed, random tempo changes, long silence
""".strip()

        if music_mode is None:
            music_mode = self.choose_music_mode()

        # Configura il set di generi musicali
        theme_genres = {
            "rock": ["alternative rock", "indie rock", "modern rock", "pop punk", "classic rock revival", "garage rock", "synth rock"],
            "dance/disco": ["disco house", "dance pop", "club dance", "nu disco", "synthpop", "eurodance", "groove house"],
            "latin/reggaeton/dembow": ["reggaeton", "dembow", "latin pop", "moombahton", "bachata pop", "urban latin fusion"],
            "synthwave": ["synthwave", "outrun", "retrowave", "dreamwave", "dark synthwave"],
            "lofi chill": ["lofi hip hop", "chillhop", "lofi chill", "jazzhop", "ambient lofi"],
            "pop ballad": ["pop ballad", "piano pop", "acoustic pop", "indie pop ballad", "r&b ballad"]
        }

        genre_guideline = ""
        genre_pool_str = ""
        if theme and theme.lower() in theme_genres:
            genre_pool = theme_genres[theme.lower()]
            genre_pool_str = ", ".join(genre_pool)
            genre_guideline = f"""
IL PALINSESTO RICHIEDE IL TEMA: {theme.upper()}!
Devi forzare e scegliere un genere appartenente a questo tema specifico. Scegli tra: {genre_pool_str}.
Ispirati al sound, strumenti, ritmo e produzione tipici di {theme.upper()} (ad esempio chitarre elettriche per il rock, ritmi incalzanti 4/4 e bassi pulsanti per la dance/disco, o il classico ritmo sincopato "tresillo" e bassi dembow per reggaeton/latin).
"""
        else:
            genre_pool_str = "modern pop, dance pop, electro pop, chill pop, indie pop, nu disco, funk pop, tropical pop, deep house, melodic house, afro house, synthwave, future bass, soft urban pop, modern lounge, cinematic electronic"
            genre_guideline = f"Scegli un genere moderno e diverso ogni volta da questa lista: {genre_pool_str}."

        fallback_dict = {
            "prompt": fallback_prompt,
            "duration": duration_seconds,
            "mode": music_mode,
            "title": "Newsica AI Track"
        }
        recent_music_titles = get_recent_music_titles(limit=8)
        recent_music_titles_str = ", ".join(recent_music_titles) if recent_music_titles else "nessuno"

        system_prompt = f"""
Sei il Music Director AI di NewsicaTV, una web radio / web TV automatizzata 24/7.

Devi generare un prompt per ACE-Step per creare un brano moderno da {duration_seconds} secondi, adatto a rotazione radio.

Rispondi SOLO con JSON valido.
Non usare markdown.
Non aggiungere spiegazioni.

JSON richiesto:
{{
  "title": "Titolo originale breve del brano",
  "genre": "Genere scelto",
  "mood": "Mood del brano",
  "tempo_bpm": 120,
  "mode": "{music_mode}",
  "duration_seconds": {duration_seconds},
  "fade_out_seconds": 8,
  "prompt": "Prompt completo in inglese da inviare ad ACE-Step"
}}

CONTESTO:
- Fascia oraria: {time_of_day}
- Modalità musicale richiesta: {music_mode}
- Durata: {duration_seconds} secondi
- Fade out: ultimi 8 secondi
- Uso: rotazione radio / webTV / filler musicale / palinsesto NewsicaTV
- Titoli musicali recenti da evitare: {recent_music_titles_str}

{genre_guideline}

REGOLE PER IL PROMPT:
1. Il campo "prompt" deve essere in inglese.
2. Non citare artisti reali, band reali, brani reali o marchi.
3. Non usare "in the style of", "similar to", "like [artist]".
4. Il brano deve essere moderno, pulito, radio-ready, streaming-ready.
5. Specifica sempre:
   - genre
   - mood
   - tempo BPM
   - instruments (se rock usa chitarre elettriche distorte o pulite, basso, batteria reale. Se dance/disco usa synth, cassa in 4/4, claps. Se reggaeton usa percussione dembow sincopata).
   - production
   - structure temporale
   - vocals
   - lyrics se presenti
   - ending
   - negative prompt
6. La struttura DEVE ESSERE ESATTAMENTE QUESTA (usa i minuti:secondi precisi calcolati per questa canzone):
   {t_intro} intro
   {t_verse1} verse/groove
   {t_build} build/pre-chorus
   {t_chorus1} chorus/drop/main hook
   {t_verse2} second verse or soft bridge
   {t_chorus2} final chorus/drop/main hook
   {t_fade} final chorus continues with smooth fade out
7. Il finale deve sempre dire:
   "The final 8 seconds must fade out smoothly and naturally. No abrupt ending. No spoken outro."
8. Evita:
   low quality, distorted vocals, out of tune vocals, bad timing, messy mix, muddy bass, harsh highs, old-fashioned arrangement, theatrical singing, opera vocals, excessive vibrato, abrupt ending, spoken outro, crackle, noise, clipping, overcompressed, random tempo changes, long silence.
9. Deve sembrare un brano moderno da radio/web radio, non una demo amatoriale.
10. Non generare musica troppo sperimentale, horror, noise, metal o trap aggressiva.
11. Il campo "title" deve essere molto vario rispetto agli ultimi titoli usati.
12. Evita tassativamente titoli troppo generici o ricorrenti come: Pulse, Beat, Vibes, Groove, Rhythm, Neon, Electric, Night, Dream, Motion, Fire, Light, Club, Dance se sono gia comparsi di recente.
13. Non riusare la stessa parola dominante tra i titoli recenti. Se nei titoli recenti compare "Pulse", non usarla di nuovo; stessa regola per "Beat", "Neon", "Electric" e simili.
14. Il titolo deve avere 2 o 3 parole, sembrare editoriale e distintivo, non un placeholder.

REGOLE PER LA FASCIA ORARIA:
- night / late night / 00:00-05:00: chill, lounge, synthwave, deep house, soft electronic.
- morning / 06:00-10:00: bright, optimistic, fresh pop, acoustic pop, light dance.
- lunch / 11:00-14:00: warm, sunny, groovy, nu disco, funk pop, tropical pop.
- afternoon / 15:00-18:00: energetic, catchy, dance pop, electro pop, indie pop.
- evening / 19:00-23:00: stylish, melodic house, synth pop, cinematic electronic.

REGOLE PER LA MODALITÀ MUSICALE:
- Se mode = "instrumental":
  Il brano deve essere strumentale.
  Niente lyrics, niente parole cantate, niente spoken words.
  Puoi usare texture vocali non verbali solo se pulite e moderne.
- Se mode = "vocal_hook":
  Il brano deve includere solo un breve hook vocale catchy (es. una o due frasi o parole chiave ripetute nel ritornello).
  Usa 1 o 2 frasi brevi, radiofoniche e ripetibili.
  Niente strofe lunghe cantate.
- Se mode = "full_lyrics":
  Il brano deve includere lyrics originali complete con:
  [Verse 1]
  [Build]
  [Chorus]
  [Verse 2]
  [Chorus]
  Le lyrics devono essere cantate in modo moderno, semplice, orecchiabile e adatte a una radio. Scrivile per intero sotto la sezione "Lyrics:".
- Se mode = "vocal_chops":
  Il brano deve usare vocal chops moderni come texture musicale.
  Niente parole complete comprensibili.
  Niente spoken words.

FORMATO INTERNO DEL CAMPO "prompt":
Create an HIGH PRODUCTION {duration_seconds}-second [GENRE] song.

Mood: ...
Tempo: ... BPM.
Style: ...
Production: ...
Instruments: ...

Structure:
{t_intro} ...
{t_verse1} ...
{t_build} ...
{t_chorus1} ...
{t_verse2} ...
{t_chorus2} ...
{t_fade} ...

Vocals:
...

Lyrics:
...
"""

        payload = {
            "model": self.model,
            "prompt": system_prompt,
            "stream": False,
            "options": {
                "temperature": 1.0,
                "top_p": 0.92,
            },
        }

        try:
            response = requests.post(self.ollama_url, json=payload, timeout=45)

            if response.status_code == 200:
                raw_result = response.json().get("response", "").strip()
                result = self._extract_json_object(raw_result)
                parsed = json.loads(result)

                prompt = parsed.get("prompt", "").strip()

                if self._is_valid_music_prompt(prompt):
                    parsed_title = " ".join(str(parsed.get("title", "")).split())
                    if self._is_music_title_too_similar(parsed_title, recent_music_titles):
                        logger.warning(
                            "Titolo musicale troppo simile ai recenti ('%s'). Uso fallback.",
                            parsed_title,
                        )
                        log_decision(
                            "EditorialDirector",
                            f"Titolo musicale troppo simile ai recenti: '{parsed_title}'. Uso fallback.",
                            level="WARNING",
                        )
                        return fallback_dict

                    add_music_title(parsed_title)
                    logger.info(
                        "🎵 Prompt ACE-Step generato: title='%s', genre='%s', mode='%s', bpm='%s', duration=%s",
                        parsed_title,
                        parsed.get("genre"),
                        parsed.get("mode"),
                        parsed.get("tempo_bpm"),
                        parsed.get("duration_seconds"),
                    )

                    log_decision(
                        "EditorialDirector",
                        (
                            f"Prompt ACE-Step generato per '{time_of_day}' "
                            f"title='{parsed_title}', "
                            f"genre='{parsed.get('genre')}', "
                            f"mode='{parsed.get('mode')}', "
                            f"bpm='{parsed.get('tempo_bpm')}', "
                            f"duration={parsed.get('duration_seconds')}s"
                        ),
                        level="MUSIC",
                    )

                    return {
                        "prompt": prompt,
                        "duration": parsed.get("duration_seconds", duration_seconds),
                        "mode": parsed.get("mode", music_mode),
                        "title": parsed_title or "Newsica AI Track"
                    }

                logger.warning("Prompt ACE-Step generato ma non valido o incompleto. Uso fallback.")
                log_decision(
                    "EditorialDirector",
                    "Prompt ACE-Step generato ma non valido o incompleto. Uso fallback.",
                    level="WARNING",
                )

            else:
                logger.warning(f"Ollama ha restituito status {response.status_code}, uso fallback.")
                log_decision(
                    "EditorialDirector",
                    f"Errore generazione prompt ACE-Step status {response.status_code}. Uso fallback.",
                    level="WARNING",
                )

        except Exception as e:
            logger.error(f"❌ Errore nella generazione prompt ACE-Step: {e}. Uso fallback.")
            log_decision(
                "EditorialDirector",
                f"Errore generazione prompt ACE-Step. Uso fallback: {e}",
                level="ERROR",
            )

        return fallback_dict


    def _extract_json_object(self, text: str) -> str:
        """
        Estrae il primo oggetto JSON da una risposta LLM.
        """
        cleaned = text.replace("```json", "").replace("```", "").strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1

        if start == -1 or end == 0:
            raise ValueError("Nessun oggetto JSON trovato nella risposta LLM.")

        return cleaned[start:end]

    def _is_valid_music_prompt(self, prompt: str) -> bool:
        if not prompt:
            return False

        normalized = prompt.lower().strip()

        if len(normalized) < 250:
            return False

        has_duration = any(str(sec) in normalized for sec in range(150, 211)) or "second" in normalized or "seconds" in normalized

        has_fade = "fade" in normalized or "fade out" in normalized

        if not has_duration or not has_fade:
            return False

        quality_checks = [
            "structure" in normalized,
            "tempo" in normalized or "bpm" in normalized,
            "production" in normalized or "mix" in normalized,
            "instruments" in normalized,
            "vocals" in normalized or "instrumental" in normalized,
            "ending" in normalized,
            "negative prompt" in normalized,
            "0:00" in normalized or "00:00" in normalized,
        ]

        return sum(quality_checks) >= 4

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    agent = EditorialDirectorAgent()

    sched = agent.generate_dynamic_schedule()
    print(json.dumps(sched, indent=2, ensure_ascii=False))

    print("\n--- ACE-Step prompt example ---\n")
    prompt = agent.generate_music_prompt("afternoon")
    print(prompt)
