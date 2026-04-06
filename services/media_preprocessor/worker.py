"""Media Preprocessor Worker.

Consumes events from ``post-image-processing`` (all incoming post images),
downloads each image once to a shared local directory, then publishes a
``LocalMediaEventDTO`` event to ``ml-inference-tasks`` so downstream ML
workers can read from disk instead of fetching the image over the network
repeatedly.

No ML inference is performed here.
"""

import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.redis_streams import RedisStreamConsumer, RedisStreamPublisher
from shared.schemas.schemas import LocalMediaEventDTO, PostImageEventDTO
from shared.utils.logger import get_logger

LOGGER = get_logger("media-preprocessor")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

STREAM_INPUT = "post-image-processing"
STREAM_OUTPUT = "ml-inference-tasks"
STREAM_DLQ = "ai-processing-dlq"

CONSUMER_GROUP = "media-preprocessor-group"
CONSUMER_NAME = "media-preprocessor-worker-1"

ImageDownloader = Callable[[str, str], str]


def _decode_event(data: Dict[Any, Any]) -> Dict[str, Any]:
    """Decode a raw Redis bytes/string dict to Python str values."""
    decoded: Dict[str, Any] = {}
    for k, v in data.items():
        key = k.decode("utf-8") if isinstance(k, bytes) else str(k)
        val = v.decode("utf-8") if isinstance(v, bytes) else v
        decoded[key] = val
    return decoded


def _http_downloader(image_url: str, dest_path: str) -> str:
    """Production downloader ? fetches image_url and writes bytes to dest_path.

    Imported lazily so requests is never imported during unit tests that
    inject a mock downloader.
    """
    import requests  # noqa: PLC0415

    response = requests.get(image_url, timeout=30)
    response.raise_for_status()
    with open(dest_path, "wb") as fh:
        fh.write(response.content)
    return dest_path


class MediaPreprocessorWorker:
    """Downloads an image to shared local storage and emits a LocalMediaEventDTO.

    Both collaborators are injected so unit tests never touch the network or
    a real Redis instance.
    """

    def __init__(self, publisher: RedisStreamPublisher, downloader: ImageDownloader) -> None:
        self._publisher = publisher
        self._downloader = downloader

    def handle_message(self, message_id: str, data: Dict[Any, Any]) -> None:
        try:
            normalized = _decode_event(data)
            event = PostImageEventDTO.model_validate(normalized)
        except (ValidationError, Exception) as exc:
            LOGGER.warning(
                "MediaPreprocessor: invalid incoming event, routing to DLQ",
                extra={"message_id": message_id, "error": str(exc)},
            )
            self._publisher.publish(
                STREAM_DLQ,
                {
                    "originalMessageId": message_id,
                    "serviceName": "media-preprocessor",
                    "error": str(exc),
                    "errorType": type(exc).__name__,
                },
            )
            return

        shared_media_dir = os.getenv("SHARED_MEDIA_DIR", "/tmp/kaleidoscope_media")
        dest_path = os.path.join(shared_media_dir, f"{event.mediaId}.jpg")
        os.makedirs(shared_media_dir, exist_ok=True)

        try:
            local_path = self._downloader(event.mediaUrl, dest_path)
        except Exception as exc:
            LOGGER.warning(
                "MediaPreprocessor: download failed, routing to DLQ",
                extra={
                    "message_id": message_id,
                    "media_id": event.mediaId,
                    "url": event.mediaUrl,
                    "error": str(exc),
                },
            )
            self._publisher.publish(
                STREAM_DLQ,
                {
                    "originalMessageId": message_id,
                    "serviceName": "media-preprocessor",
                    "error": str(exc),
                    "errorType": type(exc).__name__,
                    "mediaId": event.mediaId,
                    "correlationId": event.correlationId,
                },
            )
            return

        outgoing = LocalMediaEventDTO.model_validate({
            "postId": event.postId,
            "mediaId": event.mediaId,
            "localFilePath": local_path,
            "correlationId": event.correlationId,
        })

        self._publisher.publish(
            STREAM_OUTPUT,
            {
                "postId": outgoing.postId,
                "mediaId": outgoing.mediaId,
                "localFilePath": outgoing.localFilePath,
                "correlationId": outgoing.correlationId,
            },
        )

        LOGGER.info(
            "MediaPreprocessor: image downloaded and event published",
            extra={
                "media_id": outgoing.mediaId,
                "local_path": outgoing.localFilePath,
                "correlation_id": outgoing.correlationId,
            },
        )


def main() -> None:
    LOGGER.info("Media Preprocessor Worker starting...")

    shutdown_event = threading.Event()

    def _shutdown(signum, frame):
        LOGGER.info("Shutdown signal received (%s)", signum)
        shutdown_event.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    publisher = RedisStreamPublisher(REDIS_URL)
    consumer = RedisStreamConsumer(
        REDIS_URL,
        STREAM_INPUT,
        CONSUMER_GROUP,
        CONSUMER_NAME,
        shutdown_event=shutdown_event,
    )

    worker = MediaPreprocessorWorker(publisher=publisher, downloader=_http_downloader)

    try:
        LOGGER.info("Worker ready -- waiting for messages")
        consumer.consume(
            lambda msg_id, data: worker.handle_message(msg_id, data),
            block_ms=5000,
            count=1,
        )
    except KeyboardInterrupt:
        LOGGER.info("Interrupted by user")
    finally:
        consumer.close()
        publisher.close()
        LOGGER.info("Media Preprocessor Worker shut down")


if __name__ == "__main__":
    main()
