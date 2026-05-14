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

function normalizeSpeakerClass(speaker) {
  const normalized = (speaker || "").trim();
  if (normalized === "怡潔") {
    return "speaker-yijie";
  }
  if (normalized === "德奕") {
    return "speaker-deyi";
  }
  if (normalized === "緯麒") {
    return "speaker-weiqi";
  }
  if (normalized === "學員" || normalized === "提問者" || normalized === "回應者") {
    return "speaker-student";
  }
  return "speaker-generic";
}

function parseTranscriptLine(paragraph) {
  const match = String(paragraph || "").match(/^([^：:]{1,12})[：:]\s*(.+)$/);
  if (!match) {
    return {
      kind: "plain",
      text: String(paragraph || "").trim()
    };
  }

  return {
    kind: "speaker",
    speaker: match[1].trim(),
    text: match[2].trim()
  };
}

function splitClosingSummary(paragraphs = []) {
  if (!Array.isArray(paragraphs) || paragraphs.length === 0) {
    return { body: [], closingSummary: "" };
  }

  const items = [...paragraphs];
  const last = String(items.at(-1) || "").trim();
  const summaryMatch = last.match(/^段落小結[：:]\s*(.+)$/);
  if (!summaryMatch) {
    return { body: items, closingSummary: "" };
  }

  items.pop();
  return {
    body: items,
    closingSummary: summaryMatch[1].trim()
  };
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
    if (section.kind) {
      meta.append(createBadge(section.kind));
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

    const { body, closingSummary } = splitClosingSummary(section.transcript || []);
    const transcriptContainer = node.querySelector(".transcript-paragraphs");
    transcriptContainer.replaceChildren(...body.map((paragraph) => {
      const parsed = parseTranscriptLine(paragraph);
      const p = document.createElement("p");
      p.className = "transcript-line";
      if (parsed.kind === "speaker") {
        const speaker = document.createElement("span");
        speaker.className = `speaker-label ${normalizeSpeakerClass(parsed.speaker)}`;
        speaker.textContent = `${parsed.speaker}：`;

        const text = document.createElement("span");
        text.className = "speaker-text";
        text.textContent = parsed.text;
        p.append(speaker, text);
        return p;
      }

      p.textContent = parsed.text;
      return p;
    }));

    const closingSummaryBlock = node.querySelector(".closing-summary");
    if (section.closingSummary || closingSummary) {
      node.querySelector(".closing-summary-text").textContent = section.closingSummary || closingSummary;
      closingSummaryBlock.hidden = false;
    } else {
      closingSummaryBlock.hidden = true;
    }

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
