const fillId = 'demo-fill-1';

async function request(path, options) {
  const response = await fetch(path, options);
  if (response.ok) {
    return response.json();
  }

  let body = {};
  try {
    body = await response.json();
  } catch {
    body = {};
  }
  throw { code: body.code, status: response.status };
}

export function createTradingClient() {
  return {
    getFill() {
      return request(`/api/v1/fills/${fillId}`);
    },
    askQuestion(question) {
      return request(`/api/v1/fills/${fillId}/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });
    },
  };
}
