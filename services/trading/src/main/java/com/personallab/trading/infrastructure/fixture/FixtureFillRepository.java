package com.personallab.trading.infrastructure.fixture;

import com.personallab.trading.domain.Fill;
import com.personallab.trading.domain.FillRepository;
import java.nio.file.Path;
import java.time.Instant;
import java.util.Optional;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

public class FixtureFillRepository implements FillRepository {
    private final Optional<Fill> fixture;

    public FixtureFillRepository(ObjectMapper objectMapper, String fixturePath) {
        try {
            JsonNode node = objectMapper.readTree(Path.of(fixturePath).toFile()).path("fill");
            fixture = Optional.of(new Fill(
                    node.path("fill_id").asText(),
                    node.path("symbol").asText(),
                    node.path("side").asText(),
                    node.path("quantity").asInt(),
                    node.path("price_krw").asInt(),
                    Instant.parse(node.path("filled_at").asText()),
                    node.path("synthetic").asBoolean()));
        } catch (RuntimeException exception) {
            throw new IllegalStateException("Synthetic fixture is unavailable");
        }
    }

    @Override
    public Optional<Fill> findById(String fillId) {
        return fixture.filter(fill -> fill.fillId().equals(fillId));
    }
}
