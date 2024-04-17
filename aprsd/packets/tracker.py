import datetime
import threading

from oslo_config import cfg
import wrapt

from aprsd.packets import collector, core
from aprsd.utils import objectstore


CONF = cfg.CONF


class PacketTrack(objectstore.ObjectStoreMixin):
    """Class to keep track of outstanding text messages.

    This is a thread safe class that keeps track of active
    messages.

    When a message is asked to be sent, it is placed into this
    class via it's id.  The TextMessage class's send() method
    automatically adds itself to this class.  When the ack is
    recieved from the radio, the message object is removed from
    this class.
    """

    _instance = None
    _start_time = None
    lock = threading.Lock()

    data: dict = {}
    total_tracked: int = 0

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._start_time = datetime.datetime.now()
            cls._instance._init_store()
        return cls._instance

    @wrapt.synchronized(lock)
    def __getitem__(self, name):
        return self.data[name]

    @wrapt.synchronized(lock)
    def __iter__(self):
        return iter(self.data)

    @wrapt.synchronized(lock)
    def keys(self):
        return self.data.keys()

    @wrapt.synchronized(lock)
    def items(self):
        return self.data.items()

    @wrapt.synchronized(lock)
    def values(self):
        return self.data.values()

    @wrapt.synchronized(lock)
    def stats(self, serializable=False):
        stats = {
            "total_tracked": self.total_tracked,
        }
        pkts = {}
        for key in self.data:
            last_send_time = self.data[key].last_send_time
            pkts[key] = {
                "last_send_time": last_send_time,
                "send_count": self.data[key].send_count,
                "retry_count": self.data[key].retry_count,
                "message": self.data[key].raw,
            }
        stats["packets"] = pkts
        return stats

    @wrapt.synchronized(lock)
    def __len__(self):
        return len(self.data)

    @wrapt.synchronized(lock)
    def rx(self, packet: type[core.Packet]) -> None:
        """When we get a packet from the network, check if we should remove it."""
        if isinstance(packet, core.AckPacket):
            self._remove(packet.msgNo)
        elif isinstance(packet, core.RejectPacket):
            self._remove(packet.msgNo)
        elif packet.ackMsgNo:
            # Got a piggyback ack, so remove the original message
            self._remove(packet.ackMsgNo)

    @wrapt.synchronized(lock)
    def tx(self, packet: type[core.Packet]) -> None:
        """Add a packet that was sent."""
        key = packet.msgNo
        packet.send_count = 0
        self.data[key] = packet
        self.total_tracked += 1

    @wrapt.synchronized(lock)
    def get(self, key):
        return self.data.get(key, None)

    @wrapt.synchronized(lock)
    def remove(self, key):
        self._remove(key)

    def _remove(self, key):
        try:
            del self.data[key]
        except KeyError:
            pass


# Now register the PacketList with the collector
# every packet we RX and TX goes through the collector
# for processing for whatever reason is needed.
collector.PacketCollector().register(PacketTrack)
