import com.dippie.moviercm.service.catalog.CatalogValidator;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import java.nio.file.Path;

/** Offline probe: calls the production validator; does not start Spring or a database. */
public class CATALOG_01_ValidatorProbe {
    public static void main(String[] args) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        CatalogValidator validator = new CatalogValidator();
        for (String arg : args) {
            JsonNode data = mapper.readTree(Path.of(arg).toFile());
            System.out.println(mapper.writeValueAsString(java.util.Map.of(
                "case", Path.of(arg).getFileName().toString(),
                "errors", validator.validate(data))));
        }
    }
}
