import { useCallback, useEffect, useState } from 'react';

import { FillsTable } from '../../shared/fills-table.jsx';
import { formatPrice, formatQuantity, formatSide } from '../../shared/trade-format.js';

function unavailableMessage(code) {
  if (code === 'LEDGER_UNAVAILABLE') {
    return '원장을 지금 사용할 수 없습니다. 잠시 후 다시 불러와 주세요.';
  }
  return '원장을 불러오지 못했습니다. 다시 불러와 주세요.';
}

const conflictFields = [
  { field: 'symbol', label: '종목', format: String },
  { field: 'side', label: '방향', format: formatSide },
  { field: 'quantity', label: '수량', format: formatQuantity },
  { field: 'price_krw', label: '가격', format: formatPrice },
  { field: 'filled_at', label: '체결 시각 (UTC)', format: String },
];

export function LedgerScreen({ client }) {
  const [ledger, setLedger] = useState({ fills: [], positions: [], conflicts: [] });
  const [state, setState] = useState('loading');
  const [error, setError] = useState('');

  const loadLedger = useCallback(async () => {
    setState('loading');
    setError('');
    try {
      setLedger(await client.getLedger());
      setState('ready');
    } catch (loadError) {
      setError(unavailableMessage(loadError.code));
      setState('error');
    }
  }, [client]);

  useEffect(() => {
    loadLedger();
  }, [loadLedger]);

  return (
    <section aria-labelledby="ledger-title" className="ledger-content">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Personal Trading Lab</p>
          <h1 id="ledger-title">합성 원장</h1>
        </div>
        <span className="badge">합성 데이터</span>
      </div>
      <p className="ledger-intro">체결은 원장에 한 번만 반영합니다. 같은 식별자에 다른 내용이 들어오면 기존 기록과 잔고를 유지하고 확인 대상으로 남깁니다.</p>
      {state === 'loading' && <p role="status">원장을 불러오는 중입니다.</p>}
      {state === 'error' && (
        <div role="alert" className="ledger-error">
          <p>{error}</p>
          <button type="button" onClick={loadLedger}>다시 불러오기</button>
        </div>
      )}
      {state === 'ready' && (
        <div className="ledger-sections">
          <section aria-labelledby="ledger-fill-heading">
            <h2 id="ledger-fill-heading">체결 내역</h2>
            {ledger.fills.length === 0
              ? <p>기록된 체결이 없습니다.</p>
              : <FillsTable fills={ledger.fills} />}
          </section>
          <section aria-labelledby="ledger-position-heading">
            <h2 id="ledger-position-heading">보유 수량</h2>
            {ledger.positions.length === 0 ? <p>계산할 보유 수량이 없습니다.</p> : (
              <ul className="position-list">
                {ledger.positions.map((position) => <li key={position.symbol}><span>{position.symbol}</span><strong>{formatQuantity(position.quantity)}</strong></li>)}
              </ul>
            )}
          </section>
          <section aria-labelledby="ledger-conflict-heading">
            <h2 id="ledger-conflict-heading">확인 필요</h2>
            {ledger.conflicts.length === 0 ? <p>확인할 상충 기록이 없습니다.</p> : (
              <div className="conflict-list">
                <p>기존 체결과 잔고는 유지했습니다.</p>
                {ledger.conflicts.map((conflict) => {
                  const changes = conflictFields.map(({ field, label, format }) => ({
                    field,
                    label,
                    format,
                    previous: conflict[`existing_${field}`],
                    received: conflict[`received_${field}`],
                  })).filter(({ previous, received }) => previous !== received);
                  const key = JSON.stringify([
                    conflict.source,
                    conflict.fill_id,
                    ...conflictFields.map(({ field }) => conflict[`received_${field}`]),
                  ]);
                  return (
                    <article key={key} className="conflict-card">
                      <h3>{conflict.fill_id}</h3>
                      <p>{conflict.source}에서 같은 체결 ID로 원장과 다른 내용을 보냈습니다.</p>
                      {changes.length > 0 ? (
                        <dl>
                          {changes.map(({ field, label, format, previous, received }) => (
                            <div key={field}>
                              <dt>{label}</dt>
                              <dd>{`${format(previous)} → ${format(received)}`}</dd>
                            </div>
                          ))}
                        </dl>
                      ) : <p>비교할 변경 항목이 없습니다.</p>}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}
    </section>
  );
}
