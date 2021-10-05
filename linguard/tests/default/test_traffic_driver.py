import os
from datetime import datetime
from typing import Dict

import pytest

from linguard.core.drivers.traffic_storage_driver import TrafficData
from linguard.core.drivers.traffic_storage_driver_json import TrafficStorageDriverJson


class TrafficStorageDriverJsonMock(TrafficStorageDriverJson):

    def __init__(self, filepath: str):
        super().__init__(filepath)

    def get_session_and_stored_data(self) -> Dict[datetime, Dict[str, TrafficData]]:
        return {
            datetime.strptime("15/09/2021 15:24:34", self.DEFAULT_TIMESTAMP_FORMAT):
                {"39a855187c4c4ca694d8c3f215e76cdd": TrafficData(0, 0), "39a855187c4c4ca694d8c3f215e76cde": TrafficData(0, 0)},
            datetime.strptime("15/09/2021 16:24:34", self.DEFAULT_TIMESTAMP_FORMAT):
                {"39a855187c4c4ca694d8c3f215e76cdd": TrafficData(0, 0), "39a855187c4c4ca694d8c3f215e76cde": TrafficData(0, 0)},
            datetime.strptime("15/09/2021 17:24:34", self.DEFAULT_TIMESTAMP_FORMAT):
                {"39a855187c4c4ca694d8c3f215e76cdd": TrafficData(0, 0), "39a855187c4c4ca694d8c3f215e76cde": TrafficData(0, 0)},
            datetime.strptime("15/09/2021 18:24:34", self.DEFAULT_TIMESTAMP_FORMAT):
                {"39a855187c4c4ca694d8c3f215e76cdd": TrafficData(0, 0), "39a855187c4c4ca694d8c3f215e76cde": TrafficData(0, 0)},
            datetime.strptime("15/09/2021 19:24:34", self.DEFAULT_TIMESTAMP_FORMAT):
                {"39a855187c4c4ca694d8c3f215e76cdd": TrafficData(0, 0), "39a855187c4c4ca694d8c3f215e76cde": TrafficData(0, 0)},
            datetime.strptime("15/09/2021 20:24:34", self.DEFAULT_TIMESTAMP_FORMAT):
                {"39a855187c4c4ca694d8c3f215e76cdd": TrafficData(0, 0), "39a855187c4c4ca694d8c3f215e76cde": TrafficData(0, 0)},
            datetime.strptime("15/09/2021 21:24:34", self.DEFAULT_TIMESTAMP_FORMAT):
                {"39a855187c4c4ca694d8c3f215e76cdd": TrafficData(0, 0), "39a855187c4c4ca694d8c3f215e76cde": TrafficData(0, 0)},
            datetime.strptime("15/09/2021 22:24:34", self.DEFAULT_TIMESTAMP_FORMAT):
                {"39a855187c4c4ca694d8c3f215e76cdd": TrafficData(0, 0), "39a855187c4c4ca694d8c3f215e76cde": TrafficData(0, 0)},
            datetime.strptime("15/09/2021 23:24:34", self.DEFAULT_TIMESTAMP_FORMAT):
                {"39a855187c4c4ca694d8c3f215e76cdd": TrafficData(0, 0), "39a855187c4c4ca694d8c3f215e76cde": TrafficData(0, 0)},
            datetime.strptime("16/09/2021 00:24:34", self.DEFAULT_TIMESTAMP_FORMAT):
                {"39a855187c4c4ca694d8c3f215e76cdd": TrafficData(0, 0), "39a855187c4c4ca694d8c3f215e76cde": TrafficData(0, 0)},
            datetime.strptime("16/09/2021 01:24:34", self.DEFAULT_TIMESTAMP_FORMAT):
                {"39a855187c4c4ca694d8c3f215e76cdd": TrafficData(0, 0), "39a855187c4c4ca694d8c3f215e76cde": TrafficData(0, 0)},
            datetime.strptime("16/09/2021 02:24:34", self.DEFAULT_TIMESTAMP_FORMAT):
                {"39a855187c4c4ca694d8c3f215e76cdd": TrafficData(0, 0), "39a855187c4c4ca694d8c3f215e76cde": TrafficData(0, 0)}
        }


class TestJsonTrafficDriver:

    @pytest.fixture(autouse=True)
    def cleanup(self):
        yield
        if self.driver and os.path.exists(self.driver.filepath):
            os.remove(self.driver.filepath)

    def test_load_no_data(self):
        self.driver = TrafficStorageDriverJson("traffic.json")
        data = self.driver.get_session_and_stored_data()
        assert data is not None
        assert len(data) == 0

    def test_store_no_data(self):
        self.driver = TrafficStorageDriverJson("traffic.json")
        self.driver.save_data()
        data = self.driver.load_data()
        assert data is not None
        assert len(data) == 0

    def test_load_data(self):
        self.driver = TrafficStorageDriverJson("traffic.json")
        with open(self.driver.filepath, "w") as f:
            f.write("""
            {"15/09/2021 15:24:34": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "15/09/2021 15:25:02": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "15/09/2021 15:27:58": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "15/09/2021 15:32:14": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "15/09/2021 15:34:26": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "15/09/2021 15:35:15": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "15/09/2021 15:40:04": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "15/09/2021 16:28:00": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "15/09/2021 16:28:06": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "15/09/2021 16:29:39": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "21/09/2021 00:10:30": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "21/09/2021 00:11:34": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "21/09/2021 00:16:07": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "21/09/2021 00:17:01": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 22:42:26": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 22:42:46": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 22:43:01": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 22:46:28": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 22:52:52": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 22:52:56": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 22:53:05": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 22:57:40": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 22:57:53": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 22:58:27": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 22:58:51": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 22:59:08": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:00:14": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:01:04": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:02:02": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:13:26": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:32:03": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:34:39": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:39:37": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:40:43": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:45:07": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:46:33": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:48:07": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:48:26": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:48:49": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:49:09": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:51:02": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:51:42": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:52:06": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:52:58": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:53:21": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:53:41": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:54:28": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:56:15": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "28/09/2021 23:56:30": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "29/09/2021 00:09:35": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}, "04/10/2021 19:37:40": {"39a855187c4c4ca694d8c3f215e76cdd": {"rx": 0, "tx": 0}, "39a855187c4c4ca694d8c3f215e76cde": {"rx": 0, "tx": 0}}}
            """)
        data = self.driver.get_session_and_stored_data()
        assert data is not None
        assert len(data) > 0

    def test_store_data(self):
        self.driver = TrafficStorageDriverJsonMock("traffic.json")
        self.driver.save_data()
        data = self.driver.load_data()
        assert data is not None
        assert len(data) > 0
