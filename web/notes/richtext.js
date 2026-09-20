// 채팅 답변(신뢰할 수 없는 텍스트)을 createElement·textContent 로만 그린다. HTML 문자열 주입은 쓰지 않는다.
// window.MotgaRich = { render, tokenizeBlocks, tokenizeInline, normalizeAnchor }
(() => {
  "use strict";
  if (window.MotgaRich) return;
  const MAX_TEX = 500; // 이보다 긴 수식은 KaTeX 에 넘기지 않고 원문 그대로 보여 준다
  const WORD = /[0-9A-Za-z_À-ɏ぀-ヿ一-鿿가-힣]/;
  const ANCHOR = /^\[\[L\d+#s\d+@t=\d+\]\]/;
  const WIKI = /^\[\[([^\]\n|]+)(?:\|([^\]\n]+))?\]\]/;
  const LINK = /^\[([^\]\n]*)\]\(([^()\s]+)\)/;
  const HEADING = /^ {0,3}(#{1,6})\s+(.*)$/;
  const QUOTE = /^ {0,3}>\s?(.*)$/;
  const FENCE = /^ {0,3}(`{3,}|~{3,})(.*)$/;
  const BULLET = /^ {0,3}([-*])\s+(.*)$/;
  const ORDERED = /^ {0,3}(\d{1,9})[.)]\s+(.*)$/;
  const RULE = /^ {0,3}([-*_])(\s*\1){2,}\s*$/;

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  };
  const textNode = (value) => document.createTextNode(value);
  const normalizeAnchor = (value) => String(value == null ? "" : value).replace(/[[\]]/g, "").trim();

  function isBlockStart(line) {
    if (!line.trim()) return true;
    const t = line.trim();
    return (
      HEADING.test(line) ||
      QUOTE.test(line) ||
      FENCE.test(line) ||
      BULLET.test(line) ||
      ORDERED.test(line) ||
      RULE.test(line) ||
      t.startsWith("$$") ||
      t.startsWith("\\[")
    );
  }

  // ── 블록 ──────────────────────────────────────────────────────────────
  function tokenizeBlocks(text) {
    const lines = String(text == null ? "" : text).replace(/\r\n?/g, "\n").split("\n");
    const blocks = [];
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) {
        i += 1;
        continue;
      }
      if (RULE.test(line)) {
        i += 1;
        continue;
      }
      const fence = FENCE.exec(line);
      if (fence) {
        const mark = fence[1][0];
        const closer = new RegExp("^ {0,3}" + (mark === "`" ? "`" : "~") + "{3,}\\s*$");
        const body = [];
        i += 1;
        while (i < lines.length && !closer.test(lines[i])) {
          body.push(lines[i]);
          i += 1;
        }
        if (i < lines.length) i += 1; // 닫는 울타리
        blocks.push({ type: "code", text: body.join("\n"), lang: fence[2].trim() });
        continue;
      }
      const trimmed = line.trim();
      if (trimmed.startsWith("$$") || trimmed.startsWith("\\[")) {
        const open = trimmed.startsWith("$$") ? "$$" : "\\[";
        const close = open === "$$" ? "$$" : "\\]";
        const start = i;
        const head = trimmed.slice(open.length);
        const at = head.indexOf(close);
        if (at >= 0) {
          const tail = head.slice(at + close.length).trim();
          blocks.push({ type: "math", tex: head.slice(0, at).trim() });
          if (tail) blocks.push({ type: "p", text: tail });
          i += 1;
          continue;
        }
        const body = [head];
        let closed = false;
        i += 1;
        while (i < lines.length) {
          const at2 = lines[i].indexOf(close);
          if (at2 >= 0) {
            body.push(lines[i].slice(0, at2));
            closed = true;
            i += 1;
            break;
          }
          body.push(lines[i]);
          i += 1;
        }
        if (closed) {
          blocks.push({ type: "math", tex: body.join("\n").trim() });
        } else {
          // 닫히지 않은 수식이 답변 전체를 삼키지 않게 원문 문단으로 되돌린다
          blocks.push({ type: "p", text: lines.slice(start, i).join("\n") });
        }
        continue;
      }
      const heading = HEADING.exec(line);
      if (heading) {
        blocks.push({ type: "heading", text: heading[2].trim() });
        i += 1;
        continue;
      }
      if (QUOTE.test(line)) {
        const body = [];
        while (i < lines.length && QUOTE.test(lines[i])) {
          body.push(QUOTE.exec(lines[i])[1]);
          i += 1;
        }
        blocks.push({ type: "quote", text: body.join("\n") });
        continue;
      }
      const ordered = ORDERED.test(line);
      if (ordered || BULLET.test(line)) {
        const rule = ordered ? ORDERED : BULLET;
        const items = [];
        while (i < lines.length) {
          const m = rule.exec(lines[i]);
          if (m) {
            items.push(m[2]);
            i += 1;
            continue;
          }
          if (isBlockStart(lines[i]) || !items.length) break;
          items[items.length - 1] += "\n" + lines[i].trim(); // 이어지는 줄
          i += 1;
        }
        blocks.push({ type: "list", ordered, items });
        continue;
      }
      const body = [line];
      i += 1;
      while (i < lines.length && !isBlockStart(lines[i])) {
        body.push(lines[i]);
        i += 1;
      }
      blocks.push({ type: "p", text: body.join("\n") });
    }
    return blocks;
  }

  // ── 인라인 ────────────────────────────────────────────────────────────
  function emphasisEnd(src, start, mark) {
    const next = src[start + 1];
    if (!next || /\s/.test(next) || next === mark) return -1;
    for (let j = start + 1; j < src.length; j += 1) {
      const ch = src[j];
      if (ch === "\n") return -1;
      if (ch === "\\") {
        j += 1;
        continue;
      }
      if (ch === mark && !/\s/.test(src[j - 1])) return j;
    }
    return -1;
  }

  function tokenizeInline(text) {
    const src = String(text == null ? "" : text);
    const out = [];
    let buf = "";
    const flush = () => {
      if (buf) out.push({ type: "text", value: buf });
      buf = "";
    };
    let i = 0;
    while (i < src.length) {
      const c = src[i];
      if (c === "\\") {
        const n = src[i + 1];
        if (n === "(" || n === "[") {
          const close = n === "(" ? "\\)" : "\\]";
          const end = src.indexOf(close, i + 2);
          if (end !== -1) {
            const tex = src.slice(i + 2, end).trim();
            if (tex) {
              flush();
              out.push({ type: "math", tex, display: n === "[" });
              i = end + 2;
              continue;
            }
          }
          buf += c;
          i += 1;
          continue;
        }
        if (n !== undefined && "$*_`[]\\".indexOf(n) !== -1) {
          buf += n; // \$100 → 그냥 달러 문자
          i += 2;
          continue;
        }
        buf += c;
        i += 1;
        continue;
      }
      if (c === "`") {
        let n = 1;
        while (src[i + n] === "`") n += 1;
        const fence = "`".repeat(n);
        const end = src.indexOf(fence, i + n);
        if (end !== -1 && end > i + n) {
          flush();
          out.push({ type: "code", value: src.slice(i + n, end).replace(/^ | $/g, "") });
          i = end + n;
          continue;
        }
        buf += c;
        i += 1;
        continue;
      }
      if (c === "$") {
        if (src[i + 1] === "$") {
          const end = src.indexOf("$$", i + 2);
          if (end !== -1) {
            const tex = src.slice(i + 2, end).trim();
            if (tex) {
              flush();
              out.push({ type: "math", tex, display: true });
              i = end + 2;
              continue;
            }
          }
          buf += c;
          i += 1;
          continue;
        }
        const next = src[i + 1];
        if (next && !/\s/.test(next)) {
          let j = i + 1;
          let close = -1;
          while (j < src.length) {
            const ch = src[j];
            if (ch === "\n") break; // 인라인 수식은 줄을 넘지 않는다
            if (ch === "\\") {
              j += 2;
              continue;
            }
            if (ch === "$") {
              close = j;
              break;
            }
            j += 1;
          }
          // 닫는 $ 바로 앞이 공백이면 가격 표기($5 … $10)로 보고 수식이 아니다
          if (close > i + 1 && !/\s/.test(src[close - 1])) {
            flush();
            out.push({ type: "math", tex: src.slice(i + 1, close), display: false });
            i = close + 1;
            continue;
          }
        }
        buf += c;
        i += 1;
        continue;
      }
      if (c === "[") {
        const rest = src.slice(i);
        const a = ANCHOR.exec(rest);
        if (a) {
          flush();
          out.push({ type: "anchor", value: a[0] });
          i += a[0].length;
          continue;
        }
        const w = WIKI.exec(rest);
        if (w) {
          buf += (w[2] || w[1].split("/").pop()).trim(); // 채팅에서는 링크가 아니라 글자
          i += w[0].length;
          continue;
        }
        const l = LINK.exec(rest);
        if (l) {
          if (/^https?:\/\//i.test(l[2])) {
            flush();
            out.push({ type: "link", label: l[1] || l[2], href: l[2] });
          } else {
            buf += l[0]; // http(s) 가 아니면 링크로 만들지 않는다
          }
          i += l[0].length;
          continue;
        }
        buf += c;
        i += 1;
        continue;
      }
      if (c === "*" && src[i + 1] === "*") {
        const end = src.indexOf("**", i + 2);
        if (end > i + 2) {
          const inner = src.slice(i + 2, end);
          if (inner.trim() && !/\n\s*\n/.test(inner)) {
            flush();
            out.push({ type: "bold", children: tokenizeInline(inner) });
            i = end + 2;
            continue;
          }
        }
        buf += "**";
        i += 2;
        continue;
      }
      if (c === "*" || c === "_") {
        // snake_case_name·변수명 안의 _ 는 기울임이 아니다
        const prev = i > 0 ? src[i - 1] : "";
        const ok = c === "*" || !WORD.test(prev);
        const end = ok ? emphasisEnd(src, i, c) : -1;
        if (end !== -1 && (c === "*" || !WORD.test(src[end + 1] || ""))) {
          flush();
          out.push({ type: "italic", children: tokenizeInline(src.slice(i + 1, end)) });
          i = end + 1;
          continue;
        }
        buf += c;
        i += 1;
        continue;
      }
      buf += c;
      i += 1;
    }
    flush();
    return out;
  }

  // ── 그리기 ────────────────────────────────────────────────────────────
  function mathFallback(node, tex) {
    node.textContent = "";
    node.append(el("code", "n-math-fallback", tex));
  }

  function renderMath(parent, tex, display) {
    const source = String(tex == null ? "" : tex).trim();
    if (!source) return;
    const node = el(display ? "div" : "span", display ? "n-math n-math-block" : "n-math");
    const katex = window.katex;
    if (source.length > MAX_TEX || !katex || typeof katex.render !== "function") {
      mathFallback(node, source);
    } else {
      try {
        katex.render(source, node, {
          throwOnError: false,
          displayMode: !!display,
          strict: "ignore",
          trust: false,
          maxExpand: 200,
          maxSize: 20,
        });
      } catch {
        mathFallback(node, source);
      }
    }
    parent.append(node);
  }

  function renderAnchor(parent, token, options, used) {
    let node = null;
    if (options && typeof options.anchor === "function") {
      try {
        node = options.anchor(token);
      } catch {
        node = null;
      }
    }
    if (node && typeof node === "object") {
      parent.append(node);
      const key = normalizeAnchor(token);
      if (used.indexOf(key) === -1) used.push(key);
    } else {
      parent.append(textNode(token));
    }
  }

  function renderInline(parent, tokens, options, used) {
    for (const t of tokens) {
      if (t.type === "text") {
        if (t.value) parent.append(textNode(t.value));
      } else if (t.type === "code") {
        parent.append(el("code", "n-code", t.value));
      } else if (t.type === "math") {
        renderMath(parent, t.tex, t.display);
      } else if (t.type === "anchor") {
        renderAnchor(parent, t.value, options, used);
      } else if (t.type === "link") {
        const a = el("a", "n-link", t.label);
        a.href = t.href;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        parent.append(a);
      } else if (t.type === "bold" || t.type === "italic") {
        const n = el(t.type === "bold" ? "strong" : "em");
        renderInline(n, t.children || [], options, used);
        parent.append(n);
      }
    }
  }

  function renderBlock(parent, block, options, used) {
    if (block.type === "code") {
      const pre = el("pre", "n-code-block");
      pre.append(el("code", "", block.text));
      parent.append(pre);
      return;
    }
    if (block.type === "math") {
      renderMath(parent, block.tex, true);
      return;
    }
    if (block.type === "list") {
      const list = el(block.ordered ? "ol" : "ul", "n-list");
      for (const item of block.items) {
        const li = el("li");
        renderInline(li, tokenizeInline(item), options, used);
        list.append(li);
      }
      parent.append(list);
      return;
    }
    if (block.type === "heading") {
      // 채팅 말풍선 안에서는 큰 제목 대신 굵은 한 줄로 낮춘다
      const p = el("p", "n-rich-heading");
      const strong = el("strong");
      renderInline(strong, tokenizeInline(block.text), options, used);
      p.append(strong);
      parent.append(p);
      return;
    }
    const node = el(block.type === "quote" ? "blockquote" : "p");
    renderInline(node, tokenizeInline(block.text), options, used);
    parent.append(node);
  }

  function render(parent, text, opts) {
    const options = opts || {};
    const used = [];
    if (!parent || text == null || text === "") return { anchors: used };
    let blocks;
    try {
      blocks = tokenizeBlocks(text);
    } catch {
      blocks = [{ type: "p", text: String(text) }];
    }
    for (const block of blocks) {
      try {
        renderBlock(parent, block, options, used);
      } catch {
        // 한 블록이 깨져도 나머지 답변은 보여 준다
      }
    }
    return { anchors: used };
  }

  window.MotgaRich = { render, tokenizeBlocks, tokenizeInline, normalizeAnchor };
})();
