# Paralinguistic tagger implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small in-process gap-classifier ANN that inserts Chatterbox paralinguistic tags into normalized text before `NanoEngine.synthesize`, trained from plain→tagged JSONL pairs with confidence controlled by env.

**Architecture:** New `server/paralinguistic/` package (`align`, `model`, `tagger`, `train`) sits beside the monolithic `talking_page_server.py`. `Service.synthesize` calls `prepare_text` → `ParalinguisticTagger.annotate` → `validate_chunk` → engine. Weights load lazily; missing model file logs once and passes plain text.

**Tech Stack:** Python 3.11, PyTorch (already in `server/requirements.txt`), `unittest` (existing test style), JSONL training data.

**Spec:** `docs/superpowers/specs/2026-10-08-paralinguistic-tagger-design.md`

## Global Constraints

- Allowed tags only: `[clear throat]`, `[sigh]`, `[shush]`, `[cough]`, `[groan]`, `[sniff]`, `[gasp]`, `[chuckle]`, `[laugh]`, plus class `none`.
- Run tagger after `prepare_text` on every chunk when `TALKING_PAGE_TAGGER_ENABLED` is not `0` and model file exists.
- Insert a tag at a gap only if softmax probability ≥ `TALKING_PAGE_TAG_CONFIDENCE_THRESHOLD` (default `0.65`) and class ≠ `none`.
- Reject post-annotate text over 2,000 characters via existing `validate_chunk`.
- Invalid tagger env at startup → `ValueError` (same as token/host validation).
- No new HTTP routes; extension unchanged.
- CI tagger tests must not load Chatterbox.

---

## File structure

