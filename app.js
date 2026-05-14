async function loadTranscript() {
  try {
    const response = await fetch("./content/transcript.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Unable to load transcript.json: ${response.status}`);
    }
    return response.json();
  } catch (error) {
    if (window.__TRANSCRIPT_DATA__) {
      return window.__TRANSCRIPT_DATA__;
    }
    throw error;
  }
}

function fillText(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = value || "";
  }
}

function renderMeta(meta = {}) {
  const container = document.getElementById("meta-row");
  const chips = [
    meta.speaker ? `講者：${meta.speaker}` : "",
    meta.recordedAt ? `錄製：${meta.recordedAt}` : "",
    meta.duration ? `長度：${meta.duration}` : "",
    meta.status ? `狀態：${meta.status}` : ""
  ].filter(Boolean);

  container.replaceChildren(...chips.map((text) => {
    const chip = document.createElement("div");
    chip.className = "meta-chip";
    chip.textContent = text;
    return chip;
  }));
}

function renderAudio(audio = {}) {
  const panel = document.getElementById("audio-panel");
  const player = document.getElementById("audio-player");
  const downloadLink = document.getElementById("audio-download");

  if (!panel || !player || !audio.url) {
    if (panel) {
      panel.hidden = true;
    }
    return;
  }

  player.src = audio.url;
  player.setAttribute("aria-label", audio.label || "原始音檔播放器");
  panel.hidden = false;

  if (downloadLink) {
    downloadLink.href = audio.url;
    downloadLink.hidden = false;
  }
}

function renderList(id, items = []) {
  const container = document.getElementById(id);
  if (!container) {
    return;
  }
  container.replaceChildren(...items.map((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    return li;
  }));
}

function renderNav(sections = []) {
  const container = document.getElementById("section-nav");
  container.replaceChildren(...sections.map((section, index) => {
    const link = document.createElement("a");
    link.className = "section-link";
    link.href = `#${section.id}`;

    const strong = document.createElement("strong");
    strong.textContent = `${String(index + 1).padStart(2, "0")} ${section.title}`;

    const span = document.createElement("span");
    span.textContent = section.focus;

    link.append(strong, span);
    return link;
  }));
}

function createBadge(text) {
  const badge = document.createElement("span");
  badge.className = "segment-badge";
  badge.textContent = text;
  return badge;
}

function renderSections(sections = []) {
  const template = document.getElementById("section-template");
  const container = document.getElementById("sections");

  container.replaceChildren(...sections.map((section, index) => {
    const node = template.content.firstElementChild.cloneNode(true);

    node.id = section.id;
    node.querySelector(".segment-index").textContent = String(index + 1).padStart(2, "0");
    node.querySelector(".segment-kicker").textContent = section.kicker || `Section ${index + 1}`;
    node.querySelector(".segment-title").textContent = section.title || `未命名段落 ${index + 1}`;
    node.querySelector(".segment-focus").textContent = section.focus || "";

    const meta = node.querySelector(".segment-meta");
    if (section.timeRange) {
      meta.append(createBadge(section.timeRange));
    }
    if (section.tag) {
      meta.append(createBadge(section.tag));
    }

    const highlightList = node.querySelector(".highlight-list");
    highlightList.replaceChildren(...(section.highlights || []).map((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      return li;
    }));

    const quoteBlock = node.querySelector(".quote-block");
    if (section.quote) {
      node.querySelector(".quote-text").textContent = section.quote;
    } else {
      quoteBlock.hidden = true;
    }

    const transcriptContainer = node.querySelector(".transcript-paragraphs");
    transcriptContainer.replaceChildren(...(section.transcript || []).map((paragraph) => {
      const p = document.createElement("p");
      p.textContent = paragraph;
      return p;
    }));

    const voiceNote = node.querySelector(".voice-note");
    if (section.voiceNote) {
      node.querySelector(".voice-note-text").textContent = section.voiceNote;
    } else {
      voiceNote.hidden = true;
    }

    return node;
  }));
}

function renderPage(data) {
  fillText("page-title", data.title);
  fillText("page-subtitle", data.subtitle);
  fillText("content-note", data.contentNote);
  renderMeta(data.meta);
  renderAudio(data.audio);
  renderList("summary-list", data.summaryHighlights);
  renderNav(data.sections);
  renderSections(data.sections);
}

function renderError(error) {
  fillText("page-title", "逐字稿資料尚未準備完成");
  fillText("page-subtitle", "請確認 `content/transcript.json` 已存在且格式正確。");
  fillText("content-note", error.message);
}

loadTranscript()
  .then(renderPage)
  .catch(renderError);
