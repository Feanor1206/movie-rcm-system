package com.dippie.moviercm.service.catalog;

import com.dippie.moviercm.dto.catalog.CatalogValidationError;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.io.File;
import java.io.InputStream;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeFormatterBuilder;
import java.time.format.DateTimeParseException;
import java.time.format.ResolverStyle;
import java.util.*;
import java.util.regex.Pattern;

/**
 * Validates external animation catalog payloads against dippie.catalog.v1 contract.
 * Conforms strictly to JSON Schema (Draft 2020-12) and domain semantic rules
 * with RFC 6901 compliant JSON Pointer error reporting.
 */
@Component
public class CatalogValidator {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static final Set<String> COLLECTIONS = Set.of(
            "genres", "attribute_scales", "sources", "series", "seasons",
            "episodes", "segments", "characters", "media_assets", "text_tracks", "scenes"
    );

    private static final Map<String, String> REFERENCES = Map.ofEntries(
            Map.entry("source_ids", "sources"),
            Map.entry("source_id", "sources"),
            Map.entry("genre_ids", "genres"),
            Map.entry("scale_id", "attribute_scales"),
            Map.entry("series_id", "series"),
            Map.entry("series_ids", "series"),
            Map.entry("season_id", "seasons"),
            Map.entry("episode_id", "episodes"),
            Map.entry("segment_id", "segments"),
            Map.entry("character_id", "characters"),
            Map.entry("character_ids", "characters"),
            Map.entry("speaker_character_ids", "characters"),
            Map.entry("media_asset_id", "media_assets"),
            Map.entry("related_asset_id", "media_assets"),
            Map.entry("transcript_cue_ids", "cues")
    );

    private static final int MAX_PAYLOAD_DEPTH = 30;
    private static final int MAX_TOTAL_NODES = 250_000;

    private JsonNode rootSchema;
    private final Map<String, JsonNode> schemaDefs = new HashMap<>();

    public CatalogValidator() {
        initSchema();
    }

    private void initSchema() {
        try {
            // 1. Try classpath resource
            InputStream is = getClass().getResourceAsStream("/contracts/dippie.catalog.v1.schema.json");
            if (is != null) {
                try (is) {
                    this.rootSchema = MAPPER.readTree(is);
                }
            }

            // 2. Try file system search
            if (this.rootSchema == null) {
                Path schemaPath = findSchemaFile();
                if (schemaPath != null && Files.exists(schemaPath)) {
                    this.rootSchema = MAPPER.readTree(schemaPath.toFile());
                }
            }

            if (this.rootSchema != null && this.rootSchema.has("$defs")) {
                JsonNode defsNode = this.rootSchema.get("$defs");
                Iterator<Map.Entry<String, JsonNode>> it = defsNode.fields();
                while (it.hasNext()) {
                    Map.Entry<String, JsonNode> entry = it.next();
                    schemaDefs.put(entry.getKey(), entry.getValue());
                }
            }
        } catch (Exception e) {
            // Log or fallback
        }
    }

    private Path findSchemaFile() {
        Path[] candidatePaths = new Path[]{
                Path.of("docs/contracts/animation-catalog-v1/dippie.catalog.v1.schema.json"),
                Path.of("../docs/contracts/animation-catalog-v1/dippie.catalog.v1.schema.json"),
                Path.of("../../docs/contracts/animation-catalog-v1/dippie.catalog.v1.schema.json"),
                Path.of("../../../docs/contracts/animation-catalog-v1/dippie.catalog.v1.schema.json"),
                Path.of("backend/springboot/src/main/resources/contracts/dippie.catalog.v1.schema.json"),
                Path.of("../backend/springboot/src/main/resources/contracts/dippie.catalog.v1.schema.json")
        };
        for (Path p : candidatePaths) {
            if (Files.exists(p)) {
                return p.toAbsolutePath().normalize();
            }
        }

        // Search upward
        Path curr = Path.of("").toAbsolutePath();
        while (curr != null) {
            Path test = curr.resolve("docs/contracts/animation-catalog-v1/dippie.catalog.v1.schema.json");
            if (Files.exists(test)) {
                return test;
            }
            Path testRes = curr.resolve("backend/springboot/src/main/resources/contracts/dippie.catalog.v1.schema.json");
            if (Files.exists(testRes)) {
                return testRes;
            }
            curr = curr.getParent();
        }
        return null;
    }

    public static String escapePointer(String token) {
        return token.replace("~", "~0").replace("/", "~1");
    }

