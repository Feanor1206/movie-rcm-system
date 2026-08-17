package com.dippie.moviercm.repository;

import com.dippie.moviercm.entity.Movie;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface MovieRepository extends JpaRepository<Movie, String> {

    List<Movie> findAllByOrderByRatingDesc();

    List<Movie> findAllByOrderByYearDesc();

    List<Movie> findByTitleContainingIgnoreCase(String title);

    List<Movie> findByGenresContainingIgnoreCase(String genre);

    @Query("SELECT m FROM Movie m WHERE LOWER(m.title) LIKE LOWER(CONCAT('%', :query, '%')) OR LOWER(m.description) LIKE LOWER(CONCAT('%', :query, '%')) OR LOWER(m.genres) LIKE LOWER(CONCAT('%', :query, '%'))")
    List<Movie> searchMovies(@Param("query") String query);

    @Query("SELECT m FROM Movie m WHERE LOWER(m.genres) LIKE LOWER(CONCAT('%', :genre, '%'))")
    List<Movie> findByGenre(@Param("genre") String genre);
}
