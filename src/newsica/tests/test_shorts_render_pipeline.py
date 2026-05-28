import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from newsica.shorts.render_pipeline import ShortRenderPipeline


class TestShortsRenderPipeline(unittest.TestCase):
    def _make_pipeline(self, tmp):
        return ShortRenderPipeline(
            tmp_dir=tmp,
            assets_dir=tmp,
            output_dir=tmp,
            ollama_url="http://localhost:11434/api/generate",
            model_name="gemma3:12b",
        )

    def test_generate_srt_writes_expected_file(self):
        """generate_srt scrive un file SRT leggibile con il testo fornito."""
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self._make_pipeline(tmp)
            pipeline.generate_srt("uno due tre quattro", 2.0)
            self.assertTrue(os.path.exists(pipeline.tmp_srt))
            with open(pipeline.tmp_srt, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("uno due tre", content)

    def test_generate_srt_timing_covers_full_duration(self):
        """L'ultimo timestamp dell'SRT deve coprire l'intera durata audio."""
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self._make_pipeline(tmp)
            duration = 5.0
            pipeline.generate_srt("parola uno due tre quattro cinque sei", duration)
            with open(pipeline.tmp_srt, "r", encoding="utf-8") as f:
                content = f.read()
            # L'SRT deve avere almeno un blocco
            self.assertIn("-->", content)
            # La somma delle durate di chunk deve approssimarsi a 'duration'
            import re
            timestamps = re.findall(
                r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", content
            )
            self.assertTrue(len(timestamps) > 0, "Nessun timestamp trovato nell'SRT")

    def test_generate_audio_returns_tuple_with_duration_and_clean_text(self):
        """generate_audio deve restituire (float, str) — contratto per l'allineamento SRT/TTS.

        Questo test garantisce che chiunque chiami generate_audio riceva il testo
        pulito effettivamente passato a Kokoro, da usare poi in generate_srt.
        """
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self._make_pipeline(tmp)

            fake_samples = [0.0] * 22050  # 1 secondo a 22050 Hz
            fake_sr = 22050
            mock_kokoro = MagicMock()
            mock_kokoro.create.return_value = (fake_samples, fake_sr)
            mock_kokoro.get_voice_style.return_value = MagicMock()

            import soundfile as sf

            with patch("newsica.shorts.render_pipeline.Kokoro", return_value=mock_kokoro), \
                 patch("newsica.shorts.render_pipeline.sf.write") as mock_write:
                result = pipeline.generate_audio("Ciao mondo, questa è una notizia", "news")

            # Il risultato DEVE essere una tupla di due elementi
            self.assertIsInstance(result, tuple, "generate_audio deve restituire una tupla")
            self.assertEqual(len(result), 2, "La tupla deve avere esattamente 2 elementi")

            duration, clean_text = result
            self.assertIsInstance(duration, float, "Il primo elemento deve essere la durata (float)")
            self.assertIsInstance(clean_text, str, "Il secondo elemento deve essere il testo pulito (str)")
            self.assertGreater(duration, 0, "La durata deve essere positiva")
            self.assertGreater(len(clean_text), 0, "Il testo pulito non deve essere vuoto")

    def test_download_image_returns_none_with_empty_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self._make_pipeline(tmp)
            self.assertIsNone(pipeline._download_image(""))

    @patch.dict(os.environ, {"SHORTS_FORCED_ALIGN": "false"})
    def test_generate_srt_uses_legacy_when_forced_align_disabled(self):
        """Con SHORTS_FORCED_ALIGN=false deve usare solo il sistema character-based,
        senza mai invocare _generate_srt_forced_align."""
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self._make_pipeline(tmp)
            with patch.object(pipeline, "_generate_srt_forced_align") as mock_fa, \
                 patch.object(pipeline, "_generate_srt_character_based") as mock_cb:
                pipeline.generate_srt("ciao mondo notizia", 3.0)

            mock_fa.assert_not_called()
            mock_cb.assert_called_once_with("ciao mondo notizia", 3.0)

    @patch.dict(os.environ, {"SHORTS_FORCED_ALIGN": "true"})
    def test_generate_srt_uses_forced_align_when_env_enabled(self):
        """Con SHORTS_FORCED_ALIGN=true e WAV presente deve tentare il forced alignment.
        Se MMS_FA restituisce True, il fallback character-based non deve essere chiamato."""
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self._make_pipeline(tmp)
            # Simula WAV già presente
            open(pipeline.tmp_audio, "w").close()
            with patch.object(pipeline, "_generate_srt_forced_align", return_value=True) as mock_fa, \
                 patch.object(pipeline, "_generate_srt_character_based") as mock_cb:
                pipeline.generate_srt("ciao mondo notizia", 3.0)

            mock_fa.assert_called_once_with("ciao mondo notizia")
            mock_cb.assert_not_called()

    @patch.dict(os.environ, {"SHORTS_FORCED_ALIGN": "true"})
    def test_generate_srt_falls_back_to_legacy_when_forced_align_fails(self):
        """Con SHORTS_FORCED_ALIGN=true ma forced alignment che fallisce,
        deve attivare il fallback character-based automaticamente."""
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = self._make_pipeline(tmp)
            open(pipeline.tmp_audio, "w").close()
            with patch.object(pipeline, "_generate_srt_forced_align", return_value=False) as mock_fa, \
                 patch.object(pipeline, "_generate_srt_character_based") as mock_cb:
                pipeline.generate_srt("testo di test", 4.0)

            mock_fa.assert_called_once()
            mock_cb.assert_called_once_with("testo di test", 4.0)


if __name__ == "__main__":
    unittest.main()
