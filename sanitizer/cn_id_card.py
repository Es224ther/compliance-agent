"""Chinese resident identity card recognizer."""

import re

PRESIDIO_AVAILABLE = False

CN_ID_PATTERN = re.compile(
    r"(?<!\d)([1-9]\d{5}(18|19|20)\d{2}"
    r"(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx])(?!\d)"
)
CN_ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
CN_ID_CHECK_CODES = ["1", "0", "X", "9", "8", "7", "6", "5", "4", "3", "2"]


def is_valid_cn_id_card(value: str) -> bool:
    """Validate an 18-digit Chinese resident identity card number."""

    if not CN_ID_PATTERN.fullmatch(value):
        return False

    total = sum(int(digit) * weight for digit, weight in zip(value[:17], CN_ID_WEIGHTS))
    expected = CN_ID_CHECK_CODES[total % 11]
    return value[-1].upper() == expected


class ChineseIdCardRecognizer:
    """Compatibility recognizer placeholder for environments without Presidio."""

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: object | None = None,
    ) -> list[object]:
        del text, entities, nlp_artifacts
        return []
