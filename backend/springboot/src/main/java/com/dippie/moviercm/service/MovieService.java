package com.dippie.moviercm.service;

import com.dippie.moviercm.dto.MovieResponse;
import com.dippie.moviercm.dto.PageResponse;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.repository.MovieRepository;
import jakarta.persistence.criteria.CriteriaBuilder;
import jakarta.persistence.criteria.Expression;
import jakarta.persistence.criteria.Predicate;
import jakarta.persistence.criteria.Root;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class MovieService {

    private static final Set<String> ALLOWED_SORT_FIELDS = Set.of("rating", "year", "title");

    private final MovieRepository movieRepository;

    public MovieService(MovieRepository movieRepository) {
        this.movieRepository = movieRepository;
    }

    /**
     * Escape special SQL LIKE metacharacters: backslash, percent, underscore.
     */
    private String escapeLike(String input) {
        if (input == null) return "";
        return input.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
    }

    /**
     * Escape POSIX regex metacharacters: \ . [ ] { } ( ) * + ? ^ $ |
     */
    private String escapeRegex(String input) {
        if (input == null) return "";
        return input.replaceAll("([\\\\.\\[\\]{}()*+?^$|])", "\\\\$1");
    }

    /**
     * C3 & R1: Exact CSV genre token predicate with generalized whitespace normalization.
     * Matches token T case-insensitively as an exact item in a comma-separated list.
     * Boundary rule: (start of string OR comma), optional whitespace/tabs, TOKEN, optional whitespace/tabs, (comma OR end of string).
     * Preserves internal whitespace in multi-word genres (e.g. "Sci-Fi & Fantasy", "Martial Arts").
     * Supports both H2 and PostgreSQL via standard REGEXP_LIKE.
     * Guarantees:
     * - "Drama" matches "Drama" and "Animation,  Drama \t" but NOT "Melodrama"
     * - "Animation" matches "  Animation, Family" and "Animation" but NOT "NonAnimation"
     * - Input wildcards or regex chars do not corrupt matching.
     */
    private Predicate buildGenreTokenPredicate(CriteriaBuilder cb, Root<Movie> root, String rawToken) {
        if (rawToken == null || rawToken.trim().isEmpty()) {
            return cb.conjunction();
        }
        String token = rawToken.trim().toLowerCase();
        String escaped = escapeRegex(token);
        String pattern = "(^|[,])[ \t]*" + escaped + "[ \t]*([,]|$)";

        Expression<String> g = cb.lower(root.get("genres"));
        return cb.and(
                cb.isNotNull(g),
                cb.isTrue(cb.function("REGEXP_LIKE", Boolean.class, g, cb.literal(pattern)))
        );
    }

    /**
     * R2: Consistent search predicate searching title OR description.
     * Safely handles null description and escapes literal wildcards.
     */
    private Predicate buildSearchPredicate(CriteriaBuilder cb, Root<Movie> root, String rawQuery) {
        if (rawQuery == null || rawQuery.trim().isEmpty()) {
            return cb.conjunction();
        }
        String term = "%" + escapeLike(rawQuery.trim().toLowerCase()) + "%";
        Predicate titleMatch = cb.like(cb.lower(root.get("title")), term, '\\');
        Predicate descMatch = cb.and(
                cb.isNotNull(root.get("description")),
                cb.like(cb.lower(root.get("description")), term, '\\')
        );
        return cb.or(titleMatch, descMatch);
    }

    @Transactional(readOnly = true)
    public List<MovieResponse> getAllMovies() {
        return movieRepository.findAll(Sort.by(Sort.Direction.DESC, "rating").and(Sort.by(Sort.Direction.ASC, "id"))).stream()
                .map(MovieResponse::fromEntity)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public List<MovieResponse> getAllMovies(String search, String genre) {
        boolean hasSearch = search != null && !search.trim().isEmpty();
        boolean hasGenre = genre != null && !genre.trim().isEmpty();

        if (!hasSearch && !hasGenre) {
            return getAllMovies();
        }

        Specification<Movie> spec = (root, q, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            if (hasSearch) {
                predicates.add(buildSearchPredicate(cb, root, search));
            }
            if (hasGenre) {
                predicates.add(buildGenreTokenPredicate(cb, root, genre));
            }
            return cb.and(predicates.toArray(new Predicate[0]));
        };

        return movieRepository.findAll(spec, Sort.by(Sort.Direction.DESC, "rating").and(Sort.by(Sort.Direction.ASC, "id"))).stream()
                .map(MovieResponse::fromEntity)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public MovieResponse getMovieById(String id) {
        Movie movie = movieRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Movie not found with id: " + id));
        return MovieResponse.fromEntity(movie);
    }

    @Transactional(readOnly = true)
    public List<MovieResponse> searchMovies(String query) {
        if (query == null || query.trim().isEmpty()) {
            return getAllMovies();
        }
        Specification<Movie> spec = (root, q, cb) -> buildSearchPredicate(cb, root, query);
        return movieRepository.findAll(spec, Sort.by(Sort.Direction.DESC, "rating").and(Sort.by(Sort.Direction.ASC, "id"))).stream()
                .map(MovieResponse::fromEntity)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public List<MovieResponse> filterByGenre(String genre) {
        if (genre == null || genre.trim().isEmpty()) {
            return getAllMovies();
        }
        Specification<Movie> spec = (root, q, cb) -> buildGenreTokenPredicate(cb, root, genre);
        return movieRepository.findAll(spec, Sort.by(Sort.Direction.DESC, "rating").and(Sort.by(Sort.Direction.ASC, "id"))).stream()
                .map(MovieResponse::fromEntity)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public PageResponse<MovieResponse> browseMovies(
            String query,
            String genre,
            String genres,
            Boolean animationOnly,
            Integer yearMin,
            Integer yearMax,
            String sort,
            String direction,
            int page,
            int size
    ) {
        // 1. Validation
        if (page < 0) {
            throw new IllegalArgumentException("Chỉ số trang (page) không được âm: " + page);
        }
        if (size < 1 || size > 100) {
            throw new IllegalArgumentException("Kích thước trang (size) phải nằm trong khoảng 1 đến 100: " + size);
        }
        if (yearMin != null && yearMax != null && yearMin > yearMax) {
            throw new IllegalArgumentException("Năm tối thiểu (yearMin: " + yearMin + ") không được lớn hơn năm tối đa (yearMax: " + yearMax + ")");
        }

        String sortField = (sort == null || sort.trim().isEmpty()) ? "rating" : sort.trim().toLowerCase();
        if (!ALLOWED_SORT_FIELDS.contains(sortField)) {
            throw new IllegalArgumentException("Trường sắp xếp không hợp lệ: '" + sort + "'. Các trường được hỗ trợ: " + ALLOWED_SORT_FIELDS);
        }

        String sortDirStr = (direction == null || direction.trim().isEmpty()) ? "desc" : direction.trim().toLowerCase();
        if (!"asc".equals(sortDirStr) && !"desc".equals(sortDirStr)) {
            throw new IllegalArgumentException("Chiều sắp xếp không hợp lệ: '" + direction + "'. Phải là 'asc' hoặc 'desc'");
        }

        // 2. Build Specification with R1 and R2 predicates
        Specification<Movie> spec = (root, q, cb) -> {
            List<Predicate> predicates = new ArrayList<>();

            if (query != null && !query.trim().isEmpty()) {
                predicates.add(buildSearchPredicate(cb, root, query));
            }

            if (genre != null && !genre.trim().isEmpty()) {
                predicates.add(buildGenreTokenPredicate(cb, root, genre));
            }

            if (genres != null && !genres.trim().isEmpty()) {
                Arrays.stream(genres.split(","))
                        .map(String::trim)
                        .filter(token -> !token.isEmpty())
                        .forEach(token -> predicates.add(buildGenreTokenPredicate(cb, root, token)));
            }

            if (Boolean.TRUE.equals(animationOnly)) {
                predicates.add(buildGenreTokenPredicate(cb, root, "Animation"));
            }

            if (yearMin != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("year"), yearMin));
            }

            if (yearMax != null) {
                predicates.add(cb.lessThanOrEqualTo(root.get("year"), yearMax));
            }

            return predicates.isEmpty() ? cb.conjunction() : cb.and(predicates.toArray(new Predicate[0]));
        };

        // 3. Stable Sort Tie-Break (id ASC)
        Sort.Direction dir = "asc".equals(sortDirStr) ? Sort.Direction.ASC : Sort.Direction.DESC;
        Sort sortObj = Sort.by(dir, sortField).and(Sort.by(Sort.Direction.ASC, "id"));
        Pageable pageable = PageRequest.of(page, size, sortObj);

        // 4. Query & Map
        Page<Movie> moviePage = movieRepository.findAll(spec, pageable);
        List<MovieResponse> items = moviePage.getContent().stream()
                .map(MovieResponse::fromEntity)
                .collect(Collectors.toList());

        return new PageResponse<>(
                items,
                moviePage.getNumber(),
                moviePage.getSize(),
                moviePage.getTotalElements(),
                moviePage.getTotalPages(),
                moviePage.hasNext(),
                moviePage.hasPrevious()
        );
    }
}
