"""Test audio_mixer — T4."""
from videobulkremixer.audio_mixer import guess_language_from_filename


class TestGuessLanguage:
    def test_suffix_en(self):
        assert guess_language_from_filename("voice_EN.mp3") == "en"

    def test_suffix_vi(self):
        assert guess_language_from_filename("voiceover_VI.mp3") == "vi"

    def test_lower_ja(self):
        assert guess_language_from_filename("audio_ja.mp3") == "ja"

    def test_no_lang(self):
        assert guess_language_from_filename("bgmusic.mp3") == ""

    def test_multi_underscores(self):
        assert guess_language_from_filename("ad_summer_ko.mp3") == "ko"

    def test_dash_separator(self):
        assert guess_language_from_filename("voice-pt.mp3") == "pt"
