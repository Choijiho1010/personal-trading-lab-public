import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';

import { LedgerScreen } from './ledger-screen.jsx';

import fixture from '../../../../../contracts/synthetic-ledger.fixture.json';
import { createLedgerClient } from './ledger-client.js';

const { fills, positions, conflicts } = fixture;

afterEach(() => vi.unstubAllGlobals());

describe('LedgerScreen', () => {
  it('shows synthetic fills, positions, and a conflict that did not change the ledger', async () => {
    const fetch = vi.fn(async (path) => {
      const collection = path.split('/').at(-1);
      return { ok: true, json: async () => ({ [collection]: fixture[collection] }) };
    });
    vi.stubGlobal('fetch', fetch);

    render(<LedgerScreen client={createLedgerClient()} />);

    expect(await screen.findByText('합성 원장')).toBeInTheDocument();
    expect(screen.getAllByText('partial-1')).toHaveLength(2);
    expect(screen.getByText('합성 데이터')).toBeInTheDocument();
    expect(screen.getByText('partial-2')).toBeInTheDocument();
    expect(screen.getByText('sell-1')).toBeInTheDocument();
    expect(fetch.mock.calls).toEqual([
      ['/api/v1/ledger/fills'],
      ['/api/v1/ledger/positions'],
      ['/api/v1/ledger/conflicts'],
    ]);
    expect(screen.getByText('5주')).toBeInTheDocument();
    expect(screen.getByText('4주 → 6주')).toBeInTheDocument();
    expect(screen.getByText('기존 체결과 잔고는 유지했습니다.')).toBeInTheDocument();
  });

  it('shows distinct symbol, side and time conflicts even when amounts match', async () => {
    const base = { ...conflicts[0], received_quantity: 4 };
    const client = {
      getLedger: vi.fn().mockResolvedValue({
        fills,
        positions,
        conflicts: [
          { ...base, received_symbol: 'OTHER' },
          { ...base, received_side: 'SELL' },
          { ...base, received_filled_at: '2026-11-13T00:00:00.000001Z' },
        ],
      }),
    };

    render(<LedgerScreen client={client} />);

    const cards = await screen.findAllByRole('article');
    expect(cards).toHaveLength(3);
    expect(within(cards[0]).getByText('SAMPLE → OTHER')).toBeInTheDocument();
    expect(within(cards[1]).getByText('매수 → 매도')).toBeInTheDocument();
    expect(within(cards[2]).getByText(/2026-11-13T00:00:00Z.*→.*2026-11-13T00:00:00\.000001Z/)).toBeInTheDocument();
    cards.forEach((card) => {
      expect(within(card).queryByText('수량')).not.toBeInTheDocument();
      expect(within(card).queryByText('가격')).not.toBeInTheDocument();
    });
  });

  it('shows empty state for each ledger result', async () => {
    const client = {
      getLedger: vi.fn().mockResolvedValue({ fills: [], positions: [], conflicts: [] }),
    };

    render(<LedgerScreen client={client} />);

    expect(await screen.findByText('기록된 체결이 없습니다.')).toBeInTheDocument();
    expect(screen.getByText('계산할 보유 수량이 없습니다.')).toBeInTheDocument();
    expect(screen.getByText('확인할 상충 기록이 없습니다.')).toBeInTheDocument();
  });

  it('keeps the page readable when the ledger is unavailable and retries', async () => {
    let available = false;
    const fetch = vi.fn(async (path) => {
      const collection = path.split('/').at(-1);
      if (!available && collection === 'fills') {
        return { ok: false, status: 503, json: async () => ({ code: 'LEDGER_UNAVAILABLE' }) };
      }
      return { ok: true, json: async () => ({ [collection]: fixture[collection] }) };
    });
    vi.stubGlobal('fetch', fetch);

    render(<LedgerScreen client={createLedgerClient()} />);

    expect(await screen.findByText('원장을 지금 사용할 수 없습니다. 잠시 후 다시 불러와 주세요.')).toBeInTheDocument();
    available = true;
    fireEvent.click(screen.getByRole('button', { name: '다시 불러오기' }));
    expect(await screen.findByRole('cell', { name: 'partial-1' })).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(6);
  });
});
