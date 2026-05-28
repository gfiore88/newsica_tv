import os
import unittest
from unittest.mock import patch, MagicMock

from newsica.agents.shorts_agent import ShortsAgent

class TestShortsAgent(unittest.TestCase):

    @patch('newsica.agents.shorts_agent.subprocess.run')
    @patch('newsica.agents.shorts_agent.Kokoro')
    @patch('newsica.agents.shorts_agent.requests.post')
    def test_shorts_agent_run(self, mock_post, mock_kokoro, mock_subprocess):
        # Mock LLM
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Test script for short video."}
        mock_post.return_value = mock_response

        # Mock Kokoro TTS
        mock_kokoro_instance = MagicMock()
        mock_kokoro.return_value = mock_kokoro_instance
        # Simulate (samples, sample_rate)
        mock_kokoro_instance.create.return_value = ([0.0] * 48000, 24000)

        # Mock subprocess (FFmpeg)
        mock_subprocess.return_value = MagicMock(returncode=0)

        agent = ShortsAgent()

        # Evitiamo di sovrascrivere raw_news.json vero se esiste
        with patch.object(agent, '_get_top_news', return_value={"title": "Test Title", "description": "Test Desc"}):
            result = agent.run()

        self.assertEqual(result["status"], "success")
        self.assertIn("Test script", result["script"])
        self.assertIn("output/shorts/short_", result["output"].replace("\\", "/"))
        self.assertTrue(result.get("caption"))
        self.assertEqual(len(result.get("hashtags", [])), 5)

        metadata_path = os.path.splitext(result["output"])[0] + ".json"
        self.assertTrue(os.path.exists(metadata_path))

        # Verifica file creati (pulizia)
        if os.path.exists(agent.tmp_bg):
            os.remove(agent.tmp_bg)
        if os.path.exists(agent.tmp_srt):
            os.remove(agent.tmp_srt)
        if os.path.exists(agent.tmp_audio):
            os.remove(agent.tmp_audio)
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
            
        import glob
        for f in glob.glob(os.path.join(os.path.dirname(agent.tmp_bg), "frame_*.png")):
            os.remove(f)
        frames_txt = os.path.join(os.path.dirname(agent.tmp_bg), "frames.txt")
        if os.path.exists(frames_txt):
            os.remove(frames_txt)

    @patch('newsica.agents.shorts_agent.subprocess.run')
    @patch('newsica.agents.shorts_agent.Kokoro')
    @patch('newsica.agents.shorts_agent.requests.post')
    def test_shorts_agent_run_funfact_mode(self, mock_post, mock_kokoro, mock_subprocess):
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Curiosita incredibile del momento."}
        mock_post.return_value = mock_response

        mock_kokoro_instance = MagicMock()
        mock_kokoro.return_value = mock_kokoro_instance
        mock_kokoro_instance.create.return_value = ([0.0] * 48000, 24000)
        mock_subprocess.return_value = MagicMock(returncode=0)

        agent = ShortsAgent()

        with patch.object(agent, '_build_funfact_news_item', return_value={
            "title": "Il trend curioso del giorno",
            "description": "Dettaglio 1: qualcosa di sorprendente.",
            "summary": "Dettaglio 1: qualcosa di sorprendente.",
            "source": "funfact_web",
            "theme_color": "funfact",
        }):
            result = agent.run(mode="funfact")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["mode"], "funfact")
        self.assertEqual(len(result.get("hashtags", [])), 5)

        metadata_path = os.path.splitext(result["output"])[0] + ".json"
        if os.path.exists(metadata_path):
            os.remove(metadata_path)

    @patch('newsica.agents.shorts_agent.subprocess.run')
    @patch('newsica.agents.shorts_agent.Kokoro')
    @patch('newsica.agents.shorts_agent.requests.post')
    def test_shorts_agent_run_sport_mode(self, mock_post, mock_kokoro, mock_subprocess):
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Aggiornamento sportivo del momento."}
        mock_post.return_value = mock_response

        mock_kokoro_instance = MagicMock()
        mock_kokoro.return_value = mock_kokoro_instance
        mock_kokoro_instance.create.return_value = ([0.0] * 48000, 24000)
        mock_subprocess.return_value = MagicMock(returncode=0)

        agent = ShortsAgent()

        with patch.object(agent, '_get_news_item_for_mode', return_value={
            "title": "Finale combattuta fino all'ultimo",
            "description": "Il punto chiave della notizia sportiva.",
            "summary": "Il punto chiave della notizia sportiva.",
            "source": "ansa_sport",
            "theme_color": "sport",
        }):
            result = agent.run(mode="sport")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["mode"], "sport")
        self.assertEqual(len(result.get("hashtags", [])), 5)

        metadata_path = os.path.splitext(result["output"])[0] + ".json"
        if os.path.exists(metadata_path):
            os.remove(metadata_path)

    def test_shorts_agent_skips_generation_when_news_retrieval_is_placeholder(self):
        agent = ShortsAgent()
        with patch.object(agent, "_get_news_item_for_mode", return_value={
            "title": "Nessuna notizia disponibile al momento",
            "summary": "Stiamo aggiornando i nostri sistemi.",
            "description": "Stiamo aggiornando i nostri sistemi.",
            "source": "news",
            "theme_color": "news",
        }), patch.object(agent, "_generate_script") as mock_script, patch.object(agent, "_generate_audio") as mock_audio, patch.object(
            agent, "_render_video"
        ) as mock_render, patch.object(agent, "_write_metadata") as mock_meta:
            result = agent.run(mode="news")

        self.assertEqual(result["status"], "retrieval_failed")
        self.assertIn("Retrieve news degradato", result["message"])
        self.assertFalse(mock_script.called)
        self.assertFalse(mock_audio.called)
        self.assertFalse(mock_render.called)
        self.assertFalse(mock_meta.called)

if __name__ == '__main__':
    unittest.main()
