const words = (text) => text.match(/[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?/g) || [];

export function chunkText(text) {
  if (words(text).length > 10_000) throw new Error("Talking Page reads up to 10,000 words at once.");
  const blocks = text.trim().split(/\n\s*\n/).map((block) => block.replace(/\s+/g, " ").trim()).filter(Boolean);
  const chunks = [];
  for (let blockIndex = 0; blockIndex < blocks.length; blockIndex += 1) {
    const sentences = blocks[blockIndex].match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [];
    let current = "";
    for (const sentence of sentences.map((sentence) => sentence.trim()).filter(Boolean)) {
      if (sentence.length > 2000) throw new Error("One sentence is too long; select a shorter passage.");
      if (current && current.length + sentence.length + 1 > 1600) {
        chunks.push({ text: current, gapAfterMs: 120 });
        current = sentence;
      } else {
        current = `${current} ${sentence}`.trim();
      }
    }
    if (current) chunks.push({ text: current, gapAfterMs: blockIndex === blocks.length - 1 ? 0 : 450 });
  }
  return chunks;
}
