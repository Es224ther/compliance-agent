"""Chinese resident identity card recognizer."""

import re

try:
    from presidio_analyzer import LocalRecognizer, RecognizerResult
    from presidio_analyzer.nlp_engine import NlpArtifacts

    PRESIDIO_AVAILABLE = True
except ModuleNotFoundError:
    LocalRecognizer = object
    RecognizerResult = object
    NlpArtifacts = object
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


if PRESIDIO_AVAILABLE:

    class ChineseIdCardRecognizer(LocalRecognizer):
        """Detect valid Chinese resident identity card numbers."""

        def __init__(self) -> None:
            super().__init__(
                supported_entities=["CN_ID"],
                name="Chinese ID Card Recognizer",
                supported_language="zh",
                context=["身份证", "身份证号", "证件号"],
            )

        def analyze(
            self,
            text: str,
            entities: list[str],
            nlp_artifacts: NlpArtifacts | None = None,
        ) -> list[RecognizerResult]:
            if entities and "CN_ID" not in entities:
                return []

            results: list[RecognizerResult] = []
            for match in CN_ID_PATTERN.finditer(text):
                candidate = match.group(1)
                if not is_valid_cn_id_card(candidate):
                    continue
                results.append(
                    RecognizerResult(
                        entity_type="CN_ID",
                        start=match.start(1),
                        end=match.end(1),
                        score=0.95,
                    )
                )
            return results
