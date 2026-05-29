import json
import time
import requests
import re
import html
import random
from datetime import datetime
from newsica.config.paths import TMP_DIR
from newsica.sources.collector import collect_news_items
from newsica.domain.characters import get_character
from newsica.editorial.source_filters import filter_items_for_character, fallback_general_news
from newsica.editorial.fallback_scripts import build_fallback_script
from newsica.editorial.title_rules import is_general_news_title

DISCOVERY_QUERIES = [
    "tendenze tecnologia e societa 2026",
    "trend caldi del momento attualita",
    "fenomeni emergenti cultura pop e social",
    "innovazioni scientifiche incredibili e scoperte recenti",
    "nuovi comportamenti giovanili e stile di vita",
    "dibattiti e discussioni calde internet oggi",
    "longevita biohacking e benessere trend 2026",
    "nuove tendenze alimentari e sostenibilita nel mondo",
    "misteri e stranezze affascinanti dal mondo",
    "comportamento umano psicologia sociale oggi",
]

PODCAST_FALLBACK_TOPICS = [
    {"title": "Gli Agenti Autonomi IA nel 2026", "query": "agenti autonomi IA 2026 novita lavoro"},
    {"title": "La Gen Z e la riscoperta della vita offline", "query": "Gen Z vita offline digital detox motivi"},
    {"title": "Il fenomeno del Biohacking e della longevità", "query": "biohacking longevita salute novita"},
    {"title": "Storie e miti dei viaggiatori nel tempo su internet", "query": "viaggiatori nel tempo leggende internet famose"},
    {"title": "Il ritorno dei vinili e delle tecnologie analogiche", "query": "ritorno vinili cassette tecnologia analogica trend"},
    {"title": "Perché siamo ossessionati dai podcast true crime?", "query": "psicologia attrazione true crime podcast motivi"},
]

SHORTS_FUNFACT_FALLBACK_TOPICS = [
    {"title": "La curiosità tech che sta facendo parlare tutti", "query": "curiosita tecnologia del momento fenomeno virale"},
    {"title": "Il trend social più strano delle ultime ore", "query": "trend social strano del momento curiosita"},
    {"title": "Il dettaglio pop che nessuno si aspettava", "query": "cultura pop curiosita ultime notizie"},
    {"title": "La notizia leggera che sta girando ovunque", "query": "notizia leggera curiosita del momento web"},
]

