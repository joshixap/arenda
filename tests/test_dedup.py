"""Tests for deduplication hash and parser registry."""
import pytest

from parser_service.parsers.base import BaseParser, PARSER_REGISTRY


def test_dedup_hash_deterministic():
    h1 = BaseParser.compute_dedup_hash("ул. Ленина, 1", 45.5, 30000)
    h2 = BaseParser.compute_dedup_hash("ул. Ленина, 1", 45.5, 30000)
    assert h1 == h2


def test_dedup_hash_case_insensitive():
    h1 = BaseParser.compute_dedup_hash("УЛ. ЛЕНИНА, 1", 45.5, 30000)
    h2 = BaseParser.compute_dedup_hash("ул. ленина, 1", 45.5, 30000)
    assert h1 == h2


def test_dedup_hash_area_rounding():
    h1 = BaseParser.compute_dedup_hash("addr", 45.49, 30000)
    h2 = BaseParser.compute_dedup_hash("addr", 45.50, 30000)
    assert h1 == h2


def test_dedup_hash_price_sensitivity():
    h1 = BaseParser.compute_dedup_hash("addr", 45.0, 30000)
    h2 = BaseParser.compute_dedup_hash("addr", 45.0, 31000)
    assert h1 != h2


def test_parser_registry_populated():
    # Import triggers auto-registration
    import parser_service.parsers.avito  # noqa
    import parser_service.parsers.cian  # noqa
    assert "avito" in PARSER_REGISTRY
    assert "cian" in PARSER_REGISTRY


def test_all_parsers_registered():
    import parser_service.parsers.avito  # noqa
    import parser_service.parsers.cian  # noqa
    import parser_service.parsers.domclick  # noqa
    import parser_service.parsers.yandex  # noqa
    import parser_service.parsers.n1  # noqa
    import parser_service.parsers.youla  # noqa
    import parser_service.parsers.move  # noqa
    expected = {"avito", "cian", "domclick", "yandex", "n1", "youla", "move"}
    assert expected.issubset(set(PARSER_REGISTRY.keys()))
