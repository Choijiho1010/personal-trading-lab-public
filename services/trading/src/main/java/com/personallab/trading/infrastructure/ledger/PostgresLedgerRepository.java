package com.personallab.trading.infrastructure.ledger;

import com.personallab.trading.domain.FillConflict;
import com.personallab.trading.domain.LedgerFill;
import com.personallab.trading.domain.LedgerReplay;
import com.personallab.trading.domain.LedgerRepository;
import com.personallab.trading.domain.Position;
import com.personallab.trading.domain.ReplayScope;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.List;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.ConnectionCallback;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import org.springframework.transaction.support.TransactionTemplate;

public class PostgresLedgerRepository implements LedgerRepository {
    private final JdbcTemplate jdbc;
    private final TransactionTemplate transactions;

    public PostgresLedgerRepository(JdbcTemplate jdbc, TransactionTemplate transactions) {
        this.jdbc = jdbc;
        this.transactions = transactions;
        transactions.executeWithoutResult(status -> {
            jdbc.execute("select pg_advisory_xact_lock(623414070)");
            jdbc.execute((ConnectionCallback<Void>) connection -> {
                ScriptUtils.executeSqlScript(connection, new ClassPathResource("db/migration/V001__synthetic_ledger.sql"));
                return null;
            });
        });
    }

    @Override
    public InsertResult record(LedgerFill fill) {
        return transactions.execute(status -> recordInTransaction(fill));
    }

    private InsertResult recordInTransaction(LedgerFill fill) {
        int inserted = jdbc.update("""
                insert into ledger_fills (source, fill_id, symbol, side, quantity, price_krw, filled_at, collected_at, synthetic)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?) on conflict (source, fill_id) do nothing
                """, fill.source(), fill.fillId(), fill.symbol(), fill.side(), fill.quantity(),
                fill.priceKrw(), Timestamp.from(fill.filledAt()), Timestamp.from(fill.collectedAt()), fill.synthetic());
        if (inserted == 1) {
            return InsertResult.INSERTED;
        }
        LedgerFill original = jdbc.queryForObject("""
                select source, fill_id, symbol, side, quantity, price_krw, filled_at, collected_at, synthetic
                from ledger_fills where source = ? and fill_id = ?
                """, this::fill, fill.source(), fill.fillId());
        if (sameFacts(original, fill)) {
            return InsertResult.DUPLICATE;
        }
        jdbc.update("""
                insert into ledger_fill_conflicts
                (source, fill_id, received_symbol, received_side, received_quantity, received_price_krw, received_filled_at)
                values (?, ?, ?, ?, ?, ?, ?) on conflict do nothing
                """, fill.source(), fill.fillId(), fill.symbol(), fill.side(), fill.quantity(),
                fill.priceKrw(), Timestamp.from(fill.filledAt()));
        return InsertResult.CONFLICT;
    }

    private boolean sameFacts(LedgerFill original, LedgerFill received) {
        return original.symbol().equals(received.symbol()) && original.side().equals(received.side())
                && original.quantity() == received.quantity() && original.priceKrw() == received.priceKrw()
                && original.filledAt().equals(received.filledAt()) && original.synthetic() == received.synthetic();
    }

    @Override
    public List<LedgerFill> fills() {
        return jdbc.query("""
                select source, fill_id, symbol, side, quantity, price_krw, filled_at, collected_at, synthetic
                from ledger_fills order by filled_at, source, fill_id
                """, this::fill);
    }

    @Override
    public List<Position> positions() {
        return jdbc.query("""
                select symbol, sum(case when side = 'BUY' then quantity else -quantity end) as quantity
                from ledger_fills group by symbol order by symbol
                """, (rs, row) -> new Position(rs.getString("symbol"), rs.getLong("quantity")));
    }

    @Override
    public LedgerReplay replay(ReplayScope scope) {
        Timestamp cutoff = Timestamp.from(scope.cutoff());
        return jdbc.query("""
                with known_fills as (
                    select source, fill_id, symbol, side, quantity, price_krw, filled_at, collected_at, synthetic
                    from ledger_fills
                    where symbol = ? and filled_at < ? and collected_at < ? and synthetic
                ), position as (
                    select coalesce(sum(case when side = 'BUY' then quantity else -quantity end), 0) as net_quantity
                    from known_fills
                )
                select known_fills.*, position.net_quantity
                from position left join known_fills on known_fills.filled_at >= ?
                order by filled_at, source, fill_id
                """, rs -> {
            List<LedgerFill> fills = new ArrayList<>();
            long position = 0;
            while (rs.next()) {
                position = rs.getLong("net_quantity");
                if (rs.getString("fill_id") != null) {
                    fills.add(fill(rs, fills.size()));
                }
            }
            return new LedgerReplay(scope.symbol(), scope.fromDate(), scope.asOf(), List.copyOf(fills), position);
        }, scope.symbol(), cutoff, cutoff, Timestamp.from(scope.start()));
    }

    @Override
    public List<FillConflict> conflicts() {
        return jdbc.query("""
                select c.source, c.fill_id, f.quantity as existing_quantity, c.received_quantity,
                       f.price_krw as existing_price_krw, c.received_price_krw,
                       f.symbol as existing_symbol, c.received_symbol, f.side as existing_side, c.received_side,
                       f.filled_at as existing_filled_at, c.received_filled_at
                from ledger_fill_conflicts c join ledger_fills f on c.source = f.source and c.fill_id = f.fill_id
                order by c.source, c.fill_id, c.received_quantity, c.received_price_krw, c.received_symbol,
                         c.received_side, c.received_filled_at
                """, (rs, row) -> new FillConflict(rs.getString("source"), rs.getString("fill_id"),
                rs.getInt("existing_quantity"), rs.getInt("received_quantity"),
                rs.getInt("existing_price_krw"), rs.getInt("received_price_krw"),
                rs.getString("existing_symbol"), rs.getString("received_symbol"), rs.getString("existing_side"),
                rs.getString("received_side"), rs.getTimestamp("existing_filled_at").toInstant(),
                rs.getTimestamp("received_filled_at").toInstant()));
    }

    private LedgerFill fill(ResultSet rs, int row) throws SQLException {
        return new LedgerFill(rs.getString("source"), rs.getString("fill_id"), rs.getString("symbol"),
                rs.getString("side"), rs.getInt("quantity"), rs.getInt("price_krw"),
                rs.getTimestamp("filled_at").toInstant(), rs.getTimestamp("collected_at").toInstant(),
                rs.getBoolean("synthetic"));
    }
}
