from __future__ import annotations

from typing import Any

from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write.point import Point
from influxdb_client.client.write_api import SYNCHRONOUS

from ..sensors.base import Measurement
from .base import BaseExporter


class InfluxDBExporter(BaseExporter):
    def __init__(self, config: dict[str, Any]) -> None:
        self._client = InfluxDBClient(
            url=config["url"], token=config["token"], org=config["org"]
        )
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        self._bucket: str = config["bucket"]
        self._org: str = config["org"]

    def export(self, measurement: Measurement) -> None:
        point = Point(measurement.name)  # type: ignore[no-untyped-call]
        for key, value in measurement.values.items():
            point = point.field(key, value)  # type: ignore[no-untyped-call]
        self._write_api.write(bucket=self._bucket, org=self._org, record=point)

    def close(self) -> None:
        self._client.close()  # type: ignore[no-untyped-call]
