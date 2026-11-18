package com.personallab.trading.infrastructure.research;

import com.personallab.trading.domain.LedgerFill;
import com.personallab.trading.domain.ReplayAnswer;
import com.personallab.trading.domain.ReplayAnswer.Evidence;
import com.personallab.trading.domain.ReplayScope;
import com.personallab.trading.domain.ResearchUnavailable;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import tools.jackson.databind.JsonNode;

final class ReplayResponse {
    private ReplayResponse() {
    }

    static ReplayAnswer parse(JsonNode node, ReplayScope scope, List<LedgerFill> fills) {
        JsonNode answerNode = node.path("answer");
        JsonNode evidenceNode = node.path("evidence");
        if (!node.isObject() || node.size() != 3 || !answerNode.isTextual() || !evidenceNode.isArray()) {
            throw invalidResponse();
        }
        String status = text(node, "status");
        String answer = answerNode.asString();
        if ("insufficient_evidence".equals(status) && answer.isEmpty() && evidenceNode.isEmpty()) {
            return new ReplayAnswer(status, answer, List.of());
        }
        if (!"answered".equals(status) || isBlank(answer) || evidenceNode.isEmpty()) {
            throw invalidResponse();
        }

        Map<String, LedgerFill> allowedFills = new HashMap<>();
        for (LedgerFill fill : fills) {
            allowedFills.put(evidenceId("fill", fill.source(), fill.fillId()), fill);
        }
        Set<String> cited = new HashSet<>();
        List<Evidence> evidence = new ArrayList<>();
        Instant start = scope.start();
        Instant cutoff = scope.cutoff();
        for (JsonNode citation : evidenceNode) {
            Evidence item = parseEvidence(citation, allowedFills, start, cutoff);
            if (!cited.add(item.id())) {
                throw invalidResponse();
            }
            evidence.add(item);
        }
        return new ReplayAnswer(status, answer, List.copyOf(evidence));
    }

    private static Evidence parseEvidence(
            JsonNode node, Map<String, LedgerFill> fills, Instant start, Instant cutoff) {
        String id = text(node, "id");
        String kind = text(node, "kind");
        String source = text(node, "source");
        String referenceId = text(node, "reference_id");
        Instant occurredAt = Instant.parse(text(node, "occurred_at"));
        Instant collectedAt = Instant.parse(text(node, "collected_at"));

        if (!node.isObject() || !id.equals(evidenceId(kind, source, referenceId))
                || !referenceId.matches("[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
                || occurredAt.isBefore(start) || collectedAt.isBefore(occurredAt) || !collectedAt.isBefore(cutoff)) {
            throw invalidResponse();
        }

        String title = null;
        switch (kind) {
            case "fill" -> {
                LedgerFill fill = fills.get(id);
                if (node.size() != 6 || fill == null || !fill.filledAt().equals(occurredAt)
                        || !fill.collectedAt().equals(collectedAt)) {
                    throw invalidResponse();
                }
            }
            case "disclosure" -> {
                if (node.size() != 7 || !"synthetic-disclosures".equals(source)) {
                    throw invalidResponse();
                }
                title = text(node, "title");
            }
            default -> throw invalidResponse();
        }
        return new Evidence(id, kind, source, referenceId, occurredAt, collectedAt, title);
    }

    private static String text(JsonNode node, String field) {
        JsonNode value = node.path(field);
        if (!value.isTextual() || isBlank(value.asString())) {
            throw invalidResponse();
        }
        return value.asString();
    }

    private static boolean isBlank(String value) {
        return value.codePoints().allMatch(c -> Character.isWhitespace(c) || Character.isSpaceChar(c));
    }

    private static String evidenceId(String kind, String source, String referenceId) {
        return "evidence:" + kind + ":" + source + ":" + referenceId;
    }

    private static ResearchUnavailable invalidResponse() {
        return new ResearchUnavailable("upstream_invalid_response");
    }
}
