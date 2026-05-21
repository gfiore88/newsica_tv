# 0029 - Coerenza tra titolo di palinsesto e contenuto generato

## Contesto

Il palinsesto può generare titoli specifici, ad esempio "Benessere in Movimento: Esercizi per l'Ufficio". La pipeline contenuti, però, passava quel titolo solo come introduzione parlata e non come vincolo del prompt LLM. Di conseguenza il copione poteva seguire spunti RSS generici e parlare di argomenti diversi dal titolo mostrato in overlay.

Inoltre gli asset audio pre-prodotti erano identificati solo dallo slot orario. Se il palinsesto cambiava tema o tipo di rubrica per lo stesso orario, esisteva il rischio di riusare audio non coerente.

## Decisione

Il titolo dello slot diventa un vincolo editoriale esplicito:

- `ContentStrategistAgent` inserisce nel prompt una sezione `TEMA OBBLIGATORIO DELLA PUNTATA`.
- Il prompt wellness chiarisce che quel tema ha priorità sugli spunti RSS.
- Il fallback locale wellness produce un copione coerente quando il titolo riguarda esercizi per ufficio/scrivania.
- `llm_processor.py` supporta un titolo opzionale da CLI o variabile `NEWSICA_BLOCK_TITLE` per mantenere coerente anche il percorso legacy.
- `SystemAdminAgent` scrive un `manifest.json` negli asset pronti con slot, rubrica, titolo e timestamp.
- `DirectorAgent` rifiuta asset pronti privi di manifest valido o non coerenti con rubrica/titolo attuali.

## Conseguenze

Il titolo del programma non è più solo grafica: guida il contenuto generato e il fallback. Se un asset non corrisponde al palinsesto corrente, la regia non lo manda in onda e aspetta rigenerazione o fallback musicale.

Questo aumenta leggermente la rigidità della pre-produzione: vecchi asset senza manifest devono essere rigenerati. È intenzionale, perché evita incoerenze editoriali visibili in diretta.
