import com.dippie.moviercm.service.catalog.CatalogImportService;
import com.dippie.moviercm.service.catalog.CatalogQueryService;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import java.lang.reflect.Proxy;
import java.util.*;

/** Calls current production pure methods; repositories are empty in-memory proxies. */
public class CATALOG_01_F01_LogicProbe {
    public static void main(String[] args) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        var importConstructor = CatalogImportService.class.getConstructors()[0];
        var service = (CatalogImportService) importConstructor.newInstance(new Object[importConstructor.getParameterCount()]);
        JsonNode incoming = mapper.readTree("{\"id\":\"shared\",\"title\":\"stale\",\"record\":{\"revision\":1}}");
        String oldRaw = "{\"id\":\"shared\",\"title\":\"newer\",\"record\":{\"revision\":5}}";
        var revision = service.evaluateDiff(incoming, oldRaw, "{\"revision\":5}", 5, 10);
        JsonNode reordered = mapper.readTree("{\"record\":{\"revision\":1},\"title\":\"same\",\"id\":\"shared\"}");
        String canonicalOld = "{\"id\":\"shared\",\"title\":\"same\",\"record\":{\"revision\":1}}";
        var order = service.evaluateDiff(reordered, canonicalOld, "{\"revision\":1}", 1, 1);
        var queryConstructor = CatalogQueryService.class.getConstructors()[0];
        Object[] repositories = Arrays.stream(queryConstructor.getParameterTypes())
            .map(type -> Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[]{type},
                (proxy, method, values) -> {
                    if (method.getName().equals("findAll")) return List.of();
                    throw new UnsupportedOperationException(method.getName());
                })).toArray();
        var query = (CatalogQueryService) queryConstructor.newInstance(repositories);
        System.out.println(mapper.writeValueAsString(Map.of(
            "lower_entity_revision_in_higher_package", Map.of("expected", "CONFLICT", "actual", revision.name()),
            "reordered_identical_object", Map.of("expected", "UNCHANGED", "actual", order.name()),
            "empty_db_export", query.exportSearchableCatalog())));
    }
}
