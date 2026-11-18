create table if not exists ledger_fills (
    source varchar(80) not null check (source = 'synthetic-broker'),
    fill_id varchar(80) not null,
    symbol varchar(20) not null,
    side varchar(4) not null check (side in ('BUY', 'SELL')),
    quantity integer not null check (quantity > 0),
    price_krw integer not null check (price_krw > 0),
    filled_at timestamptz not null,
    collected_at timestamptz not null check (collected_at >= filled_at),
    synthetic boolean not null check (synthetic),
    primary key (source, fill_id)
);

create table if not exists ledger_fill_conflicts (
    source varchar(80) not null,
    fill_id varchar(80) not null,
    received_symbol varchar(20) not null,
    received_side varchar(4) not null,
    received_quantity integer not null,
    received_price_krw integer not null,
    received_filled_at timestamptz not null,
    observed_at timestamptz not null default current_timestamp,
    primary key (source, fill_id, received_symbol, received_side, received_quantity, received_price_krw, received_filled_at),
    foreign key (source, fill_id) references ledger_fills (source, fill_id)
);
