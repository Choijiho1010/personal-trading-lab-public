import { useEffect, useRef } from 'react';

import { formatKoreanTime, formatPrice, formatQuantity, formatSide } from './trade-format.js';

export function FillsTable({ fills, citation }) {
  const citedRow = useRef(null);

  useEffect(() => {
    citedRow.current?.focus();
  }, [citation, fills]);

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr><th>출처</th><th>체결 ID</th><th>종목</th><th>방향</th><th>수량</th><th>가격</th><th>체결 시각 (KST)</th></tr>
        </thead>
        <tbody>
          {fills.map((fill) => {
            const isCited = citation?.source === fill.source && citation.reference_id === fill.fill_id;
            return (
              <tr
                key={JSON.stringify([fill.source, fill.fill_id])}
                className={isCited ? 'is-cited' : undefined}
                ref={isCited ? citedRow : undefined}
                tabIndex={isCited ? -1 : undefined}
              >
                <td>{fill.source}</td>
                <td>{fill.fill_id}</td>
                <td>{fill.symbol}</td>
                <td>{formatSide(fill.side)}</td>
                <td>{formatQuantity(fill.quantity)}</td>
                <td>{formatPrice(fill.price_krw)}</td>
                <td><time dateTime={fill.filled_at}>{formatKoreanTime(fill.filled_at)}</time></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
