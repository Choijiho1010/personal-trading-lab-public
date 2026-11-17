package com.personallab.trading.domain;

public interface ResearchClient {
    ResearchAnswer ask(String requestId, ResearchQuestion question);
}
