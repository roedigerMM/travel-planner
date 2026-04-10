function createOriginChip(origin) {
  const chip = document.createElement("div");
  chip.className = "chip";
  chip.dataset.originChip = "true";
  const providerSkyId = origin.provider_sky_id || "";
  const providerEntityId = origin.provider_entity_id || "";
  chip.innerHTML = `
    <span>${origin.iata} · ${origin.sub_type}</span>
    <button type="button" data-remove-origin aria-label="Remove ${origin.iata}">&times;</button>
    <input type="hidden" name="origin_iata" value="${origin.iata}" />
    <input type="hidden" name="origin_sub_type" value="${origin.sub_type}" />
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
  chip.innerHTML = `
    <span>${label}</span>
    <button type="button" data-remove-preference aria-label="Remove ${label}">&times;</button>
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
  const labels = Array.from(container.querySelectorAll("[data-preference-chip] span")).map((el) => el.textContent.trim());
  hidden.value = labels.join(", ");
}

function appendChatBubble(thread, role, content) {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role === "assistant" ? "chat-bubble-assistant" : "chat-bubble-user"}`;
  bubble.textContent = content;
  thread.appendChild(bubble);
  thread.scrollTop = thread.scrollHeight;
}

function renderCandidates(container, candidates) {
  if (!candidates || candidates.length === 0) {
    container.innerHTML = "<p>No candidates were stored for this search.</p>";
    return;
  }

  const cards = candidates.map((candidate) => `
    <li class="candidate-card">
      <strong>${candidate.destination_iata}</strong>
      ${candidate.price !== null ? `<span> — ${candidate.price.toFixed(2)} ${candidate.currency_code || ""}</span>` : ""}
      ${candidate.source === "demo" ? "<p><em>Demo data fallback</em></p>" : ""}
      <p>Origins: ${candidate.origin_iatas.join(", ")}</p>
      ${candidate.departure_date ? `<p>Departure: ${candidate.departure_date}</p>` : ""}
      ${candidate.ai_fit_score !== null ? `<p><strong>Fit:</strong> ${candidate.ai_fit_score}/100</p>` : ""}
      ${candidate.ai_rationale ? `<p>${candidate.ai_rationale}</p>` : ""}
    </li>
  `);
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

    if (abortController) {
      abortController.abort();
    }
    abortController = new AbortController();

    try {
      const response = await fetch(`/api/locations/suggest?keyword=${encodeURIComponent(keyword)}&subTypes=AIRPORT,CITY`, {
        signal: abortController.signal,
      });
      const items = await response.json();
      items.forEach((item) => {
        const wrapper = document.createElement("div");
        wrapper.className = "suggestion";
        wrapper.innerHTML = `<button type="button">${item.iata} · ${item.name || item.city_name || "Unknown"} (${item.sub_type})</button>`;
        wrapper.querySelector("button").addEventListener("click", () => {
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
        suggestions.appendChild(wrapper);
      });
    } catch (error) {
      if (error.name !== "AbortError") {
        suggestions.innerHTML = "<span class=\"notice notice-error\">Suggestions are temporarily unavailable.</span>";
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
      return;
    }

    appendChatBubble(thread, "user", message);
    input.value = "";
    send.disabled = true;

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
      (payload.preferences || []).forEach((preference) => {
        chips.appendChild(createPreferenceChip(preference.label));
      });
      summary.value = payload.preference_summary || "";
      updatePreferenceHiddenValue(container);
    } catch (error) {
      appendChatBubble(thread, "assistant", error.message || "The assistant is temporarily unavailable.");
    } finally {
      send.disabled = false;
    }
  });
});

document.querySelectorAll("[data-enrich-button]").forEach((button) => {
  button.addEventListener("click", async () => {
    const searchId = button.dataset.searchId;
    const status = document.querySelector("[data-enrich-status]");
    const container = document.querySelector("[data-candidates-container]");
    button.disabled = true;
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
    }
  });
});
