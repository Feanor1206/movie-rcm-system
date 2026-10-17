package com.dippie.moviercm.service.catalog;

import com.dippie.moviercm.config.StorageKeyConfig;
import com.dippie.moviercm.dto.catalog.CatalogImportResponse;
import com.dippie.moviercm.dto.catalog.CatalogValidationError;
import com.dippie.moviercm.dto.catalog.CatalogValidationResult;
import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.entity.catalog.*;
import com.dippie.moviercm.exception.CatalogConflictException;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.repository.catalog.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.File;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.*;

@Service
public class CatalogImportService {

    private static final Logger logger = LoggerFactory.getLogger(CatalogImportService.class);
    private final ObjectMapper objectMapper = new ObjectMapper();

    private final CatalogValidator validator;
    private final CatalogPackageRepository packageRepository;
    private final CatalogGenreRepository genreRepository;
    private final CatalogAttributeScaleRepository scaleRepository;
    private final CatalogSourceRepository sourceRepository;
    private final CatalogSeriesRepository seriesRepository;
    private final CatalogSeasonRepository seasonRepository;
    private final CatalogEpisodeRepository episodeRepository;
    private final CatalogSegmentRepository segmentRepository;
    private final CatalogCharacterRepository characterRepository;
    private final CatalogMediaAssetRepository mediaAssetRepository;
    private final CatalogTextTrackRepository textTrackRepository;
    private final CatalogSceneRepository sceneRepository;
    private final CatalogSnapshotRepository snapshotRepository;

    private final MediaAssetRepository legacyMediaAssetRepository;
    private final MovieRepository legacyMovieRepository;
    private final StorageKeyConfig storageKeyConfig;
    private final CatalogSyncWorker syncWorker;

    @Autowired
    public CatalogImportService(
            CatalogValidator validator,
            CatalogPackageRepository packageRepository,
            CatalogGenreRepository genreRepository,
            CatalogAttributeScaleRepository scaleRepository,
            CatalogSourceRepository sourceRepository,
            CatalogSeriesRepository seriesRepository,
            CatalogSeasonRepository seasonRepository,
            CatalogEpisodeRepository episodeRepository,
            CatalogSegmentRepository segmentRepository,
            CatalogCharacterRepository characterRepository,
            CatalogMediaAssetRepository mediaAssetRepository,
            CatalogTextTrackRepository textTrackRepository,
            CatalogSceneRepository sceneRepository,
            CatalogSnapshotRepository snapshotRepository,
            MediaAssetRepository legacyMediaAssetRepository,
            MovieRepository legacyMovieRepository,
            StorageKeyConfig storageKeyConfig,
            @Autowired(required = false) CatalogSyncWorker syncWorker) {
        this.validator = validator;
        this.packageRepository = packageRepository;
        this.genreRepository = genreRepository;
        this.scaleRepository = scaleRepository;
        this.sourceRepository = sourceRepository;
        this.seriesRepository = seriesRepository;
        this.seasonRepository = seasonRepository;
        this.episodeRepository = episodeRepository;
        this.segmentRepository = segmentRepository;
        this.characterRepository = characterRepository;
        this.mediaAssetRepository = mediaAssetRepository;
        this.textTrackRepository = textTrackRepository;
        this.sceneRepository = sceneRepository;
        this.snapshotRepository = snapshotRepository;
        this.legacyMediaAssetRepository = legacyMediaAssetRepository;
        this.legacyMovieRepository = legacyMovieRepository;
        this.storageKeyConfig = storageKeyConfig;
        this.syncWorker = syncWorker;
    }

    public static String bytesToHex(byte[] hash) {
        StringBuilder hexString = new StringBuilder();
        for (byte b : hash) {
            String hex = Integer.toHexString(0xff & b);
            if (hex.length() == 1) hexString.append('0');
            hexString.append(hex);
        }
        return hexString.toString();
    }

    public static String formatDouble(double d) {
        if (Double.isNaN(d) || Double.isInfinite(d)) return "null";
        if (d == 0.0) {
            return (Double.doubleToRawLongBits(d) == Double.doubleToRawLongBits(-0.0)) ? "-0.0" : "0.0";
        }
        String s = Double.toString(d);
        int eIdx = s.indexOf('E');
        if (eIdx == -1) {
            return s;
        }
        String mantissa = s.substring(0, eIdx);
        int exp = Integer.parseInt(s.substring(eIdx + 1));
        boolean negative = mantissa.startsWith("-");
        String absM = negative ? mantissa.substring(1) : mantissa;

        if (exp >= -4 && exp < 0) {
            int dot = absM.indexOf('.');
            String digits = (dot != -1) ? absM.substring(0, dot) + absM.substring(dot + 1) : absM;
            while (digits.endsWith("0")) {
                digits = digits.substring(0, digits.length() - 1);
            }
            int leadingZeros = -exp - 1;
            StringBuilder sb = new StringBuilder();
            if (negative) sb.append("-");
            sb.append("0.");
            for (int i = 0; i < leadingZeros; i++) sb.append("0");
            sb.append(digits);
            return sb.toString();
        } else if (exp >= 0 && exp < 16) {
            java.math.BigDecimal bd = java.math.BigDecimal.valueOf(d);
            String plain = bd.toPlainString();
            if (!plain.contains(".")) {
                plain += ".0";
            }
            return plain;
        }

        if (absM.endsWith(".0")) {
            absM = absM.substring(0, absM.length() - 2);
        }
        int absExp = Math.abs(exp);
        String expSign = exp >= 0 ? "+" : "-";
        String expStr = (absExp < 10 ? "0" : "") + absExp;
        return (negative ? "-" : "") + absM + "e" + expSign + expStr;
    }

    public static JsonNode sortJsonNode(JsonNode node) {
        if (node == null) return null;
        if (node.isDouble() || node.isFloat()) {
            return com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.rawValueNode(
                new com.fasterxml.jackson.databind.util.RawValue(formatDouble(node.asDouble()))
            );
        }
        if (node.isObject()) {
            com.fasterxml.jackson.databind.node.ObjectNode objectNode = (com.fasterxml.jackson.databind.node.ObjectNode) node;
            List<String> fieldNames = new ArrayList<>();
            objectNode.fieldNames().forEachRemaining(fieldNames::add);
            Collections.sort(fieldNames);
            com.fasterxml.jackson.databind.node.ObjectNode sorted = com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.objectNode();
            for (String field : fieldNames) {
                sorted.set(field, sortJsonNode(objectNode.get(field)));
            }
            return sorted;
        } else if (node.isArray()) {
            com.fasterxml.jackson.databind.node.ArrayNode arrayNode = (com.fasterxml.jackson.databind.node.ArrayNode) node;
            com.fasterxml.jackson.databind.node.ArrayNode sorted = com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.arrayNode();
            for (JsonNode elem : arrayNode) {
                sorted.add(sortJsonNode(elem));
            }
            return sorted;
        }
        return node;
    }

