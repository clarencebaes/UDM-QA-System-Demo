export function participationSummary(respondents, enrolled) {
  const responses = Math.max(0, Number(respondents) || 0);
  const expected = Math.max(0, Number(enrolled) || 0);
  return {
    remaining: Math.max(0, expected - responses),
    denominator: expected,
    valid: expected > 0 && responses <= expected,
  };
}
