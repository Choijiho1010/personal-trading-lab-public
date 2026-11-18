package com.personallab.trading;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.groups.Tuple.tuple;

import com.personallab.trading.domain.FillConflict;
import com.personallab.trading.domain.LedgerFill;
import com.personallab.trading.domain.LedgerRepository;
import com.personallab.trading.domain.Position;
import com.personallab.trading.infrastructure.ledger.PostgresLedgerRepository;
import java.net.URI;
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
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.support.TransactionTemplate;

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
