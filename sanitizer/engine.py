"""AnalyzerEngine wrapper for local multilingual PII detection."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(
    r"(?i)(?<![a-z0-9._%+-])[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}(?![a-z0-9._%+-])"
)
CN_PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")

EN_MODEL_NAME = "en_core_web_lg"
ZH_MODEL_NAME = "zh_core_web_sm"
SUPPORTED_LANGUAGES = ["en", "zh"]

try:
    import spacy
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
    from presidio_analyzer.nlp_engine import SpacyNlpEngine

    from sanitizer.cn_id_card import ChineseIdCardRecognizer, CN_ID_PATTERN
    from sanitizer.cn_name import ChineseNameRecognizer
    from sanitizer.cn_phone import ChinesePhoneRecognizer

    PRESIDIO_AVAILABLE = True
except ModuleNotFoundError:
    spacy = None
    AnalyzerEngine = None
    Pattern = None
    PatternRecognizer = None
    RecognizerRegistry = None
    SpacyNlpEngine = None
    ChineseIdCardRecognizer = None
    ChineseNameRecognizer = None
    ChinesePhoneRecognizer = None
    from sanitizer.cn_id_card import CN_ID_PATTERN

    PRESIDIO_AVAILABLE = False


@dataclass(slots=True)
class DetectionResult:
    """Minimal recognizer result used by the fallback engine."""

    entity_type: str
    start: int
    end: int
    score: float


if PRESIDIO_AVAILABLE:

    class SafeSpacyNlpEngine(SpacyNlpEngine):
        """SpaCy engine which falls back to blank pipelines instead of downloading."""

        def load(self) -> None:
            self.nlp = {}
            for model in self.models:
                lang_code = model["lang_code"]
                model_name = model["model_name"]
                try:
                    self.nlp[lang_code] = spacy.load(model_name)
                except OSError:
                    LOGGER.warning(
                        "spaCy model %s is unavailable for %s; falling back to spacy.blank(%s)",
                        model_name,
                        lang_code,
                        lang_code,
                    )
                    pipeline = spacy.blank(lang_code)
                    if "sentencizer" not in pipeline.pipe_names:
                        pipeline.add_pipe("sentencizer")
                    self.nlp[lang_code] = pipeline


class SanitizerEngine:
    """Wrapper around Presidio AnalyzerEngine with Chinese custom recognizers."""

    def __init__(self) -> None:
        self._fallback_mode = not PRESIDIO_AVAILABLE
        self.zh_ner_available = False
        self.en_ner_available = False

        if self._fallback_mode:
            LOGGER.warning(
                "Presidio dependencies are unavailable; using regex-only sanitizer fallback."
            )
            self.analyzer = None
            return

        self.zh_ner_available = self._is_model_available(ZH_MODEL_NAME)
        self.en_ner_available = self._is_model_available(EN_MODEL_NAME)

        self.nlp_engine = SafeSpacyNlpEngine(
            models=[
                {"lang_code": "en", "model_name": EN_MODEL_NAME},
                {"lang_code": "zh", "model_name": ZH_MODEL_NAME},
            ]
        )
        self.nlp_engine.load()

        registry = RecognizerRegistry(supported_languages=SUPPORTED_LANGUAGES)
        registry.load_predefined_recognizers(languages=["en"], nlp_engine=self.nlp_engine)
        self._register_chinese_recognizers(registry)

        self.analyzer = AnalyzerEngine(
            registry=registry,
            nlp_engine=self.nlp_engine,
            supported_languages=SUPPORTED_LANGUAGES,
        )

    @staticmethod
    def _is_model_available(model_name: str) -> bool:
        try:
            spacy.load(model_name)
            return True
        except OSError:
            return False

    def _register_chinese_recognizers(self, registry: RecognizerRegistry) -> None:
        registry.add_recognizer(ChinesePhoneRecognizer())
        registry.add_recognizer(ChineseIdCardRecognizer())
        registry.add_recognizer(self._build_chinese_email_recognizer())
        if self.zh_ner_available:
            registry.add_recognizer(ChineseNameRecognizer())
        else:
            LOGGER.warning(
                "spaCy model %s is unavailable; Chinese PERSON detection is disabled and regex recognizers remain active",
                ZH_MODEL_NAME,
            )

    @staticmethod
    def _build_chinese_email_recognizer() -> PatternRecognizer:
        return PatternRecognizer(
            supported_entity="EMAIL_ADDRESS",
            name="Chinese Email Recognizer",
            supported_language="zh",
            patterns=[
                Pattern(
                    name="zh_email_pattern",
                    regex=EMAIL_PATTERN.pattern,
                    score=0.85,
                )
            ],
            context=["邮箱", "邮件", "email"],
        )

    def analyze(
        self,
        text: str,
        language: str,
        entities: list[str] | None = None,
    ):
        """Analyze text for PII entities in the requested language."""

        if self._fallback_mode:
            return self._fallback_analyze(text=text, entities=entities)

        return self.analyzer.analyze(text=text, language=language, entities=entities)

    def _fallback_analyze(
        self,
        text: str,
        entities: list[str] | None = None,
    ) -> list[DetectionResult]:
        requested = set(entities or ["EMAIL_ADDRESS", "CN_PHONE", "CN_ID"])
        results: list[DetectionResult] = []

        if "EMAIL_ADDRESS" in requested:
            results.extend(
                DetectionResult(
                    entity_type="EMAIL_ADDRESS",
                    start=match.start(),
                    end=match.end(),
                    score=0.85,
                )
                for match in EMAIL_PATTERN.finditer(text)
            )

        if "CN_PHONE" in requested:
            results.extend(
                DetectionResult(
                    entity_type="CN_PHONE",
                    start=match.start(),
                    end=match.end(),
                    score=0.85,
                )
                for match in CN_PHONE_PATTERN.finditer(text)
            )

        if "CN_ID" in requested:
            results.extend(
                DetectionResult(
                    entity_type="CN_ID",
                    start=match.start(1),
                    end=match.end(1),
                    score=0.95,
                )
                for match in CN_ID_PATTERN.finditer(text)
            )

        return sorted(results, key=lambda item: (item.start, item.end))


