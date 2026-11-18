import { FillsTable } from '../../shared/fills-table.jsx';
import { formatQuantity } from '../../shared/trade-format.js';

const scopeFields = [
  { name: 'symbol', label: '종목', type: 'text' },
  { name: 'from_date', label: '조회 시작일', type: 'date' },
  { name: 'as_of', label: '기준일', type: 'date' },
];

export function ReplayLedgerScreen({ scope, draft, onChange, onLoad, ledger, error, citation }) {
  const { fills, position_quantity: quantity } = ledger ?? {};
  const missingCitation = citation && fills &&
    !fills.some((fill) => fill.source === citation.source && fill.fill_id === citation.reference_id);

  return (
    <section aria-labelledby="replay-ledger-title">
      <div className="section-heading">
        <h1 id="replay-ledger-title">거래 원장</h1>
        <span className="badge">합성 데이터</span>
      </div>
      <form className="replay-filters" onSubmit={onLoad}>
        {scopeFields.map(({ name, label, type }) => (
          <label key={name}>
            {label}
            <input
              type={type}
              name={name}
              value={draft[name]}
              onChange={(event) => onChange(name, event.target.value)}
              required
            />
          </label>
        ))}
        <button type="submit">원장 조회</button>
      </form>
      {error && <p role="alert">{error}</p>}
      {!ledger && !error && <p role="status">원장을 불러오는 중입니다.</p>}
      {ledger && (
        <div className="ledger-sections">
          <section aria-labelledby="replay-position-heading">
            <h2 id="replay-position-heading">기준일 보유 수량</h2>
            <p className="replay-period">{scope.symbol} · {scope.from_date} ~ {scope.as_of} (KST)</p>
            <strong className="replay-quantity">{formatQuantity(quantity)}</strong>
          </section>
          <section aria-labelledby="replay-fills-heading">
            <h2 id="replay-fills-heading">기간 내 체결</h2>
            {missingCitation && <p role="status">원장에서 인용된 체결을 찾지 못했습니다.</p>}
            {fills.length > 0
              ? <FillsTable fills={fills} citation={citation} />
              : <p>선택한 기간에 체결이 없습니다.</p>}
          </section>
        </div>
      )}
    </section>
  );
}
