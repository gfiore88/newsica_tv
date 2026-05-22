# 0031 - Recupero preparazioni stale negli asset pre-prodotti

## Contesto

Alle 16:30 lo slot "Podcast: Viaggi e Avventure" e' stato inizializzato correttamente, ma l'audio del podcast non era in `runtime/assets/ready/1630`. Esisteva invece una cartella vuota `runtime/assets/preparing/1630` vecchia di ore. Il PreparationAgent la interpretava come "asset gia' in preparazione" e non rigenerava mai il podcast.

Il DirectorAgent ha quindi rispettato il palinsesto, lanciando il jingle podcast, ma poi e' passato alla musica di fallback per continuita' stream.

## Decisione

- `SystemAdminAgent.prepare_slot()` archivia e rigenera preparazioni stale: oltre 30 minuti, oppure vuote da oltre 5 minuti.
- `PreparationAgent.get_future_slots()` include anche lo slot corrente se iniziato da meno di 30 minuti, cosi' puo' recuperare contenuti mancanti durante la fascia.
- `DirectorAgent._handle_podcast_progression()` puo' agganciare un podcast appena diventa disponibile anche se la fascia e' gia' in fallback musicale.
- Anche i podcast pronti vengono validati con `manifest.json` rubrica/titolo, come le altre rubriche.

## Conseguenze

Una cartella `preparing` orfana non blocca piu' indefinitamente uno slot. Se il podcast arriva in ritardo ma dentro la fascia, puo' ancora andare in onda. Se non arriva in tempo, la regia resta in musica di fallback e non blocca lo stream.

La correzione entra in vigore al prossimo restart del Director/PreparationAgent. La cartella stale dello slot 16:30 e' stata archiviata manualmente durante l'incidente.
