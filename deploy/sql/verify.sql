-- Read-only checks for the wasteflow database. Safe to run any time; changes nothing.
--   mysql -h <RDS_ENDPOINT> -P 3306 -u <USER> -p wasteflow < deploy/sql/verify.sql
SELECT VERSION() AS mysql_version, @@character_set_database AS charset, @@time_zone AS tz;
SELECT table_name, engine, table_collation, table_rows
  FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY table_name;
SELECT table_name, column_name, column_type
  FROM information_schema.columns WHERE table_schema = DATABASE() ORDER BY table_name, ordinal_position;
SELECT constraint_name, table_name, column_name, referenced_table_name, referenced_column_name
  FROM information_schema.key_column_usage WHERE table_schema = DATABASE() AND referenced_table_name IS NOT NULL;
SELECT COUNT(*) AS bins, MIN(fill_level) AS min_fill, MAX(fill_level) AS max_fill FROM bins;
SELECT COUNT(*) AS collection_records FROM collection_records;
-- Orphans must be 0 (the foreign key guarantees it):
SELECT COUNT(*) AS orphan_records FROM collection_records r LEFT JOIN bins b ON b.id = r.bin_id WHERE b.id IS NULL;
