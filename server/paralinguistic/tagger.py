import logging
from pathlib import Path

import torch

from server.paralinguistic.align import build_tagged_string
from server.paralinguistic.model import GapTaggerModel
from server.paralinguistic.tags import INDEX_TO_TAG
from server.paralinguistic.tokens import tokenize_words

logger = logging.getLogger(__name__)


class ParalinguisticTagger:
    def __init__(self, model_path: str | Path, confidence_threshold: float, enabled: bool = True):
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self.enabled = enabled
        self._model: GapTaggerModel | None = None
        self._vocab: dict[str, int] | None = None
        self._warned_missing = False

    def _load(self):
        if self._model is not None:
            return
        if not self.model_path.is_file():
            if not self._warned_missing:
                logger.warning("paralinguistic tagger model not found at %s; passing plain text", self.model_path)
                self._warned_missing = True
            return
        checkpoint = torch.load(self.model_path, map_location="cpu", weights_only=False)
        self._vocab = checkpoint["vocab"]
        vocab_size = max(self._vocab.values()) + 1
        self._model = GapTaggerModel(vocab_size=vocab_size)
        self._model.load_state_dict(checkpoint["model_state"])
        self._model.eval()

    def _word_to_index(self, word: str) -> int:
        assert self._vocab is not None
        return self._vocab.get(word.lower(), self._vocab.get("<unk>", 0))

    def annotate(self, text: str) -> str:
        if not self.enabled:
            return text
        words = tokenize_words(text)
        if not words:
            return text
        self._load()
        if self._model is None or self._vocab is None:
            return text
        indices = torch.tensor([[self._word_to_index(word) for word in words]], dtype=torch.long)
        with torch.no_grad():
            logits = self._model(indices)[0]
            probs = torch.softmax(logits, dim=-1)
        gap_classes: list[int] = []
        for gap in range(len(words) + 1):
            prob_row = probs[gap]
            best_index = int(prob_row.argmax().item())
            best_prob = float(prob_row[best_index].item())
            if best_index != 0 and best_prob >= self.confidence_threshold:
                gap_classes.append(best_index)
            else:
                gap_classes.append(0)
        return build_tagged_string(words, gap_classes)
