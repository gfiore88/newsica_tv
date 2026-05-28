import os
import tempfile
import unittest

from newsica.shorts.render_pipeline import ShortRenderPipeline


class TestShortsRenderPipeline(unittest.TestCase):
    def test_generate_srt_writes_expected_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = ShortRenderPipeline(
                tmp_dir=tmp,
                assets_dir=tmp,
                output_dir=tmp,
                ollama_url="http://localhost:11434/api/generate",
                model_name="gemma3:12b",
            )
            pipeline.generate_srt("uno due tre quattro", 2.0)
            self.assertTrue(os.path.exists(pipeline.tmp_srt))
            with open(pipeline.tmp_srt, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("uno due tre", content)

    def test_download_image_returns_none_with_empty_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = ShortRenderPipeline(
                tmp_dir=tmp,
                assets_dir=tmp,
                output_dir=tmp,
                ollama_url="http://localhost:11434/api/generate",
                model_name="gemma3:12b",
            )
            self.assertIsNone(pipeline._download_image(""))


if __name__ == "__main__":
    unittest.main()
