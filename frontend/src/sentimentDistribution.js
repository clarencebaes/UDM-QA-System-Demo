// Use mutually exclusive saved categories so Constructive is not counted twice.
export function sentimentDistribution(data={}) {
  const source=data?.sentiment||data||{};
  return Object.fromEntries(["positive","constructive","negative","neutral","unclassified"].map(key=>[key,Number((key==="unclassified" ? source.unclassified_comments??source.unclassified : source[key])||0)]));
}
