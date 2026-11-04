export function dhondt(votes, seats, eligible) {
  const alloc = {};
  const parties = [...eligible];
  for (const party of parties) alloc[party] = 0;
  if (seats <= 0 || parties.length === 0) return alloc;

  for (let seat = 0; seat < seats; seat += 1) {
    let winner = null;
    let best = -Infinity;
    for (const party of parties) {
      const score = (votes[party] || 0) / (alloc[party] + 1);
      if (score > best || (score === best && (winner === null || party > winner))) {
        best = score;
        winner = party;
      }
    }
    if (winner === null) break;
    alloc[winner] += 1;
  }
  return alloc;
}

export function qualifyingParties(nationalVotes, alliances, threshold) {
  const total = Object.values(nationalVotes).reduce((sum, n) => sum + n, 0);
  if (!total) return new Set();

  const allianceShare = {};
  for (const [name, members] of Object.entries(alliances || {})) {
    const votes = members.reduce((sum, party) => sum + (nationalVotes[party] || 0), 0);
    allianceShare[name] = votes / total;
  }

  const qualified = new Set();
  for (const [party, votes] of Object.entries(nationalVotes)) {
    if (party.startsWith("I")) continue;
    if (votes / total >= threshold) {
      qualified.add(party);
      continue;
    }
    for (const [name, members] of Object.entries(alliances || {})) {
      if (members.includes(party) && allianceShare[name] >= threshold) {
        qualified.add(party);
        break;
      }
    }
  }
  return qualified;
}

export function sumVotes(units) {
  const national = {};
  for (const unit of units) {
    for (const [party, votes] of Object.entries(unit.votes)) {
      national[party] = (national[party] || 0) + votes;
    }
  }
  return national;
}

export function allocateDistricts(districts, alliances, threshold) {
  const national = sumVotes(districts);
  const qualified = qualifyingParties(national, alliances, threshold);
  const seatsByParty = {};
  const seatsByDistrict = {};
  const seatsByProvince = {};

  for (const district of districts) {
    const eligible = new Set(qualified);
    for (const [party, votes] of Object.entries(district.votes)) {
      if (party.startsWith("I") && votes > 0) eligible.add(party);
    }
    if (eligible.size === 0) {
      for (const [party, votes] of Object.entries(district.votes)) {
        if (votes > 0) eligible.add(party);
      }
    }
    const result = dhondt(district.votes, district.seats, eligible);
    seatsByDistrict[district.id] = result;
    const province = district.province_base;
    seatsByProvince[province] = seatsByProvince[province] || {};
    for (const [party, seats] of Object.entries(result)) {
      seatsByParty[party] = (seatsByParty[party] || 0) + seats;
      seatsByProvince[province][party] =
        (seatsByProvince[province][party] || 0) + seats;
    }
  }

  return { seatsByParty, seatsByDistrict, seatsByProvince, national, qualified };
}
