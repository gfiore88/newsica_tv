# 🔎 Task Brief: Identità Speaker e Ticker Intelligente (MVP 3)

## Obiettivo
Concludere l'MVP 3 implementando le due funzionalità che danno un'identità definitiva e televisiva al canale:
1. **Identità Speaker**: Dare nomi (Nora, Leo, Maya, Colonnello) e caratteristiche vocali univoche a ogni format, differenziando la velocità e il tono per simulare una vera redazione tramite `tts_generator.py`.
2. **Ticker Intelligente**: Creazione di un `ticker_agent.py` che aggiorni costantemente il testo scorrevole in basso (letto dal `drawtext` di FFmpeg), mostrando ora esatta, blocco in onda, prossima rubrica e notizie flash, senza limiti statici.

## Vincoli Tecnici
- **Tutto Locale**: Usare solo le voci ONNX locali e Python standard.
- **Sincronia Ticker**: Il file `tmp/ticker.txt` deve essere aggiornato atomicamente ogni pochi secondi. FFmpeg (`reload=1`) lo leggerà automaticamente al volo.

## Piano di Lavoro
1. **Fase 3 (AI Integrator)**:
   - Aggiornamento di `src/tts_generator.py` per associare le velocità corrette ai personaggi (Nora più veloce per le news, Maya più lenta per il wellness, ecc.).
2. **Fase 4 (Python Engineer)**:
   - Sviluppo di `src/ticker_agent.py` in esecuzione infinita.
   - Integrazione di `ticker_agent.py` in `director.py` (avvio come thread in background al momento del boot della regia).
3. **Fase 6 (System Admin)**:
   - Validazione flussi e log per garantire che il Ticker non vada in errore se il file state non è pronto.
