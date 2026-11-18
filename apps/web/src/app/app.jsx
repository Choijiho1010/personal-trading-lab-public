import { useState } from 'react';
import { FillQuestionScreen } from '../features/fill-question/fill-question-screen.jsx';
import { createTradingClient } from '../features/fill-question/trading-client.js';
import { createLedgerClient } from '../features/ledger/ledger-client.js';
import { LedgerScreen } from '../features/ledger/ledger-screen.jsx';
import { createReplayClient } from '../features/trade-replay/replay-client.js';
import { TradeReplay } from '../features/trade-replay/trade-replay.jsx';

const client = createTradingClient();
const ledgerClient = createLedgerClient();
const replayClient = createReplayClient();
const screens = [
  ['replay-ledger', '거래 원장'],
  ['replay-question', '거래 질문'],
  ['question', '체결에 질문하기'],
  ['ledger', '합성 원장'],
];

export function App() {
  const [screen, setScreen] = useState('replay-ledger');
  const inReplay = screen === 'replay-ledger' || screen === 'replay-question';

  return (
    <main className="page-shell">
      <nav aria-label="Personal Trading Lab 화면" className="app-nav">
        {screens.map(([id, label]) => (
          <button
            key={id}
            type="button"
            aria-current={screen === id ? 'page' : undefined}
            className={screen === id ? 'is-current' : ''}
            onClick={() => setScreen(id)}
          >
            {label}
          </button>
        ))}
      </nav>
      <section className="panel">
        {inReplay && (
          <TradeReplay
            client={replayClient}
            showQuestions={screen === 'replay-question'}
            onShowLedger={() => setScreen('replay-ledger')}
          />
        )}
        {screen === 'question' && <FillQuestionScreen client={client} />}
        {screen === 'ledger' && <LedgerScreen client={ledgerClient} />}
      </section>
    </main>
  );
}
