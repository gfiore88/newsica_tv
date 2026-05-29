import unittest

from newsica.editorial.fallback_scripts import build_fallback_script
from newsica.editorial.podcast_contract import validate_podcast_script


class TestPodcastContract(unittest.TestCase):
    def test_rejects_truncated_podcast_script_without_closure(self):
        script = """
[SPEAKER: Giulia] Ben ritrovati a Newsica Podcast. Oggi affrontiamo un tema che mi pare particolarmente stimolante, e forse un po' inquietante: Heidegger, l'intelligenza artificiale e la possibilità che, in un certo senso, stiamo diventando più barbari. Marco, sei pronto a questo tuffo nella filosofia?

[SPEAKER: Marco] Più che pronto, Giulia. Heidegger è un personaggio che scatena sempre un bel dibattito, soprattutto quando lo metti a confronto con la tecnologia. E l'idea che l'IA possa farci regredire, beh, è una provocazione interessante.

[SPEAKER: Giulia] Provocazione che, a ben guardare, ha delle radici profonde. Heidegger, come sappiamo, ha sviluppato una filosofia esistenzialista che mette al centro l'essere, l'esistenza umana. E la sua critica alla tecnologia, in particolare, è piuttosto severa.

[SPEAKER: Marco] Esatto. Nel suo pensiero, la tecnologia non è neutra. Non è solo uno strumento che mettiamo a disposizione dell'uomo. Piuttosto, è un modo di rivelare l'essere, ma anche di nasconderlo. E qui entra in gioco il concetto di oblio dell'essere.

[SPEAKER: Giulia] Sì, l'oblio dell'essere. Heidegger sosteneva che la tecnica moderna ci allontana dalla nostra vera essenza, ci fa dimenticare il significato profondo dell'esistenza. Ci spinge a ridurre tutto a calcolo, a performance, a disponibilità.

[SPEAKER: Marco] E questo si collega perfettamente a quello che stiamo vedendo con l'intelligenza artificiale. L'IA promette di automatizzare tutto, di risolvere i nostri problemi, di renderci la vita più facile.

[SPEAKER: Giulia] È un punto cruciale. Non possiamo semplicemente lamentarci della tecnologia, dobbiamo cercare di utilizzarla
""".strip()

        is_valid, issues = validate_podcast_script(script)

        self.assertFalse(is_valid)
        self.assertTrue(any("frase completa" in issue for issue in issues))
        self.assertTrue(any("chiusura naturale" in issue for issue in issues))

    def test_rejects_music_breaks_in_podcast(self):
        script = """
[SPEAKER: Giulia] Apriamo la puntata con una riflessione ampia sul rapporto tra città e tecnologia, cercando di capire che cosa stia cambiando davvero nel nostro modo di vivere gli spazi quotidiani.
[MUSIC_BREAK]
[SPEAKER: Marco] Riprendiamo tra poco.
""".strip()

        is_valid, issues = validate_podcast_script(script)

        self.assertFalse(is_valid)
        self.assertTrue(any("[MUSIC_BREAK]" in issue for issue in issues))

    def test_fallback_podcast_script_respects_contract(self):
        filtered_news = [
            {"title": "Primo tema", "summary": "Una sintesi abbastanza ricca per permettere un ragionamento articolato sulla portata culturale e sociale della notizia."},
            {"title": "Secondo tema", "summary": "Un altro passaggio utile per collegare conseguenze pratiche, percezioni pubbliche e sviluppi possibili nel breve periodo."},
            {"title": "Terzo tema", "summary": "Un contesto che aiuta a non leggere la vicenda come un episodio isolato ma come parte di un cambiamento più ampio."},
        ]

        script = build_fallback_script("podcast", filtered_news, title="Newsica Podcast")
        is_valid, issues = validate_podcast_script(script)

        self.assertTrue(is_valid, f"Il fallback podcast dovrebbe rispettare il contratto editoriale: {issues}")


if __name__ == "__main__":
    unittest.main()
