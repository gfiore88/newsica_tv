# 0017 - Estrarre fonti e selezione contenuti dallo scraper

## Stato

Accettata

## Contesto

`src/scraper.py` conteneva insieme registry RSS, fetch dei feed, deduplica, memoria anti-ripetizione, scoring wellness, meteo e scrittura di `tmp/raw_news.json`. Questo rendeva difficile aggiungere fonti o cambiare la rotazione senza modificare direttamente l'entrypoint runtime.

## Decisione

Lo scraper resta compatibile come comando `python src/scraper.py`, ma delega a `src/newsica/sources/`:

- `registry.py`: feed RSS, gruppi fonte e preferenze;
- `rss.py`: download e parsing feed RSS;
- `rotation.py`: chiavi, deduplica, similarità e memoria recenti;
- `wellness.py`: scoring e selezione wellness;
- `weather.py`: dati meteo Open-Meteo;
- `collector.py`: orchestrazione della raccolta e output normalizzato.

La cache da 15 minuti e il file `tmp/raw_news.json` restano invariati.

## Conseguenze

Aggiungere o ribilanciare fonti ora richiede modifiche concentrate nei moduli `sources`, non nel runtime della regia. La prossima fase può produrre output separati per rubrica, ma per ora l'interfaccia resta `tmp/raw_news.json` per evitare regressioni su `llm_processor.py`.
