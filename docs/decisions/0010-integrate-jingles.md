# 0010 - Integrare i jingle nella regia live

## Stato

Accettata

## Contesto

NewsicaTV ha ora una cartella `assets/jingles/` con un jingle classico di identita' canale e un jingle dedicato alle breaking news. Prima di questa decisione la breaking news usava un allarme sintetico generato al volo e la regia passava direttamente da musica a speaker senza ident radiofonico.

## Decisione

- La regia usa `assets/jingles/newsicatv_jingle.mp3` prima dei blocchi speaker programmati.
- Le rubriche sportive usano `assets/jingles/jingle_sport.mp3`; se non esiste, la regia salta il jingle e prosegue senza bloccare la messa in onda.
- Lo stato ON AIR viene aggiornato prima del jingle, cosi' overlay e audio annunciano la rubrica in arrivo in modo coerente.
- Il jingle classico rispetta gli stop di palinsesto, skip manuali e breaking news: se cambia fascia viene interrotto come gli altri contenuti regolari.
- Il breaking news agent usa `assets/jingles/jingle_breaking_news.mp3` come apertura dell'edizione straordinaria.
- Se il jingle breaking non esiste, resta disponibile il fallback locale con tono sintetico FFmpeg.

## Conseguenze

La transizione canzone -> rubrica diventa piu' riconoscibile e radiofonica, senza introdurre servizi esterni o costi. Il sidechain speaker/musica resta nel mix delle rubriche, quindi la voce continua ad andare sopra un sottofondo musicale abbassato automaticamente.
