# ADR 0009: Rotazione notizie e memoria editoriale

## Context

Le rubriche news ripetevano spesso gli stessi titoli perche' lo scraper prendeva pochi item dai feed ANSA principali. Se il feed non cambiava abbastanza rapidamente, ogni nuova generazione del copione riceveva quasi le stesse notizie.

## Decision

Lo scraper ora amplia il bacino gratuito con piu' feed RSS:

- ANSA ultimora, mondo, cronaca, politica, economia, cultura, tecnologia;
- ANSA sport;
- ANSA salute/benessere e lifestyle;
- Sky TG24 RSS per ulteriore varieta' generalista.

La selezione usa `tmp/recent_news.json` per ricordare le notizie gia' usate nelle ultime rotazioni e preferire item freschi. Inoltre bilancia le fonti e filtra titoli troppo simili per evitare che la stessa storia arrivi due volte da feed diversi.

## Consequences

- `tmp/raw_news.json` contiene una selezione piu' varia.
- La rubrica news puo' pescare da piu' fonti e categorie.
- Se non ci sono alternative fresche, il sistema ricade comunque sulle notizie disponibili invece di restare vuoto.
