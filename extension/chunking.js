const words = (text) => text.match(/[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?/g) || [];

const GAP_HEADING_MS = 750;
const GAP_PARAGRAPH_MS = 450;
const GAP_LIST_ITEM_MS = 250;
const GAP_SENTENCE_MS = 120;
const MAX_CHUNK_CHARS = 1_600;
const MAX_SENTENCE_CHARS = 2_000;

function isHeadingBlock(block, blockIndex, blockCount) {
  if (blockCount <= 1) return false;
  return !/[.!?]["']?\s*$/.test(block.trim());
}

function isListItemBlock(block) {
  return /^[-*•]\s/.test(block.trim()) || /^\d+[.)]\s/.test(block.trim());
}

function gapForBlock(block, blockIndex, blockCount) {
  if (blockIndex === blockCount - 1) return 0;
  if (isHeadingBlock(block)) return GAP_HEADING_MS;
  if (isListItemBlock(block)) return GAP_LIST_ITEM_MS;
  return GAP_PARAGRAPH_MS;
}

export function wordCount(text) {
  return words(text).length;
}

export function chunkText(text) {
  if (wordCount(text) > 10_000) {
    throw new Error("Talking Page reads up to 10,000 words at once.");
  }

  const blocks = text
    .trim()
    .split(/\n\s*\n/)
    .map((block) => block.replace(/\s+/g, " ").trim())
    .filter(Boolean);

  const chunks = [];

  for (let blockIndex = 0; blockIndex < blocks.length; blockIndex += 1) {
    const block = blocks[blockIndex];
    const heading = isHeadingBlock(block, blockIndex, blocks.length);
    const sentences = block.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [block];

    let current = "";
    for (const rawSentence of sentences.map((sentence) => sentence.trim()).filter(Boolean)) {
      const sentence = heading && !/[.!?]["']?\s*$/.test(rawSentence) ? `${rawSentence}.` : rawSentence;

      if (sentence.length > MAX_SENTENCE_CHARS) {
        throw new Error("One sentence is too long; select a shorter passage.");
      }

      if (current && current.length + sentence.length + 1 > MAX_CHUNK_CHARS) {
        chunks.push({ text: current, gapAfterMs: GAP_SENTENCE_MS });
        current = sentence;
      } else {
        current = `${current} ${sentence}`.trim();
      }
    }

    if (current) {
      chunks.push({ text: current, gapAfterMs: gapForBlock(block, blockIndex, blocks.length) });
    }
  }

  return chunks;
}
