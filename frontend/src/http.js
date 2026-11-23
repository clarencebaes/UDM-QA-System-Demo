// Let the browser wait for slow responses without an application deadline.
// Never retry writes automatically because they may already be saved.
export async function fetchText(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  return { response, text };
}
