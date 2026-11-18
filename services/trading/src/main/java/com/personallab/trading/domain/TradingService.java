package com.personallab.trading.domain;

import java.util.List;
import java.util.Optional;

public class TradingService {
    private final FillRepository fills;
    private final ResearchClient research;

    public TradingService(FillRepository fills, ResearchClient research) {
        this.fills = fills;
        this.research = research;
    }

    public Optional<Fill> findFill(String fillId) {
        return fills.findById(fillId);
    }

    public ResearchAnswer ask(String requestId, String fillId, String question) {
        Fill fill = fills.findById(fillId).orElseThrow(FillNotFound::new);
        ResearchAnswer answer = research.ask(requestId, new ResearchQuestion(question, FillEvidence.from(fill)));
        if (answer == null || answer.answer() == null || answer.answer().isBlank() || !List.of(fill.fillId()).equals(answer.evidenceIds())) {
            throw new ResearchUnavailable("upstream_invalid_response");
        }
        return answer;
    }

    public static final class FillNotFound extends RuntimeException {
    }
}
