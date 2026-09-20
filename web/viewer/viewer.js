(() => {
  if (window.Motga) return;
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const btn = (text, cls, fn) => {
    const n = el("button", cls, text);
    n.type = "button";
    n.onclick = fn;
    return n;
  };
  const read = (key, fallback) => {
    try {
      return JSON.parse(localStorage.getItem(key)) ?? fallback;
    } catch {
      return fallback;
    }
  };
  const emit = (name, detail) =>
    window.dispatchEvent(new CustomEvent(name, { detail }));
  const state = {
    view: "note",
    slug: "lectures/L3_그래프_탐색",
    anchor: null,
    files: [],
    local: read("motga-documents", []),
    mock: read("motga-mock", true),
    hiddenSlugs: new Set(read("motga-hidden-slugs", [])),
    page: null,
  };
  function toast(message) {
    const n = el("div", "v-toast", message);
    n.setAttribute("role", "status");
    document.documentElement.append(n);
    setTimeout(() => n.remove(), 4500);
  }
  function save(key, data) {
    try {
      localStorage.setItem(key, JSON.stringify(data));
      return true;
    } catch {
      toast("저장 공간이 부족하거나 브라우저 저장이 차단되었습니다.");
      return false;
    }
  }
  async function api(path, options) {
    const url = state.mock
      ? `/mock${path.replace("/api", "").split("?")[0]}.json`
      : path;
    const response = await fetch(
      url,
      state.mock
        ? undefined
        : {
            ...options,
            headers: {
              "Content-Type": "application/json",
              ...options?.headers,
            },
          },
    );
    if (!response.ok) {
      let message = `요청에 실패했습니다 (${response.status})`;
      try {
        message = (await response.json()).error?.message || message;
      } catch {}
      throw new Error(message);
    }
    return response.json();
  }
  const time = (t) =>
    `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
  const app = (window.Motga = {
    el,
    btn,
    read,
    save,
    emit,
    toast,
    api,
    state,
    time,
  });
  let root,
    main,
    nav,
    pane,
    frame,
    media,
    currentSegment,
    requestId = 0;
  const pages = [];
  const localAssets = new Map();
  function anchor(value) {
    const n = btn(
      `↗ ${value.replace(/\[|\]/g, "").replace(/#s\d+@t=(\d+)/, (_, t) => ` · ${time(+t)}`)}`,
      "v-anchor",
      () => openAnchor(value),
    );
    n.dataset.anchor = value.replace(/\[|\]/g, "");
    return n;
  }
  app.anchor = anchor;
  function conceptPreview(target, page, kind = "wiki") {
    return;
  }
  function inline(parent, text) {
    const regex =
      /\[\[L\d+#s\d+@t=\d+\]\]|\[\[([^\]|]+)(?:\|([^\]]+))?\]\]|\*\*([^*]+)\*\*|\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g;
    let last = 0;
    for (const m of text.matchAll(regex)) {
      parent.append(document.createTextNode(text.slice(last, m.index)));
      if (m[0].startsWith("[[L")) parent.append(anchor(m[0]));
      else if (m[1]) {
        const concept = btn(m[2] || m[1].split("/").pop(), "v-concept", () =>
          show("note", m[1]),
        );
        const preview = pages.find((p) => p.slug === m[1]);
        parent.append(concept);
      } else if (m[4]) {
        const link = el("a", "v-concept", m[4]);
        if (!/SRCH000|PROF000/.test(m[5])) {
          link.href = m[5];
          link.target = "_blank";
          link.rel = "noopener noreferrer";
        } else link.title = "샘플 영상 · 실제 영상은 아직 등록되지 않았습니다";

        parent.append(link);
      } else parent.append(el("strong", "", m[3]));
      last = m.index + m[0].length;
    }
    parent.append(document.createTextNode(text.slice(last)));
  }
  function markdown(parent, text) {
    for (const line of text.replace(/^---[\s\S]*?---\s*/, "").split("\n")) {
      if (!line.trim() || line.startsWith("# ")) continue;
      let node;
      if (/^###? /.test(line)) node = el(line.startsWith("###") ? "h3" : "h2");
      else if (line.startsWith(">")) node = el("blockquote");
      else node = el("p", line.startsWith("- ") ? "v-bullet" : "");
      inline(
        node,
        line
          .replace(/^(#{2,3} |>[ ]?|- )/, "")
          .replace("[!ref]", "참고 자료 ·")
          .replace("[!youtube]", "▷ 관련 영상 ·"),
      );
      if (node.tagName === "BLOCKQUOTE" && node.querySelector(".v-anchor")) {
        node.classList.add("v-clickable-quote");
        node.onclick = (e) => {
          if (!e.target.closest("button,a") && !getSelection()?.toString())
            openAnchor(node.querySelector(".v-anchor").dataset.anchor);
        };
      }
      parent.append(node);
    }
  }
  function sidebar() {
    nav.replaceChildren();
    const brand = el("div", "v-brand");
    brand.append(el("span", "v-brand-mark"), el("span", "v-brand-word", "Lecki"));
    nav.append(brand, el("div", "v-workspace", "Lecki의 lecture note"));
    const search = btn("⌕   검색", "v-nav", () => show("search"));
    nav.append(search);
    nav.append(
      btn(
        "▥   대시보드",
        `v-nav ${state.view === "dashboard" ? "active" : ""}`,
        () => show("dashboard"),
      ),
    );
    nav.append(
      btn(
        `🗑   휴지통${state.hiddenSlugs.size ? ` (${state.hiddenSlugs.size})` : ""}`,
        `v-nav ${state.view === "trash" ? "active" : ""}`,
        () => show("trash"),
      ),
      el("div", "v-nav-label", "내 라이브러리"),
      el("div", "v-folder", "⌄  ▱  알고리즘"),
    );
    for (const p of pages.filter((p) => p.type === "lecture" && !state.hiddenSlugs.has(p.slug))) {
      const item = el("div", "v-nav-local-row");
      const link = btn(
        `▤  ${p.title.replace(/^L\d+\. /, "").split(" — ")[0]}`,
        `v-nav v-file ${state.slug === p.slug && state.view === "note" ? "active" : ""}`,
        () => show("note", p.slug),
      );
      const del = btn("🗑", "v-icon-button v-nav-delete", (e) => {
        e.stopPropagation();
        deleteNote(p.slug);
      });
      del.title = "노트 숨기기";
      del.setAttribute("aria-label", `${p.title} 삭제`);
      item.append(link, del);
      nav.append(item);
    }
    nav.append(el("div", "v-folder", "⌄  ▱  개념 노트"));
    for (const p of pages.filter((p) => p.type === "concept" && !state.hiddenSlugs.has(p.slug))) {
      const item = el("div", "v-nav-local-row");
      const link = btn(
        `◇  ${p.title}`,
        `v-nav v-file ${state.slug === p.slug && state.view === "note" ? "active" : ""}`,
        () => show("note", p.slug),
      );
      const del = btn("🗑", "v-icon-button v-nav-delete", (e) => {
        e.stopPropagation();
        deleteNote(p.slug);
      });
      del.title = "노트 숨기기";
      del.setAttribute("aria-label", `${p.title} 삭제`);
      item.append(link, del);
      nav.append(item);
    }
    for (const p of state.local) {
      const item = el("div", "v-nav-local-row");
      const link = btn(`▤  ${p.title}`, "v-nav v-file", () => show("local", p.id));
      const del = btn("🗑", "v-icon-button v-nav-delete", (e) => {
        e.stopPropagation();
        deleteLocal(p.id);
      });
      del.title = "노트 삭제";
      del.setAttribute("aria-label", `${p.title} 삭제`);
      item.append(link, del);
      nav.append(item);
    }
    const bottom = el("div", "v-sidebar-bottom");
    bottom.append(btn("＋  강의 자료 추가", "v-add", () => show("upload")));
    const profile = btn("", "v-profile", settings);
    const profileAvatar = el("span", "v-profile-avatar", "L");
    const profileName = el("span", "v-profile-name", "Lecki");
    const profileGear = el("span", "v-profile-gear", "⚙");
    profile.append(profileAvatar, profileName, profileGear);
    profile.append(el("small", "", "개인 학습 공간"));
    bottom.append(profile);
    nav.append(bottom);
  }
  function heading(eyebrow, title, subtitle) {
    main.append(el("div", "v-eyebrow", eyebrow), el("h1", "", title));
    if (subtitle) main.append(el("p", "v-subtitle", subtitle));
  }
  async function show(view, slug) {
    state.view = view;
    if (slug) state.slug = slug;
    sidebar();
    main.replaceChildren();
    main.scrollTop = 0;
    root.classList.remove("v-menu-open");
    if (view === "dashboard") {
      heading(
        "MY LEARNING / OVERVIEW",
        "대시보드",
        "내 강의의 근거를 확인하고, 더 정확한 노트로 만들어 보세요.",
      );

      const board = el("section", "v-dashboard-board");
      const left = el("div", "v-dashboard-panel v-dashboard-panel-left");
      const leftHeader = el("div", "v-doodle-header", "대시보드");
      const leftList = el("div", "v-doodle-list");
      ["검색", "교수님 발언", "AI 정보", "레퍼런스", "Inbox", "ABC"].forEach((label) => {
        const item = el("div", "v-doodle-item", label);
        item.innerHTML = `<span>${label}</span>`;
        leftList.append(item);
      });
      left.append(leftHeader, leftList);

      const center = el("div", "v-dashboard-panel v-dashboard-panel-center");
      const centerHeader = el("div", "v-doodle-header-lite", "Overall");
      const metrics = el("div", "v-doodle-metrics");
      [
        { pct: "74%", label: "정확도" },
        { pct: "65%", label: "검증" },
        { pct: "80%", label: "완성도" },
      ].forEach(({ pct, label }) => {
        const meter = el("div", "v-doodle-meter");
        const ring = el("div", "v-doodle-ring");
        ring.style.setProperty("--percent", pct);
        ring.append(el("strong", "", pct));
        meter.append(ring, el("span", "v-doodle-meter-label", label));
        metrics.append(meter);
      });
      center.append(centerHeader, metrics);

      const right = el("div", "v-dashboard-panel v-dashboard-panel-right");
      const rightHeader = el("div", "v-doodle-header-lite", "Agent");
      const agentStack = el("div", "v-doodle-agent-stack");
      ["검색", "검색", "근거", "검증", "쓰다"].forEach((text, index) => {
        const chip = el("div", "v-doodle-chip", text);
        if (index === 2) chip.classList.add("v-doodle-chip-strong");
        agentStack.append(chip);
      });
      const agentCard = el("div", "v-doodle-agent-card");
      agentCard.append(
        el("span", "v-doodle-agent-line", "for 16s"),
        el("span", "v-doodle-agent-line", "로그"),
      );
      right.append(rightHeader, agentStack, agentCard);

      const prompt = el("div", "v-dashboard-prompt");
      prompt.append(
        el("div", "v-dashboard-prompt-title", "이 부분이 핵심이네요!"),
        el("div", "v-dashboard-prompt-actions", ""),
      );
      const actions = prompt.querySelector(".v-dashboard-prompt-actions");
      actions.append(
        el("button", "v-doodle-button", "둘기"),
        el("button", "v-doodle-button v-doodle-button-dark", "수정"),
      );

      board.append(left, center, right);
      main.append(board, prompt);
      emit("dashboard-open", { main });
      return;
    }
    if (view === "trash") {
      const hidden = pages.filter((p) => state.hiddenSlugs.has(p.slug));
      heading(
        "TRASH",
        hidden.length ? "숨긴 노트를 복원할 수 있어요." : "휴지통이 비어 있습니다.",
        "숨김 처리한 노트는 목록에서 보이지 않지만, 여기서 다시 복원할 수 있습니다.",
      );
      if (!hidden.length) {
        main.append(el("p", "v-empty", "숨긴 노트가 아직 없습니다."));
        return;
      }
      const list = el("div", "v-trash-list");
      for (const p of hidden) {
        const row = el("div", "v-trash-row");
        const info = el("div", "v-trash-info");
        info.append(
          el("strong", "v-trash-title", p.title),
          el("small", "v-muted", p.type === "lecture" ? "강의 노트" : "개념 노트"),
        );
        const actions = el("div", "v-trash-actions");
        actions.append(
          btn("복원", "v-secondary", () => restoreHiddenNote(p.slug)),
        );
        row.append(info, actions);
        list.append(row);
      }
      main.append(list);
      return;
    }
    if (view === "upload") return upload();
    if (view === "search") return searchView();
    if (view === "local") {
      const p = state.local.find((p) => p.id === state.slug);
      if (!p) return show("note", pages[0]?.slug);
      heading(
        "내 자료 / 로컬 노트",
        p.title,
        "이 브라우저에 저장된 자료입니다. AI 분석은 아직 연결되지 않았습니다.",
      );
      const delBtn = btn("🗑  노트 삭제", "v-secondary v-btn-danger", () =>
        deleteLocal(p.id),
      );
      delBtn.title = "이 노트를 삭제합니다";
      main.append(delBtn);
      main.append(
        el(
          "div",
          "v-notice",
          "영상·PDF 파일은 새로고침 후 다시 선택해야 합니다. 텍스트와 노트 제목은 유지됩니다.",
        ),
      );
      for (const asset of localAssets.get(p.id) || []) {
        if (/\.(mp4|webm|mp3|wav|m4a)$/i.test(asset.name)) {
          const player = el(
            /\.(mp4|webm)$/i.test(asset.name) ? "video" : "audio",
            "v-local-media",
          );
          player.controls = true;
          player.src = asset.url;
          main.append(el("h3", "", asset.name), player);
        } else if (/\.pdf$/i.test(asset.name)) {
          const link = el("a", "v-secondary", `▤ ${asset.name} · PDF 열기 ↗`);
          link.href = asset.url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          main.append(link);
        }
      }
      markdown(
        main,
        p.text ||
          "텍스트 전사본이 없습니다. 강의 자료 추가에서 TXT 또는 MD 파일을 함께 선택해 주세요.",
      );
      return;
    }
    state.page = pages.find((p) => p.slug === state.slug) || pages[0];
    const p = state.page;
    if (!p) {
      heading("내 라이브러리", "노트를 불러오지 못했습니다");
      return;
    }
    state.slug = p.slug;
    sidebar();
    heading(
      "",
      p.title,
      "2026년 9월 20일  ·  원본과 연결된 나의 지식",
    );
    const meta = el("div", "v-meta");
    meta.append(
      el(
        "span",
        "v-badge",
        p.status === "approved" ? "✓ 검토 완료" : "◷ 검토 필요",
      ),
      el("span", "", "L3 · 8개 구간"),
      el("span", "", state.mock ? "샘플 강의" : "강의 노트"),
    );
    const delNoteBtn = btn("🗑  노트 삭제", "v-secondary v-btn-danger", () =>
      deleteNote(p.slug),
    );
    delNoteBtn.title = "이 노트를 목록에서 숨깁니다";
    meta.append(delNoteBtn);
    main.append(meta);
    const callout = el("div", "v-intro");
    callout.append(
      el("span", "v-spark", "✧"),
      el("div", "", "이해가 멈춘 순간, 원본으로 돌아가세요."),
    );
    callout.append(
      el(
        "small",
        "",
        "시간 칩을 누르면 해당 강의 구간과 필기를 함께 볼 수 있어요.",
      ),
    );
    main.append(callout);
    const article = el("article", "v-article");
    markdown(article, p.body);
    main.append(article);
    const summary = el("section", "v-summary");
    summary.append(
      el("div", "v-eyebrow", "TAKEAWAY"),
      el("h2", "", "오늘의 핵심, 한눈에"),
    );
    const summaryText = el("p");
    inline(
      summaryText,
      p.type === "lecture"
        ? "그래프 표현 방식에 따라 탐색 비용이 달라집니다. [[L3#s3@t=230]] BFS는 큐, DFS는 스택 또는 재귀를 사용합니다. [[L3#s5@t=330]] [[L3#s7@t=430]]"
        : p.body
            .replace(/^---[\s\S]*?---/, "")
            .split("\n")
            .find((line) => line.trim() && !line.startsWith("#")) ||
            "원본과 연결된 개념을 복습해 보세요.",
    );
    summary.append(summaryText);
    main.append(summary);

    const noteFooter = el("footer", "v-note-footer");
    noteFooter.append(
      el("div", "", "CONNECT EVERYTHING, SORT EVERYTHING"),
    );
    main.append(noteFooter);
  }
  app.show = show;
  function searchView() {
    heading(
      "SEARCH",
      "어떤 개념을 찾고 있나요?",
      "강의 제목과 노트 본문을 한 번에 검색하세요.",
    );
    const input = el("input", "v-search-input");
    input.placeholder = "BFS, 그래프, 시간복잡도…";
    input.setAttribute("aria-label", "노트 검색");
    const results = el("div", "v-results");
    const render = () => {
      results.replaceChildren();
      const q = input.value.trim().toLowerCase();
      const found = [
        ...pages,
        ...state.local.map((p) => ({
          ...p,
          body: p.text || "",
          slug: p.id,
          type: "local",
        })),
      ].filter((p) => `${p.title} ${p.body}`.toLowerCase().includes(q));
      for (const p of found) {
        const b = btn(p.title, "v-result", () =>
          show(p.type === "local" ? "local" : "note", p.slug),
        );
        b.append(
          el("small", "", p.body.replace(/[#>*\[\]]/g, "").slice(0, 140)),
        );
        results.append(b);
      }
      if (!found.length)
        results.append(
          el(
            "p",
            "v-empty",
            "검색 결과가 없습니다. 다른 단어로 검색해 보세요.",
          ),
        );
    };
    input.oninput = render;
    main.append(input, results);
    render();
    input.focus();
  }
  function upload() {
    heading(
      "NEW LECTURE",
      "강의 자료 불러오기",
      "흩어져 있던 강의 영상과 전사본, 슬라이드를 한곳에 모으세요.",
    );
    const input = el("input");
    input.type = "file";
    input.multiple = true;
    input.accept = ".mp4,.webm,.mp3,.wav,.m4a,.pdf,.txt,.md";
    input.hidden = true;
    const drop = btn("", "v-dropzone", () => input.click());
    drop.append(
      el("div", "v-upload-icon", "↥"),
      el("h2", "", "파일을 여기에 놓아주세요"),
      el("p", "", "또는 클릭하여 내 컴퓨터에서 선택"),
      el("small", "", "MP4, MP3, WAV, PDF, TXT, MD"),
    );
    const list = el("div", "v-upload-list");
    const title = el("input", "v-search-input");
    title.placeholder = "강의 제목을 입력하세요";
    title.setAttribute("aria-label", "강의 제목");
    const draw = () => {
      list.replaceChildren();
      for (const file of state.files) {
        const row = el("div", "v-upload-row");
        row.append(
          el("span", "", `▤  ${file.name}`),
          el("small", "", `${(file.size / 1024 / 1024).toFixed(2)} MB`),
          btn("×", "v-icon-button", () => {
            state.files = state.files.filter((f) => f !== file);
            draw();
          }),
        );
        list.append(row);
      }
      create.disabled = !state.files.length;
    };
    const add = (files) => {
      const accepted = [...files].filter((f) =>
        /\.(mp4|webm|mp3|wav|m4a|pdf|txt|md)$/i.test(f.name),
      );
      if (accepted.length !== files.length)
        toast("지원하지 않는 파일 형식은 제외했습니다.");
      state.files = [...state.files, ...accepted].filter(
        (f, i, arr) =>
          arr.findIndex((a) => a.name === f.name && a.size === f.size) === i,
      );
      if (!title.value && accepted[0])
        title.value = accepted[0].name.replace(/\.[^.]+$/, "");
      draw();
    };
    input.onchange = () => add(input.files);
    drop.ondragover = (e) => {
      e.preventDefault();
      drop.classList.add("dragging");
    };
    drop.ondragleave = () => drop.classList.remove("dragging");
    drop.ondrop = (e) => {
      e.preventDefault();
      drop.classList.remove("dragging");
      add(e.dataTransfer.files);
    };
    const create = btn("노트 만들기  →", "v-primary", async () => {
      if (!title.value.trim()) {
        title.focus();
        toast("강의 제목을 입력해 주세요.");
        return;
      }
      create.disabled = true;
      const selected = [...state.files];
      const name = title.value.trim();
      main.replaceChildren();
      heading(
        "PREPARING",
        "자료를 준비하고 있어요",
        "선택한 파일을 브라우저에서 읽고 있습니다.",
      );
      const progress = el("progress", "v-progress");
      progress.max = selected.length;
      progress.value = 0;
      const status = el("p", "v-subtitle", `0 / ${selected.length}`);
      main.append(progress, status, el("h2", "", name));
      try {
        let text = "";
        for (const [i, f] of selected.entries()) {
          if (/\.(txt|md)$/i.test(f.name)) {
            if (f.size > 5 * 1024 * 1024)
              throw new Error("텍스트 파일은 5MB 이하로 선택해 주세요.");
            text += `${await f.text()}\n`;
          }
          progress.value = i + 1;
          status.textContent = `${i + 1} / ${selected.length} 파일 준비 완료`;
        }
        const p = {
          id: `local-${Date.now()}`,
          title: name,
          text,
          files: selected.map((f) => f.name),
        };
        if (!save("motga-documents", [...state.local, p]))
          throw new Error("자료를 저장하지 못했습니다.");
        state.local.push(p);
        localAssets.set(
          p.id,
          selected
            .filter((f) => /\.(mp4|webm|mp3|wav|m4a|pdf)$/i.test(f.name))
            .map((f) => ({ name: f.name, url: URL.createObjectURL(f) })),
        );
        state.files = [];
        show("local", p.id);
        toast("로컬 노트가 만들어졌습니다.");
      } catch (e) {
        toast(e.message);
        show("upload");
      }
    });
    main.append(
      input,
      drop,
      el("h3", "", "선택한 자료"),
      list,
      title,
      el(
        "p",
        "v-muted",
        "자료는 이 브라우저에 보관됩니다. AI 노트 생성은 백엔드 연결 후 사용할 수 있습니다.",
      ),
      create,
    );
    draw();
  }
  function restoreHiddenNote(slug) {
    if (!state.hiddenSlugs.has(slug)) return;
    state.hiddenSlugs.delete(slug);
    save("motga-hidden-slugs", [...state.hiddenSlugs]);
    sidebar();
    toast("숨긴 노트를 복원했습니다.");
    if (state.view === "trash") show("trash");
    else show("note", slug);
  }
  function deleteNote(slug) {
    const p = pages.find((p) => p.slug === slug);
    if (!p) return;
    const dialog = el("dialog", "v-dialog");
    dialog.append(
      el("h2", "", "노트 숨기기"),
      el("p", "v-muted", `"${p.title}" 노트를 목록에서 숨기시겠습니까? 새로고침 후에도 유지되며, 휴지통에서 복원할 수 있습니다.`),
    );
    dialog.append(
      btn("숨기기", "v-primary v-btn-danger", () => {
        state.hiddenSlugs.add(slug);
        save("motga-hidden-slugs", [...state.hiddenSlugs]);
        dialog.close();
        toast(`"${p.title}" 노트를 휴지통으로 보냈습니다.`);
        const next = pages.find((p) => !state.hiddenSlugs.has(p.slug));
        if (next) show("note", next.slug);
        else show("dashboard");
      }),
      btn("취소", "v-secondary", () => dialog.close()),
    );
    dialog.addEventListener("close", () => dialog.remove());
    root.append(dialog);
    dialog.showModal();
  }
  function deleteLocal(id) {
    const p = state.local.find((p) => p.id === id);
    if (!p) return;
    const dialog = el("dialog", "v-dialog");
    dialog.append(
      el("h2", "", "노트 삭제"),
      el("p", "v-muted", `"${p.title}" 노트를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`),
    );
    dialog.append(
      btn("삭제", "v-primary v-btn-danger", () => {
        state.local = state.local.filter((p) => p.id !== id);
        save("motga-documents", state.local);
        localAssets.delete(id);
        dialog.close();
        toast(`"${p.title}" 노트를 삭제했습니다.`);
        const next = state.local[0];
        if (next) show("local", next.id);
        else show("note", pages[0]?.slug);
      }),
      btn("취소", "v-secondary", () => dialog.close()),
    );
    dialog.addEventListener("close", () => dialog.remove());
    root.append(dialog);
    dialog.showModal();
  }
  function settings() {
    const dialog = el("dialog", "v-dialog");
    dialog.append(el("h2", "", "학습 공간 설정"));
    const label = el("label", "v-setting");
    const check = el("input");
    check.type = "checkbox";
    check.checked = state.mock;
    label.append(check, document.createTextNode("샘플 데이터 모드"));
    dialog.append(
      label,
      el(
        "p",
        "v-muted",
        "끄면 같은 주소의 /api 서버를 사용합니다. 로컬 자료 가져오기는 브라우저에서 처리됩니다.",
      ),
    );
    dialog.append(
      btn("저장", "v-primary", () => {
        state.mock = check.checked;
        save("motga-mock", state.mock);
        dialog.close();
        toast("설정을 저장했습니다.");
      }),
      btn("닫기", "v-secondary", () => dialog.close()),
    );
    if (state.hiddenSlugs.size > 0) {
      const trashBtn = btn(
        `🗑  휴지통 열기 (${state.hiddenSlugs.size}개)`,
        "v-secondary",
        () => {
          dialog.close();
          show("trash");
        },
      );
      trashBtn.style.marginTop = "12px";
      trashBtn.style.width = "100%";
      dialog.append(trashBtn);
      const restoreBtn = btn(
        `↩  숨긴 노트 모두 복원`,
        "v-secondary",
        () => {
          state.hiddenSlugs.clear();
          save("motga-hidden-slugs", []);
          dialog.close();
          sidebar();
          toast("숨긴 노트를 모두 복원했습니다.");
        },
      );
      restoreBtn.style.marginTop = "8px";
      restoreBtn.style.width = "100%";
      dialog.append(restoreBtn);
    }
    dialog.addEventListener("close", () => dialog.remove());
    root.append(dialog);
    dialog.showModal();
  }
  async function openAnchor(value) {
    const clean = value.replace(/\[|\]/g, "");
    const match = /^L(\d+)#s(\d+)@t=(\d+)$/.exec(clean);
    if (!match) return toast("유효한 강의 앵커가 아닙니다.");
    const id = ++requestId;
    try {
      const lecture = `L${match[1]}`,
        s = +match[2],
        t = +match[3];
      const data = await api(`/api/segments/${lecture}`);
      const seg = data.segments.find(
        (x) => x.s === s && x.t_start <= t && t <= x.t_end,
      );
      if (!seg) throw new Error("이 시간에 해당하는 원본 구간이 없습니다.");
      const source = state.mock
        ? { frame: `/raw/${lecture}/${seg.final_frame}`, video: data.video }
        : await api(`/api/source?anchor=${encodeURIComponent(clean)}`);
      if (id !== requestId) return;
      state.anchor = clean;
      currentSegment = { ...seg, lecture };
      pane.hidden = false;
      root.classList.add("v-has-player");
      frame.src = source.slide || source.frame || "";
      frame.hidden = !frame.src;
      frame.alt = `${lecture} 슬라이드 ${s} · 원본 프레임`;
      document.getElementById("v-source-title").textContent =
        `${lecture} · 슬라이드 ${s} · ${time(t)}`;
      const host = document.getElementById("v-media");
      media?.pause();
      media = null;
      host.replaceChildren();
      if (!state.mock) {
        if (source.video.kind === "youtube") {
          const link = el("a", "v-secondary", "YouTube에서 이 구간 열기 ↗");
          const url = new URL(source.video.src, location.origin);
          if (["https:", "http:"].includes(url.protocol)) {
            url.searchParams.set("t", t);
            link.href = url.href;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            host.append(link);
          }
        } else {
          media = el(source.video.kind === "audio" ? "audio" : "video");
          media.controls = true;
          media.src = source.video.src;
          const player = media;
          let boundaryHandled = null;
          media.onloadedmetadata = () => {
            player.currentTime = Math.min(
              t,
              Number.isFinite(player.duration) ? player.duration : t,
            );
            player.play().catch(() => {});
          };
          media.onerror = () =>
            toast(
              "원본 미디어를 불러올 수 없습니다. 파일 경로를 확인해 주세요.",
            );
          media.ontimeupdate = () => {
            if (currentSegment?.lecture !== lecture) return;
            if (
              !player.paused &&
              boundaryHandled === currentSegment.k &&
              player.currentTime > currentSegment.t_end
            ) {
              const next = data.segments.find(
                (x) =>
                  x.t_start <= player.currentTime &&
                  player.currentTime < x.t_end,
              );
              if (next && next.k !== currentSegment.k) {
                currentSegment = { ...next, lecture };
                boundaryHandled = null;
                frame.src = `/raw/${lecture}/${next.final_frame}`;
                document.getElementById("v-source-title").textContent =
                  `${lecture} · 슬라이드 ${next.s} · ${time(player.currentTime)}`;
              }
            }
            if (
              player.currentTime >= currentSegment.t_end &&
              boundaryHandled !== currentSegment.k &&
              !player.paused &&
              document.getElementById("v-auto-pause").checked
            ) {
              boundaryHandled = currentSegment.k;
              player.pause();
              root.classList.add("v-split");
              emit("segment-boundary", {
                lecture,
                k: currentSegment.k,
                s: currentSegment.s,
                t_end: currentSegment.t_end,
                frame: `/raw/${lecture}/${currentSegment.final_frame}`,
              });
            }
          };
          host.append(media);
        }
      } else
        host.append(
          el(
            "div",
            "v-media-empty",
            "▷  원본 영상 미등록 · 샘플 프레임을 표시합니다",
          ),
        );
      emit("anchor-open", { lecture, s, t, anchor: clean });
      emit("segment-boundary", {
        lecture,
        k: seg.k,
        s,
        t_end: seg.t_end,
        frame: source.frame,
      });
    } catch (e) {
      toast(e.message);
    }
  }
  function init() {
    if (document.getElementById("v-root")) return;
    root = el("div", "v-app");
    root.id = "v-root";
    if (innerWidth <= 950) root.classList.add("v-chat-hidden");
    document.documentElement.append(root);
    document.documentElement.classList.add("v-mounted");
    nav = el("aside", "v-sidebar");
    nav.setAttribute("aria-label", "주 탐색");
    const workspace = el("div", "v-work");
    const top = el("header", "v-topbar");
    top.append(
      btn("☰", "v-icon-button v-mobile-menu", () =>
        root.classList.toggle("v-menu-open"),
      ),
      el("span", "", "나의 학습 공간"),
      el("span", "v-top-status", "✧  강의와 이해 사이"),
      btn("Agent  ◫", "v-secondary", () =>
        root.classList.toggle("v-chat-hidden"),
      ),
    );
    main = el("main", "v-main");
    workspace.append(top, main);
    pane = el("aside", "v-player");
    pane.id = "v-pane";
    pane.hidden = true;
    const ph = el("div", "v-player-head");
    const pt = el("strong", "", "원본 보기");
    pt.id = "v-source-title";
    ph.append(
      pt,
      btn("↔", "v-icon-button", () => root.classList.toggle("v-split")),
      btn("×", "v-icon-button", () => {
        pane.hidden = true;
        media?.pause();
        root.classList.remove("v-has-player", "v-split");
      }),
    );
    frame = el("img", "v-frame");
    frame.onerror = () => {
      frame.hidden = true;
    };
    const mh = el("div");
    mh.id = "v-media";
    pane.append(ph, frame, mh);
    let dragState = null;
    ph.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button")) return;
      dragState = {
        x: event.clientX,
        y: event.clientY,
        left: pane.offsetLeft,
        top: pane.offsetTop,
      };
      pane.classList.add("v-player-dragging");
      ph.setPointerCapture?.(event.pointerId);
    });
    window.addEventListener("pointermove", (event) => {
      if (!dragState) return;
      const dx = event.clientX - dragState.x;
      const dy = event.clientY - dragState.y;
      pane.style.left = `${Math.min(Math.max(16, dragState.left + dx), innerWidth - pane.offsetWidth - 16)}px`;
      pane.style.top = `${Math.min(Math.max(16, dragState.top + dy), innerHeight - pane.offsetHeight - 16)}px`;
      pane.style.right = "auto";
    });
    window.addEventListener("pointerup", () => {
      dragState = null;
      pane.classList.remove("v-player-dragging");
    });
    const chat = el("aside", "v-chat");
    chat.id = "chat-slot";
    root.append(nav, workspace, pane, chat);
    fetch("/web/viewer/library.json")
      .then((r) => {
        if (!r.ok) throw new Error("노트 목록을 불러오지 못했습니다.");
        return r.json();
      })
      .then((data) => {
        pages.push(...data);
        show("note");
        const a = new URLSearchParams(location.search).get("anchor");
        if (a) openAnchor(a);
      })
      .catch((e) => {
        toast(e.message);
        heading("MOTGA", "자료를 불러오지 못했습니다");
      });
    emit("motga-ready");
  }
  window.addEventListener("anchor-request", (e) => openAnchor(e.detail.anchor));
  window.addEventListener("context-request", () =>
    emit("context-reply", { slug: state.slug, anchor: state.anchor }),
  );
  for (const name of ["notes-closed", "note-saved"])
    window.addEventListener(name, (e) => {
      if (
        media &&
        currentSegment?.lecture === e.detail?.lecture &&
        currentSegment?.k === e.detail?.k
      )
        media.play().catch(() => {});
    });
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      show("search");
    }
    if (e.key === "Escape") {
      root?.classList.remove("v-menu-open");
    }
  });
  document.addEventListener("mouseup", (e) => {
    if (e.target.closest("#v-selection")) return;
    document.getElementById("v-selection")?.remove();
    const selection = getSelection();
    if (!selection?.toString().trim()) return;
    const start = selection.getRangeAt(0).startContainer;
    const block = (start.nodeType === 1 ? start : start.parentElement)?.closest(
      ".v-article p,.v-article blockquote",
    );
    if (!block) return;
    let chip = block.querySelector(".v-anchor");
    let prev = block.previousElementSibling;
    while (!chip && prev && !/^H2$/.test(prev.tagName)) {
      chip = prev.querySelector(".v-anchor");
      prev = prev.previousElementSibling;
    }
    if (!chip) return;
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    const b = btn("↗ 원본 보기", "v-selection", () => {
      openAnchor(chip.dataset.anchor);
      b.remove();
    });
    b.id = "v-selection";
    b.style.left = `${Math.min(rect.left, innerWidth - 150)}px`;
    b.style.top = `${Math.max(8, rect.top - 42)}px`;
    root.append(b);
  });
  document.addEventListener("nav", init);
  init();
})();
