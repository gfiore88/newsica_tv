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

        # Verifica file creati (pulizia)
        if os.path.exists(agent.tmp_bg):
            os.remove(agent.tmp_bg)
        if os.path.exists(agent.tmp_srt):
            os.remove(agent.tmp_srt)
        if os.path.exists(agent.tmp_audio):
            os.remove(agent.tmp_audio)
            
        import glob
        for f in glob.glob(os.path.join(os.path.dirname(agent.tmp_bg), "frame_*.png")):
            os.remove(f)
        frames_txt = os.path.join(os.path.dirname(agent.tmp_bg), "frames.txt")
        if os.path.exists(frames_txt):
            os.remove(frames_txt)

if __name__ == '__main__':
    unittest.main()
