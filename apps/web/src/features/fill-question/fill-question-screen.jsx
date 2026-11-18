import { useCallback, useEffect, useRef, useState } from 'react';

const maxQuestionLength = 500;

function formatKoreanTime(value) {
  const dateTime = new Intl.DateTimeFormat('ko-KR', {
    dateStyle: 'long',
    timeStyle: 'medium',
    timeZone: 'Asia/Seoul',
  }).format(new Date(value));
  return `${dateTime} 한국 표준시 (KST)`;
}

function countCodePoints(value) {
  return Array.from(value).length;
}

function questionError(question) {
  if (!question.trim()) {
    return '질문을 입력해 주세요.';
  }
  if (countCodePoints(question) > maxQuestionLength) {
    return '질문은 500자 이하여야 합니다.';
  }
  return '';
}

function errorMessage(code) {
  if (code === 'RESEARCH_UNAVAILABLE') {
    return '답변 서비스를 지금 사용할 수 없습니다. 다시 질문해 주세요.';
  }
  if (code === 'FILL_NOT_FOUND') {
    return '체결을 찾을 수 없습니다. 체결 조회를 다시 시도해 주세요.';
  }
  return '질문을 처리하지 못했습니다. 다시 질문해 주세요.';
}

export function FillQuestionScreen({ client }) {
  const [fill, setFill] = useState(null);
  const [loadState, setLoadState] = useState('loading');
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [submitState, setSubmitState] = useState('idle');
  const [submitError, setSubmitError] = useState('');
  const [cited, setCited] = useState(false);
  const rowRef = useRef(null);

  const loadFill = useCallback(async () => {
    setLoadState('loading');
    try {
      setFill(await client.getFill());
      setLoadState('ready');
    } catch {
      setLoadState('error');
    }
  }, [client]);

  useEffect(() => {
    loadFill();
  }, [loadFill]);

  async function submit(event) {
    event.preventDefault();
    const validationError = questionError(question);
    if (validationError || submitState === 'submitting') {
      return;
    }
    setSubmitState('submitting');
    setSubmitError('');
    setAnswer(null);
    setCited(false);
    try {
      setAnswer(await client.askQuestion(question));
      setSubmitState('idle');
    } catch (error) {
      setSubmitError(errorMessage(error.code));
      setSubmitState('idle');
    }
  }

  function showEvidence() {
    setCited(true);
    rowRef.current?.focus();
  }

  const validationError = questionError(question);

  return (
    <section aria-labelledby="page-title">
        <p className="eyebrow">Personal Trading Lab</p>
        <h1 id="page-title">체결을 확인하고 질문하기</h1>
        {loadState === 'loading' && <p role="status">체결 내역을 불러오는 중입니다.</p>}
        {loadState === 'error' && (
          <div role="alert">
            <p>체결 조회 오류가 발생했습니다.</p>
            <button type="button" onClick={loadFill}>다시 불러오기</button>
          </div>
        )}
        {fill && (
          <section aria-labelledby="fill-heading">
            <div className="section-heading">
              <h2 id="fill-heading">체결 내역</h2>
              {fill.synthetic && <span className="badge">합성 데이터</span>}
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>체결 ID</th><th>종목</th><th>방향</th><th>수량</th><th>가격</th><th>체결 시각</th></tr>
                </thead>
                <tbody>
                  <tr ref={rowRef} tabIndex="-1" className={cited ? 'is-cited' : ''}>
                    <td>{fill.fill_id}</td><td>{fill.symbol}</td><td>{fill.side === 'BUY' ? '매수' : fill.side}</td><td>{fill.quantity}주</td><td>{fill.price_krw.toLocaleString('ko-KR')}원</td><td>{formatKoreanTime(fill.filled_at)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        )}
        <section aria-labelledby="question-heading" className="question-section">
          <h2 id="question-heading">거래에 질문하기</h2>
          <form onSubmit={submit}>
            <label htmlFor="question">질문</label>
            <textarea id="question" value={question} onChange={(event) => setQuestion(event.target.value)} disabled={loadState !== 'ready' || submitState === 'submitting'} />
            {question && validationError && <p role="alert">{validationError}</p>}
            <button type="submit" disabled={loadState !== 'ready' || submitState === 'submitting' || Boolean(validationError)}>{submitState === 'submitting' ? '답변을 기다리는 중입니다.' : '질문하기'}</button>
          </form>
          {answer && (
            <section aria-label="답변" className="answer">
              <h3>답변</h3>
              <p>{answer.answer}</p>
              <button type="button" onClick={showEvidence}>근거 보기</button>
            </section>
          )}
          {submitError && <p role="alert">{submitError}</p>}
        </section>
    </section>
  );
}
