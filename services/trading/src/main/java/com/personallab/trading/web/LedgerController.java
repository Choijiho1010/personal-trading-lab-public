package com.personallab.trading.web;

import com.personallab.trading.domain.LedgerFill;
import com.personallab.trading.domain.LedgerReplay;
import com.personallab.trading.domain.LedgerService;
import com.personallab.trading.domain.ReplayAnswer;
import com.personallab.trading.domain.ReplayScope;
import jakarta.servlet.http.HttpServletResponse;
import java.time.Instant;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.dao.DataAccessException;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.CannotCreateTransactionException;
import org.springframework.transaction.TransactionSystemException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.JsonNode;

@RestController
@RequestMapping("/api/v1/ledger")
public class LedgerController {
    private static final Instant MIN_TIMESTAMP = Instant.parse("0001-01-01T00:00:00Z");
    private static final Instant MAX_TIMESTAMP = Instant.parse("+10000-01-01T00:00:00Z");
    private static final Logger log = LoggerFactory.getLogger(LedgerController.class);
    private final ObjectProvider<LedgerService> provider;

    public LedgerController(ObjectProvider<LedgerService> provider) {
        this.provider = provider;
    }

    @GetMapping("/replay")
    LedgerReplay replay(
            @RequestParam(name = "symbol", required = false) String symbol,
            @RequestParam(name = "from_date", required = false) String fromDate,
            @RequestParam(name = "as_of", required = false) String asOf,
            HttpServletResponse response) {
        ReplayScope scope = replayScope(symbol, fromDate, asOf);
        return ledger(response).replay(scope);
    }

    @PostMapping("/replay/questions")
    ReplayAnswer askReplay(@RequestBody JsonNode body, HttpServletResponse response) {
        if (!body.isObject() || body.size() != 4) {
            throw new InvalidRequest();
        }
        ReplayScope scope = replayScope(text(body, "symbol"), text(body, "from_date"), text(body, "as_of"));
        String question = text(body, "question");
        if (question.codePointCount(0, question.length()) > 500
                || question.codePoints().allMatch(c -> Character.isWhitespace(c) || Character.isSpaceChar(c))) {
            throw new InvalidRequest();
        }
        LedgerService service = ledger(response);
        return service.askReplay(response.getHeader("X-Request-ID"), scope, question);
    }

    private ReplayScope replayScope(String symbol, String fromDate, String asOf) {
        if (symbol == null || !symbol.matches("[A-Z0-9][A-Z0-9.-]{0,19}")) {
            throw new InvalidRequest();
        }
        LocalDate from = replayDate(fromDate);
        LocalDate through = replayDate(asOf);
        if (through.isBefore(from)) {
            throw new InvalidRequest();
        }
        return new ReplayScope(symbol, from, through);
    }

    private LocalDate replayDate(String value) {
        if (value == null || !value.matches("[0-9]{4}-[0-9]{2}-[0-9]{2}") || value.startsWith("0000")) {
            throw new InvalidRequest();
        }
        try {
            return LocalDate.parse(value);
        } catch (DateTimeParseException invalid) {
            throw new InvalidRequest();
        }
    }

    @GetMapping("/fills")
    Map<String, Object> fills(HttpServletResponse response) {
        return Map.of("fills", ledger(response).fills());
    }

    @PostMapping("/fills")
    ResponseEntity<?> record(@RequestBody JsonNode body, HttpServletResponse response) {
        LedgerFill fill = parseFill(body);
        return switch (ledger(response).record(fill)) {
            case INSERTED -> ResponseEntity.status(201).build();
            case DUPLICATE -> ResponseEntity.ok().build();
            case CONFLICT -> ResponseEntity.status(409).body(Map.of("code", "FILL_CONFLICT"));
        };
    }

    @GetMapping("/positions")
    Map<String, Object> positions(HttpServletResponse response) {
        return Map.of("positions", ledger(response).positions());
    }

    @GetMapping("/conflicts")
    Map<String, Object> conflicts(HttpServletResponse response) {
        return Map.of("conflicts", ledger(response).conflicts());
    }

    @ExceptionHandler({LedgerUnavailable.class, DataAccessException.class, CannotCreateTransactionException.class,
            TransactionSystemException.class})
    ResponseEntity<Map<String, String>> unavailable(HttpServletResponse response) {
        log.warn("request_id={} service=trading operation=ledger status=503 reason=LEDGER_UNAVAILABLE",
                response.getHeader("X-Request-ID"));
        return ResponseEntity.status(503).body(Map.of("code", "LEDGER_UNAVAILABLE"));
    }

    private LedgerService ledger(HttpServletResponse response) {
        response.setHeader("X-Request-ID", UUID.randomUUID().toString());
        LedgerService service = provider.getIfAvailable();
        if (service == null) {
            throw new LedgerUnavailable();
        }
        return service;
    }

    private LedgerFill parseFill(JsonNode body) {
        if (!body.isObject() || body.size() != 9) {
            throw new InvalidRequest();
        }
        String source = text(body, "source");
        String fillId = text(body, "fill_id");
        String symbol = text(body, "symbol");
        String side = text(body, "side");
        Instant filledAt = instant(body, "filled_at");
        Instant collectedAt = instant(body, "collected_at");
        JsonNode synthetic = body.path("synthetic");
        if (!"synthetic-broker".equals(source) || !fillId.matches("[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
                || !symbol.matches("[A-Z0-9][A-Z0-9.-]{0,19}") || !("BUY".equals(side) || "SELL".equals(side))
                || collectedAt.isBefore(filledAt) || !synthetic.isBoolean() || !synthetic.asBoolean()) {
            throw new InvalidRequest();
        }
        return new LedgerFill(source, fillId, symbol, side, positiveInt(body, "quantity"),
                positiveInt(body, "price_krw"), filledAt, collectedAt, true);
    }

    private String text(JsonNode body, String field) {
        JsonNode value = body.path(field);
        if (!value.isTextual()) {
            throw new InvalidRequest();
        }
        return value.asText();
    }

    private int positiveInt(JsonNode body, String field) {
        JsonNode value = body.path(field);
        if (!value.isIntegralNumber() || !value.canConvertToInt() || value.asInt() < 1) {
            throw new InvalidRequest();
        }
        return value.asInt();
    }

    private Instant instant(JsonNode body, String field) {
        try {
            Instant value = Instant.parse(text(body, field));
            if (value.getNano() % 1000 != 0 || value.isBefore(MIN_TIMESTAMP) || !value.isBefore(MAX_TIMESTAMP)) {
                throw new InvalidRequest();
            }
            return value;
        } catch (DateTimeParseException invalid) {
            throw new InvalidRequest();
        }
    }

    private static final class LedgerUnavailable extends RuntimeException {
    }
}
