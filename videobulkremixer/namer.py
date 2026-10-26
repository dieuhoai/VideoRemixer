"""Sinh tên output theo naming convention."""
from __future__ import annotations

from pathlib import Path

from videobulkremixer.models import NamingConfig


def generate_name(
    config: NamingConfig,
    language: str,
    ratio: str,
    stt: int,
) -> str:
    """Sinh tên file theo mẫu Appname_VID_Concept_Geo_Language_Date_Ratio_STT."""
    return config.format_name(language=language, ratio=ratio, stt=stt)


def generate_output_path(
    output_dir: Path,
    config: NamingConfig,
    language: str,
    geo: str,
    ratio: str,
    stt: int,
) -> Path:
    """Sinh đường dẫn đầy đủ: Output/BR_pt/filename.mp4"""
    folder_name = f"{geo}_{language}" if geo else language
    folder = output_dir / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    filename = generate_name(config, language, ratio, stt)
    return folder / filename


def preview_names(
    config: NamingConfig,
    languages: list[str],
    ratios: list[str],
    count_per_combo: int = 1,
    max_preview: int = 5,
) -> list[str]:
    """Preview tên file đầu ra (tối đa max_preview dòng)."""
    names: list[str] = []
    stt = 1
    for lang in languages:
        for ratio in ratios:
            for _ in range(count_per_combo):
                names.append(generate_name(config, lang, ratio, stt))
                stt += 1
                if len(names) >= max_preview:
                    return names
    return names
