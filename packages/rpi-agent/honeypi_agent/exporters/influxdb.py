from __future__ import annotations
from influxdb_client import InfluxDBClient, Point  # type: ignore[import-untyped]
from influxdb_client.client.write_api import SYNCHRONOUS  # type: ignore[import-untyped]
from .base import BaseExporter
from ..sensors.base import Measurement


class InfluxDBExporter(BaseExporter):
    def __init__(self, config: dict) -> None:
        self._client = InfluxDBClient(url=config["url"], token=config["token"], org=config["org"])
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        self._bucket: str = config["bucket"]
        self._org: str = config["org"]

    def export(self, measurement: Measurement) -> None:
        point = Point(measurement.name)
        for key, value in measurement.values.items():
            point = point.field(key, value)
        self._write_api.write(bucket=self._bucket, org=self._org, record=point)

    def close(self) -> None:
        self._client.close()
