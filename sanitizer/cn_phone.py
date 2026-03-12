"""Chinese mainland phone recognizer."""

from presidio_analyzer import Pattern, PatternRecognizer


class ChinesePhoneRecognizer(PatternRecognizer):
    """Detect Chinese mainland mobile phone numbers."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity="CN_PHONE",
            name="Chinese Phone Recognizer",
            supported_language="zh",
            patterns=[
                Pattern(
                    name="cn_phone_pattern",
                    regex=r"1[3-9]\d{9}",
                    score=0.85,
                )
            ],
            context=["手机", "电话", "联系方式"],
        )
