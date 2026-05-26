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

    def _brainstorm_dynamic_topic(self, discovery_context):
        import os
        import json
        import re

        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
        model_name = os.getenv("OLLAMA_MODEL", "gemma3:12b")

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

        try:
            print(f"🧠 [ContentStrategist] Richiedo analisi trend e brainstorming a Ollama ({model_name})...")
            r = requests.post(ollama_url, json=payload, timeout=45)
            r.raise_for_status()
            text = r.json().get("response", "").strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\n", "", text)
                text = re.sub(r"\n```$", "", text)
            data = json.loads(text.strip())
            if "title" in data and "query" in data:
                print(f"✨ [ContentStrategist] Tema identificato dall'LLM: '{data['title']}' (query di approfondimento: '{data['query']}')")
                return data
        except Exception as e:
            print(f"⚠️ [ContentStrategist] Errore brainstorming Ollama: {e}")

        FALLBACK_TOPICS = [
            {"title": "Gli Agenti Autonomi IA nel 2026", "query": "agenti autonomi IA 2026 novita lavoro"},
            {"title": "La Gen Z e la riscoperta della vita offline", "query": "Gen Z vita offline digital detox motivi"},
            {"title": "Il fenomeno del Biohacking e della longevità", "query": "biohacking longevita salute novita"},
            {"title": "Storie e miti dei viaggiatori nel tempo su internet", "query": "viaggiatori nel tempo leggende internet famose"},
            {"title": "Il ritorno dei vinili e delle tecnologie analogiche", "query": "ritorno vinili cassette tecnologia analogica trend"},
            {"title": "Perché siamo ossessionati dai podcast true crime?", "query": "psicologia attrazione true crime podcast motivi"}
        ]
        return random.choice(FALLBACK_TOPICS)

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
            # 1. Ricerca web di scoperta per individuare trend caldi generali
            discovery_queries = [
                "tendenze tecnologia e societa 2026",
                "trend caldi del momento attualita",
                "fenomeni emergenti cultura pop e social",
                "innovazioni scientifiche incredibili e scoperte recenti",
                "nuovi comportamenti giovanili e stile di vita",
                "dibattiti e discussioni calde internet oggi",
                "longevita biohacking e benessere trend 2026",
                "nuove tendenze alimentari e sostenibilita nel mondo",
                "misteri e stranezze affascinanti dal mondo",
                "comportamento umano psicologia sociale oggi"
            ]
            discovery_query = random.choice(discovery_queries)
            print(f"🔍 [ContentStrategist] FASE 1: Ricerca web di scoperta per identificare i trend con query: '{discovery_query}'")
            discovery_results = self.search_internet(discovery_query, num_results=6)

            # Raccogliamo anche le ultime notizie locali RSS
            rss_snippets = []
            for item in filtered_news[:6]:
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

            # 2. Chiediamo a Ollama di analizzare il contesto dei trend e di estrarre/ideare una tematica
            selected_topic = self._brainstorm_dynamic_topic(discovery_context)
            topic_title = selected_topic["title"]
            query = selected_topic["query"]
            print(f"🎙️ [ContentStrategist] FASE 2: Brainstorming completato. Tema scelto: '{topic_title}'")

            # 3. Eseguiamo il secondo livello di ricerca (deep-dive) basato sulla query generata dall'LLM
            print(f"🔍 [ContentStrategist] FASE 3: Ricerca deep-dive dei fatti sul web con query: '{query}'")
            search_results = self.search_internet(query, num_results=5)

            # Se la ricerca web deep-dive fallisce, usiamo un fallback basato sulle notizie correnti o trend di scoperta
            if not search_results:
                print("⚠️ [ContentStrategist] Ricerca deep-dive vuota o fallita. Utilizzo fallback dei trend di scoperta.")
                if discovery_results:
                    search_results = discovery_results[:3]
                else:
                    for item in filtered_news[:3]:
                        search_results.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("summary", "")
                        })

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
            prompt += "Fate nascere un dibattito reale, con opinioni complementari e toni naturali. Non leggete lo studio in modo asettico, ma discutendolo come in una vera chiacchierata in studio."

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
