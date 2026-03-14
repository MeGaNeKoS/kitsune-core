from core.interfaces.recognition import BaseRecognizer
from core.features import is_available


def get_recognizer(name: str = "aniparse", **kwargs) -> BaseRecognizer:
    recognizers = {}
    if is_available("recognition"):
        from core.recognition.aniparse_recognizer import AniparseRecognizer
        recognizers[AniparseRecognizer.get_name()] = AniparseRecognizer
    if is_available("llm"):
        from core.recognition.llm_recognizer import LLMRecognizer
        recognizers[LLMRecognizer.get_name()] = LLMRecognizer

    recognizer_cls = recognizers.get(name)
    if recognizer_cls:
        return recognizer_cls(**kwargs)

    available = list(recognizers.keys()) or ["none — install kitsune-core[recognition] or kitsune-core[llm]"]
    raise ValueError(f"Recognizer {name!r} not found. Available: {', '.join(available)}")
