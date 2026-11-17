package com.personallab.trading.domain;

public final class ResearchUnavailable extends RuntimeException {
    private final String reason;

    public ResearchUnavailable(String reason) {
        this.reason = reason;
    }

    public String reason() {
        return reason;
    }
}
