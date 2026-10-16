import com.dippie.moviercm.service.catalog.*;
import com.dippie.moviercm.entity.catalog.*;
import com.dippie.moviercm.repository.catalog.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Production worker/query methods with repository proxies; no Spring, DB or HTTP. */
public class CATALOG_01_F02_Probe {
    static CatalogSeries draft;
    static Object repository(Class<?> type) {
        return Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[]{type}, (p,m,a) -> {
            if (m.getName().equals("searchSeries")) return List.of(draft);
            if (m.getName().equals("findAll") || m.getName().startsWith("search")) return List.of();
            throw new UnsupportedOperationException(m.getName());
        });
    }
    static void field(Object o, String name, Object value) throws Exception {
        Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);f.set(o,value);
    }
    public static void main(String[] args) throws Exception {
        ObjectMapper mapper=new ObjectMapper();
        draft=new CatalogSeries();draft.setId("draft_secret_series");draft.setTitle("Draft needle");
        draft.setRecordJson("{\"status\":\"draft\"}");
        Constructor<?> ctor=CatalogQueryService.class.getConstructors()[0];
        Object[] repos=Arrays.stream(ctor.getParameterTypes()).map(CATALOG_01_F02_Probe::repository).toArray();
        CatalogQueryService query=(CatalogQueryService)ctor.newInstance(repos);
        List<Object> cases=new ArrayList<>();
        for(boolean writeFailure : List.of(false,true)) {
            CatalogSnapshot snap=new CatalogSnapshot("probe",1L,"hash",0,"PENDING");
            snap.setRetryCount(0);
            CatalogSnapshotRepository repository=(CatalogSnapshotRepository)Proxy.newProxyInstance(
                CatalogSnapshotRepository.class.getClassLoader(),new Class<?>[]{CatalogSnapshotRepository.class},(p,m,a)-> {
                    if(m.getName().equals("findByStatusInOrderBySnapshotVersionAsc")) return List.of(snap);
                    if(m.getName().equals("save")) return a[0];
                    throw new UnsupportedOperationException(m.getName());
                });
            CatalogSyncWorker worker=new CatalogSyncWorker(repository,query);
            Path output=Path.of(args[0],writeFailure?"directory-not-file":"snapshot.json");
            if(writeFailure) {Files.createDirectories(output);Files.writeString(output.resolve("keep.txt"),"fixture");}
            field(worker,"snapshotPath",output.toString());field(worker,"syncToken","");
            worker.processPendingSnapshots();
            cases.add(Map.of("case",writeFailure?"disk_write_fails_no_token":"no_token_no_index_ack",
                "status",snap.getStatus(),"snapshot_file_exists",Files.isRegularFile(output),
                "expected_not_ready",true));
        }
        System.out.println(mapper.writeValueAsString(Map.of("worker",cases,
            "anonymous_search_results",query.searchCatalog("needle"))));
    }
}
