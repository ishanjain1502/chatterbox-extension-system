# Paralinguistic tagger — design

**Status:** Approved (2026-10-08)  
**Depends on:** Talking Page local TTS server (`NanoEngine`, Chatterbox-Nano)

## 1. Purpose

Insert Chatterbox-native paralinguistic tags into plain English text before synthesis so narration can use inline events (`[chuckle]`, `[sigh]`, etc.) without manual markup. A small neural **gap classifier** runs in the same Python process as the existing server, **side by side** with Chatterbox—not a separate HTTP service.

## 2. Goals

- Train from supervised pairs: **plain text → same text with `[tag]` tokens** (format A).
- Run on **every** synthesis chunk after existing `prepare_text` normalization.
- Insert tags only when the model’s confidence meets a **configurable env threshold**; otherwise pass plain text unchanged.
- Restrict outputs to the official Turbo/Nano paralinguistic set (no invented tags).

## 3. Non-goals

- Changing the Chrome extension protocol for MVP of this feature (server-side only).
- Predicting `exaggeration` / `cfg` TTS parameters (tags only).
- Hosted or GPU training infrastructure in-repo.
- Replacing Chatterbox or running a second TTS stack.

## 4. Allowed tags

Fixed vocabulary (must match Chatterbox Turbo/Nano):

| Tag |
|-----|
| `[clear throat]` |
| `[sigh]` |
| `[shush]` |
| `[cough]` |
| `[groan]` |
| `[sniff]` |
| `[gasp]` |
| `[chuckle]` |
| `[laugh]` |

Model classes: `none` plus one class per tag above.

## 5. Architecture

```text
Extension chunk (plain)
  → Service.synthesize (auth, 10k word limit on request plain text)
  → prepare_text (existing)
  → ParalinguisticTagger.annotate(text)
  → validate_chunk (2,000-character cap on final string)
  → NanoEngine.synthesize(text)
```

### Components

| Unit | Responsibility |
|------|----------------|
| `align.py` | Derive per-gap gold labels from `(plain, tagged)` pairs |
| `model.py` | Small PyTorch module (1-layer BiLSTM over word embeddings + linear head per gap) |
| `tagger.py` | Load weights, tokenize, run inference, apply threshold, build output string |
| `train.py` | CLI: read JSONL, train, write `paralinguistic_tagger.pt` + `vocab.json` |
| `Service` hook | Inject tagger between `prepare_text` and `engine.synthesize` |

Weights load **lazily** on first `annotate` call (same pattern as `NanoEngine.load`).

### Location

Under `server/paralinguistic/` (package) with tests in `server/tests/test_paralinguistic_*.py`.

## 6. Dataset

- **Format:** JSONL, one JSON object per line:
  - `{"plain": "...", "tagged": "..."}`
- **Recommended path:** `server/data/paralinguistic_pairs.jsonl` (user data; gitignore large files).
- **Fixture:** Small checked-in example for alignment and train smoke tests.
- **Scale:** On the order of **hundreds** of pairs; train/val split ~85/15; early stopping on validation F1 for non-`none` tag predictions.

Alignment assumes `tagged` equals `plain` with only allowed `[...]` tokens inserted (whitespace-normalized). Pairs that cannot be aligned are skipped at train time with a logged count.

## 7. Model (gap classifier)

1. Tokenize plain text into words (same word regex spirit as `count_words`: letters, digits, internal apostrophes).
2. For each gap index `g` in `0 .. len(words)` (before word `g`, including after the last word), compute a hidden vector from a **short context window** (e.g. words around the gap) via **learned word embeddings + 1-layer BiLSTM** (or equivalent basic ANN).
3. Linear layer → softmax over `none` + 9 tags.
4. At inference: for each gap, if `argmax != none` and `prob >= threshold`, insert ` [tag] ` at that position in the reconstructed string.

**Recommendation:** BiLSTM over the full sentence with per-gap positions taken from LSTM outputs at gap indices (single forward pass per chunk).

## 8. Confidence and environment

| Variable | Default | Behavior |
|----------|---------|----------|
| `TALKING_PAGE_TAG_CONFIDENCE_THRESHOLD` | `0.65` | Float in `[0, 1]`. Tag inserted at a gap only if `max softmax prob >= threshold` and class ≠ `none`. |
| `TALKING_PAGE_TAGGER_MODEL_PATH` | `server/models/paralinguistic_tagger.pt` (resolved relative to repo/server root) | Path to trained weights. |
| `TALKING_PAGE_TAGGER_ENABLED` | `1` | If `0`, skip annotator entirely (plain text only). |

**Always-on semantics:** When `TALKING_PAGE_TAGGER_ENABLED` is not `0` and the model file **exists**, every chunk is annotated. If the file is **missing**, log a one-time warning and pass plain text (repo usable before training). Invalid threshold or malformed env → **fail at server startup** (consistent with `Settings.from_environment`).

If **no** gap passes the threshold, output equals normalized plain text (no tags).

## 9. Integration with `talking_page_server.py`

- `Settings` gains optional tagger fields parsed from env.
- `Service.__init__` accepts an optional `ParalinguisticTagger` (default constructed from settings).
- `Service.synthesize`:
  1. Existing auth and `validate_total_word_count(text)` on incoming plain text.
  2. `normalized = prepare_text(text)`
  3. `for_synth = tagger.annotate(normalized)` when enabled and model available; else `for_synth = normalized`
  4. `validate_chunk(for_synth)` again (tags may increase length).
  5. `engine.synthesize(for_synth, ...)`

Tagger interface (for tests):

```python
def annotate(self, text: str) -> str: ...
```

## 10. Error handling

- `annotate` raises → propagate as synthesis failure with a safe client message (no stack traces over HTTP).
- Post-annotate length &gt; 2,000 characters → same `ValueError` as current `validate_chunk`.
- Training CLI: report skipped unalignable rows; non-zero exit if zero usable rows.

## 11. Testing

- **Alignment:** Synthetic pairs → expected gap labels and reconstructed tagged strings.
- **Threshold:** Mock or tiny fixture weights; high threshold → plain; low threshold + biased logits → tags appear.
- **Service:** Fake engine records input text; assert tagged string when tagger stub returns tags.
- **Config:** Invalid threshold rejected at settings load.
- CI should not require downloading Chatterbox for tagger-only tests; use fakes for `Service` integration.

## 12. Documentation

- `.env.example`: new variables with short comments.
- `README.md`: subsection on dataset format, training command, model path, and threshold tuning.

## 13. Security and privacy

- Training data stays local; no new network endpoints.
- Tagger runs in-process on text already sent to the local TTS service.

## 14. Future extensions (out of scope)

- Extension toggle for expressive vs neutral reading.
- Per-tag thresholds or max tags per chunk.
- Larger models or pre-trained encoders if the dataset grows.
