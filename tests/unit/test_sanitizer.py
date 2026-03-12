from sanitizer.anonymizer import PIIAnonymizer
from sanitizer.engine import SanitizerEngine


def test_cn_phone_detection() -> None:
    engine = SanitizerEngine()
    text = "我的手机是 13812345678"

    results = engine.analyze(text=text, language="zh", entities=["CN_PHONE"])

    assert len(results) == 1
    assert results[0].entity_type == "CN_PHONE"
    assert text[results[0].start : results[0].end] == "13812345678"


def test_cn_id_detection() -> None:
    engine = SanitizerEngine()
    text = "身份证号：11010519491231002X，请核验。"

    results = engine.analyze(text=text, language="zh", entities=["CN_ID"])

    assert len(results) == 1
    assert results[0].entity_type == "CN_ID"
    assert text[results[0].start : results[0].end] == "11010519491231002X"


def test_email_masking() -> None:
    anonymizer = PIIAnonymizer(engine=SanitizerEngine())
    text = "Please contact alice@example.com for support."

    masked_text, pii_map = anonymizer.anonymize(text=text, language="en")

    assert "[EMAIL_1]" in masked_text
    assert pii_map["[EMAIL_1]"] == "alice@example.com"


def test_pii_not_in_output() -> None:
    anonymizer = PIIAnonymizer(engine=SanitizerEngine())
    text = "我的手机是 13812345678，邮箱是 alice@example.com"

    masked_text, _ = anonymizer.anonymize(text=text, language="zh")

    assert "13812345678" not in masked_text
    assert "alice@example.com" not in masked_text
