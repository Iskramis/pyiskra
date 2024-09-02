import asyncio
import socket
import re
from ..exceptions import DeviceConnectionError, DeviceNotSupported, ProtocolNotSupported
from ..adapters import RestAPI


class Device:
    """
    Represents a base device in the Iskra system.

    Attributes:
        model (str): The model of the device.
        serial (str): The serial number of the device.
        description (str): The description of the device.
        location (str): The location of the device.
        supports_measurements (bool): Indicates whether the device supports measurements.
        supports_counters (bool): Indicates whether the device supports counters.
        measurements (None or dict): The measurements data of the device.
        counters (None or dict): The counters data of the device.
        update_timestamp (int): The timestamp of the last update.
    """

    DEVICE_PARAMETERS = {}
    model = ""
    serial = ""
    description = ""
    location = ""
    is_gateway = False
    supports_measurements = False
    supports_counters = False
    measurements = None
    counters = None
    phases = 0
    non_resettable_counters = 0
    resettable_counters = 0
    fw_version = None
    parent_device = None

    update_timestamp = 0

    @staticmethod
    async def create_device(adapter, parent_device=None):
        """
        Creates a device based on the adapter.

        Args:
            adapter: The adapter used to communicate with the device.

        Returns:
            An instance of the appropriate device subclass based on the model.

        Raises:
            ConnectionError: If failed to get basic info from the adapter.
            ValueError: If the device model is unsupported.
        """

        basic_info = await adapter.get_basic_info()

        model = basic_info.model

        from .IMPACT import Impact

        if any(
            re.match(model_pattern, model)
            for model_pattern in Impact.DEVICE_PARAMETERS.keys()
        ):
            return Impact(adapter, parent_device)

        from .WM import WM

        if any(
            re.match(model_pattern, model)
            for model_pattern in WM.DEVICE_PARAMETERS.keys()
        ):
            return WM(adapter, parent_device)

        from .MeasuringCenter import MeasuringCentre

        if any(
            re.match(model_pattern, model)
            for model_pattern in MeasuringCentre.DEVICE_PARAMETERS.keys()
        ):
            return MeasuringCentre(adapter, parent_device)

        from .SmartGateway import SmartGateway

        if any(
            re.match(model_pattern, model)
            for model_pattern in SmartGateway.DEVICE_PARAMETERS.keys()
        ):
            if isinstance(adapter, RestAPI):
                return SmartGateway(adapter, parent_device)
            else:
                # only REST API is supported for SmartGateway
                raise ProtocolNotSupported(f"Unsupported device model: {model}")

        raise DeviceNotSupported(f"Unsupported device model: {model}")

    def __init__(self, adapter, parent_device=None):
        """
        Initializes the Iskra Device.

        Args:
            adapter: The adapter used to communicate with the device.
        """
        self.adapter = adapter
        self.update_lock = asyncio.Lock()
        self.parent_device = parent_device

    async def get_basic_info(self):
        """
        Retrieves basic information from the device.

        Returns:
            dict: A dictionary containing the basic information.
        """
        basic_info = await self.adapter.get_basic_info()

        self.serial = basic_info.serial
        self.model = basic_info.model
        self.description = basic_info.description

        # Use regular expressions to match the model name and assign parameters accordingly
        for model_pattern, parameters in self.DEVICE_PARAMETERS.items():
            if re.match(model_pattern, self.model):
                self.phases = parameters["phases"]
                self.resettable_counters = parameters["resettable_counters"]
                self.non_resettable_counters = parameters["non_resettable_counters"]
                break

        return basic_info

    async def update_status(self):
        """
        Updates the status of the device.

        This method needs to be re-defined in all sub-classes.
        """
        raise NotImplementedError

    async def init(self):
        """
        Initializes the status of the device.

        This method needs to be re-defined in all sub-classes.
        """
        raise NotImplementedError

    @property
    def ip_address(self):
        """
        Returns the IP address of the device.

        Returns:
            The IP address of the device.
        """
        return self.adapter.ip_address
