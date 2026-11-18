package com.personallab.trading.domain;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

public record FillConflict(
        String source,
        @JsonProperty("fill_id") String fillId,
        @JsonProperty("existing_quantity") int existingQuantity,
        @JsonProperty("received_quantity") int receivedQuantity,
        @JsonProperty("existing_price_krw") int existingPriceKrw,
        @JsonProperty("received_price_krw") int receivedPriceKrw,
        @JsonProperty("existing_symbol") String existingSymbol,
        @JsonProperty("received_symbol") String receivedSymbol,
        @JsonProperty("existing_side") String existingSide,
        @JsonProperty("received_side") String receivedSide,
        @JsonProperty("existing_filled_at") Instant existingFilledAt,
        @JsonProperty("received_filled_at") Instant receivedFilledAt) {
}
