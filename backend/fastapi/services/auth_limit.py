from collections import OrderedDict
from threading import Lock
from time import monotonic


class AuthRateLimiter:
    def __init__(self, limit=30, window=60, max_clients=4096):
        self.limit = limit
        self.window = window
        self.max_clients = max_clients
        self.clients = OrderedDict()
        self.lock = Lock()

    def retry_after(self, client):
        now = monotonic()
        with self.lock:
            while self.clients and next(iter(self.clients.values()))[0] <= now - self.window:
                self.clients.popitem(last=False)
            started, count = self.clients.get(client, (now, 0))
            if count >= self.limit:
                return max(1, int(started + self.window - now) + 1)
            if client not in self.clients and len(self.clients) >= self.max_clients:
                self.clients.popitem(last=False)
            self.clients[client] = (started, count + 1)
            return 0
