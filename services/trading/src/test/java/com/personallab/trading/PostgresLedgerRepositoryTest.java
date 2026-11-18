package com.personallab.trading;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.groups.Tuple.tuple;

import com.personallab.trading.domain.FillConflict;
import com.personallab.trading.domain.LedgerFill;
import com.personallab.trading.domain.LedgerRepository;
import com.personallab.trading.domain.Position;
import com.personallab.trading.infrastructure.ledger.PostgresLedgerRepository;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.sql.SQLException;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.json.JsonMapper;

@EnabledIfEnvironmentVariable(named = "TRADING_LEDGER_URL", matches = ".+")
class PostgresLedgerRepositoryTest {
    private JdbcTemplate admin;
    private DriverManagerDataSource dataSource;
    private String schema;
    private LedgerRepository ledger;

    @BeforeEach
    void setUp() {
        String url = System.getenv("TRADING_LEDGER_URL");
        String user = System.getenv("TRADING_LEDGER_USERNAME");
        String password = System.getenv("TRADING_LEDGER_PASSWORD");
        admin = new JdbcTemplate(new DriverManagerDataSource(url, user, password));
        schema = "ledger_test_" + UUID.randomUUID().toString().replace("-", "");
        admin.execute("create schema " + schema);
        String separator = url.contains("?") ? "&" : "?";
        dataSource = new DriverManagerDataSource(url + separator + "currentSchema=" + schema, user, password);
        ledger = openLedger();
    }

    @AfterEach
    void cleanUp() {
        if (admin != null && schema != null) {
            admin.execute("drop schema if exists " + schema + " cascade");
        }
    }

    private LedgerRepository openLedger() {
        JdbcTemplate jdbc = new JdbcTemplate(dataSource);
        return new PostgresLedgerRepository(jdbc, new TransactionTemplate(new DataSourceTransactionManager(dataSource)));
    }

    @Test
    void keepsTheFirstEconomicFactsAndRecordsAConflict() {
        assertThat(ledger.record(fill("partial-1", "BUY", 4, 10000, 0))).isEqualTo(LedgerRepository.InsertResult.INSERTED);
        assertThat(ledger.record(recollected(fill("partial-1", "BUY", 4, 10000, 0)))).isEqualTo(LedgerRepository.InsertResult.DUPLICATE);
        assertThat(ledger.record(recollected(fill("partial-1", "BUY", 6, 10000, 0)))).isEqualTo(LedgerRepository.InsertResult.CONFLICT);

        assertThat(ledger.fills()).containsExactly(fill("partial-1", "BUY", 4, 10000, 0));
        assertThat(ledger.positions()).extracting("symbol", "quantity").containsExactly(tuple("SAMPLE", 4L));
        assertThat(ledger.conflicts()).extracting("fillId", "existingQuantity", "receivedQuantity")
                .containsExactly(tuple("partial-1", 4, 6));
    }

    @Test
    void rollsBackFailedFillAndConflictWritesAtCommit() {
        LedgerFill original = fill("partial-1", "BUY", 4, 10000, 0);
        ledger.record(original);
        ledger.record(fill("partial-1", "BUY", 6, 10000, 0));
        List<FillConflict> originalConflicts = ledger.conflicts();
        assertThat(originalConflicts).extracting(FillConflict::receivedQuantity).containsExactly(6);

        rejectWritesAtCommit();

        List<LedgerFill> failingWrites = List.of(
                fill("partial-2", "BUY", 2, 10000, 1),
                fill("partial-1", "BUY", 8, 10000, 0));
        for (LedgerFill failed : failingWrites) {
            assertThatThrownBy(() -> ledger.record(failed))
                    .hasRootCauseInstanceOf(SQLException.class)
                    .hasStackTraceContaining("injected ledger commit failure");
            assertThat(ledger.fills()).containsExactly(original);
            assertThat(ledger.positions()).containsExactly(new Position("SAMPLE", 4L));
            assertThat(ledger.conflicts()).containsExactlyElementsOf(originalConflicts);
        }
    }

