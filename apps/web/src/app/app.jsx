import { FillQuestionScreen } from '../features/fill-question/fill-question-screen.jsx';
import { createTradingClient } from '../features/fill-question/trading-client.js';

const client = createTradingClient();

export function App() {
  return <FillQuestionScreen client={client} />;
}
