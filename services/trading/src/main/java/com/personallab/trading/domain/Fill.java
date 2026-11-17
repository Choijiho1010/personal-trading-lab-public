package com.personallab.trading.domain;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

public record Fill(
        @JsonProperty("fill_id") String fillId,
        String symbol,
        String side,
        int quantity,
        @JsonProperty("price_krw") int priceKrw,
        @JsonProperty("filled_at") Instant filledAt,
        boolean synthetic) {
}
