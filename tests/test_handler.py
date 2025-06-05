import asyncio
import logging
from unittest import TestCase

from mqlog import MqttHandler
from tests.utils import AsyncMock, Mock, call


class FakeClient:
    """A fake MQTT client for testing purposes."""

    publish: None


class TestMqttHandler(TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.client.publish = AsyncMock()
        self.handler = MqttHandler(self.client, "test_topic")
        self.handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger = logging.getLogger("test")
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)

    def tearDown(self):
        """Clean up after each test"""
        self.handler.buffer.clear()
        self.handler.will_flush.clear()

    def test_default_formatter(self):
        """Handler should use default formatter if none is set"""
        self.handler.setFormatter(None)
        self.logger.info("Test message")  # Would error if no formatter

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

    def test_flush_fail(self):
        """Flushing should log an error if publish fails"""
        self.handler._logger.error = Mock()
        self.client.publish = AsyncMock(side_effect=Exception("Publish failed"))

        async def do_test(handler: logging.Handler, logger: logging.Logger):
            asyncio.create_task(handler.run())
            await asyncio.sleep(0.1)  # Allow handler to start
            logger.error("Test message")  # should trigger flush
            await asyncio.sleep(0.1)

        asyncio.run(do_test(self.handler, self.logger))

        self.handler._logger.error.assert_called()

    def test_publish(self):
        """Flushing should publish messages to MQTT topic"""
        self.handler.flush_level = logging.ERROR

        async def do_test(handler: logging.Handler, logger: logging.Logger):
            asyncio.create_task(handler.run())
            await asyncio.sleep(0.1)
            logger.info("Test message 1")
            await asyncio.sleep(0.1)
            logger.error("Test message 2")
            await asyncio.sleep(0.1)

        asyncio.run(do_test(self.handler, self.logger))

        self.client.publish.assert_called_with(
            "test_topic", "Test message 1\nTest message 2", qos=0
        )

    def test_flush_multiple(self):
        """Flushing multiple times should publish separate messages"""
        self.handler.capacity = 2

        async def do_test(handler: logging.Handler, logger: logging.Logger):
            asyncio.create_task(handler.run())
            await asyncio.sleep(0.1)
            logger.info("Test message 1")
            await asyncio.sleep(0.1)
            logger.info("Test message 2")
            await asyncio.sleep(0.1)
            logger.info("Test message 3")
            await asyncio.sleep(0.1)
            logger.info("Test message 4")
            await asyncio.sleep(0.1)

        asyncio.run(do_test(self.handler, self.logger))

        self.client.publish.assert_has_calls(
            [
                call("test_topic", "Test message 1\nTest message 2", qos=0),
                call("test_topic", "Test message 3\nTest message 4", qos=0),
            ]
        )

    def test_buffer_overflow(self):
        """Buffer should get truncated if it exceeds capacity"""
        self.handler.capacity = 3
        self.client.publish = AsyncMock(side_effect=Exception("Publish failed"))

        async def do_test(handler: logging.Handler, logger: logging.Logger):
            asyncio.create_task(handler.run())
            await asyncio.sleep(0.1)
            logger.info("Test message 1")
            await asyncio.sleep(0.1)
            logger.info("Test message 2")
            await asyncio.sleep(0.1)
            logger.info("Test message 3")
            await asyncio.sleep(0.1)
            logger.info("Test message 4")  # This will fail to flush
            await asyncio.sleep(0.1)

        asyncio.run(do_test(self.handler, self.logger))

        self.assertEqual(
            self.handler.buffer, ["Test message 2", "Test message 3", "Test message 4"]
        )