class ContentStrategistAgent:
    def __init__(self, cache_seconds=900):
        self.cache_seconds = cache_seconds
        self.output_file = TMP_DIR / "raw_news.json"
        
    def _should_use_cache(self, force_fetch=False):
        if force_fetch or not self.output_file.exists():
            return False
        age = time.time() - self.output_file.stat().st_mtime
        if age < self.cache_seconds:
            print(f"[{datetime.now()}] Cache valida ({int(age)}s di età). Salto lo scraping di rete.")
            return True
        return False
        
    def _collect_news(self, force_fetch=False):
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        if self._should_use_cache(force_fetch):
            return json.loads(self.output_file.read_text(encoding="utf-8"))
            
        print(f"[{datetime.now()}] Avvio scraping delle news...")
        all_news = collect_news_items()
        self.output_file.write_text(json.dumps(all_news, ensure_ascii=False, indent=4), encoding="utf-8")
        print(f"[{datetime.now()}] Scraping completato. Salvate {len(all_news)} notizie in {self.output_file}")
        return all_news

    def _build_prompt_payload(self, news_items, title=None, character_id=None):
        news_text = ""
        if title:
            news_text += (
                "TEMA OBBLIGATORIO DELLA PUNTATA:\n"
                f"{title}\n\n"
                "Regola editoriale: il copione deve rispettare questo titolo. "
                "Usa gli spunti sotto solo se aiutano il tema; non cambiare argomento "
                "e non trasformare la puntata in una rassegna generica.\n\n"
            )
            if character_id == "wellness":
                news_text += (
                    "Per una rubrica wellness, traduci il tema in consigli pratici, "
                    "sicuri e quotidiani. Se il titolo parla di esercizi per l'ufficio, "
                    "concentrati su movimenti semplici da scrivania, postura, pause attive "
                    "e respirazione, senza prescrizioni mediche.\n\n"
                )
            if character_id == "motori":
                news_text += (
                    "Per una rubrica auto e motori, concentrati sulle novità del settore automotive, "
                    "tecnologie di mobilità sostenibile, curiosità sul motorsport (F1, MotoGP) o "
                    "modelli di supercar, evitando toni eccessivamente tecnici o noiosi e senza "
                    "inventare dati non verificati.\n\n"
                )
            if character_id == "news":
                if is_general_news_title(title):
                    news_text += (
                        "Questa e' un'edizione news generalista. E' corretto costruire una scaletta mista con "
                        "cronaca, politica, esteri, economia, cultura, tecnologia e sport, mantenendo un tono da "
                        "telegiornale e senza trasformarla in una rubrica monotematica.\n\n"
                    )
                else:
                    news_text += (
                        "Questa e' una rubrica news tematica. Usa solo spunti coerenti con il titolo e scarta "
                        "le notizie che portano fuori argomento. Il titolo non e' decorativo.\n\n"
                    )

        news_text += "Ecco le notizie o gli spunti da rielaborare:\n\n"
        for item in news_items:
            news_text += f"- TITOLO: {item.get('title', '')}\n"
            news_text += f"  SINTESI: {item.get('summary', '')}\n\n"
        return news_text

    def search_internet(self, query, num_results=4):
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        try:
            print(f"🔍 [ContentStrategist] Eseguo ricerca web per: '{query}'...")
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            
            titles = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', r.text, re.DOTALL)
            snippets = re.findall(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', r.text, re.DOTALL)
            
            results = []
            for t, s in zip(titles, snippets):
                t_clean = html.unescape(re.sub(r'<[^>]+>', '', t).strip())
                s_clean = html.unescape(re.sub(r'<[^>]+>', '', s).strip())
                results.append({
                    "title": t_clean,
                    "snippet": s_clean
                })
                if len(results) >= num_results:
                    break
            print(f"✅ [ContentStrategist] Ricerca completata. Trovati {len(results)} risultati.")
            return results
        except Exception as e:
            print(f"⚠️ [ContentStrategist] Errore ricerca web per '{query}': {e}")
            return []

    def _discover_trend_results(self, queries=None, num_results=6):
        discovery_query = random.choice(queries or DISCOVERY_QUERIES)
        print(f"🔍 [ContentStrategist] FASE 1: Ricerca web di scoperta per identificare i trend con query: '{discovery_query}'")
        discovery_results = self.search_internet(discovery_query, num_results=num_results)
        return {
            "query": discovery_query,
            "results": discovery_results,
        }

    def _build_discovery_context(self, rss_items=None, discovery_results=None):
        rss_items = rss_items or []
        discovery_results = discovery_results or []

        rss_snippets = []
        for item in rss_items[:6]:
            rss_snippets.append(f"RSS: {item.get('title', '')} - {item.get('summary', '')}")

        discovery_context = ""
        if rss_snippets:
            discovery_context += "--- NOTIZIE RSS RECENTI ---\n" + "\n".join(rss_snippets) + "\n\n"

        if discovery_results:
            discovery_context += "--- TREND/RICERCHE DAL WEB ---\n"
            for idx, res in enumerate(discovery_results):
                discovery_context += f"Trend {idx+1}: {res['title']} - {res['snippet']}\n"
        else:
            discovery_context += "--- NESSUN RISULTATO DAL WEB ---\n(Usa solo le notizie RSS o inventa una tematica caldissima basata sulle notizie RSS)"
        return discovery_context

    def _brainstorm_dynamic_topic(self, discovery_context, format_type="podcast"):
        import os
        import json
        import re

        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
        model_name = os.getenv("OLLAMA_MODEL", "gemma3:12b")

        if format_type == "shorts_funfact":
            system_prompt = (
                "Sei l'autore e content strategist principale di NewsicaTV.\n"
                "Analizza i trend, le news leggere e le curiosita del momento ricevute nel prompt e individua un singolo "
                "argomento perfetto per uno short verticale da 30-45 secondi con tono curioso, virale ma vero.\n\n"
                "Cerca dettagli sorprendenti, fenomeni internet, costume, cultura pop, scienza pop o tecnologia consumer "
                "che possano essere raccontati come curiosita o fun fact dell'ultim'ora.\n\n"
                "REGOLE TASSATIVE:\n"
                "1. L'output deve essere ESCLUSIVAMENTE un oggetto JSON valido con due chiavi:\n"
                "   - 'title': Un titolo breve e molto curioso in italiano.\n"
                "   - 'query': Una query web MIRATA di 2-5 parole per un deep-dive sui fatti.\n"
                "2. Nessun markdown, nessun commento, solo JSON puro.\n"
                "3. Privilegia temi leggeri e sorprendenti, non breaking news tragiche o politica pesante.\n"
                "Esempio di output atteso:\n"
                '{"title": "Perché tutti parlano dei telefoni trasparenti?", "query": "telefono trasparente trend video social"}'
            )
        else:
            system_prompt = (
                "Sei l'autore e content strategist principale di NewsicaTV.\n"
                "Il tuo compito è analizzare i trend, le news e le discussioni calde ricevute nel prompt e, da queste, "
                "identificare o estrapolare una singola tematica di discussione moderna, originale e accattivante "
                "per una puntata di podcast a due voci (Giulia e Marco).\n\n"
                "Il podcast deve essere un dibattito acceso, curioso e super colloquiale. Evita banalità generiche. "
                "Cerca di individuare un aspetto controverso, un trend bizzarro di internet, un cambio di costume sociale, "
                "un paradosso tecnologico o un dilemma etico e scientifico.\n\n"
                "REGOLE TASSATIVE:\n"
                "1. L'output deve essere ESCLUSIVAMENTE un oggetto JSON valido con due chiavi:\n"
                "   - 'title': Un titolo brillante, breve, colloquiale e accattivante per il podcast (in italiano).\n"
                "   - 'query': Una query di ricerca web MIRATA (2-4 parole chiave in italiano o inglese) per effettuare "
                "un secondo livello di ricerca approfondita (deep-dive) e raccogliere fatti, retroscena e dettagli concreti su questa specifica tematica.\n"
                "2. Non includere blocchi di codice markdown (no ```json), nessun preambolo, spiegazione o commento. Rispondi solo con il JSON puro.\n"
                "3. Sii estremamente creativo, pesca spunti insoliti o controcorrente dai trend forniti.\n"
                "Esempio di output atteso:\n"
                '{"title": "Perché la Gen Z sta dicendo addio agli smartphone?", "query": "dumbphone gen z trend motivi"}'
            )

        user_prompt = (
            "Ecco il contesto dei trend recenti (RSS e Web Search) da analizzare:\n\n"
            f"{discovery_context}\n\n"
            "Analizza queste tematiche ed elabora una tematica di discussione originale e la relativa query di ricerca deep-dive. Rispondi in JSON puro."
        )

        payload = {
            "model": model_name,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": 0.85,
            }
        }
 
        from newsica.generation.tts_jobs import remote_generation_enabled, remote_llm_generate

        try:
            print(f"🧠 [ContentStrategist] Richiedo analisi trend e brainstorming...")
            if remote_generation_enabled():
                text = remote_llm_generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    options={"temperature": 0.85},
                    timeout_seconds=60
                )
            else:
                r = requests.post(ollama_url, json=payload, timeout=45)
                r.raise_for_status()
                text = r.json().get("response", "").strip()

            if text:
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\n", "", text)
                    text = re.sub(r"\n```$", "", text)
                data = json.loads(text.strip())
                if "title" in data and "query" in data:
                    print(f"✨ [ContentStrategist] Tema identificato dall'LLM: '{data['title']}' (query di approfondimento: '{data['query']}')")
                    return data
        except Exception as e:
            print(f"⚠️ [ContentStrategist] Errore brainstorming Ollama: {e}")
 
        fallback_topics = SHORTS_FUNFACT_FALLBACK_TOPICS if format_type == "shorts_funfact" else PODCAST_FALLBACK_TOPICS
        return random.choice(fallback_topics)

    def build_trend_brief(self, rss_items=None, format_type="podcast", discovery_queries=None, discovery_results_limit=6, deep_dive_results_limit=5):
        discovery = self._discover_trend_results(queries=discovery_queries, num_results=discovery_results_limit)
        discovery_results = discovery["results"]
        discovery_context = self._build_discovery_context(rss_items=rss_items, discovery_results=discovery_results)
        selected_topic = self._brainstorm_dynamic_topic(discovery_context, format_type=format_type)
        query = selected_topic["query"]
        print(f"🔍 [ContentStrategist] FASE 3: Ricerca deep-dive dei fatti sul web con query: '{query}'")
        search_results = self.search_internet(query, num_results=deep_dive_results_limit)

        if not search_results:
            print("⚠️ [ContentStrategist] Ricerca deep-dive vuota o fallita. Utilizzo fallback dei trend di scoperta.")
            if discovery_results:
                search_results = discovery_results[:3]
            else:
                search_results = [
                    {"title": item.get("title", ""), "snippet": item.get("summary", "")}
                    for item in (rss_items or [])[:3]
                ]

        return {
            "topic": selected_topic,
            "discovery_query": discovery["query"],
            "discovery_results": discovery_results,
            "deep_dive_results": search_results,
            "discovery_context": discovery_context,
        }

    def prepare_content(self, character_id, title=None, theme=None, force_fetch=False):
        """
        Prepara le istruzioni e il contesto per l'AI Integrator.
        Restituisce un dizionario con i dati strutturati.
        """
        character = get_character(character_id)
        
        if character_id == "music_only":
            filtered_news = []
            fallback_script = f"Benvenuti su NewsicaTV. È il momento di {title or 'Musica Senza Interruzioni'}. Buon ascolto."
            prompt = (
                f"TEMA EDITORIALE DELLA RUBRICA MUSICALE:\n"
                f"Titolo dello show: {title}\n"
                f"Tema musicale di riferimento: {theme or 'generale / pop moderno'}\n\n"
                "Istruzione: Scrivi un testo di introduzione radiofonica cortissimo (15-25 parole) in italiano. "
                "Il testo deve presentare lo show e invitare all'ascolto dei brani in tema. "
                "Usa un tono caldo, accattivante, profondo ed estremamente professionale da speaker radiofonico."
            )
        else:
            all_news = self._collect_news(force_fetch)
            filtered_news = filter_items_for_character(all_news, character)
            if not filtered_news:
                print(f"⚠️ Nessuna notizia specifica per '{character.id}'. Uso quelle generali.")
                filtered_news = fallback_general_news(all_news)

            fallback_script = build_fallback_script(character.id, filtered_news, title=title)

        # LOGICA SPECIALE PODCAST CON STUDIO E RICERCA WEB DINAMICA
        if character_id == "podcast":
            trend_brief = self.build_trend_brief(rss_items=filtered_news[:6], format_type="podcast")
            selected_topic = trend_brief["topic"]
            topic_title = selected_topic["title"]
            print(f"🎙️ [ContentStrategist] FASE 2: Brainstorming completato. Tema scelto: '{topic_title}'")
            search_results = trend_brief["deep_dive_results"]

            # Aggiorna il titolo del podcast dinamico
            title = f"Newsica Podcast - Focus: {topic_title}"

            # Costruisci il prompt payload speciale per il podcast con i risultati dello studio
            prompt = "FORMATO PODCAST SELEZIONATO: Dibattito Tematica Calda ed Emergente\n"
            prompt += f"TITOLO DELLA PUNTATA: {title}\n\n"
            prompt += "--- STUDIO DI RICERCA EDITORIALE E DATI DAL WEB (FATTI CONCRETI) ---\n"
            for idx, res in enumerate(search_results):
                prompt += f"FATTO/DETTAGLIO {idx+1}: {res['title']}\n"
                prompt += f"CONTESTO E RETROSCENA: {res['snippet']}\n\n"
            prompt += "--------------------------------------------------\n\n"
            prompt += "ISTRUZIONE EDITORIALE PER I CONDUTTORI (Giulia e Marco):\n"
            prompt += "Scrivete un copione brillante, parlato in modo giovanile, spontaneo ed estremamente fluido.\n"
            prompt += "I due speaker devono controbattere, confrontarsi ed argomentare basandosi rigorosamente sui dettagli, dati e curiosità dello STUDIO EDITORIALE riportato sopra.\n"
            prompt += "Fate nascere un dibattito reale, con opinioni complementari e toni naturali. Non leggete lo studio in modo asettico, ma discutendolo come in una vera chiacchierata in studio.\n"
            prompt += "IMPORTANTE: questa puntata va scritta come episodio unico continuo, senza [MUSIC_BREAK] e senza frasi del tipo 'ne parliamo dopo la musica'.\n"
            prompt += "Negli ultimi turni accompagnate invece l'ascoltatore verso una chiusura naturale e un lancio finale alla musica di NewsicaTV."

        else:
            prompt = self._build_prompt_payload(filtered_news, title=title, character_id=character.id)
            
        system_prompt = character.read_prompt()
        
        intro = ""
        if title:
            intro = character.render_intro(title)
            
        return {
            "character_id": character.id,
            "display_name": character.display_name,
            "title": title,
            "intro": intro,
            "system_prompt": system_prompt,
            "prompt": prompt,
            "fallback_script": fallback_script,
            "voice": character.voice,
            "speed": character.speed,
        }
