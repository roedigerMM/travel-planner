function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function hasValue(value) {
  return value !== null && value !== undefined && value !== "";
}

function clearInlineEmptyState(container) {
  container.querySelectorAll(".empty-inline").forEach((element) => element.remove());
}

function createOriginChip(origin) {
  const chip = document.createElement("div");
  chip.className = "chip";
  chip.dataset.originChip = "true";
  const iata = escapeHtml(origin.iata);
  const subType = escapeHtml(origin.sub_type);
  const providerSkyId = escapeHtml(origin.provider_sky_id || "");
  const providerEntityId = escapeHtml(origin.provider_entity_id || "");
  chip.innerHTML = `
    <span>${iata} · ${subType}</span>
    <button type="button" data-remove-origin aria-label="Remove ${iata}">&times;</button>
    <input type="hidden" name="origin_iata" value="${iata}" />
    <input type="hidden" name="origin_sub_type" value="${subType}" />
    <input type="hidden" name="origin_provider_sky_id" value="${providerSkyId}" />
    <input type="hidden" name="origin_provider_entity_id" value="${providerEntityId}" />
  `;
  chip.querySelector("[data-remove-origin]").addEventListener("click", () => chip.remove());
  return chip;
}

function createPreferenceChip(label) {
  const chip = document.createElement("div");
  chip.className = "chip";
  chip.dataset.preferenceChip = "true";
  const safeLabel = escapeHtml(label);
  chip.innerHTML = `
    <span>${safeLabel}</span>
    <button type="button" data-remove-preference aria-label="Remove ${safeLabel}">&times;</button>
  `;
  chip.querySelector("[data-remove-preference]").addEventListener("click", () => {
    chip.remove();
    updatePreferenceHiddenValue(chip.closest("[data-preference-chat]"));
  });
  return chip;
}

function updatePreferenceHiddenValue(container) {
  if (!container) {
    return;
  }
  const hidden = container.querySelector("[data-preference-hidden]");
  const chips = container.querySelector("[data-preference-chips]");
  const labels = Array.from(container.querySelectorAll("[data-preference-chip] span")).map((el) => el.textContent.trim());
  hidden.value = labels.join(", ");

  if (chips && labels.length === 0 && !chips.querySelector(".empty-inline")) {
    chips.innerHTML = '<p class="empty-inline">Generated tags will appear here.</p>';
  }
}

