"""Text features for the local classifiers.

Pure Python on purpose. Training and inference both call this function, so
there is no second implementation that can drift, and the runtime image needs
no numpy or scikit-learn to serve a model.
"""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass

_WORD = re.compile(r"\w+")
_DIGIT = re.compile(r"\d")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class FeatureConfig:
    word_ngrams: tuple[int, int] = (1, 2)
    char_ngrams: tuple[int, int] = (3, 5)

    def to_dict(self) -> dict[str, list[int]]:
        return {key: list(value) for key, value in asdict(self).items()}

    @classmethod
    def from_dict(cls, data: Mapping[str, list[int]]) -> "FeatureConfig":
        word, char = data["word_ngrams"], data["char_ngrams"]
        return cls(word_ngrams=(word[0], word[1]), char_ngrams=(char[0], char[1]))


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    # "118/min" and "96/min" should look alike: the shape of a measurement says
    # more about its category than the value does.
    text = _DIGIT.sub("0", text)
    return _WHITESPACE.sub(" ", text).strip()


def extract_features(text: str, config: FeatureConfig) -> Counter[str]:
    """Word n-grams plus character n-grams inside word boundaries.

    Character n-grams carry most of the signal on short clinical phrases:
    "-aemia", "mmol", "ct " survive spelling variants and unseen words.
    """
    normalized = normalize(text)
    words = _WORD.findall(normalized)
    features: Counter[str] = Counter()

    low, high = config.word_ngrams
    for size in range(low, high + 1):
        for start in range(len(words) - size + 1):
            features["w:" + " ".join(words[start : start + size])] += 1

    low, high = config.char_ngrams
    for word in words:
        padded = f" {word} "
        for size in range(low, high + 1):
            if len(padded) < size:
                break
            for start in range(len(padded) - size + 1):
                features["c:" + padded[start : start + size]] += 1
    return features


def tfidf_vector(counts: Mapping[str, int], idf: Mapping[str, float]) -> dict[str, float]:
    """Sublinear tf * idf, L2-normalised. Features unseen in training are dropped."""
    weights = {
        name: (1 + math.log(count)) * idf[name] for name, count in counts.items() if name in idf
    }
    norm = math.sqrt(sum(value * value for value in weights.values()))
    if norm == 0:
        return {}
    return {name: value / norm for name, value in weights.items()}
