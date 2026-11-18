const replayPath = '/api/v1/ledger/replay';

async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw { code: body?.code };
  }
  return response.json();
}

export function createReplayClient() {
  return {
    getLedger(scope, signal) {
      return request(`${replayPath}?${new URLSearchParams(scope)}`, { signal });
    },
    askQuestion(scope, question) {
      return request(`${replayPath}/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...scope, question }),
      });
    },
  };
}
