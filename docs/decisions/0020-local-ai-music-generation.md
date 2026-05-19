# 0020 - Brani musicali AI locali per rotazione radio

## Stato

Proposta operativa

## Contesto

NewsicaTV deve aumentare la varietà musicale senza dipendere da servizi a pagamento o API cloud. Il vincolo resta: tutto locale, tutto gratuito, con asset generati e riprodotti dalla macchina della regia.

ACE-Step è un candidato coerente perché il repository ufficiale lo presenta come modello open-source per generazione musicale, con uso locale e supporto a installazione via ambiente Python. La documentazione ufficiale dichiara anche ACE-Step v1.5 come release più avanzata e pubblicata nel 2026.

Fonti primarie:

- https://github.com/ace-step/ACE-Step
- https://arxiv.org/abs/2602.00744

## Decisione

La rotazione audio viene predisposta per due librerie:

- `assets/music/`: brani forniti manualmente;
- `assets/ai_music/`: brani generati localmente da tool AI.

`MusicLibrary` alterna le fonti quando entrambe contengono tracce valide, evitando per quanto possibile due brani consecutivi dalla stessa sorgente e lo stesso file ripetuto subito.

L'integrazione ACE-Step non deve avvenire dentro il loop live. Va introdotta come job separato che genera brani da 30-60 secondi in anticipo, li normalizza e li deposita in `assets/ai_music/`. Il director deve solo riprodurre file audio già pronti.

## Conseguenze

La live resta stabile anche se il generatore AI è lento o fallisce. Se `assets/ai_music/` è vuota, il sistema continua a usare solo `assets/music/`. Quando arriveranno brani AI validi, entreranno automaticamente nella rotazione.
