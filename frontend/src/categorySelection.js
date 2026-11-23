export function toggleCategories(current, key) {
  if (key === "all") return "all";
  const selected = new Set(current === "all" ? [] : current.split(","));
  if (selected.has(key)) selected.delete(key); else selected.add(key);
  return selected.size ? [...selected].sort().join(",") : "all";
}
