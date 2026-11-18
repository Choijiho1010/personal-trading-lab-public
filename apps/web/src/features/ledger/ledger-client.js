async function request(path) {
  const response = await fetch(path);
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

export function createLedgerClient() {
  return {
    async getLedger() {
      const [fillResult, positionResult, conflictResult] = await Promise.all([
        request('/api/v1/ledger/fills'),
        request('/api/v1/ledger/positions'),
        request('/api/v1/ledger/conflicts'),
      ]);
      return {
        fills: fillResult.fills,
        positions: positionResult.positions,
        conflicts: conflictResult.conflicts,
      };
    },
  };
}
