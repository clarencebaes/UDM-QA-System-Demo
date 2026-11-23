// Cache only public survey metadata, never a student's identity or answers.
export function createEvaluationConfigCache(fetchConfig, { now = Date.now, ttlMs = 60_000 } = {}) {
  let cached = null;
  let expires = 0;
  let pending = null;
  let generation=0;
  return {
    clear(){generation++;cached=null;expires=0;pending=null;},
    load(force = false) {
      if (pending) return pending;
      if (!force && cached && now() < expires) return Promise.resolve(cached);
      const current=generation;
      const operation = Promise.resolve().then(fetchConfig).then(data => {
        if (!Array.isArray(data?.departments) || !Array.isArray(data?.colleges)) throw new Error("Evaluation options are unavailable. Please retry.");
        if(current===generation){cached = data;expires = now() + ttlMs;}
        return data;
      }).finally(() => { if(pending===operation)pending = null; });
      pending=operation;
      return pending;
    },
  };
}
