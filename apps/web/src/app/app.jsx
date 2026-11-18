import { useState } from 'react';
import { FillQuestionScreen } from '../features/fill-question/fill-question-screen.jsx';
import { createTradingClient } from '../features/fill-question/trading-client.js';
import { createLedgerClient } from '../features/ledger/ledger-client.js';
import { LedgerScreen } from '../features/ledger/ledger-screen.jsx';

const client = createTradingClient();
const ledgerClient = createLedgerClient();

export function App() {
  const [screen, setScreen] = useState('question');

  return (
    <main className="page-shell">
      <nav aria-label="Personal Trading Lab 화면" className="app-nav">
        <button type="button" className={screen === 'question' ? 'is-current' : ''} onClick={() => setScreen('question')}>체결에 질문하기</button>
        <button type="button" className={screen === 'ledger' ? 'is-current' : ''} onClick={() => setScreen('ledger')}>합성 원장</button>
      </nav>
      <section className="panel">
        {screen === 'question' ? <FillQuestionScreen client={client} /> : <LedgerScreen client={ledgerClient} />}
      </section>
    </main>
  );
}
