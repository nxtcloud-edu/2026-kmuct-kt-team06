(() => {
  const A = window.Motga;
  if (!A || A.chatMounted) return;
  A.chatMounted = true;
  const { el, btn, api, state, emit } = A;
  let context = null,
    busy = false;
  // ── 노트별 추천 질문 ─────────────────────────────────────────
  // 서버가 만들어 두는 정적 파일. 없거나 깨져 있어도 절대 예외를 던지지 않고 고정 질문으로 돌아간다.
  const SUGGEST_URL = "/web/viewer/suggestions.local.json";
  // 방금 컴파일된 강의도 새로고침 없이 최대 1분 뒤에는 뜬다.
  const SUGGEST_TTL = 60000;
  const SUGGEST_MAX = 3;
  const SUGGEST_CHARS = 40;
  const FIXED_PROMPTS = [
    "add와 addi는 어떻게 달라?",
    "머지소트와 퀵소트의 차이를 알려줘",
    "시험에 나온다고 하신 부분",
  ];
  let suggestCache = null,
    suggestAt = 0,
    suggestPending = null;
  function loadSuggestions() {
    if (suggestPending) return suggestPending;
    if (suggestCache && Date.now() - suggestAt < SUGGEST_TTL)
      return Promise.resolve(suggestCache);
    suggestPending = fetch(SUGGEST_URL, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null)
      .then((data) => {
        suggestCache =
          data && typeof data === "object" && !Array.isArray(data) ? data : {};
        suggestAt = Date.now();
        suggestPending = null;
        return suggestCache;
      });
    return suggestPending;
  }
  // 이 슬러그의 질문 최대 3개. 형식이 뭐든 이상하면 빈 배열.
  function pickQuestions(map, slug) {
    if (!slug || !map || typeof map !== "object") return [];
    const entry = map[slug];
    if (!entry || !Array.isArray(entry.questions)) return [];
    const out = [];
    for (const raw of entry.questions) {
      if (typeof raw !== "string") continue;
      const text = raw.replace(/\s+/g, " ").trim();
      if (!text || out.includes(text)) continue;
      out.push(text);
      if (out.length >= SUGGEST_MAX) break;
    }
    return out;
  }
  function shorten(text, max = SUGGEST_CHARS) {
    const value = typeof text === "string" ? text.replace(/\s+/g, " ").trim() : "";
    return value.length > max ? `${value.slice(0, max - 1)}…` : value;
  }
  function init() {
    const slot = document.getElementById("chat-slot");
    if (!slot || slot.dataset.ready) return;
    slot.dataset.ready = "true";
    const header = el("header", "n-chat-header");
    header.append(
      el("span", "n-agent-icon", "✧"),
      el("strong", "", "Agent"),
      el("span", "n-online", "●"),
      btn("−", "v-icon-button", () =>
        document.getElementById("v-root").classList.add("v-chat-hidden"),
      ),
    );
    const tabs = el("div", "n-chat-tabs");
    let mode = "qa";
    const qa = btn("위키에 묻기", "active", () => {
      mode = "qa";
      qa.classList.add("active");
      quotes.classList.remove("active");
      input.placeholder = "강의에 대해 궁금한 점을 물어보세요";
    });
    const quotes = btn("교수님 발언 검색", "", () => {
      mode = "quotes";
      quotes.classList.add("active");
      qa.classList.remove("active");
      input.placeholder = "시험, 중요, 꼭… 원문 검색";
    });
    tabs.append(qa, quotes);
    const messages = el("div", "n-messages");
    messages.setAttribute("role", "log");
    messages.setAttribute("aria-live", "polite");
    const welcome = el("div", "n-welcome");
    welcome.append(
      el("div", "n-welcome-symbol", "✧"),
      el("h2", "", "이해하는 순간까지, 함께"),
      el("p", "", "강의 속 근거를 찾아\n궁금한 개념을 연결해 드릴게요."),
    );
    const suggestions = el("div", "n-suggestions");
    welcome.append(suggestions);
    messages.append(welcome);
    const footer = el("div", "n-chat-footer");
    const attached = el("div", "n-context");
    const form = el("form", "n-composer");
    const input = el("textarea");
    input.placeholder = "강의에 대해 궁금한 점을 물어보세요";
    input.maxLength = 500;
    input.rows = 3;
    input.setAttribute("aria-label", "Agent 질문");
    const controls = el("div", "n-composer-controls");
    const model = el("select");
    model.setAttribute("aria-label", "답변 모델");
    for (const [id, label] of [
      ["fast", "빠른 답변"],
      ["strong", "깊이 있는 답변"],
      ["gemini", "Gemini"],
    ]) {
      const o = el("option", "", label);
      o.value = id;
      model.append(o);
    }
    const send = btn("↑", "n-send");
    send.type = "submit";
    send.setAttribute("aria-label", "질문 전송");
    controls.append(
      btn("＋", "v-icon-button", () => emit("context-request")),
      model,
      send,
    );
    form.append(input, controls);
    // 대화가 시작된 뒤에는 환영 화면 대신, 입력창 위의 작은 줄로만 남는다.
    const quick = el("div", "n-quick");
    quick.hidden = true;
    footer.append(quick, attached, form);
    // ── 추천 질문 칩 ──────────────────────────────────────────
    let chipList = FIXED_PROMPTS,
      chipLive = false,
      pageToken = 0;
    const askNow = (question) => {
      if (busy) return;
      qa.click();
      input.value = question;
      form.requestSubmit();
    };
    function chip(question, live, compact) {
      const label = shorten(question);
      const b = btn(
        compact ? label : `${label}  ↗`,
        compact ? "n-quick-chip" : "",
        () => {
          // 노트별 질문은 바로 보낸다. 고정 질문은 예전처럼 입력창만 채운다.
          if (live) return askNow(question);
          input.value = question.includes("시험") ? "시험" : question;
          (question.includes("시험") ? quotes : qa).click();
          input.focus();
        },
      );
      b.title = question;
      return b;
    }
    function paintChips() {
      const started = !welcome.isConnected;
      quick.replaceChildren();
      quick.hidden = !started;
      // 대화가 비어 있을 때만 환영 화면 칩을 다시 그린다 — 질문한 뒤에는 화면을 흔들지 않는다.
      if (!started) {
        const caption = chipLive ? "이 노트에서 많이 묻는 질문" : "추천 질문";
        suggestions.replaceChildren(el("small", "n-suggest-caption", caption));
        for (const q of chipList) suggestions.append(chip(q, chipLive, false));
        return;
      }
      quick.append(el("small", "n-quick-caption", "추천 질문"));
      for (const q of chipList) quick.append(chip(q, chipLive, true));
    }
    async function applyPage(detail) {
      const token = ++pageToken;
      const slug = detail && detail.slug ? detail.slug : null;
      if (!slug) {
        chipList = FIXED_PROMPTS;
        chipLive = false;
        paintChips();
        return;
      }
      let found = [];
      try {
        const map = await loadSuggestions();
        if (token !== pageToken) return;
        found = pickQuestions(map, slug);
      } catch {
        found = [];
      }
      if (token !== pageToken) return;
      chipLive = found.length > 0;
      chipList = chipLive ? found : FIXED_PROMPTS;
      paintChips();
    }
    window.addEventListener("note-opened", (e) => applyPage(e.detail));
    window.addEventListener("context-reply", (e) => {
      context = e.detail;
      attached.replaceChildren(
        el("span", "", `▤ ${context.slug.split("/").pop()}`),
        btn("×", "v-icon-button", () => {
          context = null;
          attached.replaceChildren();
        }),
      );
    });
    form.onsubmit = async (e) => {
      e.preventDefault();
      const question = input.value.trim();
      if (!question || busy) return;
      if (mode === "quotes" && question.length < 2) {
        A.toast("검색어를 두 글자 이상 입력해 주세요.");
        return;
      }
      busy = true;
      send.disabled = true;
      const requestedMode = mode;
      welcome.remove();
      paintChips(); // 환영 화면이 사라졌으니 추천 질문은 입력창 위 한 줄로 옮긴다
      messages.append(el("div", "n-message n-user", question));
      input.value = "";
      const reply = el("div", "n-message n-agent");
      reply.append(
        el("small", "n-agent-label", "✧ MOTGA"),
        el(
          "p",
          "",
          requestedMode === "quotes"
            ? "교수님 발언을 찾고 있어요…"
            : "강의 속 근거를 확인하고 있어요…",
        ),
      );
      messages.append(reply);
      messages.scrollTop = messages.scrollHeight;
      try {
        reply.replaceChildren(
          el(
            "small",
            "n-agent-label",
            state.mock ? "✧ MOTGA · 샘플 응답" : "✧ MOTGA",
          ),
        );
        if (requestedMode === "quotes") {
          const data = await api(
            `/api/quotes?q=${encodeURIComponent(question)}`,
          );
          const found = state.mock
            ? data.filter((q) => q.quote.includes(question))
            : data;
          if (!found.length)
            reply.append(el("p", "", "일치하는 교수님 발언이 없습니다."));
          for (const q of found) {
            reply.append(el("blockquote", "", q.quote), A.anchor(q.anchor));
            if (q.agree !== undefined && q.agree !== null && q.agree < 0.8)
              reply.append(
                el(
                  "small",
                  "n-error",
                  "전사 일치율이 낮아 원본 확인이 필요합니다.",
                ),
              );
          }
        } else {
          const data = state.mock
            ? await fetch(
                /BFS|너비|큐/i.test(question) &&
                  !/DFS|차이|달라/i.test(question)
                  ? "/mock/qa.json"
                  : "/mock/qa-nogrounding.json",
              ).then((r) => {
                if (!r.ok) throw new Error("샘플 답변을 불러오지 못했습니다.");
                return r.json();
              })
            : await api("/api/qa", {
                method: "POST",
                body: JSON.stringify({
                  question,
                  model: model.value,
                  context: context || {
                    slug: state.slug,
                    anchor: state.anchor,
                  },
                }),
              });
          const inline = new Set();
          if (data.answer) {
            const answer = el("div", "n-answer");
            // 답변은 목록·굵은 글씨·수식(KaTeX)까지 그린다. 실패하면 예전처럼 한 문단으로.
            let rendered = null;
            if (window.MotgaRich) {
              try {
                rendered = window.MotgaRich.render(answer, data.answer, {
                  anchor: A.anchor,
                });
              } catch {
                rendered = null;
              }
            }
            if (rendered && answer.childNodes.length)
              for (const a of rendered.anchors) inline.add(a);
            else answer.replaceChildren(el("p", "", data.answer));
            reply.append(answer);
          } else {
            reply.append(
              el("p", "", data.message || "위키에 근거가 없습니다."),
            );
          }
          // 본문에 이미 박힌 앵커는 빼고, 남은 것만 "출처" 줄로 모은다
          const rest = (data.anchors || []).filter(
            (a) => !inline.has(String(a).replace(/[[\]]/g, "").trim()),
          );
          if (rest.length) {
            const sources = el("div", "n-sources");
            sources.append(el("small", "n-sources-label", "출처"));
            for (const a of rest) sources.append(A.anchor(a));
            reply.append(sources);
          }
          for (const n of data.notes || []) {
            const note = el("div", "n-quoted-note");
            note.append(el("small", "", "내 필기"), el("p", "", n.text));
            reply.append(note);
          }
          if (data.videos?.length) {
            reply.append(el("h4", "", "관련 영상 · 보충 자료"));
            for (const v of [...data.videos].sort(
              (a, b) => (b.source === "professor") - (a.source === "professor"),
            )) {
              if (state.mock) {
                reply.append(
                  el(
                    "div",
                    "n-video-card",
                    `▷ ${v.title}\n${v.channel} · 샘플 영상`,
                  ),
                );
                continue;
              }
              try {
                const url = new URL(v.url);
                if (url.protocol !== "https:") continue;
                const link = el(
                  "a",
                  "n-video-card",
                  `▷ ${v.title}\n${v.channel} · ${v.duration}`,
                );
                link.href = url.href;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                reply.append(link);
              } catch {}
            }
          }
        }
      } catch (error) {
        reply.append(el("p", "n-error", error.message));
        input.value = question;
      } finally {
        busy = false;
        send.disabled = false;
        messages.scrollTop = messages.scrollHeight;
      }
    };
    input.onkeydown = (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        form.requestSubmit();
      }
    };
    slot.append(header, tabs, messages, footer);
    // note-opened 를 놓쳤을 수 있으니(채팅이 늦게 붙는 경우) 지금 상태로 한 번 그린다.
    applyPage({
      slug: state.view === "note" ? state.slug : null,
      title: "",
      type: "",
    });
  }
  window.addEventListener("motga-ready", init);
  document.addEventListener("nav", init);
  init();
})();
