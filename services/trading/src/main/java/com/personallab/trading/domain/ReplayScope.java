package com.personallab.trading.domain;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;

public record ReplayScope(String symbol, LocalDate fromDate, LocalDate asOf) {
    private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

    public Instant start() {
        return fromDate.atStartOfDay(SEOUL).toInstant();
    }

    public Instant cutoff() {
        return asOf.plusDays(1).atStartOfDay(SEOUL).toInstant();
    }
}
