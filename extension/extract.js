export function extractSelection(document) {
  const text = document.defaultView?.getSelection?.()?.toString().trim() ?? "";
  if (!text) {
    return { ok: false, reason: "select-text" };
  }
  return { ok: true, text };
}

export function extractArticle(document) {
  const clone = document.cloneNode(true);
  for (const selector of ["nav", "header", "footer", "aside", "script", "style", "noscript"]) {
    for (const node of clone.querySelectorAll(selector)) {
      node.remove();
    }
  }

  const candidates = [
    clone.querySelector("article"),
    clone.querySelector("main"),
    clone.body,
  ].filter(Boolean);

  let bestText = "";
  for (const candidate of candidates) {
    const text = candidate.innerText.replace(/\s+/g, " ").trim();
    if (text.length > bestText.length) {
      bestText = text;
    }
  }

  if (bestText.length < 200) {
    return { ok: false, reason: "select-text" };
  }

  return { ok: true, text: bestText };
}