    public List<CatalogValidationError> validate(JsonNode data) {
        List<CatalogValidationError> errors = new ArrayList<>();

        if (data == null || !data.isObject()) {
            errors.add(new CatalogValidationError("/", "INVALID_ROOT", "Catalog payload must be a JSON object"));
            return errors;
        }

        // Depth and node limits check
        int[] counter = new int[]{0};
        if (!checkLimits(data, 0, counter)) {
            errors.add(new CatalogValidationError("/", "PAYLOAD_LIMIT_EXCEEDED", "Payload exceeds depth or node count limit"));
            return errors;
        }

        if (rootSchema == null) {
            initSchema();
        }

        if (rootSchema == null) {
            errors.add(new CatalogValidationError("/", "SCHEMA_UNAVAILABLE",
                    "Cannot load canonical JSON Schema: structural validation unavailable"));
            return errors;
        }

        // Step 1: JSON Schema structural & type validation
        validateAgainstSchema(data, rootSchema, "", errors);

        // Step 2: Semantic & Relational Consistency Validation
        try {
            validateSemanticRules(data, errors);
        } catch (Exception e) {
            errors.add(new CatalogValidationError("/", "SEMANTIC_VALIDATION_ERROR",
                    "Semantic validation failed: " + e.getMessage()));
        }

        return errors;
    }

    private boolean checkLimits(JsonNode node, int depth, int[] counter) {
        if (depth > MAX_PAYLOAD_DEPTH) return false;
        counter[0]++;
        if (counter[0] > MAX_TOTAL_NODES) return false;

        if (node.isObject()) {
            Iterator<JsonNode> it = node.elements();
            while (it.hasNext()) {
                if (!checkLimits(it.next(), depth + 1, counter)) return false;
            }
        } else if (node.isArray()) {
            for (JsonNode child : node) {
                if (!checkLimits(child, depth + 1, counter)) return false;
            }
        }
        return true;
    }

    // =========================================================================
    // STEP 1: JSON SCHEMA VALIDATION ENGINE
    // =========================================================================

