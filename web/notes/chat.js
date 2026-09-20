(() => {
  const A = window.Motga;
  if (!A || A.chatMounted) return;
  A.chatMounted = true;
  const { el, btn, api, state, emit } = A;
  let context = null,
    busy = false;
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
    for (const q of [
      "BFS와 DFS는 어떻게 달라?",
      "BFS의 시간복잡도를 알려줘",
      "시험에 나온다고 하신 부분",
    ])
      suggestions.append(
        btn(`${q}  ↗`, "", () => {
          input.value = q.includes("시험") ? "시험" : q;
          (q.includes("시험") ? quotes : qa).click();
          input.focus();
        }),
      );
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
    footer.append(
      attached,
      form,
      el(
        "small",
        "n-chat-disclaimer",
        "답변의 원본 근거를 함께 확인해 주세요.",
      ),
    );
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
          reply.append(
            el(
              "p",
              "",
              data.answer || data.message || "위키에 근거가 없습니다.",
            ),
          );
          for (const a of data.anchors || []) reply.append(A.anchor(a));
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
  }
  window.addEventListener("motga-ready", init);
  document.addEventListener("nav", init);
  init();
})();
