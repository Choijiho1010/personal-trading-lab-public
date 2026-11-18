package com.personallab.trading.infrastructure.research;

import com.personallab.trading.domain.LedgerReplay;
import com.personallab.trading.domain.ReplayAnswer;
import com.personallab.trading.domain.ReplayResearchClient;
import com.personallab.trading.domain.ReplayScope;
import com.personallab.trading.domain.ResearchAnswer;
import com.personallab.trading.domain.ResearchClient;
import com.personallab.trading.domain.ResearchQuestion;
import com.personallab.trading.domain.ResearchUnavailable;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.function.Function;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.node.ObjectNode;

public class HttpResearchClient implements ResearchClient, ReplayResearchClient {
    private final HttpClient client;
    private final ObjectMapper objectMapper;
    private final String baseUrl;
    private final Duration timeout;

    public HttpResearchClient(HttpClient client, ObjectMapper objectMapper, String baseUrl, long timeoutMs) {
        this.client = client;
        this.objectMapper = objectMapper;
        this.baseUrl = baseUrl;
        this.timeout = Duration.ofMillis(timeoutMs);
    }

    @Override
    public ResearchAnswer ask(String requestId, ResearchQuestion question) {
        return post("/internal/v1/research/questions", requestId, question, this::parseAnswer);
    }

    @Override
    public ReplayAnswer askReplay(String requestId, ReplayScope scope, LedgerReplay replay, String question) {
        ObjectNode payload = objectMapper.valueToTree(replay);
        payload.put("question", question);
        return post("/internal/v1/research/replay/questions", requestId, payload, body -> {
            JsonNode node = objectMapper.reader()
                    .with(DeserializationFeature.FAIL_ON_TRAILING_TOKENS,
                            DeserializationFeature.FAIL_ON_READING_DUP_TREE_KEY)
                    .readTree(body);
            return ReplayResponse.parse(node, scope, replay.fills());
        });
    }

    private <T> T post(String path, String requestId, Object payload, Function<String, T> parse) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(baseUrl + path))
                    .header("Content-Type", "application/json")
                    .header("X-Request-ID", requestId)
                    .POST(HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(payload)))
                    .build();
            var pending = client.sendAsync(request, HttpResponse.BodyHandlers.ofString());
            HttpResponse<String> response;
            try {
                response = pending.get(timeout.toMillis(), TimeUnit.MILLISECONDS);
            } catch (TimeoutException exception) {
                pending.cancel(true);
                throw new ResearchUnavailable("upstream_timeout");
            } catch (InterruptedException exception) {
                pending.cancel(true);
                Thread.currentThread().interrupt();
                throw new ResearchUnavailable("upstream_interrupted");
            }
            if (response.statusCode() != 200) {
                throw new ResearchUnavailable("upstream_status");
            }
            return parse.apply(response.body());
        } catch (ExecutionException exception) {
            String reason = exception.getCause() instanceof java.net.http.HttpTimeoutException
                    ? "upstream_timeout" : "upstream_connection";
            throw new ResearchUnavailable(reason);
        } catch (ResearchUnavailable exception) {
            throw exception;
        } catch (RuntimeException exception) {
            throw new ResearchUnavailable("upstream_invalid_response");
        }
    }

    private ResearchAnswer parseAnswer(String body) {
        JsonNode node = objectMapper.readTree(body);
        JsonNode answer = node.path("answer");
        JsonNode evidence = node.path("evidence_ids");
        if (!node.isObject() || node.size() != 2 || !answer.isTextual() || answer.asText().isBlank()
                || !evidence.isArray() || evidence.size() != 1 || !evidence.get(0).isTextual()) {
            throw new ResearchUnavailable("upstream_invalid_response");
        }
        return new ResearchAnswer(answer.asText(), List.of(evidence.get(0).asText()));
    }
}
