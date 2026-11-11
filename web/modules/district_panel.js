function normalizeName(value) {
  return String(value || "")
    .toLocaleUpperCase("tr-TR")
    .replaceAll("İ", "I")
    .replaceAll("Ş", "S")
    .replaceAll("Ğ", "G")
    .replaceAll("Ü", "U")
    .replaceAll("Ö", "O")
    .replaceAll("Ç", "C")
    .replace(/[^A-Z0-9]/g, "");
}

const SPLIT_PROVINCES = new Set(["ISTANBUL", "ANKARA", "IZMIR", "BURSA"]);

export function renderDistrictPanel(container, districts, result, parties) {
  if (!container) return;
  const partyById = new Map(parties.map((party) => [party.id, party]));
  const cards = districts
    .filter((district) => SPLIT_PROVINCES.has(normalizeName(district.province_base)))
    .map((district) => {
      const allocation = result.seatsByDistrict[district.id] || {};
      const ordered = Object.entries(allocation)
        .filter(([, seats]) => seats > 0)
        .sort((a, b) => b[1] - a[1]);
      const squares = [];
      const summary = [];
      for (const [id, seats] of ordered) {
        const party = partyById.get(id);
        for (let i = 0; i < seats; i += 1) {
          squares.push(
            `<span class="district-seat" style="background:${party?.color ?? "#9e9e9e"}" title="${party?.name ?? id}"></span>`
          );
        }
        summary.push(`${party?.short ?? id} ${seats}`);
      }
      return `
        <article class="district-card">
          <div class="district-card-head">
            <h3>${district.province}</h3>
            <span>${district.seats} mv</span>
          </div>
          <div class="district-seats">${squares.join("")}</div>
          <p>${summary.join(" · ")}</p>
        </article>`;
    });
  container.innerHTML = cards.join("");
}
