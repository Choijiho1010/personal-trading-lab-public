package com.personallab.trading.domain;

import java.util.List;

public class LedgerService {
    private final LedgerRepository ledger;

    public LedgerService(LedgerRepository ledger) {
        this.ledger = ledger;
    }

    public LedgerRepository.InsertResult record(LedgerFill fill) {
        return ledger.record(fill);
    }

    public List<LedgerFill> fills() {
        return ledger.fills();
    }

    public List<Position> positions() {
        return ledger.positions();
    }

    public List<FillConflict> conflicts() {
        return ledger.conflicts();
    }
}
