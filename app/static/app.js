function createOriginChip(origin) {
  const chip = document.createElement("div");
  chip.className = "chip";
  chip.dataset.originChip = "true";
  chip.innerHTML = `
    <span>${origin.iata} · ${origin.sub_type}</span>
    <button type="button" data-remove-origin aria-label="Remove ${origin.iata}">&times;</button>
    <input type="hidden" name="origin_iata" value="${origin.iata}" />
    <input type="hidden" name="origin_sub_type" value="${origin.sub_type}" />
  `;
  chip.querySelector("[data-remove-origin]").addEventListener("click", () => chip.remove());
  return chip;
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
          selected.appendChild(createOriginChip({ iata: item.iata, sub_type: item.sub_type }));
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
