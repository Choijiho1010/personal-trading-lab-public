package com.personallab.trading.domain;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record ResearchAnswer(String answer, @JsonProperty("evidence_ids") List<String> evidenceIds) {
}
