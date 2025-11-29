CREATE TABLE base_date (
  id SERIAL PRIMARY KEY,
  reference_date DATE NOT NULL
);

INSERT INTO base_date (reference_date)
VALUES ('2020-01-01');
