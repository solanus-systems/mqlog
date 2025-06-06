import asyncio
import logging
import unittest
from unittest import TestCase

from mqlog import MqttHandler
from tests.utils import AsyncMock, Mock, call


class FakeClient:
    """A fake MQTT client for testing purposes."""

    def __init__(self):
        self.publish = AsyncMock()
        self.up = asyncio.Event()


class TestMqttHandler(TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.handler = MqttHandler(self.client, "test_topic")
        self.logger = logging.getLogger("test")
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        self.client.up.set()  # Simulate client being ready

    def tearDown(self):
        """Clean up after each test"""
        self.handler.buffer.clear()
        self.handler.will_flush.clear()
        self.client.up.clear()

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
        self.client.publish.side_effect = Exception("Publish failed")

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
            "test_topic", "INFO:test:Test message 1\nERROR:test:Test message 2", qos=0
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
                call(
                    "test_topic",
                    "INFO:test:Test message 1\nINFO:test:Test message 2",
                    qos=0,
                ),
                call(
                    "test_topic",
                    "INFO:test:Test message 3\nINFO:test:Test message 4",
                    qos=0,
                ),
            ]
        )

    def test_buffer_overflow(self):
        """Buffer should get truncated if it exceeds capacity"""
        self.handler.capacity = 3
        self.client.up.clear()  # Simulate client being disconnected

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
            self.handler.buffer,
            [
                "INFO:test:Test message 2",
                "INFO:test:Test message 3",
                "INFO:test:Test message 4",
            ],
        )

    def test_reconnect(self):
        """Handler should reconnect and publish messages after a disconnect"""
        self.client.up.clear()  # Simulate client being disconnected

        async def do_test(
            handler: logging.Handler, logger: logging.Logger, client: FakeClient
        ):
            asyncio.create_task(handler.run())
            await asyncio.sleep(0.1)
            logger.error("Test message 1")
            await asyncio.sleep(0.1)

            # Simulate reconnect
            client.up.set()
            await asyncio.sleep(0.1)

        asyncio.run(do_test(self.handler, self.logger, self.client))

        self.client.publish.assert_called_with(
            "test_topic", "ERROR:test:Test message 1", qos=0
        )


if __name__ == "__main__":
    unittest.main()
