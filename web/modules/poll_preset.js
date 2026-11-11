import { aggregateAt, medianSample } from "./aggregate.js";

export const MAIN_PARTIES = ["P9", "P21", "P11", "P22", "P12", "P10", "P13", "P24", "P8"];
export const MAIN_PARTIES_2028 = [...MAIN_PARTIES, "YENI", "A"];
const OTHER = "OTHER";
const OPTIONS = {
  halfLifeDays: 28,
  normalize: true,
};

export function addOther(poll, mainParties = MAIN_PARTIES) {
  const other = Object.entries(poll.results)
    .filter(([id, value]) => !mainParties.includes(id) && typeof value === "number")
    .reduce((sum, [, value]) => sum + value, 0);
  return { ...poll, results: { ...poll.results, [OTHER]: other } };
}

export function parliamentActual(data, mainParties = MAIN_PARTIES) {
  const shares = data.national.shares;
  const other = Object.entries(shares)
    .filter(([id]) => !mainParties.includes(id))
    .reduce((sum, [, value]) => sum + value, 0);
  const actual = {};
  for (const id of mainParties) actual[id] = shares[id] || 0;
  actual[OTHER] = other;
  return actual;
}

export function presidentAggregate(
  pollPayload,
  round = 1,
  cutoff = "2023-05-14",
  entities = round === 1 ? ["A", "B", "C", "D"] : ["A", "B"]
) {
  const polls = pollPayload.datasets.president.polls.filter(
    (poll) => poll.round === round
  );
  const result = aggregateAt(polls, entities, cutoff, {
    ...OPTIONS,
    defaultSample: medianSample(polls),
  });
  return result.shares;
}

export function parliamentAggregate(pollPayload, cutoff = "2023-05-14", mainParties = MAIN_PARTIES) {
  const polls = pollPayload.datasets.parliament.polls.map((poll) => addOther(poll, mainParties));
  const entities = [...mainParties, OTHER];
  const result = aggregateAt(polls, entities, cutoff, {
    ...OPTIONS,
    defaultSample: medianSample(polls),
  });
  return result.shares;
}
