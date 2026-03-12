from sanitizer.anonymizer import PIIAnonymizer
from sanitizer.cn_id_card import is_valid_cn_id_card
from sanitizer.engine import SanitizerEngine
from sanitizer.pii_map import InMemoryPiiMap


def test_cn_id_card_checksum_validation() -> None:
    assert is_valid_cn_id_card("11010519491231002X") is True
    assert is_valid_cn_id_card("110105194912310021") is False


def test_pii_map_generates_expected_placeholders() -> None:
    pii_map = InMemoryPiiMap()

    assert pii_map.add("PERSON", "Alice") == "[PERSON_1]"
    assert pii_map.add("EMAIL_ADDRESS", "alice@example.com") == "[EMAIL_1]"
    assert pii_map.add("CN_PHONE", "13800138000") == "[CN_PHONE_1]"
    assert pii_map.add("CN_ID", "11010519491231002X") == "[CN_ID_1]"
    assert pii_map.to_dict()["[CN_ID_1]"] == "11010519491231002X"


def test_zh_anonymizer_masks_phone_id_and_email() -> None:
    anonymizer = PIIAnonymizer(engine=SanitizerEngine())
    text = (
        "张三的联系方式是13800138000，身份证号是11010519491231002X，"
        "邮箱是zhangsan@example.com。"
    )

    masked_text, pii_map = anonymizer.anonymize(text=text, language="zh")

    assert "[CN_PHONE_1]" in masked_text
    assert "[CN_ID_1]" in masked_text
    assert "[EMAIL_1]" in masked_text
    assert pii_map["[CN_PHONE_1]"] == "13800138000"
    assert pii_map["[CN_ID_1]"] == "11010519491231002X"
    assert pii_map["[EMAIL_1]"] == "zhangsan@example.com"
