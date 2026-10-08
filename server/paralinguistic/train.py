import argparse
import json
import random
import sys
from pathlib import Path

import torch
from torch import nn

from server.paralinguistic.align import align_pair
from server.paralinguistic.model import GapTaggerModel
from server.paralinguistic.tokens import tokenize_words


def load_pairs(data_path: Path) -> list[tuple[list[str], list[int]]]:
    examples: list[tuple[list[str], list[int]]] = []
    skipped = 0
    for line in data_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        labels = align_pair(row["plain"], row["tagged"])
        if labels is None:
            skipped += 1
            continue
        words = tokenize_words(row["plain"])
        examples.append((words, labels))
    if skipped:
        print(f"skipped {skipped} unalignable rows", file=sys.stderr)
    return examples


def build_vocab(examples: list[tuple[list[str], list[int]]]) -> dict[str, int]:
    vocab = {"<unk>": 0}
    for words, _ in examples:
        for word in words:
            key = word.lower()
            if key not in vocab:
                vocab[key] = len(vocab)
    return vocab


def examples_to_tensors(
    examples: list[tuple[list[str], list[int]]], vocab: dict[str, int]
) -> list[tuple[torch.Tensor, torch.Tensor]]:
    tensors: list[tuple[torch.Tensor, torch.Tensor]] = []
    for words, labels in examples:
        indices = [vocab.get(word.lower(), vocab["<unk>"]) for word in words]
        tensors.append(
            (
                torch.tensor(indices, dtype=torch.long),
                torch.tensor(labels, dtype=torch.long),
            )
        )
    return tensors


def train_model(
    data_path: Path,
    output_path: Path,
    epochs: int = 50,
    val_fraction: float = 0.15,
    seed: int = 42,
) -> None:
    examples = load_pairs(data_path)
    if not examples:
        raise SystemExit("no alignable training examples")
    random.seed(seed)
    random.shuffle(examples)
    split = max(1, int(len(examples) * (1 - val_fraction)))
    train_examples = examples[:split]
    val_examples = examples[split:] or examples[:1]
    vocab = build_vocab(train_examples)
    train_tensors = examples_to_tensors(train_examples, vocab)
    val_tensors = examples_to_tensors(val_examples, vocab)
    model = GapTaggerModel(vocab_size=len(vocab))
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    best_val = float("inf")
    best_state = None
    for _ in range(epochs):
        model.train()
        for word_indices, labels in train_tensors:
            logits = model(word_indices.unsqueeze(0))[0]
            loss = loss_fn(logits, labels)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for word_indices, labels in val_tensors:
                logits = model(word_indices.unsqueeze(0))[0]
                val_loss += float(loss_fn(logits, labels).item())
        val_loss /= len(val_tensors)
        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"vocab": vocab, "model_state": model.state_dict()}, output_path)


def main():
    parser = argparse.ArgumentParser(description="Train paralinguistic gap tagger")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=50)
    args = parser.parse_args()
    train_model(args.data, args.out, epochs=args.epochs)


if __name__ == "__main__":
    main()
