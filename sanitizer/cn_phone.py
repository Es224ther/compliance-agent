"""Chinese mainland phone recognizer placeholder."""

import re

CN_PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")


class ChinesePhoneRecognizer:
    """Compatibility placeholder used when Presidio is unavailable."""

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: object | None = None,
    ) -> list[object]:
        del text, entities, nlp_artifacts
        return []
