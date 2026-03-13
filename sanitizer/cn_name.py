"""Chinese PERSON recognizer placeholder."""


class ChineseNameRecognizer:
    """Compatibility placeholder used when NLP recognizers are unavailable."""

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: object | None = None,
    ) -> list[object]:
        del text, entities, nlp_artifacts
        return []
