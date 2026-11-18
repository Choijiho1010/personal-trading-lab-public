import { useEffect, useState } from 'react';

import { ReplayLedgerScreen } from './replay-ledger-screen.jsx';
import { ReplayQuestionScreen } from './replay-question-screen.jsx';

const initialScope = { symbol: 'SAMPLE', from_date: '2026-11-12', as_of: '2026-11-13' };

export function TradeReplay({ client, showQuestions, onShowLedger }) {
  const [scope, setScope] = useState(initialScope);
  const [draft, setDraft] = useState(initialScope);
  const [ledger, setLedger] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [scopeError, setScopeError] = useState('');
  const [citation, setCitation] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    async function load() {
      try {
        const result = await client.getLedger(scope, signal);
        if (!signal.aborted) setLedger(result);
      } catch (error) {
        if (!signal.aborted) {
          setLoadError(error.code === 'INVALID_REQUEST'
            ? '종목과 조회 기간을 확인해 주세요.'
            : '원장을 불러오지 못했습니다. 다시 조회해 주세요.');
        }
      }
    }

    load();
    return () => controller.abort();
  }, [client, scope]);

  function selectScope(event) {
    event.preventDefault();
    const symbol = draft.symbol.trim().toUpperCase();
    if (!/^[A-Z0-9][A-Z0-9.-]{0,19}$/.test(symbol)) {
      setScopeError('종목 코드는 영문자나 숫자로 시작하고, 점과 하이픈을 포함해 20자 이내로 입력해 주세요.');
      return;
    }
    if (draft.from_date > draft.as_of) {
      setScopeError('조회 시작일은 기준일과 같거나 그보다 앞서야 합니다.');
      return;
    }

    const nextScope = { ...draft, symbol };
    setDraft(nextScope);
    setScope(nextScope);
    setLedger(null);
    setCitation(null);
    setScopeError('');
    setLoadError('');
  }

  function showCitation(item) {
    setCitation(item);
    onShowLedger();
  }

  return (
    <>
      {!showQuestions && (
        <ReplayLedgerScreen
          scope={scope}
          draft={draft}
          onChange={(name, value) => {
            setDraft((previous) => ({ ...previous, [name]: value }));
            setScopeError('');
          }}
          onLoad={selectScope}
          ledger={ledger}
          error={scopeError || loadError}
          citation={citation}
        />
      )}
      <ReplayQuestionScreen
        key={JSON.stringify(scope)}
        client={client}
        scope={scope}
        active={showQuestions}
        onCite={showCitation}
      />
    </>
  );
}
