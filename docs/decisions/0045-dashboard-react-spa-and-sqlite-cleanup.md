# 0045: Migrazione Dashboard a React SPA e Pulizia Legacy JSON

## Contesto
L'interfaccia di amministrazione della radio (la Dashboard) era originariamente un semplice script Flask (`dashboard.py`) che restituiva un template HTML inline. Con l'aumentare delle funzionalità (Live Monitor, Palinsesto, Strumenti Editoriali), il file ha superato le 1800 righe di codice, rendendo la manutenzione difficile e l'interfaccia utente confusa (le card si sovrapponevano visivamente in un'unica pagina con scroll infinito).

Contemporaneamente, l'adozione del database SQLite (`newsica.db`) era stata implementata parzialmente (ADR 0044): le tabelle e i Repository erano stati creati, ma il codice vitale dell'applicazione (`playout.py`, `ai_music_worker.py`) continuava a invocare i vecchi wrapper Python che interagivano coi file JSON in `runtime/` (`telegram_voices.json`, `ai_music_jobs.json`, ecc.). 

Questo doppio stato creava un pericoloso debito tecnico e impediva la cancellazione definitiva dei file JSON.

## Decisione

1. **Rifattorizzazione Frontend (React + Vite)**: 
   - Abbiamo separato completamente il frontend dal backend.
   - `dashboard.py` è stato snellito (eliminati gli HTML) ed è ora un puro Backend API REST.
   - È stato inizializzato un progetto React 18 + Vite nella cartella `frontend/` con TailwindCSS v4.
   - Il layout è stato riprogettato con React Router (Sidebar laterale) e diviso in viste modulari: Regia Live, Palinsesto, Strumenti, Registro Storico.
   
2. **Completamento Switch Database (SQL-Driven)**:
   - È stata aggiunta un'ultima tabella SQLite dedicata (`chat_music_requests`).
   - Tutti gli script dell'applicazione (`playout.py`, `ai_music_worker.py`, agenti vari) sono stati riscritti per importare i moduli in `src/newsica/storage/repositories/` al posto dei vecchi moduli legacy in `src/newsica/audio/`.

3. **Pulizia (Cleanup)**:
   - I file Python legacy che facevano da wrapper JSON (`telegram_voices.py`, `ai_music_jobs.py`, `chat_music_requests.py`, `memory.py`) sono stati definitivamente cancellati.
   - I file fisici di stato `.json` presenti in `runtime/` sono stati eliminati.

## Conseguenze

- **Positivo**: Prestazioni dell'interfaccia migliorate enormemente; manutenzione semplificata per future feature web; coerenza dei dati garantita esclusivamente da SQLite; assenza di data-race sui vecchi JSON.
- **Negativo**: È necessario mantenere un passaggio di compilazione aggiuntivo (`npm run build`) in fase di deploy quando si modifica la Dashboard.
- **Risolto**: Il sistema non soffre più della frammentazione dello stato (JSON vs DB).
