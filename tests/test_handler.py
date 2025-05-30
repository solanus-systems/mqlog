import asyncio
import logging
from unittest import TestCase

from mqlog import MqttHandler


class FakeClient:
    """A fake MQTT client for testing purposes."""

    def __init__(self):
        self.calls = []

    # Store the call like a mock so we can check it later
    async def publish(self, topic, payload, qos=0):
        self.calls.append((topic, payload, qos))


class TestMqttHandler(TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.handler = MqttHandler(self.client, "test_topic")
        self.handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger = logging.getLogger("test")
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)

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

    def test_publish(self):
        """Flushing should publish messages to MQTT topic"""
        self.handler.flush_level = logging.ERROR

        async def do_test(handler, logger):
            logger.info("Test message 1")
            await asyncio.sleep(0.1)
            logger.error("Test message 2")
            await asyncio.sleep(0.1)
            handler.stop()

        async def main(handler, logger):
            await asyncio.gather(handler.run(), do_test(handler, logger))

        asyncio.run(main(self.handler, self.logger))

        self.assertEqual(
            self.client.calls, [("test_topic", "Test message 1\nTest message 2", 0)]
        )

    def test_flush_multiple(self):
        """Flushing multiple times should publish separate messages"""
        self.handler.capacity = 2

        async def do_test(handler, logger):
            logger.info("Test message 1")
            await asyncio.sleep(0.1)
            logger.info("Test message 2")
            await asyncio.sleep(0.1)
            logger.info("Test message 3")
            await asyncio.sleep(0.1)
            logger.info("Test message 4")
            await asyncio.sleep(0.1)
            handler.stop()

        async def main(handler, logger):
            await asyncio.gather(handler.run(), do_test(handler, logger))

        asyncio.run(main(self.handler, self.logger))

        self.assertEqual(
            self.client.calls,
            [
                ("test_topic", "Test message 1\nTest message 2", 0),
                ("test_topic", "Test message 3\nTest message 4", 0),
            ],
        )
