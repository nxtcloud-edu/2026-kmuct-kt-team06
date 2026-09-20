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
    folders: read("motga-folders", []),
    collapsedFolders: new Set(read("motga-collapsed-folders", [])),
    uploadFolder: null,
    // 기본은 실서버(/api). 저장된 설정이 없는 새 브라우저(발표장·심사위원)가 샘플 응답을 보지 않게 한다.
    // API 없이 화면만 개발할 때는 설정(⚙)에서 "샘플 데이터"를 켠다.
    mock: read("motga-mock", false),
    hiddenSlugs: new Set(read("motga-hidden-slugs", [])),
    page: null,
  };
  function closeMobileMenu() {
    if (root && root.classList.contains("v-menu-open")) root.classList.remove("v-menu-open");
  }
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
  let splitButton, transcript, transcriptRows = [], transcriptRequest = 0;
  function setSplit(enabled) {
    root.classList.toggle("v-split", enabled);
    splitButton.title = enabled ? "작은 플레이어로 돌아가기" : "노트와 영상 나란히 보기";
    splitButton.setAttribute("aria-label", splitButton.title);
    splitButton.setAttribute("aria-pressed", String(enabled));
  }
  function seekToTranscriptTime(timeValue) {
    if (!media) return false;
    const player = media;
    const apply = () => {
      player.currentTime = timeValue;
      highlightTranscript(timeValue);
      if (player.paused) player.play().catch(() => {});
    };
    if (player.readyState > 0 && Number.isFinite(player.duration)) {
      apply();
      return true;
    }
    const onLoaded = () => {
      player.removeEventListener("loadedmetadata", onLoaded);
      apply();
    };
    player.addEventListener("loadedmetadata", onLoaded, { once: true });
    return true;
  }
  function highlightTranscript(t) {
    for (const { row, entry } of transcriptRows) {
      const active = entry.t_start <= t && t < entry.t_end;
      row.classList.toggle("active", active);
      if (active) row.setAttribute("aria-current", "true");
      else row.removeAttribute("aria-current");
    }
  }
  async function loadTranscript(lecture, t, segments) {
    const token = ++transcriptRequest;
    transcriptRows = [];
    transcript.replaceChildren(el("h2", "", "STT 스크립트"), el("p", "v-muted", "스크립트를 불러오는 중…"));
    try {
      const response = await fetch(`/raw/${encodeURIComponent(lecture)}/transcript.json`);
      if (!response.ok) throw new Error(response.status === 404
        ? "아직 등록된 STT 스크립트가 없습니다."
        : "STT 스크립트를 불러오지 못했습니다.");
      const entries = await response.json();
      if (!Array.isArray(entries)) throw new Error("STT 스크립트 형식을 확인해 주세요.");
      if (token !== transcriptRequest) return;
      transcript.replaceChildren(el("h2", "", "STT 스크립트"));
      for (const entry of entries.filter((e) => typeof e.text === "string" && Number.isFinite(e.t_start) && Number.isFinite(e.t_end) && e.t_start >= 0 && e.t_end > e.t_start).sort((a, b) => a.t_start - b.t_start)) {
        const row = btn("", "v-transcript-row", () => {
          const segment = segments.find((s) => s.t_start <= entry.t_start && entry.t_start < s.t_end);
          if (media && !media.error) {
            seekToTranscriptTime(entry.t_start);
            setSplit(true);
          } else if (segment) {
            openAnchor(`${lecture}#s${segment.s}@t=${Math.ceil(entry.t_start)}`);
          }
        });
        row.append(el("span", "v-transcript-time", time(entry.t_start)), el("span", "", entry.text));
        transcript.append(row);
        transcriptRows.push({ row, entry });
      }
      if (!transcriptRows.length) transcript.append(el("p", "v-muted", "아직 등록된 STT 스크립트가 없습니다."));
      highlightTranscript(media?.currentTime ?? t);
    } catch (e) {
      if (token !== transcriptRequest) return;
      transcript.replaceChildren(el("h2", "", "STT 스크립트"), el("p", "v-muted", e.message),
        btn("다시 불러오기", "v-secondary", () => loadTranscript(lecture, t, segments)));
    }
  }
  const pages = [];
  const localAssets = new Map();
  // 실제 위키로 만든 목록(tools/build_library.py, gitignore)이 있으면 그걸, 없으면 커밋된 견본을 쓴다.
  async function loadPages() {
    let response = await fetch("/web/viewer/library.local.json");
    if (!response.ok) response = await fetch("/web/viewer/library.json");
    if (!response.ok) throw new Error("노트 목록을 불러오지 못했습니다.");
    return response.json();
  }
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
        const concept = btn(m[2] || m[1].split("/").pop(), "v-concept", () => {
          closeMobileMenu();
          show("note", m[1]);
        });
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
    );
    // 강의 폴더는 과목별로(library 항목의 course). course 가 없으면 "강의 노트" 하나로 묶는다.
    const courses = [...new Set(pages.filter((p) => p.type === "lecture").map((p) => p.course || "강의 노트"))];
    for (const c of courses.length ? courses : ["강의 노트"])
      renderFolder(nav, { id: `lectures:${c}`, name: c, type: "lecture", course: c });
    renderFolder(nav, { id: "concepts", name: "개념 노트", type: "concept" });
    for (const p of state.local.filter((p) => !p.folderId))
      renderFile(nav, p, true);
    const bottom = el("div", "v-sidebar-bottom");
    // 분석이 도는 동안에는 어느 화면에 있든 진행 상황 칩이 사이드바에 남는다.
    if (ingest) {
      const chip = btn(ingestChipText(), "v-ingest-chip", () => {
        closeMobileMenu();
        show("upload");
      });
      chip.title = `${ingest.title || "강의"} · 분석 진행 중`;
      bottom.append(chip);
    }
    bottom.append(btn("＋  강의 자료 추가", "v-add", () => {
      state.uploadFolder = null;
      show("upload");
    }));
    const profile = btn("", "v-profile", settings);
    const profileAvatar = el("span", "v-profile-avatar", "L");
    const profileName = el("span", "v-profile-name", "Lecki");
    const profileGear = el("span", "v-profile-gear", "⚙");
    profile.append(profileAvatar, profileName, profileGear);
    profile.append(el("small", "", "개인 학습 공간"));
    bottom.append(profile);
    nav.append(bottom);
  }
  function renderFile(parent, p, local = false) {
    const id = local ? p.id : p.slug;
    const view = local ? "local" : "note";
    const title = !local && p.type === "lecture"
      ? p.title.replace(/^L\d+\. /, "").split(" —")[0] : p.title;
    const row = el("div", "v-nav-local-row");
    row.append(btn(
      `${p.type === "concept" ? "◇" : "▤"}  ${title}`,
      `v-nav v-file ${state.slug === id && state.view === view ? "active" : ""}`,
      () => show(view, id),
    ));
    const del = btn("🗑", "v-icon-button v-nav-delete", () =>
      local ? deleteLocal(id) : deleteNote(id),
    );
    del.title = local ? "노트 삭제" : "노트 숨기기";
    del.setAttribute("aria-label", `${p.title} 삭제`);
    row.append(del);
    parent.append(row);
  }
  function renderFolder(parent, folder) {
    const section = el("div", "v-folder-section");
    section.dataset.folderId = folder.id;
    const row = el("div", "v-folder-row");
    const children = el("div", "v-folder-children");
    children.id = `folder-${folder.id}`;
    children.hidden = state.collapsedFolders.has(folder.id);
    const toggle = btn("", "v-folder", () => {
      const next = new Set(state.collapsedFolders);
      if (next.has(folder.id)) next.delete(folder.id);
      else next.add(folder.id);
      if (!save("motga-collapsed-folders", [...next])) return;
      state.collapsedFolders = next;
      children.hidden = next.has(folder.id);
      updateToggle();
    });
    function updateToggle() {
      toggle.textContent = `${children.hidden ? "›" : "⌄"}  ▱  ${folder.name}`;
      toggle.setAttribute("aria-expanded", String(!children.hidden));
    }
    toggle.setAttribute("aria-label", folder.name);
    toggle.setAttribute("aria-controls", children.id);
    updateToggle();
    const add = btn("+", "v-icon-button v-folder-add", () => addToFolder(folder));
    add.title = `${folder.name}에 추가`;
    add.setAttribute("aria-label", add.title);
    row.append(toggle, add);
    for (const child of state.folders.filter((f) => f.parentId === folder.id))
      renderFolder(children, child);
    if (folder.type)
      for (const p of pages.filter((p) => p.type === folder.type && !state.hiddenSlugs.has(p.slug)
        && (!folder.course || (p.course || "강의 노트") === folder.course)))
        renderFile(children, p);
    for (const p of state.local.filter((p) => p.folderId === folder.id))
      renderFile(children, p, true);
    if (!children.childElementCount)
      children.append(el("p", "v-folder-empty", "비어 있는 폴더"));
    section.append(row, children);
    parent.append(section);
  }
  function expandFolder(id) {
    while (id) {
      state.collapsedFolders.delete(id);
      id = state.folders.find((f) => f.id === id)?.parentId;
    }
    save("motga-collapsed-folders", [...state.collapsedFolders]);
  }
  function addToFolder(folder) {
    const dialog = el("dialog", "v-dialog");
    dialog.setAttribute("aria-label", `${folder.name}에 추가`);
    const form = el("form", "v-folder-form");
    const name = el("input", "v-search-input");
    name.placeholder = "새 폴더 이름";
    name.setAttribute("aria-label", "새 폴더 이름");
    name.required = true;
    name.maxLength = 80;
    const create = btn("폴더 만들기", "v-primary");
    create.type = "submit";
    form.onsubmit = (event) => {
      event.preventDefault();
      const title = name.value.trim();
      name.setCustomValidity(!title ? "폴더 이름을 입력해 주세요." :
        state.folders.some((f) => f.parentId === folder.id && f.name === title)
          ? "같은 이름의 폴더가 있습니다." : "");
      if (!name.reportValidity()) return;
      const folders = [...state.folders, {
        id: `folder-${crypto.randomUUID()}`, parentId: folder.id, name: title,
      }];
      if (!save("motga-folders", folders)) return;
      state.folders = folders;
      expandFolder(folder.id);
      dialog.close();
      sidebar();
      toast("하위 폴더를 만들었습니다.");
    };
    name.oninput = () => name.setCustomValidity("");
    form.append(name, create);
    dialog.append(el("h2", "", `${folder.name}에 추가`), form,
      btn("파일 추가", "v-primary", () => {
        state.uploadFolder = folder.id;
        dialog.close();
        show("upload");
      }),
      btn("취소", "v-secondary", () => dialog.close()),
    );
    dialog.addEventListener("close", () => dialog.remove());
    root.append(dialog);
    dialog.showModal();
    name.focus();
  }
  function heading(eyebrow, title, subtitle) {
    main.append(el("div", "v-eyebrow", eyebrow), el("h1", "", title));
    if (subtitle) main.append(el("p", "v-subtitle", subtitle));
  }
  async function show(view, slug) {
    state.view = view;
    if (slug) state.slug = slug;
    closeMobileMenu();
    sidebar();
    main.replaceChildren();
    main.scrollTop = 0;
    emit("view-changed", { view });
    if (view === "dashboard") {
      heading("MY LEARNING", "대시보드");
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
        const restoreBtn = btn("복원", "v-secondary", async () => {
          if (restoreBtn.disabled) return;
          restoreBtn.disabled = true;
          const ok = await restoreHiddenNote(p.slug);
          if (!ok) restoreBtn.disabled = false;
        });
        actions.append(restoreBtn);
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
      // 출처 강의 · 이 노트에 달린 앵커 수 (본문에서 센다 — 고정 문구였던 "L3 · 8개 구간" 대체)
      el(
        "span",
        "",
        `${[...new Set((p.body.match(/\[\[(L\d+)#s\d+@t=\d+\]\]/g) || []).map((a) => a.slice(2).split("#")[0]))].join("·") || (p.course || "노트")} · 출처 ${(p.body.match(/\[\[L\d+#s\d+@t=\d+\]\]/g) || []).length}곳`,
      ),
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
    input.placeholder = "레지스터, 머지소트, 캐시…";
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
    const folderId = state.uploadFolder;
    // 강의 폴더 id 는 `lectures:<과목>` 이다. 폴더 이름은 그 과목 이름을 그대로 쓴다.
    const courseFolder = courseFromFolder(folderId);
    const folderName = courseFolder ||
      (folderId === "concepts" ? "개념 노트" :
        state.folders.find((f) => f.id === folderId)?.name);
    if (!state.mock) {
      ingestView(courseFolder, folderName);
      return;
    }
    heading(
      "NEW LECTURE",
      "강의 자료 불러오기",
      "흩어져 있던 강의 영상과 전사본, 슬라이드를 한곳에 모으세요.",
    );
    if (folderName) main.append(el("p", "v-muted", `추가할 폴더: ${folderName}`));
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
          folderId,
          text,
          files: selected.map((f) => f.name),
        };
        if (!save("motga-documents", [...state.local, p]))
          throw new Error("자료를 저장하지 못했습니다.");
        state.local.push(p);
        if (folderId) expandFolder(folderId);
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
  // ── 실서버 인제스트(POST /api/ingest → 폴링) ─────────────────────────────
  // 순수 함수들(파일 종류·검증·단계·경과시간·과목 목록)은 노드에서 단위 테스트한다.
  const INGEST_KEY = "motga-ingest-job";
  const INGEST_COURSE_KEY = "motga-courses";
  const INGEST_NEW_COURSE = "__new-course__";
  const INGEST_MAX_BYTES = 500 * 1024 * 1024;
  const INGEST_ACCEPT = ".mp4,.m4a,.mp3,.wav,.txt,.md,.json,.pdf";
  const INGEST_EXT = /\.(mp4|m4a|mp3|wav|txt|md|json|pdf)$/i;
  const INGEST_STAGES = [
    ["upload", "업로드"],
    ["stt", "음성 인식"],
    ["align", "구간 정렬"],
    ["episodic", "노트 정리"],
    ["compile", "위키 컴파일"],
    ["build", "빌드"],
    ["done", "완료"],
  ];
  const INGEST_KIND_LABEL = {
    slide: "슬라이드",
    transcript: "전사본",
    media: "녹음·영상",
    other: "기타",
  };
  function fileKind(name) {
    if (/\.pdf$/i.test(name)) return "slide";
    if (/\.(md|txt|json)$/i.test(name)) return "transcript";
    if (/\.(mp4|webm|m4a|mp3|wav)$/i.test(name)) return "media";
    return "other";
  }
  function validateIngest(files) {
    const list = files || [];
    if (!list.length) return "분석할 파일을 먼저 선택해 주세요.";
    const kinds = list.map((f) => fileKind(f.name));
    if (!kinds.includes("slide"))
      return "슬라이드 PDF가 필요합니다. .pdf 파일을 함께 선택해 주세요.";
    if (!kinds.includes("transcript") && !kinds.includes("media"))
      return "타임스탬프 전사본(.md · .json) 또는 녹음·영상 파일이 필요합니다.";
    const total = list.reduce((sum, f) => sum + (f.size || 0), 0);
    if (total > INGEST_MAX_BYTES)
      return `전체 용량이 500MB를 넘습니다 (${Math.round(total / 1024 / 1024)}MB). 파일을 줄여 주세요.`;
    return "";
  }
  function stageIndex(stage) {
    return INGEST_STAGES.findIndex((s) => s[0] === stage);
  }
  function elapsedText(ms) {
    const total = Math.max(0, Math.floor((ms || 0) / 1000));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h) return `${h}시간 ${m}분`;
    if (m) return `${m}분 ${s}초`;
    return `${s}초`;
  }
  function mergeCourses(fromPages, stored) {
    const seen = new Map();
    for (const raw of [...(fromPages || []), ...(stored || [])]) {
      const name = typeof raw === "string" ? raw.trim() : "";
      if (!name) continue;
      const key = name.toLowerCase();
      if (!seen.has(key)) seen.set(key, name);
    }
    return [...seen.values()].sort((a, b) => a.localeCompare(b, "ko"));
  }
  function courseFromFolder(folderId) {
    return typeof folderId === "string" && folderId.startsWith("lectures:")
      ? folderId.slice("lectures:".length)
      : "";
  }
  function percentOf(value) {
    return Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
  }
  let ingest = null;
  let ingestStatus = null;
  let ingestError = null;
  let ingestDraft = { title: "", course: "" };
  let ingestUI = null;
  let ingestPollTimer = null;
  let ingestWatchTimer = null;
  let ingestClockTimer = null;
  let ingestFailures = 0;
  let ingestBusy = false;
  const ingestChipText = () =>
    `◷  ${ingest?.lecture || "강의"} 분석 중 ${percentOf(ingestStatus?.percent)}%`;
  function renderIngestChip() {
    const chip = document.querySelector(".v-ingest-chip");
    if (!ingest) {
      chip?.remove();
      return;
    }
    // 칩이 아직 없으면(다른 화면에서 시작됐거나 새로고침 직후) 사이드바를 한 번 다시 그린다.
    if (!chip) {
      if (nav) sidebar();
      return;
    }
    chip.textContent = ingestChipText();
  }
  function saveIngestJob(job) {
    ingest = job;
    if (job) save(INGEST_KEY, job);
    else
      try {
        localStorage.removeItem(INGEST_KEY);
      } catch {}
    renderIngestChip();
  }
  function stopIngestPolling() {
    clearInterval(ingestPollTimer);
    clearInterval(ingestWatchTimer);
    clearInterval(ingestClockTimer);
    ingestPollTimer = ingestWatchTimer = ingestClockTimer = null;
  }
  function startIngestPolling() {
    if (ingestPollTimer) return; // 화면을 다시 들어와도 타이머는 하나만
    pollIngest();
    ingestPollTimer = setInterval(pollIngest, 2000);
    // 분석 중에도 위키는 자란다 — 20초마다 목록을 다시 읽어 새 노트를 사이드바에 반영한다.
    ingestWatchTimer = setInterval(() => refreshPages(), 20000);
    ingestClockTimer = setInterval(renderIngestElapsed, 1000);
  }
  async function pollIngest() {
    if (!ingest || ingestBusy) return;
    const job = ingest.job;
    ingestBusy = true;
    try {
      const data = await api(`/api/ingest/${encodeURIComponent(job)}`);
      if (!ingest || ingest.job !== job) return;
      ingestFailures = 0;
      ingestStatus = data;
      if (data.lecture && data.lecture !== ingest.lecture)
        saveIngestJob({ ...ingest, lecture: data.lecture });
      renderIngestProgress();
      if (data.stage === "done") await finishIngest(data);
      else if (data.stage === "error")
        failIngest(data.error || data.detail || "알 수 없는 오류");
    } catch (e) {
      if (!ingest || ingest.job !== job) return;
      ingestFailures += 1;
      if (ingestFailures >= 5) failIngest(e.message);
      else renderIngestProgress();
    } finally {
      ingestBusy = false;
    }
  }
  function failIngest(reason) {
    stopIngestPolling();
    ingestDraft = {
      title: ingest?.title || ingestDraft.title,
      course: ingest?.course || ingestDraft.course,
    };
    ingestError = reason || "알 수 없는 오류";
    ingestStatus = null;
    ingestUI = null;
    saveIngestJob(null);
    if (state.view === "upload") show("upload");
    else toast(`분석 실패: ${ingestError}`);
  }
  async function finishIngest(data) {
    const lecture = data.lecture || ingest?.lecture || "";
    stopIngestPolling();
    ingestUI = null;
    ingestStatus = null;
    ingestError = null;
    saveIngestJob(null);
    state.files = [];
    ingestDraft = { title: "", course: "" };
    const result = await refreshPages();
    const added = result?.added || 0;
    const target = lecture
      ? pages.find((p) => p.slug.startsWith(`lectures/${lecture}_`))
      : null;
    if (target) {
      toast(`분석이 끝났습니다 — 새 노트 ${added}개`);
      show("note", target.slug);
      return;
    }
    toast(
      `분석이 끝났습니다 — 새 노트 ${added}개. ${lecture || "새 강의"} 노트를 목록에서 찾지 못해 이 화면에 머무릅니다.`,
    );
    if (state.view === "upload") show("upload");
  }
  // 목록 파일을 다시 읽어 바뀌었으면 pages 를 제자리에서 교체한다. { changed, added } 또는 null.
  async function refreshPages() {
    let next;
    try {
      next = await loadPages();
    } catch {
      return null;
    }
    if (!Array.isArray(next)) return null;
    const before = new Set(pages.map((p) => p.slug));
    const added = next.filter((p) => !before.has(p.slug));
    // 슬러그가 그대로여도 본문이 다시 컴파일됐을 수 있어 내용까지 비교한다.
    let same = next.length === pages.length && !added.length;
    if (same)
      try {
        same = JSON.stringify(next) === JSON.stringify(pages);
      } catch {
        same = false;
      }
    if (same) return { changed: false, added: 0 };
    if (!state.mock)
      for (const p of added) if (p.status === "grey") state.hiddenSlugs.add(p.slug);
    pages.splice(0, pages.length, ...next);
    sidebar();
    return { changed: true, added: added.length };
  }
  function resumeIngest() {
    if (state.mock) return;
    const saved = read(INGEST_KEY, null);
    if (!saved || !saved.job) return;
    ingest = saved;
    ingestStatus = null;
    ingestFailures = 0;
    renderIngestChip();
    startIngestPolling();
  }
  async function postIngest(files, title, course) {
    const form = new FormData();
    for (const f of files) form.append("files[]", f, f.name);
    form.append("title", title);
    form.append("course", course);
    // api() 는 Content-Type 을 json 으로 고정해서 multipart 경계를 깨뜨린다 — 여기서는 fetch 를 직접 쓴다.
    const response = await fetch("/api/ingest", { method: "POST", body: form });
    if (!response.ok) {
      let message = `요청에 실패했습니다 (${response.status})`;
      try {
        message = (await response.json()).error?.message || message;
      } catch {}
      throw new Error(message);
    }
    return response.json();
  }
  function renderIngestElapsed() {
    const ui = ingestUI;
    if (!ui || !ui.card.isConnected || !ingest) return;
    ui.elapsed.textContent = `경과 ${elapsedText(Date.now() - (ingest.startedAt || Date.now()))}`;
  }
  function renderIngestProgress() {
    renderIngestChip();
    const ui = ingestUI;
    if (!ui || !ui.card.isConnected) return; // 다른 화면에 있으면 칩만 갱신한다
    const data = ingestStatus || {};
    const index = stageIndex(data.stage);
    ui.steps.forEach((step, i) => {
      step.classList.toggle("done", index >= 0 && i < index);
      step.classList.toggle("current", i === index);
    });
    const percent = percentOf(data.percent);
    ui.fill.style.width = `${percent}%`;
    ui.bar.setAttribute("aria-valuenow", String(percent));
    ui.percent.textContent = `${percent}%`;
    ui.detail.textContent =
      data.detail || (index <= 0 ? "서버가 자료를 받는 중입니다…" : "진행 상황을 기다리는 중…");
    ui.warn.hidden = !ingestFailures;
    ui.warn.textContent = ingestFailures
      ? `서버 응답이 없습니다 · 다시 시도하는 중 (${ingestFailures}/5)`
      : "";
    renderIngestElapsed();
  }
  function ingestView(courseFolder, folderName) {
    ingestUI = null;
    if (ingest) return ingestProgressView();
    if (ingestError) return ingestErrorView();
    return ingestForm(courseFolder, folderName);
  }
  function ingestProgressView() {
    heading(
      "AI 분석 중",
      ingest.title || "강의 자료 분석",
      "창을 닫거나 다른 노트를 봐도 분석은 계속됩니다. 전체 강의는 보통 10~20분 걸립니다.",
    );
    const card = el("div", "v-ingest-card");
    const head = el("div", "v-ingest-card-head");
    head.append(
      el("strong", "", `${ingest.lecture || "새 강의"} · ${ingest.course || "과목 미지정"}`),
    );
    const elapsed = el("small", "v-ingest-elapsed", "경과 0초");
    head.append(elapsed);
    const steps = [];
    const stepper = el("ol", "v-ingest-steps");
    for (const [, label] of INGEST_STAGES) {
      const step = el("li", "v-ingest-step");
      step.append(el("span", "v-ingest-dot"), el("span", "v-ingest-step-label", label));
      stepper.append(step);
      steps.push(step);
    }
    const bar = el("div", "v-ingest-bar");
    bar.setAttribute("role", "progressbar");
    bar.setAttribute("aria-label", "분석 진행률");
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", "100");
    bar.setAttribute("aria-valuenow", "0");
    const fill = el("div", "v-ingest-bar-fill");
    bar.append(fill);
    const percent = el("span", "v-ingest-percent", "0%");
    const detail = el("p", "v-ingest-detail", "진행 상황을 기다리는 중…");
    detail.setAttribute("role", "status");
    const warn = el("p", "v-ingest-warn", "");
    warn.hidden = true;
    card.append(head, stepper, bar, percent, detail, warn);
    main.append(
      card,
      el(
        "p",
        "v-muted",
        "노트가 만들어지는 대로 왼쪽 목록에 하나씩 나타납니다.",
      ),
      btn("← 노트 보러 가기", "v-secondary", () => show("note")),
    );
    ingestUI = { card, steps, bar, fill, percent, detail, warn, elapsed };
    renderIngestProgress();
  }
  function ingestErrorView() {
    heading("AI 분석", "분석에 실패했습니다", "입력한 내용은 그대로 두었습니다. 다시 시도해 보세요.");
    main.append(
      el("div", "v-ingest-error", `분석 실패: ${ingestError}`),
      btn("다시 시도", "v-primary", () => {
        ingestError = null;
        show("upload");
      }),
    );
  }
  function ingestForm(courseFolder, folderName) {
    heading(
      "NEW LECTURE",
      "강의 자료 불러오기",
      "슬라이드 PDF와 함께, 타임스탬프 전사본(.md · .json) 또는 녹음·영상 파일을 올려 주세요.",
    );
    if (folderName) main.append(el("p", "v-muted", `추가할 폴더: ${folderName}`));
    const form = el("form", "v-ingest-form");
    form.onsubmit = (event) => event.preventDefault();
    const title = el("input", "v-search-input");
    title.placeholder = "강의 제목을 입력하세요";
    title.setAttribute("aria-label", "강의 제목");
    title.maxLength = 120;
    title.value = ingestDraft.title || "";
    // 과목은 자유 입력이 아니라 선택 + "새 과목 추가" 다.
    const savedCourses = read(INGEST_COURSE_KEY, []);
    const options = mergeCourses(
      pages.filter((p) => p.type === "lecture").map((p) => p.course),
      Array.isArray(savedCourses) ? savedCourses : [],
    );
    const preset = ingestDraft.course || courseFolder || "";
    if (preset && !options.some((c) => c.toLowerCase() === preset.toLowerCase()))
      options.splice(0, options.length, ...mergeCourses(options, [preset]));
    const select = el("select", "v-ingest-select");
    select.setAttribute("aria-label", "과목");
    let previous = "";
    const drawOptions = (selected) => {
      select.replaceChildren();
      const placeholder = el("option", "", "과목을 선택하세요");
      placeholder.value = "";
      placeholder.disabled = true;
      select.append(placeholder);
      for (const name of options) {
        const option = el("option", "", name);
        option.value = name;
        select.append(option);
      }
      const adder = el("option", "", "＋ 새 과목 추가…");
      adder.value = INGEST_NEW_COURSE;
      select.append(adder);
      select.value = options.some((c) => c === selected) ? selected : "";
      previous = select.value;
    };
    const newRow = el("div", "v-ingest-newcourse");
    const newName = el("input", "v-ingest-input");
    newName.placeholder = "과목 이름";
    newName.maxLength = 30;
    newName.setAttribute("aria-label", "새 과목 이름");
    const confirmCourse = btn("확인", "v-secondary", () => {
      const name = newName.value.trim();
      if (!name) {
        newName.focus();
        toast("과목 이름을 입력해 주세요.");
        return;
      }
      const existing = options.find((c) => c.toLowerCase() === name.toLowerCase());
      if (!existing) {
        options.splice(0, options.length, ...mergeCourses(options, [name]));
        const stored = read(INGEST_COURSE_KEY, []);
        save(
          INGEST_COURSE_KEY,
          mergeCourses(Array.isArray(stored) ? stored : [], [name]),
        );
      }
      drawOptions(existing || name);
      newRow.hidden = true;
      newName.value = "";
    });
    newRow.append(
      newName,
      confirmCourse,
      btn("취소", "v-secondary", () => {
        newRow.hidden = true;
        newName.value = "";
        select.value = previous;
      }),
    );
    newName.onkeydown = (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      confirmCourse.click();
    };
    select.onchange = () => {
      if (select.value !== INGEST_NEW_COURSE) {
        previous = select.value;
        newRow.hidden = true;
        return;
      }
      newRow.hidden = false;
      newName.focus();
    };
    drawOptions(preset);
    newRow.hidden = options.length > 0; // 과목이 하나도 없으면 입력칸을 펼쳐 둔다
    const input = el("input");
    input.type = "file";
    input.multiple = true;
    input.accept = INGEST_ACCEPT;
    input.hidden = true;
    const drop = btn("", "v-dropzone", () => input.click());
    drop.append(
      el("div", "v-upload-icon", "↥"),
      el("h2", "", "파일을 여기에 놓아주세요"),
      el("p", "", "또는 클릭하여 내 컴퓨터에서 선택"),
      el("small", "", "PDF(슬라이드) + MD · JSON(전사본) 또는 MP4 · M4A · MP3 · WAV(녹음·영상)"),
    );
    const list = el("div", "v-upload-list");
    const summary = el("p", "v-ingest-summary", "");
    const hint = el("p", "v-ingest-hint", "");
    const start = btn("AI 분석 시작  →", "v-primary", () => submit());
    const draw = () => {
      list.replaceChildren();
      for (const file of state.files) {
        const row = el("div", "v-upload-row v-ingest-row");
        const kind = fileKind(file.name);
        row.append(
          el("span", `v-ingest-badge v-ingest-badge-${kind}`, INGEST_KIND_LABEL[kind]),
          el("span", "v-ingest-name", file.name),
          el("small", "", `${(file.size / 1024 / 1024).toFixed(2)} MB`),
          btn("×", "v-icon-button", () => {
            state.files = state.files.filter((f) => f !== file);
            draw();
          }),
        );
        list.append(row);
      }
      const total = state.files.reduce((sum, f) => sum + f.size, 0);
      summary.textContent = state.files.length
        ? `파일 ${state.files.length}개 · 합계 ${(total / 1024 / 1024).toFixed(1)} MB / 500 MB`
        : "아직 선택한 파일이 없습니다.";
      const problem = validateIngest(state.files);
      hint.textContent = problem || "준비되었습니다. 분석을 시작할 수 있어요.";
      hint.classList.toggle("bad", Boolean(problem));
    };
    const add = (files) => {
      const accepted = [...files].filter((f) => INGEST_EXT.test(f.name));
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
    async function submit() {
      const name = title.value.trim();
      const course = select.value === INGEST_NEW_COURSE ? "" : select.value.trim();
      if (!name) {
        title.focus();
        toast("강의 제목을 입력해 주세요.");
        return;
      }
      if (!course) {
        toast(
          newRow.hidden
            ? "과목을 선택해 주세요."
            : "새 과목 이름을 입력하고 확인을 눌러 주세요.",
        );
        (newRow.hidden ? select : newName).focus();
        return;
      }
      const problem = validateIngest(state.files);
      if (problem) {
        toast(problem);
        return;
      }
      const controls = [start, title, select, drop, input];
      for (const c of controls) c.disabled = true;
      start.textContent = "업로드 중…";
      ingestDraft = { title: name, course };
      try {
        const data = await postIngest(state.files, name, course);
        if (!data || !data.job) throw new Error("서버가 작업 번호를 주지 않았습니다.");
        ingestError = null;
        ingestFailures = 0;
        ingestStatus = { stage: "upload", percent: 0, detail: "" };
        saveIngestJob({
          job: data.job,
          lecture: data.lecture || "",
          title: name,
          course,
          startedAt: Date.now(),
        });
        startIngestPolling();
        show("upload");
      } catch (e) {
        toast(e.message);
        for (const c of controls) c.disabled = false;
        start.textContent = "AI 분석 시작  →";
      }
    }
    form.append(
      el("label", "v-ingest-label", "강의 제목"),
      title,
      el("label", "v-ingest-label", "과목"),
      select,
      newRow,
    );
    main.append(
      form,
      input,
      drop,
      el("h3", "", "선택한 자료"),
      list,
      summary,
      hint,
      el(
        "p",
        "v-muted",
        "업로드한 자료는 서버에서 음성 인식 → 구간 정렬 → 노트 정리를 거쳐 위키 노트가 됩니다. 전체 강의는 보통 10~20분 걸립니다.",
      ),
      start,
    );
    draw();
  }
  // 서버 검토 상태 전환(page:<slug>). 샘플 데이터 모드에서는 호출하지 않는다.
  const reviewCall = (path, slug) =>
    api(path, {
      method: "POST",
      body: JSON.stringify({ id: `page:${slug}` }),
    });
  async function restoreHiddenNote(slug) {
    if (!state.hiddenSlugs.has(slug)) return false;
    if (!state.mock) {
      try {
        await reviewCall("/api/review/approve", slug);
      } catch (error) {
        toast(`복원 거부: ${error.message}`);
        return false;
      }
    }
    state.hiddenSlugs.delete(slug);
    save("motga-hidden-slugs", [...state.hiddenSlugs]);
    const restored = pages.find((p) => p.slug === slug);
    if (restored && restored.status === "grey") restored.status = "approved";
    sidebar();
    toast("숨긴 노트를 복원했습니다.");
    if (state.view === "trash") show("trash");
    else show("note", slug);
    return true;
  }
  function deleteNote(slug) {
    const p = pages.find((p) => p.slug === slug);
    if (!p) return;
    const dialog = el("dialog", "v-dialog");
    dialog.append(
      el("h2", "", "노트 숨기기"),
      el("p", "v-muted", `"${p.title}" 노트를 목록에서 숨기시겠습니까? 삭제되는 것이 아니라 검토함으로 옮겨지며, 휴지통에서 언제든 복원할 수 있습니다. 새로고침 후에도 유지됩니다.`),
    );
    const hideBtn = btn("숨기기", "v-primary v-btn-danger", async () => {
      if (hideBtn.disabled) return;
      hideBtn.disabled = true;
      let onServer = false;
      if (!state.mock) {
        try {
          await reviewCall("/api/review/hide", slug);
          onServer = true;
        } catch (error) {
          hideBtn.disabled = false;
          toast(`숨기기 거부: ${error.message}`);
          return;
        }
      }
      state.hiddenSlugs.add(slug);
      save("motga-hidden-slugs", [...state.hiddenSlugs]);
      dialog.close();
      toast(
        onServer
          ? `"${p.title}" 노트를 서버 검토함(휴지통)으로 옮겼습니다. 삭제되지 않았습니다.`
          : `"${p.title}" 노트를 휴지통으로 보냈습니다.`,
      );
      const next = pages.find((p) => !state.hiddenSlugs.has(p.slug));
      if (next) show("note", next.slug);
      else show("dashboard");
    });
    dialog.append(
      hideBtn,
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
        async () => {
          if (restoreBtn.disabled) return;
          restoreBtn.disabled = true;
          let failed = 0;
          for (const slug of [...state.hiddenSlugs]) {
            if (!state.mock) {
              try {
                await reviewCall("/api/review/approve", slug);
              } catch {
                failed += 1;
                continue;
              }
            }
            state.hiddenSlugs.delete(slug);
          }
          save("motga-hidden-slugs", [...state.hiddenSlugs]);
          dialog.close();
          sidebar();
          toast(
            failed
              ? `${failed}개는 서버가 복원을 거부해 휴지통에 남았습니다.`
              : "숨긴 노트를 모두 복원했습니다.",
          );
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
        if (!source.video) {
          host.append(el("p", "v-muted", "이 강의는 녹음 파일이 없습니다. 슬라이드와 교수님 발언만 표시합니다."));
        } else if (source.video.kind === "youtube") {
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
          // 그 초에서 시작: ①미디어 프래그먼트(#t=) ②메타데이터 로드 시 seek ③재생 가능 시점에 한 번 더 확인.
          // (메타데이터 직후의 seek 을 브라우저가 무시하고 0초부터 트는 경우가 있었다 — 2026-09-20 실사용 제보)
          media.preload = "auto";
          media.src = `${source.video.src}#t=${t}`;
          const player = media;
          let boundaryHandled = null;
          const seekToAnchor = () => {
            const target = Math.min(t, Number.isFinite(player.duration) ? player.duration : t);
            if (Math.abs(player.currentTime - target) > 1.5) player.currentTime = target;
          };
          let settled = false;
          media.onloadedmetadata = () => {
            seekToAnchor();
            player.play().catch(() => {});
          };
          media.oncanplay = () => {
            if (settled) return;
            settled = true;
            seekToAnchor();
          };
          media.onerror = () =>
            toast(
              "원본 미디어를 불러올 수 없습니다. 파일 경로를 확인해 주세요.",
            );
          media.ontimeupdate = () => {
            highlightTranscript(player.currentTime);
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
              document.getElementById("v-auto-pause")?.checked
            ) {
              boundaryHandled = currentSegment.k;
              player.pause();
              setSplit(true);
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
      }
      loadTranscript(lecture, t, data.segments);
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
    const content = el("div", "v-learning-content");
    workspace.append(top, content);
    pane = el("aside", "v-player");
    pane.id = "v-pane";
    pane.hidden = true;
    const ph = el("div", "v-player-head");
    const pt = el("strong", "", "원본 보기");
    pt.id = "v-source-title";
    splitButton = btn("\u2194", "v-icon-button", () => setSplit(!root.classList.contains("v-split")));
    setSplit(false);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !document.querySelector("dialog[open]")) setSplit(false);
    });
    ph.append(
      pt,
      splitButton,
      btn("×", "v-icon-button", () => {
        setSplit(false);
        requestId++;
        transcriptRequest++;
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
    transcript = el("section", "v-transcript");
    transcript.setAttribute("aria-label", "STT script");
    const visual = el("div", "v-player-visual");
    visual.append(frame, mh);
    pane.append(ph, visual, transcript);
    content.append(main, pane);
    let dragState = null;
    ph.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button") || root.classList.contains("v-split")) return;
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
    root.append(nav, workspace, chat);
    loadPages()
      .then((data) => {
        pages.push(...data);
        // 서버에서 숨긴(status: grey) 페이지는 다른 브라우저에서도 숨김으로 보이고 휴지통에서 복원할 수 있어야 한다.
        if (!state.mock)
          for (const p of pages) if (p.status === "grey") state.hiddenSlugs.add(p.slug);
        // 기본 슬러그가 실제 목록에 없으면(강의 교체·삭제) 첫 번째 강의 노트로 떨어뜨린다.
        if (!pages.some((p) => p.slug === state.slug)) {
          const visible = pages.filter((p) => !state.hiddenSlugs.has(p.slug));
          const first =
            visible.find((p) => p.type === "lecture") || visible[0] || pages[0];
          if (first) state.slug = first.slug;
        }
        show("note");
        const a = new URLSearchParams(location.search).get("anchor");
        if (a) openAnchor(a);
        // 새로고침·화면 이동으로 잃지 않도록, 저장된 분석 작업이 있으면 백그라운드에서 이어 받는다.
        resumeIngest();
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
