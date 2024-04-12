from collections import OrderedDict
import logging
import threading

from oslo_config import cfg
import wrapt

from aprsd.packets import seen_list
from aprsd.utils import objectstore


CONF = cfg.CONF
LOG = logging.getLogger("APRSD")


class PacketList(objectstore.ObjectStoreMixin):
    _instance = None
    lock = threading.Lock()
    _total_rx: int = 0
    _total_tx: int = 0

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._maxlen = 100
            cls.data = {
                "types": {},
                "packets": OrderedDict(),
            }
        return cls._instance

    @wrapt.synchronized(lock)
    def rx(self, packet):
        """Add a packet that was received."""
        self._total_rx += 1
        self._add(packet)
        ptype = packet.__class__.__name__
        if not ptype in self.data["types"]:
            self.data["types"][ptype] = {"tx": 0, "rx": 0}
        self.data["types"][ptype]["rx"] += 1
        seen_list.SeenList().update_seen(packet)

    @wrapt.synchronized(lock)
    def tx(self, packet):
        """Add a packet that was received."""
        self._total_tx += 1
        self._add(packet)
        ptype = packet.__class__.__name__
        if not ptype in self.data["types"]:
            self.data["types"][ptype] = {"tx": 0, "rx": 0}
        self.data["types"][ptype]["tx"] += 1
        seen_list.SeenList().update_seen(packet)

    @wrapt.synchronized(lock)
    def add(self, packet):
        self._add(packet)

    def _add(self, packet):
        if packet.key in self.data["packets"]:
            self.data["packets"].move_to_end(packet.key)
        elif len(self.data["packets"]) == self.maxlen:
            self.data["packets"].popitem(last=False)
        self.data["packets"][packet.key] = packet

    def copy(self):
        return self.data.copy()

    @property
    def maxlen(self):
        return self._maxlen

    @wrapt.synchronized(lock)
    def find(self, packet):
        return self.data["packets"][packet.key]

    def __len__(self):
        return len(self.data["packets"])

    @wrapt.synchronized(lock)
    def total_rx(self):
        return self._total_rx

    @wrapt.synchronized(lock)
    def total_tx(self):
        return self._total_tx

    @wrapt.synchronized(lock)
    def stats(self, serializable=False) -> dict:
        stats = {
            "total_tracked": self._total_rx + self._total_rx,
            "rx": self._total_rx,
            "tx": self._total_tx,
            "types": self.data["types"],
            "packets": self.data["packets"],
        }
        return stats
