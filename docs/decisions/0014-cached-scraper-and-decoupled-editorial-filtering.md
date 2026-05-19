# ADR 0014: Caching dello Scraper, Disaccoppiamento e Rimozione Completa dei Mock Editoriali

## Stato

Accettata

## Contesto

L'utente ha riscontrato che la rubrica *Pausa Wellness* (Maya) tendeva a ripetere frequentemente gli stessi argomenti e notizie. Inoltre, ha sollevato dubbi sulla presenza di dati statici ed editoriali prefatti ("mockati") come la tupla `WELLNESS_TIPS` nel codice, che contravvenivano alla richiesta di zero contenuti statici e mock prefissati.

Analizzando il codice abbiamo individuato le cause principali:
1. **Presenza di Mock statici**: La tupla `WELLNESS_TIPS` era un database statico hardcoded all'interno dello scraper, causando ripetizione degli stessi argomenti.
2. **Bug di Fallback in `select_fresh_wellness`**: Se un personaggio preferito non aveva più elementi freschi (non ancora trasmessi), il sistema ricadeva forzatamente sull'intera lista di elementi `light_items`, riproponendo gli stessi elementi statici.
3. **Mancanza di Caching**: Lo scraper eseguiva interrogazioni HTTP su 11 feed RSS e le API Open-Meteo ad ogni singolo avvio di `run_pipeline`, causando latenza di rete durante la generazione dei blocchi.

## Decisione

Per risolvere definitivamente questi problemi e aderire in modo rigoroso alla direttiva "zero mock in tutto il codice", abbiamo implementato le seguenti modifiche strutturali:

### 1. Rimozione Completa dei Mock Editoriali (`WELLNESS_TIPS`)
* Abbiamo **completamente eliminato** la tupla `WELLNESS_TIPS` e ogni riferimento a fonti `wellness_tip`.
* La rubrica *Pausa Wellness* ora funziona **al 100% in modo dinamico**, leggendo esclusivamente le ultime notizie reali dai feed RSS `ansa_salute_benessere` e `ansa_lifestyle`.
* La conduttrice Maya e il processore LLM prendono queste notizie in tempo reale e creano un copione narrato originale, inserendo aneddoti spontanei e transizioni senza bisogno di appoggiarsi a consigli preconfezionati.

### 2. Ottimizzazione della Selezione e Priorità delle Fonti
Abbiamo riadattato `select_fresh_wellness` per operare esclusivamente sulle notizie fresche dinamiche dei feed attivi:
* Le fonti preferite e pesate maggiormente sono ora `ansa_lifestyle` (+4 di punteggio) e `ansa_salute_benessere` (+3 di punteggio).
* La rotazione dei contenuti recenti viene tracciata rigorosamente via `recent_wellness.json` e riutilizza l'algoritmo Least Recently Used (LRU) solo in caso di esaurimento totale delle notizie fresche giornaliere.

### 3. Caching Intelligente a 15 Minuti dello Scraper
Abbiamo implementato una cache basata sul file `tmp/raw_news.json` in `src/scraper.py`:
* Se il file `tmp/raw_news.json` esiste ed è stato modificato meno di 15 minuti fa, lo scraper riutilizza il pool consolidato senza fare chiamate esterne.
* Questo velocizza drasticamente le transizioni (da ~2-5 secondi di latenza a 0 secondi).
* È possibile forzare lo scraping di rete passando il flag `--force` a `scraper.py`.

### 4. Decoupling e Pulizia Architetturale (Decentralizzazione)
Abbiamo formalizzato la suddivisione delle responsabilità tra i moduli:
* **`scraper.py` (Ingestion & Consolidamento):** Raccoglie tutti i feed, gestisce il caching temporale e struttura il file centrale `tmp/raw_news.json`.
* **`llm_processor.py` (Filtro Personaggio & Generazione):** Filtra e seleziona i contenuti da `tmp/raw_news.json` in base al personaggio attivo (`news`, `sport`, `wellness`, `meteo`) gestendo le memorie locali degli elementi trasmessi prima dell'invio all'LLM (Ollama).

## Conseguenze

* **Zero Mock**: Non c'è più alcun dato editoriale o consiglio preconfezionato nel codice sorgente. La rubrica *Pausa Wellness* è interamente dinamica e generata in tempo reale dalle notizie RSS del giorno.
* **Zero Ripetizioni**: Maya (Wellness) ora ruota in modo pulito e stabile tra le notizie fresche di ANSA Salute e Lifestyle.
* **Caricamento Istantaneo**: La transizione tra i blocchi non soffre più della latenza dei download RSS grazie alla cache.
* **Architettura Pulita**: Disaccoppiamento perfetto tra ingestione (scraper) ed elaborazione (llm_processor).
