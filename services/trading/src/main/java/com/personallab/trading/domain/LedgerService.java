package com.personallab.trading.domain;

import java.util.List;

public class LedgerService {
    private final LedgerRepository ledger;
    private final ReplayResearchClient research;

    public LedgerService(LedgerRepository ledger, ReplayResearchClient research) {
        this.ledger = ledger;
        this.research = research;
    }

    public LedgerReplay replay(ReplayScope scope) {
        return ledger.replay(scope);
    }

    public ReplayAnswer askReplay(String requestId, ReplayScope scope, String question) {
        return research.askReplay(requestId, scope, replay(scope), question);
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
