import assert from "node:assert/strict";
import test from "node:test";

import { extractArticle, extractSelection } from "../extract.js";

function dom(html, selectionText = "") {
  const parsed = parseHtml(html);

  return {
    cloneNode() {
      return parseHtml(html);
    },
    defaultView: {
      getSelection() {
        return {
          toString() {
            return selectionText;
          },
        };
      },
    },
    querySelector(selector) {
      return parsed.querySelector(selector);
    },
    body: parsed.body,
  };
}

function parseHtml(html) {
  const elementPattern = /<(nav|header|footer|aside|article|main|div|p)[^>]*>([\s\S]*?)<\/\1>/gi;
  const children = [];
  let match = elementPattern.exec(html);
  while (match) {
    children.push({
      tagName: match[1].toUpperCase(),
      innerText: match[2].replace(/<[^>]+>/g, ""),
      remove() {
        const index = children.indexOf(this);
        if (index >= 0) children.splice(index, 1);
      },
    });
    match = elementPattern.exec(html);
  }

  return {
    querySelector(selector) {
      const tag = selector.toLowerCase();
      return children.find((child) => child.tagName.toLowerCase() === tag) || null;
    },
    querySelectorAll(selector) {
      const tag = selector.toLowerCase();
      return children.filter((child) => child.tagName.toLowerCase() === tag);
    },
    body: {
      innerText: html.replace(/<[^>]+>/g, ""),
    },
  };
}

test("uses exactly selected text", () => {
  const document = dom("<p>Ignored</p>", "Chosen text");
  assert.deepEqual(extractSelection(document), { ok: true, text: "Chosen text" });
});

test("does not use body text when article extraction is uncertain", () => {
  const document = dom("<nav>Home Products</nav><div>Random page chrome</div>");
  assert.deepEqual(extractArticle(document), { ok: false, reason: "select-text" });
});
