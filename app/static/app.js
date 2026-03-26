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
