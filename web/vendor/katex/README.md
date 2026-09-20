# KaTeX 0.16.11 (vendored)

발표장에서 CDN 이 막히거나 느려도 수식이 뜨게, 저장소 안에 넣어 둔다.

- 버전: KaTeX **0.16.11**
- 출처: `https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/`
  (`katex.min.js`, `katex.min.css`, `fonts/*.woff2`)
- 라이선스: MIT — Copyright (c) 2013-2020 Khan Academy and other contributors
  (<https://github.com/KaTeX/KaTeX/blob/main/LICENSE>)

## 담아 둔 것

| 파일 | 설명 |
| --- | --- |
| `katex.min.js` | 렌더러. `web/notes/richtext.js` 가 `window.katex.render` 로만 쓴다. |
| `katex.min.css` | 스타일. `fonts/` 를 상대 경로로 참조한다. |
| `fonts/*.woff2` | CSS 가 참조하는 폰트 20개. **woff2 만** 받았다(요즘 브라우저는 `src` 목록의 woff2 를 먼저 쓴다). |

`woff`·`ttf` 는 일부러 뺐다(용량). 아주 오래된 브라우저에서는 폰트가 기본 글꼴로 떨어질 수 있다.

## 갱신 방법

```sh
cd web/vendor/katex
curl -fsS -O https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js
curl -fsS -O https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css
grep -o 'fonts/[A-Za-z0-9_.-]*\.woff2' katex.min.css | sort -u |
  while read -r f; do curl -fsS -o "$f" "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/$f"; done
```

렌더 호출은 `richtext.js` 한 곳에서만 하고, `trust: false` 를 반드시 켠 채로 쓴다
(`\href`·`\includegraphics` 같은 위험 매크로 차단).
