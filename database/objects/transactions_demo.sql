SELECT 'savepoint_walkthrough' AS exercise;
START TRANSACTION;
SELECT rating FROM movies WHERE id = 'the-last-orbit' FOR UPDATE;
SAVEPOINT before_movie_rating;
UPDATE movies SET rating = IF(rating = 10, 9, 10) WHERE id = 'the-last-orbit';
SELECT rating FROM movies WHERE id = 'the-last-orbit';
ROLLBACK TO SAVEPOINT before_movie_rating;
SELECT rating FROM movies WHERE id = 'the-last-orbit';
COMMIT;

SELECT 'read_committed_begin' AS exercise;
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT rating FROM movies WHERE id = 'the-last-orbit';

SELECT 'repeatable_read_begin' AS exercise;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
START TRANSACTION;
SELECT rating FROM movies WHERE id = 'the-last-orbit';

SELECT 'writer_change' AS exercise;
START TRANSACTION;
SELECT rating INTO @dippie_demo_original_rating FROM movies WHERE id = 'the-last-orbit' FOR UPDATE;
UPDATE movies SET rating = IF(rating = 10, 9, 10) WHERE id = 'the-last-orbit';
COMMIT;

SELECT 'reader_finish' AS exercise;
SELECT rating FROM movies WHERE id = 'the-last-orbit';
COMMIT;

SELECT 'writer_restore' AS exercise;
START TRANSACTION;
UPDATE movies SET rating = @dippie_demo_original_rating WHERE id = 'the-last-orbit';
COMMIT;
