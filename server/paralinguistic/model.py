import torch
from torch import nn

from server.paralinguistic.tags import NUM_CLASSES


class GapTaggerModel(nn.Module):
    def __init__(self, vocab_size: int, emb_dim: int = 64, hidden_dim: int = 64):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, emb_dim)
        self.lstm = nn.LSTM(emb_dim, hidden_dim, batch_first=True, bidirectional=True)
        lstm_out = hidden_dim * 2
        self.gap_head = nn.Linear(lstm_out, NUM_CLASSES)

    def forward(self, word_indices: torch.Tensor) -> torch.Tensor:
        # word_indices: [B, T]
        batch_size, seq_len = word_indices.shape
        embedded = self.embedding(word_indices)
        lstm_out, _ = self.lstm(embedded)
        gap_hidden = []
        for gap in range(seq_len + 1):
            source = min(gap, seq_len - 1) if seq_len > 0 else 0
            if seq_len == 0:
                gap_hidden.append(torch.zeros(batch_size, lstm_out.shape[-1], device=word_indices.device))
            else:
                gap_hidden.append(lstm_out[:, source, :])
        stacked = torch.stack(gap_hidden, dim=1)
        return self.gap_head(stacked)
