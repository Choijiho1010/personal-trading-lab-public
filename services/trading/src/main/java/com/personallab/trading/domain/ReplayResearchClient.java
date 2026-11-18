package com.personallab.trading.domain;

public interface ReplayResearchClient {
    ReplayAnswer askReplay(String requestId, ReplayScope scope, LedgerReplay replay, String question);
}
