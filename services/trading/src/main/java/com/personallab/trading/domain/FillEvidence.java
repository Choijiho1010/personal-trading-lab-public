package com.personallab.trading.domain;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record FillEvidence(
        @JsonProperty("fill_id") String fillId,
        String symbol,
        String side,
        int quantity,
        @JsonProperty("filled_at") Instant filledAt,
        Integer priceKrw,
        Boolean synthetic) {
    public static FillEvidence from(Fill fill) {
        return new FillEvidence(fill.fillId(), fill.symbol(), fill.side(), fill.quantity(), fill.filledAt(), null, null);
    }
}
