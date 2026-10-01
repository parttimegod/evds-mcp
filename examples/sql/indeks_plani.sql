-- Geçici tabloda tekrarlanabilir plan deneyi; üretim verisine dokunmaz.
-- psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f examples/sql/indeks_plani.sql
BEGIN;
CREATE TEMP TABLE plan_gozlem (
    kod text NOT NULL,
    tarih date NOT NULL,
    deger numeric,
    PRIMARY KEY (kod, tarih)
) ON COMMIT DROP;
INSERT INTO plan_gozlem
SELECT 'SERIES.' || s, d::date, s * 0.1
FROM generate_series(1, 1000) s
CROSS JOIN generate_series('2000-01-01'::timestamp,
                           '2019-12-01'::timestamp, '1 month') d;
ANALYZE plan_gozlem;
-- WHERE kod sabit olduğunda PK indeksi ters taranabilir; ayrı DESC
-- indeksinin gerekliliği varsayılamaz. Bu planda Sort olup olmadığına bak.
EXPLAIN (ANALYZE, BUFFERS)
SELECT tarih, deger FROM plan_gozlem
WHERE kod = 'SERIES.500' ORDER BY tarih DESC LIMIT 12;
ROLLBACK;