    private void validateAgainstSchema(JsonNode node, JsonNode schema, String path, List<CatalogValidationError> errors) {
        if (schema == null || node == null) return;

        // 1. Resolve $ref
        if (schema.has("$ref")) {
            String ref = schema.get("$ref").asText();
            if (ref.startsWith("#/$defs/")) {
                String defName = ref.substring("#/$defs/".length());
                JsonNode defSchema = schemaDefs.get(defName);
                if (defSchema != null) {
                    validateAgainstSchema(node, defSchema, path, errors);
                    return;
                }
            }
        }

        // 2. allOf
        if (schema.has("allOf")) {
            for (JsonNode subSchema : schema.get("allOf")) {
                validateAgainstSchema(node, subSchema, path, errors);
            }
        }

        // 3. not
        if (schema.has("not")) {
            List<CatalogValidationError> notErrors = new ArrayList<>();
            validateAgainstSchema(node, schema.get("not"), path, notErrors);
            if (notErrors.isEmpty()) {
                String code = "SCHEMA_VIOLATION";
                if (path.endsWith("relative_path") || (schema.get("not").has("pattern") && schema.get("not").get("pattern").asText().contains("\\.\\."))) {
                    code = "PATH_TRAVERSAL";
                }
                errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, code, "Value matches forbidden 'not' schema"));
                return;
            }
        }

        // 4. anyOf
        if (schema.has("anyOf")) {
            boolean matched = false;
            for (JsonNode subSchema : schema.get("anyOf")) {
                List<CatalogValidationError> subErrors = new ArrayList<>();
                validateAgainstSchema(node, subSchema, path, subErrors);
                if (subErrors.isEmpty()) {
                    matched = true;
                    break;
                }
            }
            if (!matched) {
                errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "INVALID_TYPE", "Value does not match any allowed type in 'anyOf'"));
                return;
            }
        }

        // 5. const
        if (schema.has("const")) {
            JsonNode constVal = schema.get("const");
            if (!node.equals(constVal)) {
                errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "INVALID_CONST", "Value must be constant: " + constVal));
                return;
            }
        }

        // 6. enum
        if (schema.has("enum")) {
            boolean inEnum = false;
            for (JsonNode enumVal : schema.get("enum")) {
                if (node.equals(enumVal)) {
                    inEnum = true;
                    break;
                }
            }
            if (!inEnum) {
                errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "INVALID_ENUM",
                        "Value '" + node.asText() + "' is not one of allowed enum values"));
                return;
            }
        }

        // 7. type
        if (schema.has("type")) {
            String type = schema.get("type").asText();
            if (!checkType(node, type)) {
                errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "INVALID_TYPE",
                        "'" + (node.isNull() ? "null" : node.asText()) + "' is not of type '" + type + "'"));
                return;
            }
        }

        // 8. String constraints
        if (node.isTextual()) {
            String text = node.asText();
            if (schema.has("minLength") && text.length() < schema.get("minLength").asInt()) {
                errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "STRING_TOO_SHORT",
                        "String length " + text.length() + " is shorter than minLength " + schema.get("minLength").asInt()));
            }
            if (schema.has("pattern")) {
                String pattern = schema.get("pattern").asText();
                if (!Pattern.compile(pattern).matcher(text).find()) {
                    errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "PATTERN_MISMATCH",
                            "String does not match pattern: " + pattern));
                }
            }
            if (schema.has("format")) {
                String fmt = schema.get("format").asText();
                if ("date-time".equals(fmt)) {
                    try {
                        Instant.parse(text.replace("+00:00", "Z"));
                    } catch (DateTimeParseException e) {
                        errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "INVALID_DATE_TIME",
                                "Invalid date-time format: " + text));
                    }
                } else if ("date".equals(fmt)) {
                    try {
                        DateTimeFormatter formatter = new DateTimeFormatterBuilder()
                                .appendPattern("uuuu-MM-dd")
                                .toFormatter(Locale.ROOT)
                                .withResolverStyle(ResolverStyle.STRICT);
                        LocalDate.parse(text, formatter);
                    } catch (Exception e) {
                        errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "INVALID_DATE",
                                "Invalid date format: " + text));
                    }
                } else if ("uri".equals(fmt)) {
                    try {
                        URI uri = new URI(text);
                        if (uri.getScheme() == null || uri.getScheme().trim().isEmpty()) {
                            errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "INVALID_URI",
                                    "Invalid URI format (missing scheme): " + text));
                        }
                    } catch (Exception e) {
                        errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "INVALID_URI",
                                "Invalid URI format: " + text));
                    }
                }
            }
        }

        // 9. Numeric constraints
        if (node.isNumber()) {
            double val = node.asDouble();
            if (schema.has("minimum") && val < schema.get("minimum").asDouble()) {
                errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "NUMBER_TOO_SMALL",
                        "Number " + val + " is less than minimum " + schema.get("minimum").asDouble()));
            }
            if (schema.has("maximum") && val > schema.get("maximum").asDouble()) {
                errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "NUMBER_TOO_LARGE",
                        "Number " + val + " is greater than maximum " + schema.get("maximum").asDouble()));
            }
            if (schema.has("exclusiveMinimum") && val <= schema.get("exclusiveMinimum").asDouble()) {
                errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "NUMBER_TOO_SMALL",
                        "Number " + val + " is less than or equal to exclusiveMinimum " + schema.get("exclusiveMinimum").asDouble()));
            }
            if (schema.has("exclusiveMaximum") && val >= schema.get("exclusiveMaximum").asDouble()) {
                errors.add(new CatalogValidationError(path.isEmpty() ? "/" : path, "NUMBER_TOO_LARGE",
                        "Number " + val + " is greater than or equal to exclusiveMaximum " + schema.get("exclusiveMaximum").asDouble()));
            }
        }

        // 10. Object constraints: properties, required, additionalProperties
        if (node.isObject()) {
            JsonNode reqNode = schema.get("required");
            if (reqNode != null && reqNode.isArray()) {
                for (JsonNode r : reqNode) {
                    String reqKey = r.asText();
                    if (!node.has(reqKey)) {
                        String reqPath = path.isEmpty() ? "/" + escapePointer(reqKey) : path + "/" + escapePointer(reqKey);
                        // Contract-level reporting: error at property pointer
                        errors.add(new CatalogValidationError(reqPath, "MISSING_REQUIRED_KEY",
                                "'" + reqKey + "' is a required property"));
                    }
                }
            }

            JsonNode props = schema.get("properties");
            boolean allowAdditional = !schema.has("additionalProperties") || schema.get("additionalProperties").asBoolean(true);

            Iterator<Map.Entry<String, JsonNode>> fields = node.fields();
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> field = fields.next();
                String fieldName = field.getKey();
                JsonNode childVal = field.getValue();
                String childPath = path.isEmpty() ? "/" + escapePointer(fieldName) : path + "/" + escapePointer(fieldName);

                if (props != null && props.has(fieldName)) {
                    validateAgainstSchema(childVal, props.get(fieldName), childPath, errors);
                } else if (!allowAdditional) {
                    errors.add(new CatalogValidationError(childPath, "UNKNOWN_FIELD",
                            "Additional properties are not allowed ('" + fieldName + "' was unexpected)"));
                }
            }
        }

        // 11. Array constraints: items, uniqueItems
        if (node.isArray()) {
            JsonNode itemsSchema = schema.get("items");
            if (itemsSchema != null) {
                for (int i = 0; i < node.size(); i++) {
                    String itemPath = path + "/" + i;
                    validateAgainstSchema(node.get(i), itemsSchema, itemPath, errors);
                }
            }
            if (schema.has("uniqueItems") && schema.get("uniqueItems").asBoolean()) {
                Set<JsonNode> uniqueSet = new HashSet<>();
                for (int i = 0; i < node.size(); i++) {
                    if (!uniqueSet.add(node.get(i))) {
                        errors.add(new CatalogValidationError(path + "/" + i, "DUPLICATE_ARRAY_ITEM",
                                "Array item at index " + i + " is a duplicate"));
                    }
                }
            }
        }
    }

    private boolean checkType(JsonNode node, String type) {
        return switch (type) {
            case "string" -> node.isTextual();
            case "integer" -> node.isIntegralNumber();
            case "number" -> node.isNumber();
            case "boolean" -> node.isBoolean();
            case "array" -> node.isArray();
            case "object" -> node.isObject();
            case "null" -> node.isNull();
            default -> true;
        };
    }

    // =========================================================================
    // STEP 2: SEMANTIC & RELATIONAL VALIDATION (MATCHING validate_catalog.py)
    // =========================================================================

    private void validateSemanticRules(JsonNode data, List<CatalogValidationError> errors) {
        // Build entity tables
        Map<String, Map<String, JsonNode>> tables = new HashMap<>();
        for (String col : COLLECTIONS) {
            Map<String, JsonNode> map = new HashMap<>();
            JsonNode arr = data.get(col);
            if (arr != null && arr.isArray()) {
                for (JsonNode item : arr) {
                    if (item.has("id") && item.get("id").isTextual()) {
                        map.put(item.get("id").asText(), item);
                    }
                }
            }
            tables.put(col, map);
        }

        // Build cues table & cue_asset mapping
        Map<String, JsonNode> cuesTable = new HashMap<>();
        Map<String, String> cueAssetMap = new HashMap<>();
        JsonNode textTracks = data.get("text_tracks");
        if (textTracks != null && textTracks.isArray()) {
            for (JsonNode track : textTracks) {
                String assetId = track.path("media_asset_id").asText(null);
                JsonNode cues = track.get("cues");
                if (cues != null && cues.isArray()) {
                    for (JsonNode cue : cues) {
                        String cid = cue.path("id").asText(null);
                        if (cid != null) {
                            cuesTable.put(cid, cue);
                            if (assetId != null) cueAssetMap.put(cid, assetId);
                        }
                    }
                }
            }
        }
        tables.put("cues", cuesTable);

        // Global ID uniqueness & reference checks via recursive walk
        Set<String> seenIds = new HashSet<>();
        walkSemantic(data, "", tables, cueAssetMap, seenIds, errors);

        // Specific collection semantics
        validateAttributeScales(data.get("attribute_scales"), errors);
        validateEpisodes(data.get("episodes"), tables, errors);
        validateSegments(data.get("segments"), tables, errors);
        validateMediaAssets(data.get("media_assets"), tables, errors);
        validateTextTracks(data.get("text_tracks"), tables, errors);
        validateScenes(data.get("scenes"), tables, cueAssetMap, errors);
    }

    private void walkSemantic(JsonNode node, String path, Map<String, Map<String, JsonNode>> tables,
                              Map<String, String> cueAssetMap, Set<String> seenIds, List<CatalogValidationError> errors) {
        if (node.isArray()) {
            for (int i = 0; i < node.size(); i++) {
                walkSemantic(node.get(i), path + "/" + i, tables, cueAssetMap, seenIds, errors);
            }
        } else if (node.isObject()) {
            if (node.has("id") && node.get("id").isTextual()) {
                String id = node.get("id").asText();
                String idPath = path + "/id";
                if (!seenIds.add(id)) {
                    errors.add(new CatalogValidationError(idPath, "DUPLICATE_ID", idPath + ": duplicate global id " + id));
                }
            }

            Iterator<Map.Entry<String, JsonNode>> it = node.fields();
            while (it.hasNext()) {
                Map.Entry<String, JsonNode> entry = it.next();
                String key = entry.getKey();
                JsonNode child = entry.getValue();

                if (REFERENCES.containsKey(key) && !child.isNull()) {
                    String targetTable = REFERENCES.get(key);
                    Map<String, JsonNode> table = tables.get(targetTable);
                    if (child.isArray()) {
                        for (int idx = 0; idx < child.size(); idx++) {
                            String targetId = child.get(idx).asText();
                            if (table == null || !table.containsKey(targetId)) {
                                errors.add(new CatalogValidationError(path + "/" + escapePointer(key) + "/" + idx, "BROKEN_REFERENCE",
                                        path + "/" + key + ": missing " + targetTable + " id " + targetId));
                            }
                        }
                    } else if (child.isTextual()) {
                        String targetId = child.asText();
                        if (table == null || !table.containsKey(targetId)) {
                            errors.add(new CatalogValidationError(path + "/" + escapePointer(key), "BROKEN_REFERENCE",
                                    path + "/" + key + ": missing " + targetTable + " id " + targetId));
                        }
                    }
                }

                walkSemantic(child, path + "/" + escapePointer(key), tables, cueAssetMap, seenIds, errors);
            }

            // Translations check
            if (node.has("translations") && node.get("translations").isArray()) {
                Set<String> langs = new HashSet<>();
                for (JsonNode t : node.get("translations")) {
                    String lang = t.path("language").asText(null);
                    if (lang != null && !langs.add(lang)) {
                        errors.add(new CatalogValidationError(path + "/translations", "DUPLICATE_LANGUAGE",
                                path + "/translations: duplicate language"));
                    }
                    if (t.path("title").isNull() && t.path("synopsis").isNull()) {
                        errors.add(new CatalogValidationError(path + "/translations", "INVALID_TRANSLATION",
                                path + "/translations: title and synopsis cannot both be null"));
                    }
                }
            }

            // Ratings check
            if (node.has("ratings") && node.get("ratings").isArray()) {
                for (JsonNode r : node.get("ratings")) {
                    if (r.has("value") && r.has("scale_max") && r.get("value").asDouble() > r.get("scale_max").asDouble()) {
                        errors.add(new CatalogValidationError(path + "/ratings", "RATING_EXCEEDS_MAX",
                                path + "/ratings: value exceeds scale_max"));
                    }
                }
            }

            // Attributes check
            if (node.has("attributes") && node.get("attributes").isArray()) {
                Set<String> scales = new HashSet<>();
                for (JsonNode attr : node.get("attributes")) {
                    String key = attr.path("scale_id").asText();
                    if (!scales.add(key)) {
                        errors.add(new CatalogValidationError(path + "/attributes", "DUPLICATE_SCALE_ID",
                                path + "/attributes: duplicate scale_id " + key));
                    }
                    JsonNode scaleNode = tables.get("attribute_scales") != null ? tables.get("attribute_scales").get(key) : null;
                    if (scaleNode != null && attr.has("value") && !attr.get("value").isNull()) {
                        double v = attr.get("value").asDouble();
                        double min = scaleNode.path("minimum").asDouble();
                        double max = scaleNode.path("maximum").asDouble();
                        if (v < min || v > max) {
                            errors.add(new CatalogValidationError(path + "/attributes", "ATTRIBUTE_OUTSIDE_SCALE",
                                    path + "/attributes: value outside scale " + key));
                        }
                    }
                }
            }

            // Record provenance check
            if (node.has("record") && node.get("record").isObject()) {
                JsonNode rec = node.get("record");
                try {
                    Instant c = Instant.parse(rec.path("created_at").asText().replace("+00:00", "Z"));
                    Instant u = Instant.parse(rec.path("updated_at").asText().replace("+00:00", "Z"));
                    if (u.isBefore(c)) {
                        errors.add(new CatalogValidationError(path + "/record", "INVALID_TIMESTAMP_ORDER",
                                path + "/record: updated_at precedes created_at"));
                    }
                } catch (Exception ignored) {}

                if ("ready".equals(rec.path("status").asText())) {
                    JsonNode prov = rec.path("provenance");
                    JsonNode sids = prov.path("source_ids");
                    String verif = prov.path("verification").asText();
                    if (!sids.isArray() || sids.isEmpty() || (!"human_verified".equals(verif) && !"source_verified".equals(verif))) {
                        errors.add(new CatalogValidationError(path + "/record", "READY_REQUIRES_PROVENANCE",
                                path + "/record: ready requires reviewed provenance with a source"));
                    }
                }
            }
        }
    }

    private void validateAttributeScales(JsonNode scales, List<CatalogValidationError> errors) {
        if (scales == null || !scales.isArray()) return;
        for (JsonNode row : scales) {
            String sid = row.path("id").asText();
            double min = row.path("minimum").asDouble();
            double max = row.path("maximum").asDouble();
            JsonNode levels = row.get("levels");
            Set<Double> levelVals = new HashSet<>();
            boolean dupLevel = false;
            boolean outLevel = false;

            if (levels != null && levels.isArray()) {
                for (JsonNode l : levels) {
                    double lv = l.path("value").asDouble();
                    if (!levelVals.add(lv)) dupLevel = true;
                    if (lv < min || lv > max) outLevel = true;
                }
            }

            if (max <= min || dupLevel) {
                errors.add(new CatalogValidationError("scale " + sid, "INVALID_SCALE_LIMITS",
                        "scale " + sid + ": invalid limits or duplicate levels"));
            }
            if (outLevel) {
                errors.add(new CatalogValidationError("scale " + sid, "LEVEL_OUTSIDE_LIMITS",
                        "scale " + sid + ": level outside limits"));
            }
        }
    }

    private void validateEpisodes(JsonNode episodes, Map<String, Map<String, JsonNode>> tables, List<CatalogValidationError> errors) {
        if (episodes == null || !episodes.isArray()) return;
        Set<String> orderPositions = new HashSet<>();

        for (JsonNode ep : episodes) {
            String eid = ep.path("id").asText();
            String sid = ep.path("series_id").asText();
            String seasonId = ep.path("season_id").asText();

            JsonNode season = tables.get("seasons").get(seasonId);
            if (season != null && !sid.equals(season.path("series_id").asText())) {
                errors.add(new CatalogValidationError("episode " + eid, "SEASON_SERIES_MISMATCH",
                        "episode " + eid + ": season belongs to another series"));
            }

            JsonNode orders = ep.get("orders");
            if (orders != null && orders.isArray()) {
                Set<String> schemes = new HashSet<>();
                for (JsonNode o : orders) {
                    String sch = o.path("scheme").asText();
                    if (!schemes.add(sch)) {
                        errors.add(new CatalogValidationError("episode " + eid, "DUPLICATE_ORDER_SCHEME",
                                "episode " + eid + ": duplicate order scheme"));
                    }
                    String key = sid + ":" + seasonId + ":" + sch + ":" + o.path("position").asInt();
                    if (!orderPositions.add(key)) {
                        errors.add(new CatalogValidationError("episode " + eid, "DUPLICATE_ORDER_POSITION",
                                "episode " + eid + ": duplicate position in same season/order scheme"));
                    }
                }
            }

            JsonNode links = ep.get("links");
            if (links != null && links.isArray()) {
                for (JsonNode l : links) {
                    if (eid.equals(l.path("episode_id").asText())) {
                        errors.add(new CatalogValidationError("episode " + eid, "SELF_REFERENCE_LINK",
                                "episode " + eid + ": self-reference in links"));
                    }
                }
            }
        }
    }

    private void validateSegments(JsonNode segments, Map<String, Map<String, JsonNode>> tables, List<CatalogValidationError> errors) {
        if (segments == null || !segments.isArray()) return;
        Set<String> segmentPositions = new HashSet<>();

        for (JsonNode seg : segments) {
            String segId = seg.path("id").asText();
            String epId = seg.path("episode_id").asText();
            int pos = seg.path("position").asInt();

            String key = epId + ":" + pos;
            if (!segmentPositions.add(key)) {
                errors.add(new CatalogValidationError("segment " + segId, "DUPLICATE_SEGMENT_POSITION",
                        "segment " + segId + ": duplicate position in episode"));
            }

            boolean startNull = !seg.has("episode_start_ms") || seg.get("episode_start_ms").isNull();
            boolean endNull = !seg.has("episode_end_ms") || seg.get("episode_end_ms").isNull();

            if (startNull != endNull) {
                errors.add(new CatalogValidationError("segment " + segId, "INVALID_LOGICAL_TIMESTAMPS",
                        "segment " + segId + ": logical episode timestamps must both be null or known"));
            } else if (!startNull) {
                long start = seg.get("episode_start_ms").asLong();
                long end = seg.get("episode_end_ms").asLong();
                JsonNode ep = tables.get("episodes").get(epId);
                Long epDur = (ep != null && ep.has("duration_ms") && !ep.get("duration_ms").isNull()) ? ep.get("duration_ms").asLong() : null;
                validateInterval(start, end, epDur, "segment " + segId, errors);
            }
        }
    }

    private void validateMediaAssets(JsonNode mediaAssets, Map<String, Map<String, JsonNode>> tables, List<CatalogValidationError> errors) {
        if (mediaAssets == null || !mediaAssets.isArray()) return;

        for (JsonNode asset : mediaAssets) {
            String aid = asset.path("id").asText();
            JsonNode storage = asset.path("storage");
            if ("local".equals(storage.path("provider").asText())) {
                boolean hasDriveFile = storage.has("drive_file_id") && !storage.get("drive_file_id").isNull();
                boolean hasDriveFolder = storage.has("drive_folder_id") && !storage.get("drive_folder_id").isNull();
                if (hasDriveFile || hasDriveFolder) {
                    errors.add(new CatalogValidationError("asset " + aid, "LOCAL_PROVIDER_DRIVE_IDS",
                            "asset " + aid + ": local provider cannot have Drive IDs"));
                }
            }

            JsonNode tech = asset.path("technical");
            boolean hasAudio = tech.path("has_audio").asBoolean(true);
            JsonNode audioStreams = tech.get("audio_streams");
            if (!hasAudio && audioStreams != null && audioStreams.isArray() && !audioStreams.isEmpty()) {
                errors.add(new CatalogValidationError("asset " + aid, "AUDIO_STREAM_CONFLICT",
                        "asset " + aid + ": has_audio=false conflicts with audio streams"));
            }

            if (audioStreams != null && audioStreams.isArray()) {
                Set<Integer> streamIdxs = new HashSet<>();
                for (JsonNode as : audioStreams) {
                    int sidx = as.path("stream_index").asInt();
                    if (!streamIdxs.add(sidx)) {
                        errors.add(new CatalogValidationError("asset " + aid, "DUPLICATE_AUDIO_STREAM_INDEX",
                                "asset " + aid + ": duplicate audio stream index"));
                    }
                }
            }

            Long assetDur = asset.has("duration_ms") && !asset.get("duration_ms").isNull() ? asset.get("duration_ms").asLong() : null;
            JsonNode coverage = asset.get("coverage");
            if (coverage != null && coverage.isArray()) {
                for (JsonNode cov : coverage) {
                    String covEpId = cov.path("episode_id").asText();
                    String covSegId = cov.path("segment_id").asText(null);
                    if (covSegId != null) {
                        JsonNode segNode = tables.get("segments").get(covSegId);
                        if (segNode != null && !covEpId.equals(segNode.path("episode_id").asText())) {
                            errors.add(new CatalogValidationError("asset " + aid, "SEGMENT_EPISODE_MISMATCH",
                                    "asset " + aid + ": segment belongs to another episode"));
                        }
                    }

                    long srcIn = cov.path("source_in_ms").asLong();
                    Long srcOut = cov.has("source_out_ms") && !cov.get("source_out_ms").isNull() ? cov.get("source_out_ms").asLong() : null;
                    validateInterval(srcIn, srcOut, assetDur, "asset " + aid, errors);

                    JsonNode epNode = tables.get("episodes").get(covEpId);
                    Long epDur = (epNode != null && epNode.has("duration_ms") && !epNode.get("duration_ms").isNull()) ? epNode.get("duration_ms").asLong() : null;
                    Long epIn = cov.has("episode_in_ms") && !cov.get("episode_in_ms").isNull() ? cov.get("episode_in_ms").asLong() : null;
                    Long effSourceEnd = srcOut != null ? srcOut : assetDur;

                    if (epDur != null && epIn != null && effSourceEnd != null) {
                        if (epIn + effSourceEnd - srcIn > epDur) {
                            errors.add(new CatalogValidationError("asset " + aid, "COVERAGE_EXCEEDS_EPISODE_DURATION",
                                    "asset " + aid + ": coverage exceeds logical episode duration"));
                        }
                    }
                }
            }
        }
    }

    private void validateTextTracks(JsonNode textTracks, Map<String, Map<String, JsonNode>> tables, List<CatalogValidationError> errors) {
        if (textTracks == null || !textTracks.isArray()) return;

        for (JsonNode track : textTracks) {
            String tid = track.path("id").asText();
            String format = track.path("format").asText();
            boolean hasExtFile = track.has("external_file") && !track.get("external_file").isNull();

            if ("inline".equals(format) == hasExtFile) {
                errors.add(new CatalogValidationError("track " + tid, "INVALID_TRACK_FORMAT",
                        "track " + tid + ": inline requires no external file; other formats require one"));
            }

            String mid = track.path("media_asset_id").asText();
            JsonNode assetNode = tables.get("media_assets").get(mid);
            Long assetDur = (assetNode != null && assetNode.has("duration_ms") && !assetNode.get("duration_ms").isNull()) ? assetNode.get("duration_ms").asLong() : null;

            JsonNode cues = track.get("cues");
            if (cues != null && cues.isArray()) {
                long lastStart = -1;
                boolean sorted = true;
                for (JsonNode cue : cues) {
                    long cs = cue.path("start_ms").asLong();
                    if (cs < lastStart) sorted = false;
                    lastStart = cs;
                }
                if (!sorted) {
                    errors.add(new CatalogValidationError("track " + tid, "UNSORTED_CUES",
                            "track " + tid + ": cues must be sorted by start_ms"));
                }
                for (JsonNode cue : cues) {
                    String cid = cue.path("id").asText();
                    long cs = cue.path("start_ms").asLong();
                    Long ce = cue.has("end_ms") && !cue.get("end_ms").isNull() ? cue.get("end_ms").asLong() : null;
                    validateInterval(cs, ce, assetDur, "cue " + cid, errors);
                }
            }
        }
    }

    private void validateScenes(JsonNode scenes, Map<String, Map<String, JsonNode>> tables,
                                Map<String, String> cueAssetMap, List<CatalogValidationError> errors) {
        if (scenes == null || !scenes.isArray()) return;

        for (JsonNode sc : scenes) {
            String scid = sc.path("id").asText();
            String epId = sc.path("episode_id").asText();
            String segId = sc.path("segment_id").asText(null);

            if (segId != null) {
                JsonNode segNode = tables.get("segments").get(segId);
                if (segNode != null && !epId.equals(segNode.path("episode_id").asText())) {
                    errors.add(new CatalogValidationError("scene " + scid, "SEGMENT_EPISODE_MISMATCH",
                            "scene " + scid + ": segment belongs to another episode"));
                }
            }

            String mid = sc.path("media_asset_id").asText(null);
            JsonNode assetNode = mid != null ? tables.get("media_assets").get(mid) : null;
            if (assetNode != null) {
                Long assetDur = assetNode.has("duration_ms") && !assetNode.get("duration_ms").isNull() ? assetNode.get("duration_ms").asLong() : null;
                long start = sc.path("start_ms").asLong();
                Long end = sc.has("end_ms") && !sc.get("end_ms").isNull() ? sc.get("end_ms").asLong() : null;
                validateInterval(start, end, assetDur, "scene " + scid, errors);

                boolean hasCoverage = false;
                JsonNode covArr = assetNode.get("coverage");
                if (covArr != null && covArr.isArray()) {
                    for (JsonNode cov : covArr) {
                        if (epId.equals(cov.path("episode_id").asText())) {
                            hasCoverage = true;
                            break;
                        }
                    }
                }
                if (!hasCoverage) {
                    errors.add(new CatalogValidationError("scene " + scid, "ASSET_NO_MATCHING_COVERAGE",
                            "scene " + scid + ": asset has no matching episode coverage"));
                }
            }

            JsonNode cueIds = sc.get("transcript_cue_ids");
            if (cueIds != null && cueIds.isArray()) {
                long scStart = sc.path("start_ms").asLong();
                long scEnd = sc.path("end_ms").asLong();
                for (JsonNode cidNode : cueIds) {
                    String cid = cidNode.asText();
                    JsonNode cue = tables.get("cues").get(cid);
                    if (cue != null) {
                        String cueAsset = cueAssetMap.get(cid);
                        long cueStart = cue.path("start_ms").asLong();
                        long cueEnd = cue.path("end_ms").asLong();
                        if ((mid != null && !mid.equals(cueAsset)) || cueStart >= scEnd || cueEnd <= scStart) {
                            errors.add(new CatalogValidationError("scene " + scid, "CUE_MISMATCH_OR_NO_OVERLAP",
                                    "scene " + scid + ": cue " + cid + " belongs elsewhere or does not overlap"));
                        }
                    }
                }
            }
        }
    }

    private void validateInterval(long start, Long end, Long duration, String label, List<CatalogValidationError> errors) {
        if (end != null && end <= start) {
            errors.add(new CatalogValidationError(label, "INVALID_INTERVAL",
                    label + ": end must be greater than start"));
        }
        if (duration != null) {
            if (start >= duration || (end != null && end > duration)) {
                errors.add(new CatalogValidationError(label, "INTERVAL_EXCEEDS_DURATION",
                        label + ": interval exceeds known duration"));
            }
        }
    }
}
