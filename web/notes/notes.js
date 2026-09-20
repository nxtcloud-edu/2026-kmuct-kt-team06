(() => {
  const A = window.Motga;
  if (!A || A.notesMounted) return;
  A.notesMounted = true;
  const { el, btn, api, state, toast, emit, read, save } = A;
  let active, editor, slot;
  const drafts = new Map();
  function init() {
    slot = document.getElementById("note-slot");
    if (!slot || slot.dataset.ready) return;
    slot.dataset.ready = "true";
    slot.append(
      el("p", "v-muted", "원본 구간을 선택하면 필기를 남길 수 있어요."),
    );
  }
  window.addEventListener("segment-boundary", async ({ detail }) => {
    init();
    if (!slot) return;
    if (active && editor)
      drafts.set(`${active.lecture}:${active.k}`, editor.value);
    active = detail;
    const context = detail;
    slot.replaceChildren();
    slot.append(el("h3", "", `나의 필기 · 슬라이드 ${detail.s}`));
    editor = el("textarea", "n-editor");
    editor.placeholder = "이 구간에서 기억하고 싶은 내용을 적어보세요…";
    editor.setAttribute("aria-label", "구간 필기");
    const field = editor;
    const error = el("p", "n-error");
    error.setAttribute("role", "alert");
    const submit = btn("필기 저장", "v-primary", async () => {
      const text = field.value.trim();
      if (!text) {
        error.textContent = "필기를 입력해 주세요.";
        return;
      }
      if (new TextEncoder().encode(text).length > 8192) {
        error.textContent = "필기는 8KB 이하로 작성해 주세요.";
        return;
      }
      submit.disabled = true;
      error.textContent = "";
      try {
        if (state.mock) {
          const notes = read("motga-notes", {});
          notes[`${context.lecture}:${context.k}`] = text;
          if (!save("motga-notes", notes))
            throw new Error("필기를 저장하지 못했습니다.");
        } else
          await api("/api/notes", {
            method: "POST",
            body: JSON.stringify({
              lecture: context.lecture,
              k: context.k,
              text,
            }),
          });
        toast(
          state.mock
            ? "필기를 이 브라우저에 저장했습니다."
            : "필기를 저장했습니다.",
        );
        emit("note-saved", context);
      } catch (e) {
        error.textContent = e.message;
      } finally {
        submit.disabled = false;
      }
    });
    const actions = el("div", "n-actions");
    actions.append(
      btn("건너뛰기", "v-secondary", () => emit("notes-closed", context)),
      submit,
    );
    slot.append(editor, error, actions);
    const key = `${detail.lecture}:${detail.k}`;
    const local = read("motga-notes", {})[key];
    if (drafts.has(key)) field.value = drafts.get(key);
    else if (state.mock && local !== undefined) field.value = local;
    else {
      try {
        const notes = await api(`/api/notes/${detail.lecture}`);
        if (active === context && !field.value)
          field.value = notes.find((n) => n.k === detail.k)?.text || "";
      } catch (e) {
        error.textContent = e.message;
      }
    }
  });
  window.addEventListener("dashboard-open", async ({ detail: { main } }) => {
    const loading = el("p", "v-muted", "학습 기록을 불러오고 있어요…");
    main.append(loading);
    try {
      const [stats, review, history] = await Promise.all([
        api("/api/stats"),
        api("/api/review"),
        api("/api/history?limit=10"),
      ]);
      if (!main.contains(loading)) return;
      loading.remove();
      const summary = el("div", "n-dashboard-summary");
      summary.append(
        el("span", "v-badge", state.mock ? "샘플 데이터" : "실시간 데이터"),
        el("h2", "", "근거가 있는 노트, 더 단단한 이해."),
        el(
          "p",
          "v-muted",
          "정확도를 추정하는 대신, 확인 가능한 검증 결과를 보여드려요.",
        ),
      );
      main.append(summary);
      const metrics = el("div", "n-metrics");
      const ratio = (n, total) => (total ? Math.round((n / total) * 100) : 0);
      for (const [label, value, sub, percent, color] of [
        [
          "강의 근거 커버리지",
          `${stats.coverage.covered}/${stats.coverage.total}`,
          "항목에 원본 근거 연결",
          ratio(stats.coverage.covered, stats.coverage.total),
          "#7375df",
        ],
        [
          "검토 완료",
          `${stats.approved}/${stats.pages}`,
          "페이지 검토 완료",
          ratio(stats.approved, stats.pages),
          "#6ea890",
        ],
        [
          "첫 검증 통과",
          `${stats.hooks.first_pass}/${stats.hooks.pages_written}`,
          "작성 페이지 기준",
          ratio(stats.hooks.first_pass, stats.hooks.pages_written),
          "#d4a35d",
        ],
      ]) {
        const card = el("section", "n-metric");
        card.append(el("h3", "", label));
        const ring = el("div", "n-ring");
        ring.style.setProperty("--percent", `${percent}%`);
        ring.style.setProperty("--ring-color", color);
        ring.append(el("strong", "", value));
        card.append(ring, el("p", "v-muted", sub));
        metrics.append(card);
      }
      main.append(metrics);
      const numbers = el("div", "n-numbers");
      for (const [label, value] of [
        ["강의", stats.lectures],
        ["개념·강의 노트", stats.pages],
        ["연결", stats.links],
        ["내 필기", stats.notes],
      ]) {
        const n = el("div");
        n.append(el("strong", "", value), el("span", "v-muted", label));
        numbers.append(n);
      }
      main.append(numbers);
      const reviews = el("section", "n-reviews");
      const title = el("h2", "", "이 부분을 함께 확인해 주세요");
      reviews.append(
        title,
        el(
          "p",
          "v-muted",
          "원본을 확인하고 검토를 완료하면 노트의 상태가 업데이트됩니다.",
        ),
      );
      main.append(reviews);
      const approved = state.mock ? read("motga-approved", []) : [];
      let remaining = review.filter((r) => !approved.includes(r.id));
      const count = el("span", "n-count", `${remaining.length}개 검토 필요`);
      reviews.append(count);
      if (!remaining.length)
        reviews.append(el("p", "v-empty", "✓ 모든 검토를 마쳤습니다."));
      for (const item of remaining) {
        const row = el("div", "n-review-row");
        const body = el("div");
        body.append(
          el(
            "span",
            "n-review-label",
            {
              low_confidence: "원본 대조 필요",
              grey: "근거 확인 필요",
              rewritten: "재작성됨",
              quote_mismatch: "인용 확인 필요",
              stt_uncertain: "전사 확인 필요",
            }[item.kind] || "검토 필요",
          ),
          el("p", "", item.text),
          el("small", "v-muted", item.reason),
        );
        const actions = el("div", "n-review-actions");
        if (item.anchor) actions.append(A.anchor(item.anchor));
        const approve = btn("확인 완료", "v-secondary", async () => {
          approve.disabled = true;
          try {
            if (state.mock) {
              const ids = read("motga-approved", []);
              if (!save("motga-approved", [...ids, item.id]))
                throw new Error("검토 상태를 저장하지 못했습니다.");
            } else
              await api("/api/review/approve", {
                method: "POST",
                body: JSON.stringify({ id: item.id }),
              });
            row.remove();
            remaining = remaining.filter((r) => r.id !== item.id);
            count.textContent = `${remaining.length}개 검토 필요`;
            if (!remaining.length)
              reviews.append(el("p", "v-empty", "✓ 모든 검토를 마쳤습니다."));
            toast("검토 완료로 표시했습니다.");
          } catch (e) {
            toast(e.message);
            approve.disabled = false;
          }
        });
        actions.append(approve);
        row.append(body, actions);
        reviews.append(row);
      }
      main.append(el("h2", "", "최근 검증 기록"));
      const wrap = el("div", "n-table-wrap");
      const table = el("table", "n-history");
      const head = el("tr");
      for (const title of ["시간", "에이전트", "파일", "결과"])
        head.append(el("th", "", title));
      table.append(head);
      for (const h of history) {
        const row = el("tr");
        row.title = h.reason || "검증 통과";
        row.append(
          el("td", "", h.ts.slice(11, 19)),
          el("td", "", h.agent),
          el("td", "", h.path.split("/").pop()),
          el(
            "td",
            h.verdict === "deny" ? "n-denied" : "n-allowed",
            h.verdict === "deny" ? "REJECTED" : "통과",
          ),
        );
        table.append(row);
      }
      wrap.append(table);
      main.append(wrap);
    } catch (e) {
      loading.textContent = e.message;
      loading.append(
        btn("다시 시도", "v-secondary", () => A.show("dashboard")),
      );
    }
  });
  window.addEventListener("motga-ready", init);
  document.addEventListener("nav", init);
  init();
})();
