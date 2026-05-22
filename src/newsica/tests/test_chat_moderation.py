import unittest
import sys
import os
import time

# Aggiunge src al path di importazione
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)

from chat_agent import clean_text, is_moderated, PROFANITY_BLACKLIST, user_last_message_time


class TestChatModeration(unittest.TestCase):
    def setUp(self):
        # Ripristina lo stato globale del rate limit prima di ogni test
        user_last_message_time.clear()

    def test_clean_text_removes_extra_whitespace(self):
        self.assertEqual(clean_text("   ciao    amico   \n  "), "ciao amico")
        self.assertEqual(clean_text(None), "")

    def test_is_moderated_accepts_clean_messages(self):
        self.assertFalse(is_moderated("User1", "Ciao a tutti! Questo stream è fantastico."))
        self.assertFalse(is_moderated("User2", "Che bella musica AI. Complimenti!"))

    def test_is_moderated_filters_long_messages(self):
        long_message = "A" * 95
        self.assertTrue(is_moderated("User1", long_message))

    def test_is_moderated_filters_blacklisted_words(self):
        # Prendi una parola a caso dal blacklist
        bad_word = list(PROFANITY_BLACKLIST)[0]
        self.assertTrue(is_moderated("User1", f"Ma che {bad_word} stai dicendo?"))

    def test_is_moderated_applies_rate_limit(self):
        # Primo messaggio: ammesso
        self.assertFalse(is_moderated("UserSpam", "Primo messaggio!"))
        
        # Secondo messaggio immediato dello stesso utente: moderato (scartato)
        self.assertTrue(is_moderated("UserSpam", "Secondo messaggio immediato!"))
        
        # Un altro utente nello stesso istante: ammesso
        self.assertFalse(is_moderated("UserClean", "Ciao da un utente diverso!"))


if __name__ == "__main__":
    unittest.main()
