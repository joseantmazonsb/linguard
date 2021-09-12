from core.drivers.traffic_storage_driver_json import TrafficStorageDriverJson


class TestTrafficDriver:

    def test_json_driver_load(self):
        driver = TrafficStorageDriverJson("traffic.json")
        assert driver.load_data() is not None
        assert driver.get_session_data() is not None
        assert driver.get_session_and_stored_data() is not None
