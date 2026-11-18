import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import disclosureFixture from '../../../../contracts/synthetic-disclosures.fixture.json';
import ledgerFixture from '../../../../contracts/synthetic-ledger.fixture.json';
import replayFixture from '../../../../contracts/synthetic-replay.fixture.json';

import { App } from './app.jsx';

const { scope, question, expected } = replayFixture;
const fills = expected.fill_ids.map((id) => ledgerFixture.fills.find((fill) => fill.fill_id === id));
const [firstFill] = fills;
const [disclosure] = disclosureFixture.disclosures;
const replayPath = '/api/v1/ledger/replay';
const questionPath = `${replayPath}/questions`;
const answer = {
  status: 'answered',
  answer: '합성 거래에서 6주를 매수하고 1주를 매도했습니다.',
  evidence: [
    {
      id: expected.evidence_ids[0],
      kind: 'fill',
      source: firstFill.source,
      reference_id: firstFill.fill_id,
      occurred_at: firstFill.filled_at,
      collected_at: firstFill.collected_at,
    },
    {
      id: expected.evidence_ids[3],
      kind: 'disclosure',
      source: disclosure.source,
      reference_id: disclosure.evidence_id,
      title: disclosure.title,
      occurred_at: disclosure.occurred_at,
      collected_at: disclosure.collected_at,
    },
  ],
};

function response(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });
}

function matchesScope(actual, expectedFields) {
  return Object.keys(actual).length === Object.keys(expectedFields).length &&
    Object.entries(expectedFields).every(([key, value]) => actual[key] === value);
}

function mockReplay({
  selectedScope = scope,
  replayFills = fills,
  position = expected.position_quantity,
  replies = [answer],
} = {}) {
  const pendingReplies = [...replies];
  const fetchMock = vi.fn(async (path, options) => {
    const url = new URL(path, 'http://localhost');
    if (url.pathname === replayPath && matchesScope(Object.fromEntries(url.searchParams), selectedScope)) {
      return response({ ...selectedScope, fills: replayFills, position_quantity: position });
    }
    if (url.pathname === replayPath && matchesScope(Object.fromEntries(url.searchParams), scope)) {
      return response({ ...scope, fills, position_quantity: expected.position_quantity });
    }
    if (path === questionPath && options?.method === 'POST' &&
      matchesScope(JSON.parse(options.body), { ...selectedScope, question })) {
      const reply = pendingReplies.shift();
      if (reply === null) {
        return response({ code: 'RESEARCH_UNAVAILABLE' }, 503, {
          'X-Request-ID': '741c1f16-a059-4fa0-a363-76de35b32281',
        });
      }
      return response(reply);
    }
    return response({ code: 'INVALID_REQUEST' }, 400);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function openQuestions() {
  fireEvent.click(screen.getByRole('button', { name: '거래 질문' }));
}

function submitQuestion() {
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: question } });
  fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }));
}

afterEach(() => vi.unstubAllGlobals());

describe('synthetic trade replay', () => {
  it('shows disclosure details and focuses the ledger row with the cited source and fill ID', async () => {
    mockReplay({ replayFills: [{ ...firstFill, source: 'another-synthetic-source' }, ...fills] });
    render(<App />);
    expect(await screen.findByText('8주')).toBeInTheDocument();

    openQuestions();
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.getByText(scope.symbol)).toBeVisible();
    expect(screen.getByText(scope.from_date)).toBeVisible();
    expect(screen.getByText(scope.as_of)).toBeVisible();
    submitQuestion();

    expect(await screen.findByText(answer.answer)).toBeVisible();
    fireEvent.click(screen.getByText(disclosure.title, { selector: 'summary' }));
    expect(screen.getByText(disclosure.source)).toBeVisible();
    expect(screen.getByText('발생 시각 (KST)')).toBeVisible();
    expect(screen.getByText('수집 시각 (KST)')).toBeVisible();
    const times = screen.getByText(disclosure.source).closest('details').querySelectorAll('time');
    expect(Array.from(times, (time) => time.dateTime)).toEqual([disclosure.occurred_at, disclosure.collected_at]);

    fireEvent.click(screen.getByRole('button', { name: /synthetic-broker.*partial-1/ }));
    const citedRow = await screen.findByRole('row', { name: /^synthetic-broker partial-1/ });
    expect(citedRow).toHaveFocus();
    expect(citedRow).toHaveClass('is-cited');
    expect(screen.getByLabelText('종목')).toHaveValue(scope.symbol);
  });

  it('preserves changed scope across screens and reports insufficient evidence for that scope', async () => {
    const selectedScope = { ...expected.empty_scope, from_date: '2026-11-11', as_of: '2026-11-14' };
    mockReplay({ selectedScope, replayFills: [], position: 0, replies: [
      { status: 'insufficient_evidence', answer: '', evidence: [] },
    ] });
    render(<App />);
    expect(await screen.findByText('8주')).toBeVisible();
    fireEvent.change(screen.getByLabelText('종목'), { target: { value: selectedScope.symbol } });
    fireEvent.change(screen.getByLabelText('조회 시작일'), { target: { value: selectedScope.from_date } });
    fireEvent.change(screen.getByLabelText('기준일'), { target: { value: selectedScope.as_of } });
    fireEvent.click(screen.getByRole('button', { name: '원장 조회' }));
    expect(await screen.findByText('선택한 기간에 체결이 없습니다.')).toBeVisible();

    openQuestions();
    submitQuestion();
    const notice = await screen.findByText(/질문에 답할 근거를 찾지 못했습니다/);
    expect(notice).toHaveTextContent(selectedScope.symbol);
    expect(notice).toHaveTextContent(selectedScope.from_date);
    expect(notice).toHaveTextContent(selectedScope.as_of);

    fireEvent.click(screen.getByRole('button', { name: '거래 원장' }));
    expect(screen.getByLabelText('종목')).toHaveValue(selectedScope.symbol);
    expect(screen.getByLabelText('조회 시작일')).toHaveValue(selectedScope.from_date);
    expect(screen.getByLabelText('기준일')).toHaveValue(selectedScope.as_of);
  });

  it('keeps the loaded ledger and allows retrying the same question after a 503', async () => {
    const fetchMock = mockReplay({ replies: [null, answer] });
    render(<App />);
    expect(await screen.findByText('8주')).toBeInTheDocument();

    openQuestions();
    submitQuestion();
    expect(await screen.findByRole('alert')).toHaveTextContent(/다시 시도/);
    fireEvent.click(screen.getByRole('button', { name: '거래 원장' }));
    expect(within(screen.getByRole('table')).getByText(firstFill.fill_id)).toBeVisible();
    expect(fetchMock.mock.calls.filter(([path]) => path.startsWith(`${replayPath}?`))).toHaveLength(1);

    openQuestions();
    expect(screen.getByLabelText('질문')).toHaveValue(question);
    fireEvent.click(screen.getByRole('button', { name: '질문 보내기' }));
    expect(await screen.findByText(answer.answer)).toBeVisible();
  });
});
