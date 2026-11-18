package com.personallab.trading.domain;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.LocalDate;
import java.util.List;

public record LedgerReplay(
        String symbol,
        @JsonProperty("from_date") LocalDate fromDate,
        @JsonProperty("as_of") LocalDate asOf,
        List<LedgerFill> fills,
        @JsonProperty("position_quantity") long positionQuantity) {
}
