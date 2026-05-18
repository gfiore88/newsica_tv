# NewsicaTV - Project Overview

## 📺 Visione del Progetto
Creare un canale YouTube (NewsicaTV) automatico H24 che operi come un vero e proprio ecosistema editoriale e televisivo gestito da AI locali. Non è un semplice aggregatore vocale di RSS, ma una regia dinamica capace di sintetizzare, impaginare e trasmettere news e musica con un taglio professionale.

## 🚨 Obiettivi Irrevocabili (Vincoli Tecnici)
1. **Local-First Totale**: Ogni componente (scraping, LLM, TTS, MusicGen, FFmpeg, Streaming) deve girare offline o in self-hosting sulla macchina locale.
2. **Zero Costi (No API SaaS)**: Nessuna dipendenza da servizi cloud commerciali (OpenAI, ElevenLabs, AWS, ecc.). Si usano solo modelli Open-Weights e tool Open Source.
3. **Sostituibilità (Decoupling)**: Ogni modulo AI deve essere interfacciato in modo da poter essere sostituito in qualsiasi momento (es. cambiare Kokoro TTS con Piper TTS senza rompere l'architettura).

## ⚠️ Rischi Principali da Mitigare
1. **Qualità Editoriale (L'effetto "AI Slop")**: Le notizie non devono essere riassunti robotici, ma avere un taglio da notiziario. Evitiamo duplicati e contenuti generici.
2. **Licenze e Copyright**: Qualsiasi fonte scrapata deve essere consentita, o usata per generare riassunti citando la fonte. La musica generata deve essere royalty-free.
3. **Stabilità H24**: Script in Python/FFmpeg devono resistere a crash, memory leak e drop di connessione.
4. **Qualità Audio/Video**: Kokoro AI e simili andranno testati a fondo sulla lingua italiana per evitare accenti stranieri o artefatti metallici fastidiosi.

## 🤖 Gli Agenti (Il Team Virtuale)
Abbiamo strutturato il progetto attorno a "ruoli" ben definiti (vedi `.agents/workflows/`). Ogni agente ha una sua specifica area di competenza, ma il principio guida è documentare e versionare ogni scelta tramite il `documentation_curator`.
