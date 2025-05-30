# Logging over MQTT

import asyncio
import logging


class MqttHandler(logging.Handler):
    """
    A handler class which sends log records to an MQTT topic.
    """

    def __init__(
        self,
        client,
        topic,
        qos=0,
        level=logging.INFO,
        flush_level=logging.ERROR,
        capacity=10,
    ):
        """
        Initialize the handler with the MQTT client and topic to publish on.

        Buffers logs as they come in. If the log level of a record is greater
        than or equal to flush_level, or the buffer is full, the buffer is
        flushed to the MQTT topic.
        """
        super().__init__(level=level)

        if flush_level < level:
            raise ValueError("Flush level must be greater than or equal to level")

        self.client = client
        self.topic = topic
        self.qos = qos
        self.flush_level = flush_level
        self.capacity = capacity
        self.buffer = []
        self.will_flush = asyncio.Event()

    def should_flush(self, record):
        return (len(self.buffer) >= self.capacity) or (
            record.levelno >= self.flush_level
        )

    # Called when the logger logs a message
    def emit(self, record):
        self.buffer.append(record)
        if self.should_flush(record):
            self.will_flush.set()

    # Needs to be run in an event loop once MQTT client is connected
    async def run(self):
        while True:
            await self.will_flush.wait()
            await self._flush()

    # Named with an underscore to avoid conflict with logging.Handler.flush
    async def _flush(self):
        if self.buffer:
            records = [self.buffer.pop(0) for _ in range(len(self.buffer))]
            msg = "\n".join(self.format(record) for record in records)
            await self.client.publish(self.topic, msg, qos=self.qos)
        self.will_flush.clear()
