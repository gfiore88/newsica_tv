# Progetto NewsicaTV - Brainstorming & Overview

## 📺 Obiettivo del Progetto
Creare un canale YouTube (NewsicaTV) completamente automatico e live H24. Il canale trasmetterà un flusso continuo alternando:
1. **Notiziari AI**: News (Italia, mondo, cronaca, sport) scritte da modelli LLM locali e lette da sistemi Text-To-Speech (TTS) locali (es. Kokoro AI).
2. **Musica AI**: Brani musicali generati tramite modelli AI open-source/gratuiti per riempire i "tempi morti" tra un notiziario e l'altro.

## 🚨 Regole Irrevocabili
- **100% LOCALE**: Tutto il codice, la generazione AI (testo, audio, musica) e lo streaming devono girare sulla macchina locale.
- **NESSUN COSTO**: Vietato utilizzare API a pagamento (OpenAI, servizi cloud SaaS, ElevenLabs, ecc.). Bisogna utilizzare esclusivamente soluzioni Free e Open Source.
- **AUTOMAZIONE TOTALE**: La pipeline (recupero news, scrittura copione, generazione audio, streaming video) deve operare in completa autonomia, gestita tramite script (Python/Bash) orchestrati dagli Agenti AI.

## 🏗️ Architettura Tecnica Ipotizzata
1. **Content Scraper / Generator (Python + Ollama/Local LLM)**
   - Recupera le ultime notizie tramite RSS feed gratuiti o web scraping (es. ANSA, gazzetta).
   - Un modello locale (Ollama con Llama-3 o simili) rielabora le notizie creando un copione da "speaker radiofonico/televisivo".
2. **Text-To-Speech (Kokoro AI)**
   - Il copione testuale viene passato a **Kokoro AI** (o un'alternativa TTS locale gratuita e di alta qualità) per generare il file audio (WAV/MP3).
3. **Music Generator (Local AI)**
   - Modelli locali (es. MusicGen / Audiocraft di Meta o varianti leggere) pre-generano tracce musicali royalty-free per i riempitivi.
4. **Streaming Engine (FFmpeg o OBS Studio)**
   - Una regia automatica (script Python + FFmpeg) prende l'audio, ci unisce un background video/immagine in loop (o generato anch'esso localmente) e lo streamma via RTMP verso YouTube Live H24.

## 🤖 Struttura degli Agenti (.agents/workflows)
I vecchi agenti ("ioVet") sono stati riciclati e riscritti per mappare esattamente queste nuove esigenze:

1. **`/orchestrator`**: Coordinatore generale. Assicura che la pipeline "Task -> Code -> Test -> Stream" sia rispettata.
2. **`/task_analyzer`**: Analizza i requisiti, definisce le priorità e stende il Task Brief per ogni nuova integrazione.
3. **`/python_engineer`**: Sviluppa gli script Python core (scraping, automazione, glue-code). Sostituisce il vecchio backend_expert.
4. **`/ai_integrator`**: Si occupa dell'integrazione, test e ottimizzazione dei modelli AI locali (Ollama, Kokoro AI, MusicGen). Sostituisce api_designer.
5. **`/streaming_expert`**: Configura la regia video/audio (FFmpeg/OBS) e il flusso RTMP per garantire lo streaming fluido H24. Sostituisce test_engineer.
6. **`/content_strategist`**: Definisce il palinsesto, le fonti delle news, il format dei prompt per il LLM. Sostituisce data_analyst.
7. **`/system_admin`**: Cura l'infrastruttura locale: processi, code, pulizia file temporanei, risorse hardware. Sostituisce legal_expert.
8. **`/code_reviewer`**: Esegue code review ferree garantendo che non ci siano API a pagamento o inefficienze critiche.

---
*Prossimi passi: riscrittura fisica dei file markdown degli agenti all'interno della cartella `.agents/workflows` per rimuovere i riferimenti a ioVet e attivare il nuovo team NewsicaTV.*
