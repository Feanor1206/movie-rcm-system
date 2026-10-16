import com.dippie.moviercm.service.catalog.CatalogImportService;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Path;
import java.util.Map;

/** Reproduce the worker's ObjectMapper.writeValueAsString + production SHA256. */
public class CATALOG_01_F03_HashProbe {
    public static void main(String[] args) throws Exception {
        ObjectMapper mapper=new ObjectMapper();
        var payload=mapper.readTree(Path.of(args[0]).toFile());
        String serialized=mapper.writeValueAsString(payload);
        System.out.println(mapper.writeValueAsString(Map.of(
            "worker_hash",CatalogImportService.computeSha256(serialized))));
    }
}
