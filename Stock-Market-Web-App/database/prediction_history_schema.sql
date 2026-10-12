CREATE TABLE IF NOT EXISTS created_tickers (
    ticker VARCHAR(10) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prediction_history (
    ticker VARCHAR(10) NOT NULL REFERENCES created_tickers(ticker) ON DELETE CASCADE,
    date DATE NOT NULL,
    value DOUBLE PRECISION NOT NULL CHECK (value >= -1 AND value <= 1),
    PRIMARY KEY (ticker, date)
);