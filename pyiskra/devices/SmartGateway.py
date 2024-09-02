from .BaseDevice import Device
from ..adapters.RestAPI import RestAPI
from ..exceptions import DeviceNotSupported, DeviceConnectionError


import logging

log = logging.getLogger(__name__)


class SmartGateway(Device):
    """
    Represents a smart gateway device.

    Attributes:
        supports_measurements (bool): Indicates if the device supports measurements.
        supports_counters (bool): Indicates if the device supports counters.
        serial (str): The serial number of the device.
        model (str): The model of the device.
        description (str): The description of the device.
        location (str): The location of the device.
        fw_version (str): The firmware version of the device.
        child_devices (list): A list of child devices connected to the gateway.
    """

    DEVICE_PARAMETERS = {
        "SG": {"phases": 0, "resettable_counters": 0, "non_resettable_counters": 0}
    }

    is_gateway = True
    child_devices = []
    supports_measurements = False
    supports_counters = False

    async def init(self):
        """
        Initializes the smart gateway device.

        This method retrieves basic information about the device, such as serial number, model, description, location,
        and firmware version. It also initializes the child devices connected to the gateway.
        """
        basic_info = await self.adapter.get_basic_info()
        self.serial = basic_info.serial
        self.model = basic_info.model
        self.description = basic_info.description
        self.location = basic_info.location
        self.fw_version = basic_info.sw_ver
        await self.update_child_devices()
        log.debug(f"Successfully initialized {self.model} {self.serial}")

    async def update_child_devices(self):
        self.child_devices = []
        child_devices = await self.adapter.get_devices()

        child_devices = [
            device for device in child_devices if "Right IR" not in device["interface"]
        ]
        for i, device in enumerate(child_devices):
            if device["model"] != "Disabled" and device["model"] != "Not Detected":
                log.debug(
                    f"Found device {device['model']} {device['serial']} connected to {self.model} {self.serial}"
                )
                adapter = RestAPI(
                    ip_address=self.adapter.ip_address,
                    authentication=self.adapter.authentication,
                    device_index=i,
                )
                try:
                    dev = await Device.create_device(adapter, self)
                    await dev.init()
                    self.child_devices.append(dev)
                except DeviceNotSupported as e:
                    log.error(
                        f"Failed to create device {device['model']} {device['serial']}: {e}"
                    )
                except DeviceConnectionError as e:
                    log.error(
                        f"Failed to connect to device {device['model']} {device['serial']}: {e}"
                    )

    def get_child_devices(self):
        """
        Returns the list of child devices connected to the gateway.

        Returns:
            list: A list of child devices.
        """
        return self.child_devices

    async def get_measurements(self):
        """
        Retrieves the measurements from the smart gateway.

        Returns:
            dict: A dictionary containing the measurements.
        """
        return await self.adapter.get_measurements()

    async def get_counters(self):
        """
        Retrieves the counters from the smart gateway.

        Returns:
            dict: A dictionary containing the counters.
        """
        return await self.adapter.get_counters()

    async def update_status(self):
        """
        Updates the status of the smart gateway.
        """
        log.debug(f"Updating status for {self.model} {self.serial}")
        # await self.update_child_devices()