```text
server/
  paralinguistic/
    __init__.py              re-exports ParalinguisticTagger, PARALINGUISTIC_TAGS
    tags.py                  fixed tag list, class index maps
    tokens.py                word regex tokenization (aligned with count_words spirit)
    align.py                 plain/tagged alignment → gap labels; reconstruct tagged string
    model.py                 GapTaggerModel (Embedding + BiLSTM + Linear)
    tagger.py                ParalinguisticTagger.annotate, lazy torch load
    train.py                 `python -m server.paralinguistic.train` CLI
  data/
    paralinguistic_pairs.fixture.jsonl   checked-in tiny dataset for tests/train smoke
  models/                              gitkeep; trained .pt written here locally
  talking_page_server.py               Settings + Service hook
  tests/
    test_paralinguistic_align.py
    test_paralinguistic_tagger.py
    test_paralinguistic_train.py
    test_config.py                     extend for tagger env
    test_service.py                    extend for tagger stub
.env.example                           tagger env keys
README.md                              paralinguistic subsection
.gitignore                             optional ignore for large `server/data/*.jsonl`
```

---

### Task 1: Tag vocabulary and word tokenization

**Files:**
- Create: `server/paralinguistic/__init__.py`
- Create: `server/paralinguistic/tags.py`
- Create: `server/paralinguistic/tokens.py`
- Test: `server/tests/test_paralinguistic_tokens.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `PARALINGUISTIC_TAGS`, `TAG_TO_INDEX`, `INDEX_TO_TAG`, `NUM_CLASSES`, `tokenize_words(text: str) -> list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# server/tests/test_paralinguistic_tokens.py
import unittest

from server.paralinguistic.tags import NUM_CLASSES, PARALINGUISTIC_TAGS, TAG_TO_INDEX
from server.paralinguistic.tokens import tokenize_words


class TokenizeWordsTest(unittest.TestCase):
    def test_tokenize_words_matches_apostrophe_words(self):
        words = tokenize_words("It's a 2nd test.")
        self.assertEqual(["It's", "a", "2nd", "test"], words)

    def test_tag_inventory_has_nine_tags_plus_none_in_model(self):
        self.assertEqual(9, len(PARALINGUISTIC_TAGS))
        self.assertIn("[chuckle]", TAG_TO_INDEX)
        self.assertEqual(NUM_CLASSES, 10)  # none + 9 tags


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/Projects/talking-page && python -m unittest server.tests.test_paralinguistic_tokens -v`  
Expected: FAIL (`ModuleNotFoundError` or missing symbols).

- [ ] **Step 3: Implement minimal code**

`server/paralinguistic/tags.py`:

```python
PARALINGUISTIC_TAGS = (
    "[clear throat]",
    "[sigh]",
    "[shush]",
    "[cough]",
    "[groan]",
    "[sniff]",
    "[gasp]",
    "[chuckle]",
    "[laugh]",
)

NONE_TAG = "none"
TAG_TO_INDEX = {NONE_TAG: 0}
for i, tag in enumerate(PARALINGUISTIC_TAGS, start=1):
    TAG_TO_INDEX[tag] = i
INDEX_TO_TAG = {index: tag for tag, index in TAG_TO_INDEX.items()}
NUM_CLASSES = len(TAG_TO_INDEX)
```

`server/paralinguistic/tokens.py`:

```python
import re

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")


def tokenize_words(text: str) -> list[str]:
    return _WORD_RE.findall(text)
```

`server/paralinguistic/__init__.py`:

```python
from server.paralinguistic.tagger import ParalinguisticTagger

__all__ = ["ParalinguisticTagger"]
```

(Stub `tagger.py` temporarily with `class ParalinguisticTagger: pass` if import fails, or defer `__init__.py` import until Task 4.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest server.tests.test_paralinguistic_tokens -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/paralinguistic/tags.py server/paralinguistic/tokens.py server/tests/test_paralinguistic_tokens.py
git commit -m "feat: add paralinguistic tag vocabulary and word tokenizer"
```

---

### Task 2: Plain/tagged alignment and reconstruction

**Files:**
- Create: `server/paralinguistic/align.py`
- Test: `server/tests/test_paralinguistic_align.py`

**Interfaces:**
- Consumes: `tokenize_words`, `PARALINGUISTIC_TAGS`, `TAG_TO_INDEX`.
- Produces:
  - `parse_tagged_text(tagged: str) -> tuple[list[str], list[str | None]]` — words and per-gap label before each word (length `len(words)`); label on gap after last word stored separately or as extra slot.
  - `align_pair(plain: str, tagged: str) -> list[int] | None` — gap labels as class indices, length `len(words) + 1`, or `None` if unalignable.
  - `apply_gap_labels(words: list[str], gap_labels: list[int], threshold: float, probs: list[list[float]] | None = None)` — not here; reconstruction helper:
  - `build_tagged_string(words: list[str], gap_class_indices: list[int]) -> str` — insert tags at gaps where index ≠ 0.

Design detail: `gap_class_indices` has length `len(words) + 1`. Index `g` is the gap before word `g` (and `g == len(words)` is after the last word). Only one tag per gap; at most one non-none per gap.

`align_pair` algorithm:
1. `words = tokenize_words(plain)`.
2. Scan `tagged` left-to-right: alternate reading optional `[...]` tokens (must be in allowed set) and next plain word from `words`.
3. If words do not match exactly, return `None`.
4. Record which tag (if any) appeared immediately before each word; final gap after last word gets trailing tag if present.

- [ ] **Step 1: Write the failing test**

```python
# server/tests/test_paralinguistic_align.py
import unittest

from server.paralinguistic.align import align_pair, build_tagged_string
from server.paralinguistic.tags import TAG_TO_INDEX
from server.paralinguistic.tokens import tokenize_words


class AlignPairTest(unittest.TestCase):
    def test_aligns_mid_sentence_chuckle(self):
        plain = "Oh that is hilarious anyway we have a model."
        tagged = "Oh that is hilarious! [chuckle] Anyway we have a model."
        labels = align_pair(plain, tagged)
        self.assertIsNotNone(labels)
        words = tokenize_words(plain)
        self.assertEqual(len(words) + 1, len(labels))
        anyway_index = words.index("anyway")
        self.assertEqual(TAG_TO_INDEX["[chuckle]"], labels[anyway_index])

    def test_build_tagged_string_round_trip(self):
        plain = "Hello world"
        tagged = "Hello [sigh] world"
        labels = align_pair(plain, tagged)
        rebuilt = build_tagged_string(tokenize_words(plain), labels)
        self.assertEqual(tagged.replace("  ", " "), rebuilt.replace("  ", " "))

    def test_returns_none_when_words_differ(self):
        self.assertIsNone(align_pair("Hello", "Hello [chuckle] there"))


if __name__ == "__main__":
    unittest.main()
```

Adjust round-trip assertion if punctuation normalization differs; `align_pair` should tokenize words only (punctuation between words is not in word list but may appear in tagged string between tokens).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest server.tests.test_paralinguistic_align -v`  
Expected: FAIL

- [ ] **Step 3: Implement `align.py`**

Implement `parse_tagged_text` using regex to find `[...]` tags and interleaved words via `tokenize_words` on remaining segments. Implement `align_pair` and `build_tagged_string` joining words with single spaces and inserting ` [tag] ` at gaps with non-zero class.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest server.tests.test_paralinguistic_align -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/paralinguistic/align.py server/tests/test_paralinguistic_align.py
git commit -m "feat: align plain and tagged paralinguistic training pairs"
```

---

### Task 3: GapTaggerModel (BiLSTM)

**Files:**
- Create: `server/paralinguistic/model.py`
- Test: `server/tests/test_paralinguistic_model.py`

**Interfaces:**
- Consumes: `NUM_CLASSES`.
- Produces:
  - `class GapTaggerModel(torch.nn.Module)` with `forward(word_indices: Tensor[B, T]) -> Tensor[B, T+1, NUM_CLASSES]` (logits per gap).

Implementation sketch:
- `Embedding(vocab_size, emb_dim=64)`
- `nn.LSTM(emb_dim, hidden=64, batch_first=True, bidirectional=True)`
- For gap `g` in `0..T`, use hidden state at position `min(g, T-1)` or concat forward at `g-1` and backward at `g` — use **concat of LSTM outputs at index `clamp(g-1,0,T-1)`** for each gap; simpler approach: run LSTM on words, pad a dummy token, take `T+1` positions from `torch.cat([h_start, h_words], dim=1)` where `h_start` is zeros.
- Recommended simple approach: `gap_hidden[g] = lstm_out[:, min(g, T-1), :]` for `g in range(T+1)` with `lstm_out` shape `[B, T, 2*hidden]`; linear to `NUM_CLASSES`.

- [ ] **Step 1: Write the failing test**

```python
import unittest
import torch

from server.paralinguistic.model import GapTaggerModel
from server.paralinguistic.tags import NUM_CLASSES


class GapTaggerModelTest(unittest.TestCase):
    def test_output_shape_has_one_more_gap_than_words(self):
        model = GapTaggerModel(vocab_size=50)
        x = torch.tensor([[1, 2, 3, 4]])
        logits = model(x)
        self.assertEqual((1, 5, NUM_CLASSES), tuple(logits.shape))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest server.tests.test_paralinguistic_model -v`  
Expected: FAIL

- [ ] **Step 3: Implement `model.py`**

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest server.tests.test_paralinguistic_model -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/paralinguistic/model.py server/tests/test_paralinguistic_model.py
git commit -m "feat: add BiLSTM gap tagger model"
```

---

### Task 4: ParalinguisticTagger inference and threshold

**Files:**
- Create: `server/paralinguistic/tagger.py`
- Modify: `server/paralinguistic/__init__.py`
- Test: `server/tests/test_paralinguistic_tagger.py`

**Interfaces:**
- Consumes: `GapTaggerModel`, `align.build_tagged_string`, `tokenize_words`, `TAG_TO_INDEX`, `INDEX_TO_TAG`.
- Produces:
  - `class ParalinguisticTagger:`  
    - `__init__(self, model_path: str | Path, confidence_threshold: float, enabled: bool = True)`  
    - `annotate(self, text: str) -> str`

Behavior:
- If `not enabled`: return `text`.
- If model file missing: set `_warned_missing` flag, log warning once, return `text`.
- Lazy-load checkpoint dict: `{"model_state": ..., "vocab": {"<unk>": 0, ...}}`.
- `torch.no_grad()` inference; softmax per gap; insert tag when `prob >= confidence_threshold` and class ≠ 0.
- Empty word list: return `text` unchanged.

- [ ] **Step 1: Write the failing test**

Use a saved tiny checkpoint in test via `torch.save` in `setUp` to a temp file, or use `unittest.mock` patch on `_load_model`. Prefer **real tiny train** in test: build model, set weights so gap 1 always predicts `[sigh]` with high logit.

```python
import tempfile
import unittest
from pathlib import Path

import torch

from server.paralinguistic.model import GapTaggerModel
from server.paralinguistic.tags import NUM_CLASSES, TAG_TO_INDEX
from server.paralinguistic.tagger import ParalinguisticTagger


class ParalinguisticTaggerTest(unittest.TestCase):
    def _write_tiny_checkpoint(self, path: Path):
        vocab = {"<unk>": 0, "hello": 1, "world": 2}
        model = GapTaggerModel(vocab_size=len(vocab))
        with torch.no_grad():
            model.gap_head.bias.zero_()
            model.gap_head.bias[TAG_TO_INDEX["[sigh]"]] = 10.0
        torch.save({"vocab": vocab, "model_state": model.state_dict()}, path)

    def test_high_threshold_skips_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "tagger.pt"
            self._write_tiny_checkpoint(ckpt)
            tagger = ParalinguisticTagger(ckpt, confidence_threshold=0.99, enabled=True)
            self.assertEqual("Hello world", tagger.annotate("Hello world"))

    def test_low_threshold_inserts_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "tagger.pt"
            self._write_tiny_checkpoint(ckpt)
            tagger = ParalinguisticTagger(ckpt, confidence_threshold=0.01, enabled=True)
            out = tagger.annotate("Hello world")
            self.assertIn("[sigh]", out)


if __name__ == "__main__":
    unittest.main()
```

Adjust if bias-only trick does not dominate; may need to set `gap_head.weight` small and bias as above.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest server.tests.test_paralinguistic_tagger -v`  
Expected: FAIL

- [ ] **Step 3: Implement `tagger.py`**

Expose `gap_head` as the final `Linear` in `GapTaggerModel` for test hook, or name module `self.classifier`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest server.tests.test_paralinguistic_tagger -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/paralinguistic/tagger.py server/paralinguistic/__init__.py server/tests/test_paralinguistic_tagger.py
git commit -m "feat: add paralinguistic tagger inference with confidence threshold"
```

---

### Task 5: Training CLI and fixture dataset

**Files:**
- Create: `server/paralinguistic/train.py`
- Create: `server/data/paralinguistic_pairs.fixture.jsonl`
- Create: `server/models/.gitkeep`
- Test: `server/tests/test_paralinguistic_train.py`

**Interfaces:**
- Consumes: `align_pair`, `GapTaggerModel`, `tokenize_words`, `NUM_CLASSES`.
- Produces: CLI entry `python -m server.paralinguistic.train --data PATH --out PATH` writing `paralinguistic_tagger.pt`.

Fixture JSONL (two lines minimum):

```json
{"plain": "Oh that is hilarious anyway we have a model.", "tagged": "Oh that is hilarious! [chuckle] Anyway we have a model."}
{"plain": "Hello world", "tagged": "Hello [sigh] world"}
```

Train script:
- Load JSONL, skip unalignable rows, print skip count.
- Build vocab from training words (`<unk>` index 0).
- Tensor dataset: variable-length sequences padded in batch.
- Loss: `CrossEntropyLoss` on all gaps (class 0 weighted or not — default unweighted).
- Train ≤ 50 epochs with early stop on val loss; default val split 15%.
- Exit code 1 if zero usable rows.

- [ ] **Step 1: Write the failing test**

```python
import json
import tempfile
import unittest
from pathlib import Path

from server.paralinguistic.train import train_model


class TrainModelTest(unittest.TestCase):
    def test_train_model_writes_checkpoint(self):
        fixture = Path(__file__).resolve().parents[1] / "data" / "paralinguistic_pairs.fixture.jsonl"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "tagger.pt"
            train_model(data_path=fixture, output_path=out, epochs=5)
            self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest server.tests.test_paralinguistic_train -v`  
Expected: FAIL

- [ ] **Step 3: Implement `train.py`**

Add `if __name__ == "__main__":` argparse.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest server.tests.test_paralinguistic_train -v`  
Expected: PASS (may take a few seconds)

- [ ] **Step 5: Commit**

```bash
git add server/paralinguistic/train.py server/data/paralinguistic_pairs.fixture.jsonl server/models/.gitkeep server/tests/test_paralinguistic_train.py
git commit -m "feat: add paralinguistic tagger training CLI"
```

---

### Task 6: Settings env parsing

**Files:**
- Modify: `server/talking_page_server.py` (`Settings`)
- Modify: `server/tests/test_config.py`

**Interfaces:**
- Consumes: none.
- Produces: `Settings` fields: `tagger_enabled: bool`, `tagger_model_path: str`, `tag_confidence_threshold: float`.

Parsing in `from_environment`:
- `TALKING_PAGE_TAGGER_ENABLED`: default `"1"`; enabled if value not in `("0", "false", "False")`.
- `TALKING_PAGE_TAG_CONFIDENCE_THRESHOLD`: default `0.65`; must parse float in `[0, 1]`.
- `TALKING_PAGE_TAGGER_MODEL_PATH`: default resolve to `Path(__file__).resolve().parent / "models" / "paralinguistic_tagger.pt"`.

- [ ] **Step 1: Write the failing test**

```python
    def test_tagger_threshold_must_be_between_zero_and_one(self):
        with patch.dict(
            os.environ,
            {
                "TALKING_PAGE_TOKEN": "a" * 32,
                "TALKING_PAGE_TAG_CONFIDENCE_THRESHOLD": "1.5",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "TALKING_PAGE_TAG_CONFIDENCE_THRESHOLD"):
                Settings.from_environment()

    def test_tagger_defaults(self):
        with patch.dict(os.environ, {"TALKING_PAGE_TOKEN": "a" * 32}, clear=True):
            settings = Settings.from_environment()
        self.assertTrue(settings.tagger_enabled)
        self.assertAlmostEqual(0.65, settings.tag_confidence_threshold)
```

Extend `Settings` dataclass with new fields **after** `voice_sample_path` with defaults so existing `Settings(host, port, token, None)` calls still work.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest server.tests.test_config -v`  
Expected: FAIL on new tests

- [ ] **Step 3: Implement env parsing**

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest server.tests.test_config -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/talking_page_server.py server/tests/test_config.py
git commit -m "feat: add paralinguistic tagger settings from environment"
```

---

### Task 7: Service synthesis hook

**Files:**
- Modify: `server/talking_page_server.py` (`Service.__init__`, `Service.synthesize`)
- Modify: `server/tests/test_service.py`

**Interfaces:**
- Consumes: `ParalinguisticTagger`, extended `Settings`.
- Produces: synthesis path that passes annotated text to the engine.

- [ ] **Step 1: Write the failing test**

```python
class RecordingEngine:
    def __init__(self):
        self.last_text = None

    def synthesize(self, text, fingerprint, source):
        self.last_text = text
        return GeneratedAudio(b"wav", 1200)


class TaggerStub:
    def __init__(self, suffix):
        self.suffix = suffix

    def annotate(self, text):
        return text + self.suffix


class ServiceTaggerTest(unittest.TestCase):
    def test_synthesize_passes_annotated_text_to_engine(self):
        engine = RecordingEngine()
        settings = Settings("127.0.0.1", 8765, "a" * 32, None)
        tagger = TaggerStub(" [chuckle]")
        service = Service(settings, engine, tagger=tagger)
        service.synthesize("a" * 32, "12-example.com", 0, "Hello.", now=100)
        self.assertIn("[chuckle]", engine.last_text)
```

Add optional `tagger=None` to `Service.__init__`; when `None`, construct `ParalinguisticTagger` from settings.

Change `synthesize` body:

```python
normalized = prepare_text(text)
for_synth = self.tagger.annotate(normalized)
validate_chunk(for_synth)
generated = self.engine.synthesize(for_synth, fingerprint, source)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest server.tests.test_service -v`  
Expected: FAIL on new test

- [ ] **Step 3: Implement hook**

- [ ] **Step 4: Run full server tests**

Run: `python -m unittest discover -s server/tests -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/talking_page_server.py server/tests/test_service.py
git commit -m "feat: run paralinguistic tagger before TTS synthesis"
```

---

### Task 8: Documentation and gitignore

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `.gitignore`

- [ ] **Step 1: Update `.env.example`**

```dotenv
# Paralinguistic tagger (Chatterbox inline tags). Model file optional until you train one.
# TALKING_PAGE_TAGGER_ENABLED=1
# TALKING_PAGE_TAG_CONFIDENCE_THRESHOLD=0.65
# TALKING_PAGE_TAGGER_MODEL_PATH=server/models/paralinguistic_tagger.pt
```

- [ ] **Step 2: Add README subsection**

Cover: JSONL format, fixture path, train command:

```powershell
python -m server.paralinguistic.train --data server/data/paralinguistic_pairs.jsonl --out server/models/paralinguistic_tagger.pt
```

Explain threshold tuning and missing-model passthrough.

- [ ] **Step 3: Gitignore large user datasets**

Add line: `server/data/paralinguistic_pairs.jsonl` (keep fixture committed).

- [ ] **Step 4: Commit**

```bash
git add .env.example README.md .gitignore
git commit -m "docs: document paralinguistic tagger training and env"
```

---

## Spec coverage (self-review)

| Spec section | Task |
|--------------|------|
| Allowed tags / gap classifier | 1, 3, 4 |
| JSONL dataset + fixture | 5 |
| Confidence env + enabled flag | 6, 4 |
| Service pipeline order | 7 |
| Missing model passthrough | 4, 6 |
| Post-annotate validate_chunk | 7 |
| Training skip unalignable | 2, 5 |
| Tests without Chatterbox | all unit tests |
| README / .env.example | 8 |

No placeholders remain; signatures consistent (`annotate`, `align_pair`, `GapTaggerModel`, `Settings` fields).
