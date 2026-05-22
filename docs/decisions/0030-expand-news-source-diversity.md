# 0030 - Espansione fonti news per cronaca, politica ed esteri

## Contesto

La pipeline news raccoglieva gia' feed ANSA per sezioni diverse, ma la selezione finale usava un limite basso e preferiva soprattutto ultimora, mondo e Sky TG24. Il risultato era una rotazione percepita come ripetitiva, con poca presenza stabile di cronaca, politica ed esteri nei copioni.

## Decisione

Estendiamo il registry fonti con feed RSS AGI gratuiti e verificati:

- cronaca;
- politica;
- estero;
- economia;
- innovazione;
- cultura;
- sport.

La selezione news passa da 6 a 10 elementi e la selezione sport da 3 a 4 elementi. I nuovi source id sono aggiunti anche ai character JSON, cosi' i contenuti raccolti possono entrare effettivamente nei prompt di news, sport, podcast e flash.

Il fallback generale non torna piu' solo ad `ansa_ultimora`, ma puo' usare l'intero pool `NEWS_SOURCES`.

## Conseguenze

I copioni hanno piu' varieta' editoriale e una migliore copertura di cronaca, politica, esteri, economia, cultura e innovazione. La raccolta RSS fa qualche richiesta in piu', ma resta locale, gratuita e con timeout per ogni feed.

La memoria anti-ripetizione continua a lavorare per evitare che le stesse storie rientrino troppo spesso.
