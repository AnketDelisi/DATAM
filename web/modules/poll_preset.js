import { aggregateAt, medianSample } from "./aggregate.js";

export const MAIN_PARTIES = ["P9", "P21", "P11", "P22", "P12", "P10", "P13", "P24"];
const OTHER = "OTHER";
const OPTIONS = {
  halfLifeDays: 28,
  normalize: true,
  houseEffects: false,
};

export function addOther(poll) {
  const other = Object.entries(poll.results)
    .filter(([id, value]) => !MAIN_PARTIES.includes(id) && typeof value === "number")
    .reduce((sum, [, value]) => sum + value, 0);
  return { ...poll, results: { ...poll.results, [OTHER]: other } };
}

export function parliamentActual(data) {
  const shares = data.national.shares;
  const other = Object.entries(shares)
    .filter(([id]) => !MAIN_PARTIES.includes(id))
    .reduce((sum, [, value]) => sum + value, 0);
  const actual = {};
  for (const id of MAIN_PARTIES) actual[id] = shares[id] || 0;
  actual[OTHER] = other;
  return actual;
}

export function presidentAggregate(pollPayload, round = 1) {
  const polls = pollPayload.datasets.president.polls.filter(
    (poll) => poll.round === round
  );
  const entities = round === 1 ? ["A", "B", "C", "D"] : ["A", "B"];
  const cutoff = round === 1 ? "2023-05-14" : "2023-05-28";
  const result = aggregateAt(polls, entities, cutoff, {
    ...OPTIONS,
    defaultSample: medianSample(polls),
  });
  return result.shares;
}

export function parliamentAggregate(pollPayload) {
  const polls = pollPayload.datasets.parliament.polls.map(addOther);
  const entities = [...MAIN_PARTIES, OTHER];
  const result = aggregateAt(polls, entities, "2023-05-14", {
    ...OPTIONS,
    defaultSample: medianSample(polls),
  });
  return result.shares;
}
