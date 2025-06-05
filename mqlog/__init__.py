# Logging over MQTT

import asyncio
import logging

_default_formatter = logging.Formatter(logging._default_fmt)


class MqttHandler(logging.Handler):
    """
    A handler class which sends log records to an MQTT topic.
    """

    def __init__(
        self,
        client,
        topic,
        qos=0,
        level=logging.NOTSET,
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
        self._logger = logging.getLogger("mqlog")

    async def run(self):
        """
        Continuously publish log records via MQTT.
        This method should be scheduled as an asyncio task.
        """
        while True:
            await self.will_flush.wait()
            await self._flush()

    # Check if we should publish an MQTT message
    def _should_flush(self, record):
        return (len(self.buffer) >= self.capacity) or (
            record.levelno >= self.flush_level
        )

    # Called by logging.Handler when the logger logs a message
    def emit(self, record):
        self.buffer.append(self.format(record))
        if self._should_flush(record):
            self.will_flush.set()

    # Override Handler.format to prevent errors if there's no formatter set
    def format(self, record):
        fmt = self.formatter or _default_formatter
        return fmt.format(record)

    # Named with an underscore to avoid conflict with logging.Handler.flush
    async def _flush(self):
        if self.buffer:
            try:
                msg = "\n".join([line for line in self.buffer])
                await self.client.publish(self.topic, msg, qos=self.qos)
                self.buffer.clear()
            except Exception as e:
                self._logger.error(f"Failed to publish logs via MQTT: {e}")
            self.will_flush.clear()
