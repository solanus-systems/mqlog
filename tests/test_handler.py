import asyncio
import logging
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, call

from mqlog import MqttHandler


class TestMqttHandler(IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.publish = AsyncMock()
        self.handler = MqttHandler(self.client, "test_topic")
        self.logger = logging.getLogger("test")
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)

    # Run for X seconds, then stop
    async def run_with_timeout(self, timeout=1):
        async with asyncio.timeout(timeout):
            await self.handler.run()
            self.handler.close()

    # Log a message at a given level after a delay of X seconds
    async def log_message(self, msg, level, delay):
        await asyncio.sleep(delay)
        self.logger.log(level, msg)

    def test_no_flush(self):
        """Buffer should not be flushed until capacity/level reached"""
        self.handler.flush_level = logging.WARNING
        self.logger.info("Test message")
        self.assertFalse(self.handler.will_flush.is_set())

    def test_flush_level(self):
        """Buffer should be flushed when a message meets flush level"""
        self.handler.flush_level = logging.WARNING
        self.logger.warning("Test message")
        self.assertTrue(self.handler.will_flush.is_set())

    def test_flush_full_buffer(self):
        """Buffer should be flushed when full"""
        self.handler.capacity = 3
        for i in range(3):
            self.logger.info(f"Test message {i}")
        self.assertTrue(self.handler.will_flush.is_set())

    async def test_publish(self):
        """Flushing should publish messages to MQTT topic"""
        self.handler.flush_level = logging.ERROR
        await asyncio.gather(
            self.run_with_timeout(1),
            self.log_message("Test message 1", logging.INFO, 0.1),
            self.log_message("Test message 2", logging.ERROR, 0.2),
            return_exceptions=True,
        )
        self.client.publish.assert_awaited_with(
            "test_topic",
            "Test message 1\nTest message 2",
            qos=0,
        )

    async def test_flush_multiple(self):
        """Flushing multiple times should publish separate messages"""
        self.handler.capacity = 2
        await asyncio.gather(
            self.run_with_timeout(1),
            self.log_message("Test message 1", logging.INFO, 0.1),
            self.log_message("Test message 2", logging.INFO, 0.2),
            self.log_message("Test message 3", logging.INFO, 0.3),
            self.log_message("Test message 4", logging.INFO, 0.4),
            return_exceptions=True,
        )
        self.client.publish.assert_has_awaits(
            [
                call("test_topic", "Test message 1\nTest message 2", qos=0),
                call("test_topic", "Test message 3\nTest message 4", qos=0),
            ]
        )
