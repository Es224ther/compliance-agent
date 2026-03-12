"""Chinese PERSON recognizer backed by spaCy NER artifacts."""

import re

from presidio_analyzer import LocalRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

CHINESE_NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,4}")


class ChineseNameRecognizer(LocalRecognizer):
    """Detect PERSON entities from the Chinese spaCy pipeline."""

    def __init__(self) -> None:
        super().__init__(
            supported_entities=["PERSON"],
            name="Chinese Name Recognizer",
            supported_language="zh",
            context=["姓名", "联系人", "用户", "先生", "女士"],
        )

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        if entities and "PERSON" not in entities:
            return []
        if not nlp_artifacts:
            return []

        results: list[RecognizerResult] = []
        for index, entity in enumerate(nlp_artifacts.entities):
            if entity.label_.upper() != "PERSON":
                continue
            if not CHINESE_NAME_RE.fullmatch(entity.text):
                continue

            score = 0.85
            if index < len(nlp_artifacts.scores):
                score = float(nlp_artifacts.scores[index])

            results.append(
                RecognizerResult(
                    entity_type="PERSON",
                    start=entity.start_char,
                    end=entity.end_char,
                    score=score,
                )
            )
        return results
