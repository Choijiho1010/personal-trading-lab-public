import { useState } from 'react';

import { formatKoreanTime } from '../../shared/trade-format.js';

function Disclosure({ item }) {
  return (
    <details>
      <summary>{item.title}</summary>
      <dl className="replay-metadata">
        <div><dt>출처</dt><dd>{item.source}</dd></div>
        <div>
          <dt>발생 시각 (KST)</dt>
          <dd><time dateTime={item.occurred_at}>{formatKoreanTime(item.occurred_at)}</time></dd>
        </div>
        <div>
          <dt>수집 시각 (KST)</dt>
          <dd><time dateTime={item.collected_at}>{formatKoreanTime(item.collected_at)}</time></dd>
        </div>
      </dl>
    </details>
  );
}

export function ReplayQuestionScreen({ client, scope, active, onCite }) {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  async function submit(event) {
    event.preventDefault();
    const text = question.trim();
    if (!text || pending) return;
    setResult(null);
    setError('');
    if ([...text].length > 500) {
      setError('질문을 500자 이내로 입력해 주세요.');
      return;
    }

    setPending(true);
    try {
      setResult(await client.askQuestion(scope, text));
    } catch (failure) {
      setError(failure.code === 'INVALID_REQUEST'
        ? '질문의 내용을 확인해 주세요.'
        : '답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');
    } finally {
      setPending(false);
    }
  }

  return (
    <section hidden={!active} aria-labelledby="replay-question-title">
      <div className="section-heading">
        <h1 id="replay-question-title">거래 질문</h1>
        <span className="badge">합성 데이터</span>
      </div>
      <dl className="replay-metadata replay-scope">
        <div><dt>종목</dt><dd>{scope.symbol}</dd></div>
        <div><dt>조회 시작일 (KST)</dt><dd>{scope.from_date}</dd></div>
        <div><dt>기준일 (KST)</dt><dd>{scope.as_of}</dd></div>
      </dl>
      <form className="question-section" onSubmit={submit}>
        <label htmlFor="replay-question">질문</label>
        <textarea id="replay-question" value={question} onChange={(event) => setQuestion(event.target.value)} disabled={pending} />
        <button type="submit" disabled={pending || !question.trim()}>질문 보내기</button>
      </form>
      {pending && <p role="status">답변을 불러오는 중입니다.</p>}
      {error && <p role="alert">{error}</p>}
      {result?.status === 'insufficient_evidence' && (
        <p role="status">{scope.symbol}의 {scope.from_date} ~ {scope.as_of} 기간에서 질문에 답할 근거를 찾지 못했습니다.</p>
      )}
      {result?.status === 'answered' && (
        <section className="answer" aria-labelledby="replay-answer-heading">
          <h2 id="replay-answer-heading">답변</h2>
          <p role="status" className="replay-answer-text">{result.answer}</p>
          <h3>인용 근거</h3>
          <ul className="replay-evidence">
            {result.evidence.map((item) => (
              <li key={item.id}>
                {item.kind === 'fill' ? (
                  <button type="button" onClick={() => onCite(item)}>
                    {item.source} · {item.reference_id} 체결 보기
                  </button>
                ) : <Disclosure item={item} />}
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}
