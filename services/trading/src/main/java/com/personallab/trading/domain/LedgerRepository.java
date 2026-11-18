package com.personallab.trading.domain;

import java.util.List;

public interface LedgerRepository {
    InsertResult record(LedgerFill fill);
    List<LedgerFill> fills();
    List<Position> positions();
    LedgerReplay replay(ReplayScope scope);
    List<FillConflict> conflicts();

    enum InsertResult { INSERTED, DUPLICATE, CONFLICT }
}
