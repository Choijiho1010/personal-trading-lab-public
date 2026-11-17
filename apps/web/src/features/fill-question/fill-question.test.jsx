import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { FillQuestionScreen } from './fill-question-screen.jsx';

const fill = {
  fill_id: 'demo-fill-1',
  symbol: 'SAMPLE',
  side: 'BUY',
  quantity: 4,
  price_krw: 10000,
  filled_at: '2026-11-13T00:00:00Z',
  synthetic: true,
};

const answer = {
  answer: '4주를 매수했습니다.',
  evidence_ids: ['demo-fill-1'],
};

describe('FillQuestionScreen', () => {
  it('loads and presents the synthetic fill in Korea time', async () => {
    const client = { getFill: vi.fn().mockResolvedValue(fill), askQuestion: vi.fn() };

    render(<FillQuestionScreen client={client} />);

    expect(screen.getByText('체결 내역을 불러오는 중입니다.')).toBeInTheDocument();
    expect(await screen.findByText('합성 데이터')).toBeInTheDocument();
    expect(screen.getByText('SAMPLE')).toBeInTheDocument();
    expect(screen.getByText('매수')).toBeInTheDocument();
    expect(screen.getByText('4주')).toBeInTheDocument();
    expect(screen.getByText('10,000원')).toBeInTheDocument();
    expect(screen.getByText(/2026년 11월 13일/)).toBeInTheDocument();
    expect(screen.getByText(/한국 표준시/)).toBeInTheDocument();
  });

  it('keeps the question and fill after a research service 503', async () => {
    const client = {
      getFill: vi.fn().mockResolvedValue(fill),
      askQuestion: vi.fn().mockRejectedValue({ code: 'RESEARCH_UNAVAILABLE' }),
    };

    render(<FillQuestionScreen client={client} />);

    await screen.findByText('합성 데이터');
    fireEvent.change(screen.getByLabelText('질문'), { target: { value: '이 거래에서 몇 주 샀어?' } });
    fireEvent.click(screen.getByRole('button', { name: '질문하기' }));

    expect(await screen.findByText('답변 서비스를 지금 사용할 수 없습니다. 다시 질문해 주세요.')).toBeInTheDocument();
    expect(screen.getByLabelText('질문')).toHaveValue('이 거래에서 몇 주 샀어?');
    expect(screen.getByText('SAMPLE')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '질문하기' })).toBeEnabled();
  });

  it('focuses and highlights the cited original fill row', async () => {
    const client = { getFill: vi.fn().mockResolvedValue(fill), askQuestion: vi.fn().mockResolvedValue(answer) };

    render(<FillQuestionScreen client={client} />);

    await screen.findByText('합성 데이터');
    fireEvent.change(screen.getByLabelText('질문'), { target: { value: '이 거래에서 몇 주 샀어?' } });
    fireEvent.click(screen.getByRole('button', { name: '질문하기' }));
    await screen.findByText('4주를 매수했습니다.');
    fireEvent.click(screen.getByRole('button', { name: '근거 보기' }));

    await waitFor(() => expect(screen.getByRole('row', { name: /demo-fill-1/ })).toHaveFocus());
    expect(screen.getByRole('row', { name: /demo-fill-1/ })).toHaveClass('is-cited');
  });

  it('uses Unicode code points when deciding whether a question exceeds 500 characters', async () => {
    const client = { getFill: vi.fn().mockResolvedValue(fill), askQuestion: vi.fn() };

    render(<FillQuestionScreen client={client} />);

    await screen.findByText('합성 데이터');
    fireEvent.change(screen.getByLabelText('질문'), { target: { value: '😀'.repeat(500) } });
    expect(screen.getByRole('button', { name: '질문하기' })).toBeEnabled();
    fireEvent.change(screen.getByLabelText('질문'), { target: { value: '😀'.repeat(501) } });
    expect(screen.getByText('질문은 500자 이하여야 합니다.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '질문하기' })).toBeDisabled();
  });
});
