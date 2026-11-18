package com.personallab.trading.domain;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;

public record ReplayAnswer(String status, String answer, List<Evidence> evidence) {
    public record Evidence(
            String id,
            String kind,
            String source,
            @JsonProperty("reference_id") String referenceId,
            @JsonProperty("occurred_at") Instant occurredAt,
            @JsonProperty("collected_at") Instant collectedAt,
            @JsonInclude(JsonInclude.Include.NON_NULL) String title) {
    }
}