    public static String computeSha256(String input) {
        try {
            if (input == null) return "";
            String trimmed = input.trim();
            byte[] bytesToHash;
            if ((trimmed.startsWith("{") && trimmed.endsWith("}")) || (trimmed.startsWith("[") && trimmed.endsWith("]"))) {
                try {
                    ObjectMapper mapper = new ObjectMapper();
                    JsonNode root = mapper.readTree(trimmed);
                    JsonNode sorted = sortJsonNode(root);
                    String canonicalJson = mapper.writeValueAsString(sorted);
                    bytesToHash = canonicalJson.getBytes(StandardCharsets.UTF_8);
                } catch (Exception parseEx) {
                    bytesToHash = input.getBytes(StandardCharsets.UTF_8);
                }
            } else {
                bytesToHash = input.getBytes(StandardCharsets.UTF_8);
            }
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(bytesToHash);
            return bytesToHex(hash);
        } catch (Exception e) {
            throw new RuntimeException("Lỗi tính SHA-256: " + e.getMessage(), e);
        }
    }

    private Integer getIntOrNull(JsonNode node, String field) {
        if (node != null && node.hasNonNull(field) && node.get(field).isNumber()) {
            return node.get(field).asInt();
        }
        return null;
    }

    private Long getLongOrNull(JsonNode node, String field) {
        if (node != null && node.hasNonNull(field) && node.get(field).isNumber()) {
            return node.get(field).asLong();
        }
        return null;
    }

    private Double getDoubleOrNull(JsonNode node, String field) {
        if (node != null && node.hasNonNull(field) && node.get(field).isNumber()) {
            return node.get(field).asDouble();
        }
        return null;
    }

    public enum DiffStatus { CREATE, UPDATE, UNCHANGED, CONFLICT }

    private int extractRevision(JsonNode node, int defaultRevision) {
        if (node != null && node.has("record") && node.get("record").has("revision")) {
            return node.get("record").get("revision").asInt();
        }
        return defaultRevision;
    }

    private int extractExistingRevision(String recordJson, Integer entityRevision, int defaultRevision) {
        if (recordJson != null) {
            try {
                JsonNode rec = objectMapper.readTree(recordJson);
                if (rec.has("revision")) {
                    return rec.get("revision").asInt(defaultRevision);
                }
            } catch (Exception ignored) {}
        }
        return entityRevision != null ? entityRevision : defaultRevision;
    }

