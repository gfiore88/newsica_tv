# 🔎 Task Brief: Automazione H24 e Regia Dinamica (MVP 2)

## Obiettivo
Evolvere il sistema da esecuzioni singole a un ciclo continuo (H24) che aggiorna le notizie, genera il copione e sintetizza l'audio in tempo reale, senza mai interrompere la trasmissione RTMP verso YouTube.

## Vincoli Tecnici
- **Tutto Locale**: Nessun uso di API a pagamento.
- **Continuità dello Stream**: FFmpeg non deve mai disconnettersi. L'audio deve essere alimentato continuamente (es. tramite pipe o playlist dinamica).
- **Risorse**: Il ciclo non deve saturare la CPU del Mac (gestire i tempi di attesa tra una generazione e l'altra).

## Piano di Lavoro
1. **Fase 4 (Python Engineer)**: Creazione di `src/director.py` (o `scheduler.py`) che gestisce il loop infinito.
2. **Fase 3 (AI Integrator)**: Ottimizzazione di Kokoro TTS per generare stream audio continui o file sequenziali.
3. **Fase 5 (Streaming Expert)**: Configurazione di FFmpeg per leggere l'audio da uno stream continuo (pipe) o concatenazione dinamica, mantenendo la grafica fissa (orologio, ticker, logo).
4. **Fase 6 (System Admin)**: Gestione dei log e della stabilità del processo in background.

## Rischi Potenziali
- **Saturazione Pipe**: Se Python genera audio più velocemente di quanto FFmpeg lo consumi (o viceversa), lo stream potrebbe bloccarsi.
- **Mancanza di News**: Se non ci sono nuove news, il sistema deve ripetere le ultime o generare contenuti di riempimento (es. meteo o jingle).
- **Memoria**: Verificare che i modelli ONNX e LLM non accumulino memoria ad ogni ciclo.
