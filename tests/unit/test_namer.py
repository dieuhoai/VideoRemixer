"""Test namer — T7."""
from videobulkremixer.models import NamingConfig
from videobulkremixer.namer import generate_name, generate_output_path, preview_names


class TestGenerateName:
    def test_full_format(self):
        nc = NamingConfig(appname="MyApp-GP", concept="SummerSale", geo="BR", date_str="261026")
        result = generate_name(nc, "pt", "9x16", 1)
        assert result == "MyApp-GP_VID_SummerSale_BR_pt_261026_9x16_001.mp4"

    def test_stt_padding(self):
        nc = NamingConfig(appname="App", concept="C", date_str="261026")
        assert "_042.mp4" in generate_name(nc, "en", "16x9", 42)
        assert "_001.mp4" in generate_name(nc, "en", "16x9", 1)


class TestGenerateOutputPath:
    def test_creates_lang_folder(self, tmp_path):
        nc = NamingConfig(appname="App", concept="C", geo="US", date_str="261026")
        path = generate_output_path(tmp_path, nc, "en", "US", "9x16", 1)
        assert path.parent.name == "US_en"
        assert path.parent.exists()

    def test_filename_matches(self, tmp_path):
        nc = NamingConfig(appname="App", concept="C", geo="BR", date_str="261026")
        path = generate_output_path(tmp_path, nc, "pt", "BR", "9x16", 3)
        assert "BR_pt_261026_9x16_003.mp4" in path.name


class TestPreviewNames:
    def test_preview_limit(self):
        nc = NamingConfig(appname="App", concept="C", date_str="261026")
        names = preview_names(nc, ["vi", "en"], ["9x16", "16x9"], count_per_combo=2, max_preview=5)
        assert len(names) == 5

    def test_preview_content(self):
        nc = NamingConfig(appname="MyApp-GP", concept="Sale", geo="WW", date_str="261026")
        names = preview_names(nc, ["en"], ["9x16"], count_per_combo=2, max_preview=3)
        assert all("MyApp-GP" in n for n in names)
        assert all(".mp4" in n for n in names)