    public JsonNode canonicalize(JsonNode node) {
        if (node == null || node.isNull()) {
            return node;
        }
        if (node.isObject()) {
            com.fasterxml.jackson.databind.node.ObjectNode sorted = objectMapper.createObjectNode();
            Map<String, JsonNode> map = new TreeMap<>();
            Iterator<Map.Entry<String, JsonNode>> fields = node.fields();
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> entry = fields.next();
                map.put(entry.getKey(), canonicalize(entry.getValue()));
            }
            for (Map.Entry<String, JsonNode> entry : map.entrySet()) {
                sorted.set(entry.getKey(), entry.getValue());
            }
            return sorted;
        } else if (node.isArray()) {
            com.fasterxml.jackson.databind.node.ArrayNode array = objectMapper.createArrayNode();
            for (JsonNode child : node) {
                array.add(canonicalize(child));
            }
            return array;
        }
        return node;
    }

    public String computeCanonicalSha256(JsonNode node) {
        if (node == null) return "";
        try {
            JsonNode canonical = canonicalize(node);
            byte[] bytes = objectMapper.writeValueAsBytes(canonical);
            return bytesToHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (Exception e) {
            return "";
        }
    }

    public String computeCanonicalSha256(String jsonStr) {
        if (jsonStr == null || jsonStr.isBlank()) return "";
        try {
            JsonNode node = objectMapper.readTree(jsonStr);
            return computeCanonicalSha256(node);
        } catch (Exception e) {
            return computeSha256(jsonStr);
        }
    }

    public DiffStatus evaluateDiff(JsonNode incomingNode, String existingRawJson, String existingRecordJson, Integer existingEntityRev, int pkgRev) {
        if (existingRawJson == null && existingRecordJson == null) {
            return DiffStatus.CREATE;
        }
        int incomingRev = extractRevision(incomingNode, pkgRev);
        int existingRev = extractExistingRevision(existingRecordJson, existingEntityRev, 1);

        if (incomingRev < existingRev) {
            return DiffStatus.CONFLICT;
        } else if (incomingRev == existingRev) {
            String incomingHash = computeCanonicalSha256(incomingNode);
            String existingHash = computeCanonicalSha256(existingRawJson);
            if (incomingHash.equals(existingHash)) {
                return DiffStatus.UNCHANGED;
            } else {
                return DiffStatus.CONFLICT;
            }
        } else {
            return DiffStatus.UPDATE;
        }
    }

    public CatalogValidationResult validateAndPreview(JsonNode data) {
        List<CatalogValidationError> errors = validator.validate(data);
        if (!errors.isEmpty()) {
            return new CatalogValidationResult(false, errors);
        }

        CatalogValidationResult result = new CatalogValidationResult(true, errors);
        JsonNode pkg = data.get("package");
        String pkgId = pkg.path("id").asText();
        int revision = pkg.path("revision").asInt(1);
        String rawJson = data.toString();
        String contentHash = computeSha256(rawJson);

        result.setPackageId(pkgId);
        result.setRevision(revision);
        result.setContentHash(contentHash);

        int toCreate = 0;
        int toUpdate = 0;
        int unchanged = 0;
        int conflicts = 0;

        // 1. Package check
        Optional<CatalogPackage> existingPkg = packageRepository.findById(pkgId);
        if (existingPkg.isPresent()) {
            int oldRev = existingPkg.get().getRevision();
            if (revision < oldRev) {
                conflicts++;
            } else if (revision == oldRev) {
                if (contentHash.equals(existingPkg.get().getContentHash())) {
                    unchanged++;
                } else {
                    conflicts++;
                }
            } else {
                toUpdate++;
            }
        } else {
            toCreate++;
        }

        // 2. Genres
        if (data.has("genres") && data.get("genres").isArray()) {
            for (JsonNode item : data.get("genres")) {
                String id = item.path("id").asText();
                Optional<CatalogGenre> existing = genreRepository.findById(id);
                DiffStatus status = evaluateDiff(item, existing.map(CatalogGenre::getRawJson).orElse(null),
                        existing.map(CatalogGenre::getRecordJson).orElse(null), null, revision);
                if (status == DiffStatus.CREATE) toCreate++;
                else if (status == DiffStatus.UPDATE) toUpdate++;
                else if (status == DiffStatus.UNCHANGED) unchanged++;
                else if (status == DiffStatus.CONFLICT) conflicts++;
            }
        }

        // 3. Attribute Scales
        if (data.has("attribute_scales") && data.get("attribute_scales").isArray()) {
            for (JsonNode item : data.get("attribute_scales")) {
                String id = item.path("id").asText();
                Optional<CatalogAttributeScale> existing = scaleRepository.findById(id);
                DiffStatus status = evaluateDiff(item, existing.map(CatalogAttributeScale::getRawJson).orElse(null),
                        existing.map(CatalogAttributeScale::getRecordJson).orElse(null), null, revision);
                if (status == DiffStatus.CREATE) toCreate++;
                else if (status == DiffStatus.UPDATE) toUpdate++;
                else if (status == DiffStatus.UNCHANGED) unchanged++;
                else if (status == DiffStatus.CONFLICT) conflicts++;
            }
        }

        // 4. Sources
        if (data.has("sources") && data.get("sources").isArray()) {
            for (JsonNode item : data.get("sources")) {
                String id = item.path("id").asText();
                Optional<CatalogSource> existing = sourceRepository.findById(id);
                DiffStatus status = evaluateDiff(item, existing.map(CatalogSource::getRawJson).orElse(null),
                        existing.map(CatalogSource::getRecordJson).orElse(null), null, revision);
                if (status == DiffStatus.CREATE) toCreate++;
                else if (status == DiffStatus.UPDATE) toUpdate++;
                else if (status == DiffStatus.UNCHANGED) unchanged++;
                else if (status == DiffStatus.CONFLICT) conflicts++;
            }
        }

        // 5. Series
        if (data.has("series") && data.get("series").isArray()) {
            for (JsonNode item : data.get("series")) {
                String id = item.path("id").asText();
                Optional<CatalogSeries> existing = seriesRepository.findById(id);
                DiffStatus status = evaluateDiff(item, existing.map(CatalogSeries::getRawJson).orElse(null),
                        existing.map(CatalogSeries::getRecordJson).orElse(null), existing.map(CatalogSeries::getRevision).orElse(null), revision);
                if (status == DiffStatus.CREATE) toCreate++;
                else if (status == DiffStatus.UPDATE) toUpdate++;
                else if (status == DiffStatus.UNCHANGED) unchanged++;
                else if (status == DiffStatus.CONFLICT) conflicts++;
            }
        }

        // 6. Seasons
        if (data.has("seasons") && data.get("seasons").isArray()) {
            for (JsonNode item : data.get("seasons")) {
                String id = item.path("id").asText();
                Optional<CatalogSeason> existing = seasonRepository.findById(id);
                DiffStatus status = evaluateDiff(item, existing.map(CatalogSeason::getRawJson).orElse(null),
                        existing.map(CatalogSeason::getRecordJson).orElse(null), existing.map(CatalogSeason::getRevision).orElse(null), revision);
                if (status == DiffStatus.CREATE) toCreate++;
                else if (status == DiffStatus.UPDATE) toUpdate++;
                else if (status == DiffStatus.UNCHANGED) unchanged++;
                else if (status == DiffStatus.CONFLICT) conflicts++;
            }
        }

        // 7. Episodes
        if (data.has("episodes") && data.get("episodes").isArray()) {
            for (JsonNode item : data.get("episodes")) {
                String id = item.path("id").asText();
                Optional<CatalogEpisode> existing = episodeRepository.findById(id);
                DiffStatus status = evaluateDiff(item, existing.map(CatalogEpisode::getRawJson).orElse(null),
                        existing.map(CatalogEpisode::getRecordJson).orElse(null), existing.map(CatalogEpisode::getRevision).orElse(null), revision);
                if (status == DiffStatus.CREATE) toCreate++;
                else if (status == DiffStatus.UPDATE) toUpdate++;
                else if (status == DiffStatus.UNCHANGED) unchanged++;
                else if (status == DiffStatus.CONFLICT) conflicts++;
            }
        }

        // 8. Segments
        if (data.has("segments") && data.get("segments").isArray()) {
            for (JsonNode item : data.get("segments")) {
                String id = item.path("id").asText();
                Optional<CatalogSegment> existing = segmentRepository.findById(id);
                DiffStatus status = evaluateDiff(item, existing.map(CatalogSegment::getRawJson).orElse(null),
                        existing.map(CatalogSegment::getRecordJson).orElse(null), existing.map(CatalogSegment::getRevision).orElse(null), revision);
                if (status == DiffStatus.CREATE) toCreate++;
                else if (status == DiffStatus.UPDATE) toUpdate++;
                else if (status == DiffStatus.UNCHANGED) unchanged++;
                else if (status == DiffStatus.CONFLICT) conflicts++;
            }
        }

        // 9. Characters
        if (data.has("characters") && data.get("characters").isArray()) {
            for (JsonNode item : data.get("characters")) {
                String id = item.path("id").asText();
                Optional<CatalogCharacter> existing = characterRepository.findById(id);
                DiffStatus status = evaluateDiff(item, existing.map(CatalogCharacter::getRawJson).orElse(null),
                        existing.map(CatalogCharacter::getRecordJson).orElse(null), existing.map(CatalogCharacter::getRevision).orElse(null), revision);
                if (status == DiffStatus.CREATE) toCreate++;
                else if (status == DiffStatus.UPDATE) toUpdate++;
                else if (status == DiffStatus.UNCHANGED) unchanged++;
                else if (status == DiffStatus.CONFLICT) conflicts++;
            }
        }

        // 10. Media Assets
        if (data.has("media_assets") && data.get("media_assets").isArray()) {
            for (JsonNode item : data.get("media_assets")) {
                String id = item.path("id").asText();
                Optional<CatalogMediaAsset> existing = mediaAssetRepository.findById(id);
                DiffStatus status = evaluateDiff(item, existing.map(CatalogMediaAsset::getRawJson).orElse(null),
                        existing.map(CatalogMediaAsset::getRecordJson).orElse(null), existing.map(CatalogMediaAsset::getRevision).orElse(null), revision);
                if (status == DiffStatus.CREATE) toCreate++;
                else if (status == DiffStatus.UPDATE) toUpdate++;
                else if (status == DiffStatus.UNCHANGED) unchanged++;
                else if (status == DiffStatus.CONFLICT) conflicts++;
            }
        }

        // 11. Text Tracks
        if (data.has("text_tracks") && data.get("text_tracks").isArray()) {
            for (JsonNode item : data.get("text_tracks")) {
                String id = item.path("id").asText();
                Optional<CatalogTextTrack> existing = textTrackRepository.findById(id);
                DiffStatus status = evaluateDiff(item, existing.map(CatalogTextTrack::getRawJson).orElse(null),
                        existing.map(CatalogTextTrack::getRecordJson).orElse(null), existing.map(CatalogTextTrack::getRevision).orElse(null), revision);
                if (status == DiffStatus.CREATE) toCreate++;
                else if (status == DiffStatus.UPDATE) toUpdate++;
                else if (status == DiffStatus.UNCHANGED) unchanged++;
                else if (status == DiffStatus.CONFLICT) conflicts++;
            }
        }

        // 12. Scenes
        if (data.has("scenes") && data.get("scenes").isArray()) {
            for (JsonNode item : data.get("scenes")) {
                String id = item.path("id").asText();
                Optional<CatalogScene> existing = sceneRepository.findById(id);
                DiffStatus status = evaluateDiff(item, existing.map(CatalogScene::getRawJson).orElse(null),
                        existing.map(CatalogScene::getRecordJson).orElse(null), existing.map(CatalogScene::getRevision).orElse(null), revision);
                if (status == DiffStatus.CREATE) toCreate++;
                else if (status == DiffStatus.UPDATE) toUpdate++;
                else if (status == DiffStatus.UNCHANGED) unchanged++;
                else if (status == DiffStatus.CONFLICT) conflicts++;
            }
        }

        result.setToCreate(toCreate);
        result.setToUpdate(toUpdate);
        result.setUnchanged(unchanged);
        result.setConflicts(conflicts);

        return result;
    }

    @Transactional
    public synchronized CatalogImportResponse importPackage(JsonNode data) {
        // 1. Re-validate in transaction
        List<CatalogValidationError> errors = validator.validate(data);
        if (!errors.isEmpty()) {
            throw new IllegalArgumentException("Dữ liệu package không hợp lệ: " + errors.get(0).getMessage());
        }

        JsonNode pkg = data.get("package");
        String pkgId = pkg.path("id").asText();
        int revision = pkg.path("revision").asInt(1);
        String version = pkg.path("version").asText("1.0.0");
        String defaultLanguage = pkg.path("default_language").asText("vi");
        String importMode = pkg.path("import_mode").asText("upsert");
        String referenceScope = pkg.path("reference_scope").asText("self_contained");
        String rawJson = data.toString();
        String contentHash = computeSha256(rawJson);

        Instant createdInstant = Instant.parse(pkg.path("created_at").asText(Instant.now().toString()));
        LocalDateTime createdAt = LocalDateTime.ofInstant(createdInstant, ZoneOffset.UTC);

        // 2. Revision & Idempotency policy check for Package
        Optional<CatalogPackage> existingOpt = packageRepository.findById(pkgId);
        if (existingOpt.isPresent()) {
            CatalogPackage existing = existingOpt.get();
            if (existing.getRevision() > revision) {
                throw new CatalogConflictException("Từ chối import: Package revision (" + revision +
                        ") thấp hơn revision hiện tại trong hệ thống (" + existing.getRevision() + ")");
            } else if (existing.getRevision() == revision) {
                if (contentHash.equals(existing.getContentHash())) {
                    logger.info("Package {} rev {} trùng khớp hoàn toàn content hash, ghi nhận idempotent unchanged.", pkgId, revision);
                    CatalogImportResponse resp = new CatalogImportResponse();
                    resp.setSuccess(true);
                    resp.setPackageId(pkgId);
                    resp.setRevision(revision);
                    resp.setContentHash(contentHash);
                    resp.setImportedAt(existing.getImportedAt());
                    String latestStatus = snapshotRepository != null
                            ? snapshotRepository.findTopByOrderBySnapshotVersionDesc().map(CatalogSnapshot::getStatus).orElse("READY")
                            : "READY";
                    resp.setIndexStatus(latestStatus);
                    resp.setMessage("Idempotent import: Package đã tồn tại với cùng revision và nội dung.");
                    return resp;
                } else {
                    throw new CatalogConflictException("Xung đột revision: Package revision " + revision +
                            " đã tồn tại nhưng có content hash khác.");
                }
            }
        }

        // 3. Save Package record (preserving managed entity and @Version optLockVersion)
        CatalogPackage pkgEntity = existingOpt.orElse(new CatalogPackage());
        pkgEntity.setId(pkgId);
        pkgEntity.setVersion(version);
        pkgEntity.setRevision(revision);
        pkgEntity.setDefaultLanguage(defaultLanguage);
        pkgEntity.setImportMode(importMode);
        pkgEntity.setReferenceScope(referenceScope);
        pkgEntity.setDescription(pkg.hasNonNull("description") ? pkg.get("description").asText() : null);
        pkgEntity.setContentHash(contentHash);
        pkgEntity.setStatus("COMMITTED");
        pkgEntity.setErrorMessage(null);
        if (pkgEntity.getCreatedAt() == null) {
            pkgEntity.setCreatedAt(createdAt);
        }
        pkgEntity.setImportedAt(LocalDateTime.now());
        packageRepository.save(pkgEntity);

        Map<String, Integer> counts = new HashMap<>();

        // 4. Upsert Genres
        int genreCount = 0;
        if (data.has("genres") && data.get("genres").isArray()) {
            for (JsonNode g : data.get("genres")) {
                String gid = g.path("id").asText();
                Optional<CatalogGenre> existingOptGen = genreRepository.findById(gid);
                DiffStatus diff = evaluateDiff(g, existingOptGen.map(CatalogGenre::getRawJson).orElse(null),
                        existingOptGen.map(CatalogGenre::getRecordJson).orElse(null), null, revision);
                if (diff == DiffStatus.CONFLICT) {
                    throw new CatalogConflictException("Xung đột revision tại thể loại [" + gid + "]");
                }

                CatalogGenre genre = existingOptGen.orElse(new CatalogGenre());
                genre.setId(gid);
                genre.setLabelsJson(g.hasNonNull("labels") ? g.get("labels").toString() : (g.hasNonNull("name") ? objectMapper.createObjectNode().put("vi", g.get("name").asText()).toString() : "{}"));
                genre.setDescription(g.hasNonNull("description") ? g.get("description").asText() : null);
                genre.setAliasesJson(g.hasNonNull("aliases") ? g.get("aliases").toString() : null);
                genre.setRecordJson(g.hasNonNull("record") ? g.get("record").toString() : null);
                genre.setRawJson(g.toString());
                genre.setUpdatedAt(LocalDateTime.now());
                genreRepository.save(genre);
                genreCount++;
            }
        }
        counts.put("genres", genreCount);

        // 5. Upsert Attribute Scales
        int scaleCount = 0;
        if (data.has("attribute_scales") && data.get("attribute_scales").isArray()) {
            for (JsonNode sc : data.get("attribute_scales")) {
                String sid = sc.path("id").asText();
                Optional<CatalogAttributeScale> existingOptScale = scaleRepository.findById(sid);
                DiffStatus diff = evaluateDiff(sc, existingOptScale.map(CatalogAttributeScale::getRawJson).orElse(null),
                        existingOptScale.map(CatalogAttributeScale::getRecordJson).orElse(null), null, revision);
                if (diff == DiffStatus.CONFLICT) {
                    throw new CatalogConflictException("Xung đột revision tại thang đo [" + sid + "]");
                }

                CatalogAttributeScale scale = existingOptScale.orElse(new CatalogAttributeScale());
                scale.setId(sid);
                scale.setName(sc.path("name").asText());
                scale.setDefinition(sc.hasNonNull("definition") ? sc.get("definition").asText() : null);
                scale.setMinimum(sc.path("minimum").asDouble(0.0));
                scale.setMaximum(sc.path("maximum").asDouble(1.0));
                scale.setLevelsJson(sc.hasNonNull("levels") ? sc.get("levels").toString() : "[]");
                scale.setSourceIdsJson(sc.hasNonNull("source_ids") ? sc.get("source_ids").toString() : null);
                scale.setVersion(sc.path("version").asText("1.0.0"));
                scale.setRecordJson(sc.hasNonNull("record") ? sc.get("record").toString() : null);
                scale.setRawJson(sc.toString());
                scale.setUpdatedAt(LocalDateTime.now());
                scaleRepository.save(scale);
                scaleCount++;
            }
        }
        counts.put("attributeScales", scaleCount);

        // 6. Upsert Sources
        int sourceCount = 0;
        if (data.has("sources") && data.get("sources").isArray()) {
            for (JsonNode src : data.get("sources")) {
                String srcId = src.path("id").asText();
                Optional<CatalogSource> existingOptSrc = sourceRepository.findById(srcId);
                DiffStatus diff = evaluateDiff(src, existingOptSrc.map(CatalogSource::getRawJson).orElse(null),
                        existingOptSrc.map(CatalogSource::getRecordJson).orElse(null), null, revision);
                if (diff == DiffStatus.CONFLICT) {
                    throw new CatalogConflictException("Xung đột revision tại nguồn [" + srcId + "]");
                }

                CatalogSource source = existingOptSrc.orElse(new CatalogSource());
                source.setId(srcId);
                source.setKind(src.path("kind").asText(src.path("source_type").asText("web")));
                source.setTitle(src.path("title").asText(src.path("name").asText(null)));
                source.setUri(src.path("url").asText(null));
                source.setRetrievedAt(src.path("retrieved_at").asText(null));
                source.setNote(src.hasNonNull("note") ? src.get("note").asText() : (src.hasNonNull("notes") ? src.get("notes").asText() : null));
                source.setRecordJson(src.hasNonNull("record") ? src.get("record").toString() : null);
                source.setRawJson(src.toString());
                source.setUpdatedAt(LocalDateTime.now());
                sourceRepository.save(source);
                sourceCount++;
            }
        }
        counts.put("sources", sourceCount);

        // 7. Upsert Series
        int seriesCount = 0;
        if (data.has("series") && data.get("series").isArray()) {
            for (JsonNode s : data.get("series")) {
                String sid = s.path("id").asText();
                Optional<CatalogSeries> existingOptSer = seriesRepository.findById(sid);
                DiffStatus diff = evaluateDiff(s, existingOptSer.map(CatalogSeries::getRawJson).orElse(null),
                        existingOptSer.map(CatalogSeries::getRecordJson).orElse(null), existingOptSer.map(CatalogSeries::getRevision).orElse(null), revision);
                if (diff == DiffStatus.CONFLICT) {
                    throw new CatalogConflictException("Xung đột revision tại bộ phim [" + sid + "]");
                }

                CatalogSeries series = existingOptSer.orElse(new CatalogSeries());
                series.setId(sid);
                series.setTitle(s.path("title").asText());
                series.setOriginalTitle(s.path("original_title").asText(null));
                series.setAliasesJson(s.hasNonNull("aliases") ? s.get("aliases").toString() : null);
                series.setTranslationsJson(s.hasNonNull("translations") ? s.get("translations").toString() : null);
                series.setSynopsis(s.path("synopsis").asText(null));
                series.setReleaseStatus(s.hasNonNull("release_status") ? s.get("release_status").asText() : (s.hasNonNull("status") ? s.get("status").asText() : null));
                Integer startYr = getIntOrNull(s, "release_year_start");
                if (startYr == null) startYr = getIntOrNull(s, "release_year");
                series.setReleaseYearStart(startYr);
                series.setReleaseYearEnd(getIntOrNull(s, "release_year_end"));
                series.setOriginCountriesJson(s.hasNonNull("origin_countries") ? s.get("origin_countries").toString() : (s.hasNonNull("origin_country") ? objectMapper.createArrayNode().add(s.get("origin_country").asText()).toString() : null));
                series.setOriginalLanguagesJson(s.hasNonNull("original_languages") ? s.get("original_languages").toString() : (s.hasNonNull("original_language") ? objectMapper.createArrayNode().add(s.get("original_language").asText()).toString() : null));
                series.setGenreIdsJson(s.hasNonNull("genre_ids") ? s.get("genre_ids").toString() : null);
                series.setCharacterIdsJson(s.hasNonNull("character_ids") ? s.get("character_ids").toString() : null);
                series.setKeywordsJson(s.hasNonNull("tags") ? s.get("tags").toString() : (s.hasNonNull("keywords") ? s.get("keywords").toString() : null));
                series.setThemesJson(s.hasNonNull("themes") ? s.get("themes").toString() : null);
                series.setAttributesJson(s.hasNonNull("attributes") ? s.get("attributes").toString() : null);
                series.setRatingsJson(s.hasNonNull("ratings") ? s.get("ratings").toString() : null);
                series.setAdvisoriesJson(s.hasNonNull("content_advisory") ? s.get("content_advisory").toString() : null);
                series.setArtworksJson(s.hasNonNull("artwork") ? s.get("artwork").toString() : (s.hasNonNull("artworks") ? s.get("artworks").toString() : null));
                series.setExternalIdsJson(s.hasNonNull("external_ids") ? s.get("external_ids").toString() : null);
                series.setRecordJson(s.hasNonNull("record") ? s.get("record").toString() : null);
                series.setRevision(extractRevision(s, revision));
                series.setRawJson(s.toString());
                series.setUpdatedAt(LocalDateTime.now());
                seriesRepository.save(series);

                syncSeriesToLegacyMovie(series);
                seriesCount++;
            }
        }
        counts.put("series", seriesCount);

        // 8. Upsert Seasons
        int seasonCount = 0;
        if (data.has("seasons") && data.get("seasons").isArray()) {
            for (JsonNode sea : data.get("seasons")) {
                String seaId = sea.path("id").asText();
                Optional<CatalogSeason> existingOptSea = seasonRepository.findById(seaId);
                DiffStatus diff = evaluateDiff(sea, existingOptSea.map(CatalogSeason::getRawJson).orElse(null),
                        existingOptSea.map(CatalogSeason::getRecordJson).orElse(null), existingOptSea.map(CatalogSeason::getRevision).orElse(null), revision);
                if (diff == DiffStatus.CONFLICT) {
                    throw new CatalogConflictException("Xung đột revision tại mùa phim [" + seaId + "]");
                }

                CatalogSeason season = existingOptSea.orElse(new CatalogSeason());
                season.setId(seaId);
                season.setSeriesId(sea.path("series_id").asText());
                Integer seasonNum = getIntOrNull(sea, "number");
                if (seasonNum == null) seasonNum = getIntOrNull(sea, "season_number");
                season.setNumber(seasonNum);
                season.setTitle(sea.path("title").asText());
                season.setSynopsis(sea.hasNonNull("synopsis") ? sea.get("synopsis").asText() : (sea.hasNonNull("description") ? sea.get("description").asText() : null));
                season.setKind(sea.path("kind").asText("standard"));
                season.setReleaseDate(sea.hasNonNull("release_date") ? sea.get("release_date").asText() : (sea.hasNonNull("release_year") ? sea.get("release_year").asText() : null));
                season.setArtworksJson(sea.hasNonNull("artwork") ? sea.get("artwork").toString() : (sea.hasNonNull("artworks") ? sea.get("artworks").toString() : null));
                season.setRecordJson(sea.hasNonNull("record") ? sea.get("record").toString() : null);
                season.setRevision(extractRevision(sea, revision));
                season.setRawJson(sea.toString());
                season.setUpdatedAt(LocalDateTime.now());
                seasonRepository.save(season);
                seasonCount++;
            }
        }
        counts.put("seasons", seasonCount);

        // 9. Upsert Episodes
        int episodeCount = 0;
        if (data.has("episodes") && data.get("episodes").isArray()) {
            for (JsonNode ep : data.get("episodes")) {
                String epId = ep.path("id").asText();
                Optional<CatalogEpisode> existingOptEp = episodeRepository.findById(epId);
                DiffStatus diff = evaluateDiff(ep, existingOptEp.map(CatalogEpisode::getRawJson).orElse(null),
                        existingOptEp.map(CatalogEpisode::getRecordJson).orElse(null), existingOptEp.map(CatalogEpisode::getRevision).orElse(null), revision);
                if (diff == DiffStatus.CONFLICT) {
                    throw new CatalogConflictException("Xung đột revision tại tập phim [" + epId + "]");
                }

                CatalogEpisode episode = existingOptEp.orElse(new CatalogEpisode());
                episode.setId(epId);
                episode.setSeriesId(ep.path("series_id").asText());
                episode.setSeasonId(ep.hasNonNull("season_id") ? ep.get("season_id").asText() : null);
                Integer epNum = getIntOrNull(ep, "number");
                if (epNum == null) epNum = getIntOrNull(ep, "episode_number");
                episode.setNumber(epNum);
                episode.setTitle(ep.path("title").asText());
                episode.setAliasesJson(ep.hasNonNull("aliases") ? ep.get("aliases").toString() : null);
                episode.setKind(ep.hasNonNull("kind") ? ep.get("kind").asText() : (ep.hasNonNull("episode_type") ? ep.get("episode_type").asText() : "standard"));
                episode.setSynopsis(ep.path("synopsis").asText(null));
                episode.setDurationMs(getLongOrNull(ep, "duration_ms"));
                episode.setReleaseDate(ep.hasNonNull("release_date") ? ep.get("release_date").asText() : (ep.hasNonNull("air_date") ? ep.get("air_date").asText() : null));
                episode.setPrimaryLanguage(ep.path("primary_language").asText(null));
                episode.setGenreIdsJson(ep.hasNonNull("genre_ids") ? ep.get("genre_ids").toString() : null);
                episode.setCharacterIdsJson(ep.hasNonNull("character_ids") ? ep.get("character_ids").toString() : null);
                episode.setKeywordsJson(ep.hasNonNull("tags") ? ep.get("tags").toString() : (ep.hasNonNull("keywords") ? ep.get("keywords").toString() : null));
                episode.setAttributesJson(ep.hasNonNull("attributes") ? ep.get("attributes").toString() : null);
                episode.setRatingsJson(ep.hasNonNull("ratings") ? ep.get("ratings").toString() : null);
                episode.setArtworksJson(ep.hasNonNull("artwork") ? ep.get("artwork").toString() : (ep.hasNonNull("artworks") ? ep.get("artworks").toString() : null));
                episode.setLinksJson(ep.hasNonNull("links") ? ep.get("links").toString() : (ep.hasNonNull("external_ids") ? ep.get("external_ids").toString() : null));
                episode.setRecordJson(ep.hasNonNull("record") ? ep.get("record").toString() : null);
                episode.setRevision(extractRevision(ep, revision));
                episode.setRawJson(ep.toString());
                episode.setUpdatedAt(LocalDateTime.now());
                episodeRepository.save(episode);

                syncEpisodeToLegacyMovie(episode);
                episodeCount++;
            }
        }
        counts.put("episodes", episodeCount);

        // 10. Upsert Segments
        int segmentCount = 0;
        if (data.has("segments") && data.get("segments").isArray()) {
            for (JsonNode seg : data.get("segments")) {
                String segId = seg.path("id").asText();
                Optional<CatalogSegment> existingOptSeg = segmentRepository.findById(segId);
                DiffStatus diff = evaluateDiff(seg, existingOptSeg.map(CatalogSegment::getRawJson).orElse(null),
                        existingOptSeg.map(CatalogSegment::getRecordJson).orElse(null), existingOptSeg.map(CatalogSegment::getRevision).orElse(null), revision);
                if (diff == DiffStatus.CONFLICT) {
                    throw new CatalogConflictException("Xung đột revision tại phân đoạn [" + segId + "]");
                }

                CatalogSegment segment = existingOptSeg.orElse(new CatalogSegment());
                segment.setId(segId);
                segment.setEpisodeId(seg.path("episode_id").asText());
                segment.setPosition(seg.path("position").asInt(1));
                segment.setTitle(seg.path("title").asText());
                segment.setSynopsis(seg.path("synopsis").asText(null));
                segment.setEpisodeStartMs(getLongOrNull(seg, "episode_start_ms"));
                segment.setEpisodeEndMs(getLongOrNull(seg, "episode_end_ms"));
                segment.setCharacterIdsJson(seg.hasNonNull("character_ids") ? seg.get("character_ids").toString() : null);
                segment.setKeywordsJson(seg.hasNonNull("tags") ? seg.get("tags").toString() : (seg.hasNonNull("keywords") ? seg.get("keywords").toString() : null));
                segment.setAttributesJson(seg.hasNonNull("attributes") ? seg.get("attributes").toString() : null);
                segment.setPlotFactsJson(seg.hasNonNull("plot_facts") ? seg.get("plot_facts").toString() : null);
                segment.setRecordJson(seg.hasNonNull("record") ? seg.get("record").toString() : null);
                segment.setRevision(extractRevision(seg, revision));
                segment.setRawJson(seg.toString());
                segment.setUpdatedAt(LocalDateTime.now());
                segmentRepository.save(segment);
                segmentCount++;
            }
        }
        counts.put("segments", segmentCount);

        // 11. Upsert Characters
        int characterCount = 0;
        if (data.has("characters") && data.get("characters").isArray()) {
            for (JsonNode c : data.get("characters")) {
                String cid = c.path("id").asText();
                Optional<CatalogCharacter> existingOptChar = characterRepository.findById(cid);
                DiffStatus diff = evaluateDiff(c, existingOptChar.map(CatalogCharacter::getRawJson).orElse(null),
                        existingOptChar.map(CatalogCharacter::getRecordJson).orElse(null), existingOptChar.map(CatalogCharacter::getRevision).orElse(null), revision);
                if (diff == DiffStatus.CONFLICT) {
                    throw new CatalogConflictException("Xung đột revision tại nhân vật [" + cid + "]");
                }

                CatalogCharacter character = existingOptChar.orElse(new CatalogCharacter());
                character.setId(cid);
                character.setName(c.path("name").asText());
                character.setDescription(c.path("description").asText(null));
                character.setSeriesIdsJson(c.hasNonNull("series_ids") ? c.get("series_ids").toString() : null);
                character.setRole(c.path("role").asText(null));
                character.setVoiceCreditsJson(c.hasNonNull("voice_credits") ? c.get("voice_credits").toString() : (c.hasNonNull("voice_actors") ? c.get("voice_actors").toString() : null));
                character.setAliasesJson(c.hasNonNull("aliases") ? c.get("aliases").toString() : null);
                character.setTraitsJson(c.hasNonNull("traits") ? c.get("traits").toString() : null);
                character.setRelationshipsJson(c.hasNonNull("relationships") ? c.get("relationships").toString() : null);
                character.setArtworksJson(c.hasNonNull("artwork") ? c.get("artwork").toString() : (c.hasNonNull("artworks") ? c.get("artworks").toString() : null));
                character.setRecordJson(c.hasNonNull("record") ? c.get("record").toString() : null);
                character.setRevision(extractRevision(c, revision));
                character.setRawJson(c.toString());
                character.setUpdatedAt(LocalDateTime.now());
                characterRepository.save(character);
                characterCount++;
            }
        }
        counts.put("characters", characterCount);

        // 12. Upsert Media Assets & Sync to Streaming Registry
        int mediaCount = 0;
        if (data.has("media_assets") && data.get("media_assets").isArray()) {
            for (JsonNode ma : data.get("media_assets")) {
                String mid = ma.path("id").asText();
                Optional<CatalogMediaAsset> existingOptAsset = mediaAssetRepository.findById(mid);
                DiffStatus diff = evaluateDiff(ma, existingOptAsset.map(CatalogMediaAsset::getRawJson).orElse(null),
                        existingOptAsset.map(CatalogMediaAsset::getRecordJson).orElse(null), existingOptAsset.map(CatalogMediaAsset::getRevision).orElse(null), revision);
                if (diff == DiffStatus.CONFLICT) {
                    throw new CatalogConflictException("Xung đột revision tại media asset [" + mid + "]");
                }

                CatalogMediaAsset asset = existingOptAsset.orElse(new CatalogMediaAsset());
                asset.setId(mid);

                JsonNode storage = ma.get("storage");
                String provider = "local";
                if (storage != null && storage.hasNonNull("provider")) {
                    String pStr = storage.get("provider").asText();
                    if ("drive".equalsIgnoreCase(pStr) || "google_drive".equalsIgnoreCase(pStr)) {
                        provider = "drive";
                    }
                }
                asset.setStorageProvider(provider);

                String storageKey = storage != null ? storage.path("storage_key").asText(storage.path("root_storage_key").asText(null)) : null;
                if (storageKey != null && !storageKey.isBlank()) {
                    if (!storageKeyConfig.isAllowed(provider, storageKey)) {
                        throw new IllegalArgumentException("storage_key '" + storageKey + "' không được phép cho nhà cung cấp: " + provider);
                    }
                }
                asset.setStorageKey(storageKey != null ? storageKey : "local_main");
                asset.setRelativePath(storage != null ? storage.path("relative_path").asText(null) : null);
                asset.setDriveFileId(storage != null ? storage.path("drive_file_id").asText(null) : null);
                asset.setDriveFolderId(storage != null ? storage.path("drive_folder_id").asText(null) : null);

                Long sizeBytes = getLongOrNull(ma, "size_bytes");
                if (sizeBytes == null) sizeBytes = getLongOrNull(ma, "byte_length");
                asset.setSizeBytes(sizeBytes != null ? sizeBytes : 0L);
                asset.setSha256(ma.path("sha256").asText(null));
                asset.setDurationMs(getLongOrNull(ma, "duration_ms"));
                asset.setRole(ma.path("role").asText("feature"));
                asset.setEditionLabel(ma.hasNonNull("edition_label") ? ma.get("edition_label").asText() : ma.path("edition").asText(null));
                asset.setSpokenLanguagesJson(ma.hasNonNull("spoken_languages") ? ma.get("spoken_languages").toString() : (ma.hasNonNull("language") ? objectMapper.createArrayNode().add(ma.get("language").asText()).toString() : null));
                asset.setContentType("video");
                asset.setTechnicalJson(ma.hasNonNull("technical") ? ma.get("technical").toString() : null);
                asset.setCoverageJson(ma.hasNonNull("coverage") ? ma.get("coverage").toString() : null);
                asset.setAccessPolicy(ma.hasNonNull("access_policy") ? ma.get("access_policy").asText("public") : "public");
                asset.setEnabled(ma.path("enabled").asBoolean(true));
                asset.setRecordJson(ma.hasNonNull("record") ? ma.get("record").toString() : null);
                asset.setRevision(extractRevision(ma, revision));
                asset.setRawJson(ma.toString());
                asset.setUpdatedAt(LocalDateTime.now());
                mediaAssetRepository.save(asset);

                // Sync to legacy media_assets for direct HTTP 206 streaming via /api/media/stream/{mid}
                syncToLegacyMediaAsset(asset);
                mediaCount++;
            }
        }
        counts.put("mediaAssets", mediaCount);

        // 13. Upsert Text Tracks
        int trackCount = 0;
        if (data.has("text_tracks") && data.get("text_tracks").isArray()) {
            for (JsonNode tt : data.get("text_tracks")) {
                String tid = tt.path("id").asText();
                Optional<CatalogTextTrack> existingOptTrack = textTrackRepository.findById(tid);
                DiffStatus diff = evaluateDiff(tt, existingOptTrack.map(CatalogTextTrack::getRawJson).orElse(null),
                        existingOptTrack.map(CatalogTextTrack::getRecordJson).orElse(null), existingOptTrack.map(CatalogTextTrack::getRevision).orElse(null), revision);
                if (diff == DiffStatus.CONFLICT) {
                    throw new CatalogConflictException("Xung đột revision tại phụ đề / text track [" + tid + "]");
                }

                CatalogTextTrack track = existingOptTrack.orElse(new CatalogTextTrack());
                track.setId(tid);
                track.setMediaAssetId(tt.path("media_asset_id").asText());
                track.setKind(tt.path("kind").asText("subtitles"));
                track.setLanguage(tt.path("language").asText("vi"));
                track.setLabel(tt.path("label").asText(null));
                track.setFormat(tt.path("format").asText("vtt"));
                track.setExternalFileJson(tt.hasNonNull("external_file") ? tt.get("external_file").toString() : null);
                track.setCuesJson(tt.hasNonNull("cues") ? tt.get("cues").toString() : null);
                track.setRecordJson(tt.hasNonNull("record") ? tt.get("record").toString() : null);
                track.setRevision(extractRevision(tt, revision));
                track.setRawJson(tt.toString());
                track.setUpdatedAt(LocalDateTime.now());
                textTrackRepository.save(track);
                trackCount++;
            }
        }
        counts.put("textTracks", trackCount);

        // 14. Upsert Scenes
        int sceneCount = 0;
        if (data.has("scenes") && data.get("scenes").isArray()) {
            for (JsonNode sc : data.get("scenes")) {
                String scId = sc.path("id").asText();
                Optional<CatalogScene> existingOptScene = sceneRepository.findById(scId);
                DiffStatus diff = evaluateDiff(sc, existingOptScene.map(CatalogScene::getRawJson).orElse(null),
                        existingOptScene.map(CatalogScene::getRecordJson).orElse(null), existingOptScene.map(CatalogScene::getRevision).orElse(null), revision);
                if (diff == DiffStatus.CONFLICT) {
                    throw new CatalogConflictException("Xung đột revision tại cảnh phim [" + scId + "]");
                }

                CatalogScene scene = existingOptScene.orElse(new CatalogScene());
                scene.setId(scId);
                scene.setMediaAssetId(sc.path("media_asset_id").asText());
                scene.setEpisodeId(sc.path("episode_id").asText());
                scene.setSegmentId(sc.hasNonNull("segment_id") ? sc.get("segment_id").asText() : null);
                scene.setStartMs(sc.path("start_ms").asLong(0L));
                scene.setEndMs(sc.path("end_ms").asLong(0L));
                scene.setTitle(sc.path("title").asText(null));
                scene.setSummary(sc.path("summary").asText(null));
                scene.setVisualDescription(sc.hasNonNull("visual_description") ? sc.get("visual_description").asText() : sc.path("visual_summary").asText(null));
                scene.setCharacterIdsJson(sc.hasNonNull("character_ids") ? sc.get("character_ids").toString() : null);
                scene.setVisualTagsJson(sc.hasNonNull("visual_tags") ? sc.get("visual_tags").toString() : (sc.hasNonNull("keywords") ? sc.get("keywords").toString() : null));
                scene.setSoundEventsJson(sc.hasNonNull("sound_events") ? sc.get("sound_events").toString() : null);
                scene.setTranscriptCueIdsJson(sc.hasNonNull("transcript_cue_ids") ? sc.get("transcript_cue_ids").toString() : null);
                scene.setRecordJson(sc.hasNonNull("record") ? sc.get("record").toString() : null);
                scene.setRevision(extractRevision(sc, revision));
                scene.setRawJson(sc.toString());
                scene.setUpdatedAt(LocalDateTime.now());
                sceneRepository.save(scene);
                sceneCount++;
            }
        }
        counts.put("scenes", sceneCount);

        // 15. Assign global monotonic generation and record snapshot in catalog_snapshots outbox
        int totalItems = genreCount + scaleCount + sourceCount + seriesCount + seasonCount +
                episodeCount + segmentCount + characterCount + mediaCount + trackCount + sceneCount;
        long nextGeneration = snapshotRepository != null
                ? snapshotRepository.findMaxSnapshotVersion() + 1L
                : 1L;

        CatalogSnapshot snapshot = new CatalogSnapshot(
                "snap_" + System.currentTimeMillis() + "_" + pkgId + "_g" + nextGeneration,
                nextGeneration,
                contentHash,
                totalItems,
                "PENDING"
        );
        snapshot.setRetryCount(0);
        if (snapshotRepository != null) {
            snapshotRepository.save(snapshot);
        }

        // 16. Trigger Outbox Worker asynchronously after transaction commit
        if (org.springframework.transaction.support.TransactionSynchronizationManager.isSynchronizationActive()) {
            org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(
                    new org.springframework.transaction.support.TransactionSynchronization() {
                        @Override
                        public void afterCommit() {
                            java.util.concurrent.CompletableFuture.runAsync(() -> {
                                try {
                                    if (syncWorker != null) {
                                        syncWorker.processPendingSnapshots();
                                    }
                                } catch (Exception e) {
                                    logger.warn("Không thể kích hoạt outbox sync worker sau commit: {}", e.getMessage());
                                }
                            });
                        }
                    }
            );
        } else {
            java.util.concurrent.CompletableFuture.runAsync(() -> {
                try {
                    if (syncWorker != null) {
                        syncWorker.processPendingSnapshots();
                    }
                } catch (Exception e) {
                    logger.warn("Không thể kích hoạt outbox sync worker: {}", e.getMessage());
                }
            });
        }

        CatalogImportResponse response = new CatalogImportResponse();
        response.setSuccess(true);
        response.setImportId(snapshot.getId());
        response.setPackageId(pkgId);
        response.setRevision(revision);
        response.setContentHash(contentHash);
        response.setImportedAt(LocalDateTime.now());
        response.setCounts(counts);
        response.setIndexStatus("PENDING");
        response.setMessage("Nhập dữ liệu package thành công và ghi nhận outbox snapshot.");

        return response;
    }

    private void syncSeriesToLegacyMovie(CatalogSeries s) {
        String mid = s.getId();
        if (!legacyMovieRepository.existsById(mid)) {
            Integer yr = s.getReleaseYearStart() != null ? s.getReleaseYearStart() : 2026;
            Movie m = Movie.builder()
                    .id(mid)
                    .title(s.getTitle())
                    .year(yr)
                    .rating(0.0)
                    .runtime("Series")
                    .genres("Animation")
                    .description(s.getSynopsis() != null ? s.getSynopsis() : "")
                    .build();
            legacyMovieRepository.save(m);
        }
    }

    private void syncEpisodeToLegacyMovie(CatalogEpisode ep) {
        String mid = ep.getId();
        if (!legacyMovieRepository.existsById(mid)) {
            long durSec = ep.getDurationMs() != null ? ep.getDurationMs() / 1000 : 1200;
            long mins = durSec / 60;
            Movie m = Movie.builder()
                    .id(mid)
                    .title(ep.getTitle())
                    .year(2026)
                    .rating(0.0)
                    .runtime(mins + "m")
                    .genres("Animation")
                    .description(ep.getSynopsis() != null ? ep.getSynopsis() : "")
                    .build();
            legacyMovieRepository.save(m);
        }
    }

    private void syncToLegacyMediaAsset(CatalogMediaAsset cAsset) {
        String aid = cAsset.getId();
        String provider = "drive".equalsIgnoreCase(cAsset.getStorageProvider()) ? "drive" : "local";
        String relPath = cAsset.getRelativePath();
        if (relPath == null || relPath.isBlank()) {
            relPath = cAsset.getDriveFileId() != null ? cAsset.getDriveFileId() + ".mp4" : "media/" + aid + ".mp4";
        }

        // Determine movie ID mapping from coverage or default to asset id
        String movieId = aid;
        if (cAsset.getCoverageJson() != null) {
            try {
                JsonNode cov = objectMapper.readTree(cAsset.getCoverageJson());
                if (cov.isArray() && cov.size() > 0) {
                    movieId = cov.get(0).path("episode_id").asText(aid);
                }
            } catch (Exception ignored) {}
        }

        // Ensure movie exists in legacy repository
        if (!legacyMovieRepository.existsById(movieId)) {
            Movie m = Movie.builder()
                    .id(movieId)
                    .title("Phim liên kết " + aid)
                    .year(2026)
                    .rating(0.0)
                    .genres("Animation")
                    .build();
            legacyMovieRepository.save(m);
        }

        // Access Policy evaluation (C2)
        boolean isPublic = false;
        if (cAsset.getAccessPolicy() != null) {
            isPublic = "public".equalsIgnoreCase(cAsset.getAccessPolicy());
        }

        // MIME type evaluation: check container or role
        String mimeType = "video/mp4";
        String role = cAsset.getRole() != null ? cAsset.getRole() : "feature";
        if (role.toLowerCase().contains("audio") || (cAsset.getContentType() != null && cAsset.getContentType().toLowerCase().contains("audio"))) {
            mimeType = "audio/mp4";
        }

        MediaAsset legacy = legacyMediaAssetRepository.findById(aid).orElse(new MediaAsset());
        legacy.setId(aid);
        legacy.setMovieId(movieId);
        legacy.setKind(role);
        legacy.setStorageProvider(provider);
        legacy.setStorageKey(cAsset.getStorageKey());
        legacy.setRelativePath(relPath);
        legacy.setVersion("v1_" + aid);
        legacy.setMimeType(mimeType);
        legacy.setByteLength(cAsset.getSizeBytes() != null ? cAsset.getSizeBytes() : 0L);
        legacy.setDurationSeconds(cAsset.getDurationMs() != null ? cAsset.getDurationMs() / 1000.0 : null);
        legacy.setPublic(isPublic);
        legacy.setAvailable(Boolean.TRUE.equals(cAsset.getEnabled()));
        legacyMediaAssetRepository.save(legacy);
    }
}
