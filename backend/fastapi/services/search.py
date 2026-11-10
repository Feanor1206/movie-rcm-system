class SearchService:
    def __init__(self, *, registry=None, reranker=None, calibration=None):
        self.registry = registry
        self.reranker = reranker
        self.calibration = calibration

    def search(self, snapshot, query, limit=8, constraints=None):
        if snapshot is None or not snapshot.is_ready:
            return []
        index = snapshot.hybrid_index
        if index is None or not index.is_ready:
            return []
        return index.search(query, limit=limit, constraints=constraints,
                            reranker=self.reranker,
                            gpu_gate=self.registry.gpu_slot if self.registry else None,
                            calibration=self.calibration)