function appendChatBubble(thread, role, content) {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role === "assistant" ? "chat-bubble-assistant" : "chat-bubble-user"}`;
  bubble.textContent = content;
  thread.appendChild(bubble);
  thread.scrollTop = thread.scrollHeight;
}

function candidateMeta(candidate) {
  if (candidate.destination_code && candidate.destination_code !== (candidate.destination_name || "")) {
    const type = candidate.destination_type ? ` · ${escapeHtml(candidate.destination_type)}` : "";
    return `<p class="meta-line">Code: ${escapeHtml(candidate.destination_code)}${type}</p>`;
  }
  if (candidate.destination_type) {
    return `<p class="meta-line">${escapeHtml(candidate.destination_type)}</p>`;
  }
  return "";
}

function renderCandidates(container, candidates) {
  if (!candidates || candidates.length === 0) {
    container.innerHTML = '<p class="empty-state empty-block">No candidates were stored for this search.</p>';
    return;
  }

  const cards = candidates.map((candidate) => {
    const title = escapeHtml(candidate.destination_name || candidate.destination_iata || candidate.destination_code || "Unknown destination");
    const price = hasValue(candidate.price) ? `${Number(candidate.price).toFixed(2)} ${escapeHtml(candidate.currency_code || "")}` : "Not available";
    const origins = Array.isArray(candidate.origin_iatas) ? candidate.origin_iatas.map(escapeHtml).join(", ") : "Not available";
    const departure = candidate.departure_date ? escapeHtml(candidate.departure_date) : "Flexible";
    const fitScore = hasValue(candidate.ai_fit_score)
      ? `
        <div class="fit-score">
          <span>${escapeHtml(candidate.ai_fit_score)}</span>
          <small>/100 fit</small>
        </div>
      `
      : "";

    return `
      <li class="candidate-card">
        <div class="candidate-topline">
          <div>
            <h3>${title}</h3>
            ${candidateMeta(candidate)}
          </div>
          ${fitScore}
        </div>

        <dl class="candidate-facts">
          <div>
            <dt>Price</dt>
            <dd>${price}</dd>
          </div>
          <div>
            <dt>Origins</dt>
            <dd>${origins}</dd>
          </div>
          <div>
            <dt>Departure</dt>
            <dd>${departure}</dd>
          </div>
        </dl>

        ${candidate.source === "demo" ? '<p class="demo-badge">Demo data fallback</p>' : ""}
        ${candidate.ai_rationale ? `<p class="candidate-rationale">${escapeHtml(candidate.ai_rationale)}</p>` : ""}
      </li>
    `;
  });
  container.innerHTML = `<ul class="candidate-list">${cards.join("")}</ul>`;
}

document.querySelectorAll("[data-origin-picker]").forEach((form) => {
  const searchInput = form.querySelector("[data-origin-search]");
  const suggestions = form.querySelector("[data-origin-suggestions]");
  const selected = form.querySelector("[data-selected-origins]");
  if (!searchInput || !suggestions || !selected) {
    return;
  }

  selected.querySelectorAll("[data-remove-origin]").forEach((button) => {
    button.addEventListener("click", () => button.closest("[data-origin-chip]").remove());
  });

  let abortController = null;
  searchInput.addEventListener("input", async () => {
    const keyword = searchInput.value.trim();
    suggestions.innerHTML = "";
    if (keyword.length < 3) {
      return;
    }

    suggestions.innerHTML = '<span class="empty-inline">Searching locations...</span>';

    if (abortController) {
      abortController.abort();
    }
    abortController = new AbortController();

    try {
      const response = await fetch(`/api/locations/suggest?keyword=${encodeURIComponent(keyword)}&subTypes=AIRPORT,CITY`, {
        signal: abortController.signal,
      });
      const items = await response.json();
      suggestions.innerHTML = "";

      if (!items.length) {
        suggestions.innerHTML = '<span class="empty-inline">No matching airports or cities found.</span>';
        return;
      }

      items.forEach((item) => {
        const wrapper = document.createElement("div");
        wrapper.className = "suggestion";
        const label = `${item.iata} · ${item.name || item.city_name || "Unknown"} (${item.sub_type})`;
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label;
        button.addEventListener("click", () => {
          selected.appendChild(
            createOriginChip({
              iata: item.iata,
              sub_type: item.sub_type,
              provider_sky_id: item.provider_sky_id,
              provider_entity_id: item.provider_entity_id,
            }),
          );
          searchInput.value = "";
          suggestions.innerHTML = "";
        });
        wrapper.appendChild(button);
        suggestions.appendChild(wrapper);
      });
    } catch (error) {
      if (error.name !== "AbortError") {
        suggestions.innerHTML = '<span class="notice notice-error">Suggestions are temporarily unavailable.</span>';
      }
    }
  });
});

document.querySelectorAll("[data-preference-chat]").forEach((container) => {
  const thread = container.querySelector("[data-preference-thread]");
  const input = container.querySelector("[data-preference-input]");
  const send = container.querySelector("[data-preference-send]");
  const chips = container.querySelector("[data-preference-chips]");
  const summary = container.querySelector("[data-preference-summary]");
  const defaultSendText = send.textContent;

  chips.querySelectorAll("[data-remove-preference]").forEach((button) => {
    button.addEventListener("click", () => {
      button.closest("[data-preference-chip]").remove();
      updatePreferenceHiddenValue(container);
    });
  });
  updatePreferenceHiddenValue(container);

  send.addEventListener("click", async () => {
    const message = input.value.trim();
    if (!message) {
      input.focus();
      return;
    }

    appendChatBubble(thread, "user", message);
    input.value = "";
    send.disabled = true;
    send.textContent = "Generating...";

    try {
      const response = await fetch("/api/preferences/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [{ role: "user", content: message }],
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.message || "Preference chat failed.");
      }

      if (payload.assistant_message) {
        appendChatBubble(thread, "assistant", payload.assistant_message);
      }
      chips.innerHTML = "";
      clearInlineEmptyState(chips);
      (payload.preferences || []).forEach((preference) => {
        chips.appendChild(createPreferenceChip(preference.label));
      });
      summary.value = payload.preference_summary || "";
      updatePreferenceHiddenValue(container);
    } catch (error) {
      appendChatBubble(thread, "assistant", error.message || "The assistant is temporarily unavailable.");
    } finally {
      send.disabled = false;
      send.textContent = defaultSendText;
    }
  });
});

document.querySelectorAll("[data-enrich-button]").forEach((button) => {
  button.addEventListener("click", async () => {
    const searchId = button.dataset.searchId;
    const status = document.querySelector("[data-enrich-status]");
    const container = document.querySelector("[data-candidates-container]");
    const defaultButtonText = button.textContent;
    button.disabled = true;
    button.textContent = "Enriching...";
    status.textContent = "Running AI enrichment...";

    try {
      const response = await fetch(`/api/searches/${searchId}/enrich`, { method: "POST" });
      const payload = await response.json();
      status.textContent = payload.message || "AI enrichment finished.";
      renderCandidates(container, payload.candidates || []);
    } catch (error) {
      status.textContent = "AI enrichment could not be completed.";
    } finally {
      button.disabled = false;
      button.textContent = defaultButtonText;
    }
  });
});
