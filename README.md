# mqlog

[![ci](https://github.com/solanus-systems/mqlog/actions/workflows/ci.yml/badge.svg)](https://github.com/solanus-systems/mqlog/actions/workflows/ci.yml)

Async logging over MQTT for micropython.

## Installation

On a micropython device, install with `mip` from the REPL:

```python
>>> import mip
>>> mip.install("github:solanus-systems/mqlog")
```

Or on a unix build of micropython via the CLI:

```bash
micropython -m mip install github:solanus-systems/mqlog
```

## Usage

This module implements async logging over MQTT via a custom handler.

It was designed to work with [`amqc`](https://github.com/solanus-systems/amqc), but you can provide any client with an awaitable `publish` method of the form:

```python
async def publish(topic, msg, qos):
    pass # your implementation here
```

The client also needs an awaitable `asyncio.Event` called `up` to check whether the connection is functioning. This is used to determine whether the handler should continue buffering messages or attempt to publish them immediately.

Then, you can create a logger and add the handler:

```python
import logging
from mqlog import MqttHandler

# Create an MQTT client
client = ...

# Create a logger
logger = logging.getLogger("my_logger")
logger.setLevel(logging.INFO)
handler = MqttHandler(client, "my_topic")
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)
```

Once the logger is set up, add a task to the event loop to process messages:

```python
import asyncio

async def main():
    await asyncio.create_task(handler.run())

asyncio.run(main())
```

The handler will buffer log messages until either its capacity is reached or a log message meeting the `flush_level` is logged. The `flush_level` defaults to `ERROR`, meaning that only `ERROR` or `FATAL` messages will trigger an immediate publish. You can change this behavior by setting the `flush_level` when creating the handler:

```python
handler = MqttHandler(client, "my_topic", flush_level=logging.INFO)
```

You can also configure the maximum number of messages to buffer with the `capacity` parameter:

```python
handler = MqttHandler(client, "my_topic", capacity=3) # default is 10
```

See `mqlog/__init__.py` for more configurable options.

## Developing

You need python and a build of micropython with `asyncio` support. Follow the steps in the CI workflow to get a `micropython` binary and add it to your `PATH`.

Before making changes, install the development dependencies:

```bash
pip install -r dev-requirements.txt
```

After making changes, you can run the linter:

```bash
ruff check
```

Before running tests, install the test dependencies:

```bash
./bin/setup
```

Then, you can run the tests using the micropython version of `unittest`:

```bash
micropython -m unittest
```

## Releasing

To release a new version, update the version in `package.json`. Commit your changes and make a pull request. After merging, create a new tag and push to GitHub:

```bash
git tag vX.Y.Z
git push --tags
```