    @Test
    void returnsServiceUnavailableWithRequestIdWhenLedgerCommitFails() throws Exception {
        LedgerFill original = fill("partial-1", "BUY", 4, 10000, 0);
        ledger.record(original);
        ledger.record(fill("partial-1", "BUY", 6, 10000, 0));
        rejectWritesAtCommit();

        try (var application = new SpringApplicationBuilder(TradingApplication.class)
                .run("--server.address=127.0.0.1", "--server.port=0", "--trading.ledger.enabled=true",
                        "--trading.ledger.url=" + dataSource.getUrl(),
                        "--trading.ledger.username=" + dataSource.getUsername(),
                        "--trading.ledger.password=" + dataSource.getPassword());
                var client = HttpClient.newHttpClient()) {
            String port = application.getEnvironment().getRequiredProperty("local.server.port");
            URI uri = URI.create("http://127.0.0.1:" + port + "/api/v1/ledger/fills");
            List<LedgerFill> failingWrites = List.of(
                    fill("partial-2", "BUY", 2, 10000, 1),
                    fill("partial-1", "BUY", 8, 10000, 0));
            for (LedgerFill failed : failingWrites) {
                String json = """
                        {"source":"synthetic-broker","fill_id":"%s","symbol":"SAMPLE","side":"BUY",
                         "quantity":%d,"price_krw":10000,"filled_at":"%s","collected_at":"%s","synthetic":true}
                        """.formatted(failed.fillId(), failed.quantity(), failed.filledAt(), failed.collectedAt());
                HttpRequest request = HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(5))
                        .header("Content-Type", "application/json")
                        .header("Accept", "application/json")
                        .POST(HttpRequest.BodyPublishers.ofString(json))
                        .build();
                HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
                assertThat(response.statusCode()).isEqualTo(503);
                assertThat(response.body()).isEqualTo("{\"code\":\"LEDGER_UNAVAILABLE\"}");
                assertThat(response.headers().firstValue("X-Request-ID"))
                        .hasValueSatisfying(id -> assertThat(UUID.fromString(id).toString()).isEqualTo(id));
                assertThat(ledger.fills()).containsExactly(original);
                assertThat(ledger.positions()).containsExactly(new Position("SAMPLE", 4L));
                assertThat(ledger.conflicts()).extracting(FillConflict::receivedQuantity).containsExactly(6);
            }
        }
    }

    @Test
    void replayUsesHistoricalHoldingsAndExcludesFutureLateAndOtherSymbolFills() throws Exception {
        ObjectMapper mapper = JsonMapper.builder().findAndAddModules().build();
        Path contracts = Path.of("../../contracts");
        var fixture = mapper.readTree(contracts.resolve("synthetic-replay.fixture.json"));
        var original = mapper.readTree(contracts.resolve("synthetic-ledger.fixture.json"));
        seedReplayLedger(mapper, fixture, original);

        LedgerFill conflicting = fill("partial-1", "BUY", 61, 10000, 0);
        assertThat(ledger.record(conflicting)).isEqualTo(LedgerRepository.InsertResult.CONFLICT);
        Instant cutoff = Instant.parse("2026-11-13T15:00:00Z");
        ledger.record(new LedgerFill("synthetic-broker", "future-1", "SAMPLE", "BUY", 30, 10000,
                cutoff, cutoff, true));
        Instant start = Instant.parse("2026-11-11T15:00:00Z");
        ledger.record(new LedgerFill("synthetic-broker", "start-1", "AT-START", "BUY", 4, 10000,
                start, start, true));

        try (var application = new SpringApplicationBuilder(TradingApplication.class)
                .run("--server.address=127.0.0.1", "--server.port=0", "--trading.ledger.enabled=true",
                        "--trading.ledger.url=" + dataSource.getUrl(),
                        "--trading.ledger.username=" + dataSource.getUsername(),
                        "--trading.ledger.password=" + dataSource.getPassword());
                var client = HttpClient.newHttpClient()) {
            String port = application.getEnvironment().getRequiredProperty("local.server.port");
            String url = "http://127.0.0.1:" + port + "/api/v1/ledger/replay";
            var scope = fixture.path("scope");
            String dates = "&from_date=" + scope.path("from_date").asString() + "&as_of=" + scope.path("as_of").asString();
            var replay = getReplay(client, mapper, url + "?symbol=" + scope.path("symbol").asString() + dates);
            var expected = fixture.path("expected");
            assertThat(replay.path("position_quantity")).isEqualTo(expected.path("position_quantity"));
            assertThat(replay.path("fills").isArray()).isTrue();
            assertThat(replay.path("fills").valueStream().map(row -> row.path("fill_id").asString()).toList())
                    .containsExactlyElementsOf(expected.path("fill_ids").valueStream().map(row -> row.asString()).toList());

            var earlier = getReplay(client, mapper, url + "?symbol=SAMPLE&from_date=2026-11-12&as_of=2026-11-12");
            assertThat(earlier.path("fills").size()).isZero();
            assertThat(earlier.path("position_quantity").asLong()).isEqualTo(3);
            var empty = getReplay(client, mapper, url + "?symbol=UNKNOWN" + dates);
            assertThat(empty.path("fills").size()).isZero();
            assertThat(empty.path("position_quantity").asLong()).isZero();
            var boundary = getReplay(client, mapper, url + "?symbol=AT-START" + dates);
            assertThat(boundary.path("fills").get(0).path("fill_id").asString()).isEqualTo("start-1");
        }
    }

    private JsonNode getReplay(HttpClient client, ObjectMapper mapper, String url) throws Exception {
        var response = client.send(HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(5)).build(),
                HttpResponse.BodyHandlers.ofString());
        assertThat(response.statusCode()).isEqualTo(200);
        assertThat(response.headers().firstValue("X-Request-ID"))
                .hasValueSatisfying(id -> assertThat(UUID.fromString(id).toString()).isEqualTo(id));
        return mapper.readTree(response.body());
    }

    @Test
    @ExtendWith(OutputCaptureExtension.class)
    void bridgesOnlyTheScopedQuestionAndRejectsInvalidResearchResponses(CapturedOutput output) throws Exception {
        ObjectMapper mapper = JsonMapper.builder().findAndAddModules().build();
        Path contracts = Path.of("../../contracts");
        var fixture = mapper.readTree(contracts.resolve("synthetic-replay.fixture.json"));
        var original = mapper.readTree(contracts.resolve("synthetic-ledger.fixture.json"));
        seedReplayLedger(mapper, fixture, original);
        String answered = """
                {"status":"answered","answer":"기준일까지 8주를 보유했습니다.","evidence":[
                  {"id":"evidence:fill:synthetic-broker:partial-1","kind":"fill","source":"synthetic-broker",
                   "reference_id":"partial-1","occurred_at":"2026-11-13T00:00:00Z",
                   "collected_at":"2026-11-13T00:00:01Z"},
                  {"id":"evidence:disclosure:synthetic-disclosures:sample-disclosure-1","kind":"disclosure",
                   "source":"synthetic-disclosures","reference_id":"sample-disclosure-1","title":"합성 샘플 공시",
                   "occurred_at":"2026-11-12T00:00:00Z","collected_at":"2026-11-12T00:01:00Z"}
                ]}
                """;
        var outgoing = new AtomicReference<JsonNode>();
        var requestId = new AtomicReference<String>();
        var reply = new AtomicReference<>(answered);
        var delay = new AtomicReference<>(false);
        var upstream = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        upstream.createContext("/internal/v1/research/replay/questions", exchange -> {
            try (exchange) {
                requestId.set(exchange.getRequestHeaders().getFirst("X-Request-ID"));
                outgoing.set(mapper.readTree(exchange.getRequestBody()));
                if (delay.get()) {
                    try {
                        Thread.sleep(2000);
                    } catch (InterruptedException interrupted) {
                        Thread.currentThread().interrupt();
                    }
                }
                byte[] body = reply.get().getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.sendResponseHeaders(200, body.length);
                exchange.getResponseBody().write(body);
            }
        });
        upstream.start();
        try (var application = new SpringApplicationBuilder(TradingApplication.class)
                .run("--server.address=127.0.0.1", "--server.port=0", "--trading.ledger.enabled=true",
                        "--trading.ledger.url=" + dataSource.getUrl(),
                        "--trading.ledger.username=" + dataSource.getUsername(),
                        "--trading.ledger.password=" + dataSource.getPassword(),
                        "--trading.research.base-url=http://127.0.0.1:" + upstream.getAddress().getPort(),
                        "--trading.research.timeout-ms=1000");
                var client = HttpClient.newHttpClient()) {
            String port = application.getEnvironment().getRequiredProperty("local.server.port");
            String base = "http://127.0.0.1:" + port + "/api/v1/ledger/replay";
            var question = mapper.createObjectNode();
            fixture.path("scope").properties().forEach(field -> question.set(field.getKey(), field.getValue()));
            question.set("question", fixture.path("question"));
            HttpRequest request = HttpRequest.newBuilder(URI.create(base + "/questions"))
                    .header("Content-Type", "application/json")
                    .header("X-Request-ID", "untrusted-client-id")
                    .POST(HttpRequest.BodyPublishers.ofString(question.toString()))
                    .timeout(Duration.ofSeconds(5))
                    .build();
            var success = client.send(request, HttpResponse.BodyHandlers.ofString());
            assertThat(success.statusCode()).isEqualTo(200);
            assertThat(mapper.readTree(success.body())).isEqualTo(mapper.readTree(answered));
            assertThat(success.headers().firstValue("X-Request-ID")).hasValue(requestId.get());
            assertThat(UUID.fromString(requestId.get()).toString()).isEqualTo(requestId.get());
            var expectedPayload = question.deepCopy();
            expectedPayload.set("fills", original.path("fills"));
            expectedPayload.set("position_quantity", fixture.path("expected").path("position_quantity"));
            assertThat(outgoing.get()).isEqualTo(expectedPayload);

            String insufficient = """
                    {"status":"insufficient_evidence","answer":"","evidence":[]}
                    """;
            reply.set(insufficient);
            var empty = client.send(request, HttpResponse.BodyHandlers.ofString());
            assertThat(empty.statusCode()).isEqualTo(200);
            assertThat(mapper.readTree(empty.body())).isEqualTo(mapper.readTree(insufficient));

            JsonNode repeated = mapper.readTree(answered);
            repeated.path("evidence").asArray().add(repeated.path("evidence").get(0));
            for (String invalid : List.of(
                    repeated.toString(),
                    answered.replace("partial-1", "opening-1"),
                    answered.replace("2026-11-12T00:01:00Z", "2026-11-13T15:00:00Z"),
                    answered.replace("2026-11-13T00:00:01Z", "2026-11-13T00:00:02Z"),
                    answered.replace("기준일까지 8주를 보유했습니다.", ""),
                    "{\"status\":\"answered\",\"answer\":\"8주\",\"evidence\":[]}",
                    answered.replace("\"title\":", "\"unknown\":"),
                    answered.replace("partial-1", "unknown-fill"),
                    answered + "{}")) {
                reply.set(invalid);
                assertResearchUnavailable(client, request, requestId);
            }
            delay.set(true);
            assertResearchUnavailable(client, request, requestId);
            assertThat(output.getAll())
                    .contains("request_id=" + requestId.get(), "reason=upstream_timeout", "reason=upstream_invalid_response")
                    .doesNotContain(fixture.path("question").asString(), "합성 샘플 공시", "untrusted-client-id");
            var replay = getReplay(client, mapper, base + "?symbol=SAMPLE&from_date=2026-11-12&as_of=2026-11-13");
            assertThat(replay.path("fills").size()).isEqualTo(3);
        } finally {
            upstream.stop(0);
        }
    }

    private void seedReplayLedger(ObjectMapper mapper, JsonNode fixture, JsonNode original) {
        for (var row : original.path("fills")) {
            ledger.record(mapper.treeToValue(row, LedgerFill.class));
        }
        ledger.record(mapper.treeToValue(fixture.path("prior_fill"), LedgerFill.class));
        for (var row : fixture.path("additional_fills")) {
            ledger.record(mapper.treeToValue(row, LedgerFill.class));
        }
    }

    private void assertResearchUnavailable(HttpClient client, HttpRequest request, AtomicReference<String> requestId)
            throws Exception {
        var response = client.send(request, HttpResponse.BodyHandlers.ofString());
        assertThat(response.statusCode()).isEqualTo(503);
        assertThat(response.body()).isEqualTo("{\"code\":\"RESEARCH_UNAVAILABLE\"}");
        assertThat(response.headers().firstValue("X-Request-ID")).hasValue(requestId.get());
    }

    private void rejectWritesAtCommit() {
        JdbcTemplate jdbc = new JdbcTemplate(dataSource);
        jdbc.execute("""
                create function fail_ledger_commit() returns trigger language plpgsql as $$
                begin
                    raise check_violation using message = 'injected ledger commit failure';
                end;
                $$
                """);
        jdbc.execute("""
                create constraint trigger fail_fill_commit after insert on ledger_fills
                deferrable initially deferred for each row execute function fail_ledger_commit()
                """);
        jdbc.execute("""
                create constraint trigger fail_conflict_commit after insert on ledger_fill_conflicts
                deferrable initially deferred for each row execute function fail_ledger_commit()
                """);
    }

    @Test
    void distinguishesConflictsWithTheSameQuantityAndPrice() {
        LedgerFill original = fill("partial-1", "BUY", 4, 10000, 0);
        LedgerFill opposite = fill("partial-1", "SELL", 4, 10000, 0);
        LedgerFill differentTime = fill("partial-1", "BUY", 4, 10000, 4);

        ledger.record(original);
        ledger.record(opposite);
        ledger.record(differentTime);
        ledger.record(recollected(opposite));

        assertThat(ledger.fills()).containsExactly(original);
        assertThat(ledger.conflicts())
                .extracting(FillConflict::receivedSide, FillConflict::receivedFilledAt)
                .containsExactlyInAnyOrder(tuple("SELL", opposite.filledAt()), tuple("BUY", differentTime.filledAt()));
    }

    @Test
    void computesPositionsFromSeparatePartialFills() {
        ledger.record(fill("partial-1", "BUY", 4, 10000, 0));
        ledger.record(fill("partial-2", "BUY", 2, 10100, 2));
        ledger.record(fill("sell-1", "SELL", 1, 10200, 4));

        assertThat(ledger.positions()).extracting("symbol", "quantity")
                .containsExactly(tuple("SAMPLE", 5L));
    }

    @Test
    void reopensTheSameLedgerAndRetainsTheFirstFill() {
        LedgerFill fill = fill("restart", "BUY", 4, 10000, 0);
        ledger.record(fill);
        LedgerRepository reopened = openLedger();
        assertThat(reopened.fills()).containsExactly(fill);
        assertThat(reopened.positions()).containsExactly(new Position("SAMPLE", 4L));
    }

    @Test
    void keepsPositionsWiderThanOneFill() {
        ledger.record(fill("first", "BUY", Integer.MAX_VALUE, 10000, 0));
        ledger.record(fill("second", "BUY", 1, 10000, 1));
        assertThat(ledger.positions()).extracting(Position::quantity)
                .containsExactly((long) Integer.MAX_VALUE + 1);
    }

    @Test
    void concurrentIdenticalIngestionCreatesOneFill() throws Exception {
        CyclicBarrier ready = new CyclicBarrier(2);
        LedgerFill fill = fill("race-1", "BUY", 4, 10000, 0);
        try (var workers = Executors.newFixedThreadPool(2)) {
            var first = workers.submit(() -> {
                ready.await(5, TimeUnit.SECONDS);
                return ledger.record(fill);
            });
            var second = workers.submit(() -> {
                ready.await(5, TimeUnit.SECONDS);
                return ledger.record(fill);
            });
            assertThat(List.of(first.get(10, TimeUnit.SECONDS), second.get(10, TimeUnit.SECONDS)))
                    .containsExactlyInAnyOrder(LedgerRepository.InsertResult.INSERTED,
                            LedgerRepository.InsertResult.DUPLICATE);
        }
        assertThat(ledger.fills()).containsExactly(fill);
    }

    private LedgerFill recollected(LedgerFill fill) {
        return new LedgerFill(fill.source(), fill.fillId(), fill.symbol(), fill.side(), fill.quantity(),
                fill.priceKrw(), fill.filledAt(), fill.collectedAt().plusSeconds(30), fill.synthetic());
    }

    private LedgerFill fill(String id, String side, int quantity, int price, int offsetSeconds) {
        return new LedgerFill("synthetic-broker", id, "SAMPLE", side, quantity, price,
                Instant.parse("2026-11-13T00:00:00Z").plusSeconds(offsetSeconds),
                Instant.parse("2026-11-13T00:00:01Z").plusSeconds(offsetSeconds), true);
    }
}
