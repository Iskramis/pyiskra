import aiohttp
import base64
import logging
from aiohttp import ClientConnectionError, ServerTimeoutError
from .BaseAdapter import Adapter
from ..helper import (
    BasicInfo,
    Measurements,
    Measurement,
    Phase_Measurements,
    Total_Measurements,
    Counters,
    Counter,
    get_counter_type,
)

from ..exceptions import (
    NotAuthorised,
    ProtocolNotSupported,
    InvalidResponseCode,
    DeviceConnectionError,
    DeviceTimeoutError,
)

log = logging.getLogger(__name__)


class RestAPI(Adapter):
    """Adapter class for making REST API calls."""

    def __init__(self, ip_address, device_index=None, authentication=None):
        """
        Initialize the RestAPI adapter.

        Args:
            ip_address (str): The IP address of the REST API.
            device_index (int, optional): The index of the device. Defaults to None.
            authentication (dict, optional): The authentication credentials. Defaults to None.
        """
        self.ip_address = ip_address
        self.device_index = device_index
        self.authentication = authentication

    async def get_resource(self, resource):
        """
        Get a resource from the REST API.

        Args:
            resource (str): The resource path.

        Returns:
            dict: The parsed JSON response.

        Raises:
            Exception: If an error occurs while making the REST API call.
        """
        headers = {}
        if self.authentication:
            authentication = self.authentication

            if (password := authentication.get("password")) and (
                username := authentication.get("username")
            ):
                headers["cookie"] = "Authorization=Basic " + base64.b64encode(
                    (username + ":" + password).encode("utf-8")
                ).decode("utf-8")

        # Set a timeout for the REST API call
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"http://{self.ip_address}/{resource}", headers=headers
                ) as response:
                    return await RestAPI.handle_response(response)
        except ServerTimeoutError as e:
            raise DeviceTimeoutError(
                f"Timeout occurred while connecting to the RestAPI: {e}"
            ) from e
        except ClientConnectionError as e:
            raise DeviceConnectionError(
                f"Error occurred while connecting to the RestAPI: {e}"
            ) from e
        except NotAuthorised as e:
            raise NotAuthorised(f"Not authorised to access the device: {e}") from e
        except ProtocolNotSupported as e:
            raise ProtocolNotSupported(f"{e}") from e
        except InvalidResponseCode:
            raise DeviceConnectionError(
                f"Invalid response code while connecting to the RestAPI"
            )
        except Exception as e:
            raise DeviceConnectionError(
                f"Error occurred while connecting to the RestAPI: {e}"
            ) from e

    @staticmethod
    async def handle_response(response):
        """
        Handle the HTTP response.

        Args:
            response: The HTTP response object.

        Returns:
            dict: The parsed JSON response.

        Raises:
            Exception: If the response status is unexpected.
        """
        if response.status == 200:
            return await RestAPI.parse_resource(response)
        elif response.status == 403:
            raise NotAuthorised("Not authorised")
        elif response.status == 404:
            raise ProtocolNotSupported("Device not supported by RestAPI")
        else:
            raise InvalidResponseCode("Invalid response code")

    @staticmethod
    async def parse_resource(response):
        """
        Parse the HTTP response.

        Args:
            response: The HTTP response object.

        Returns:
            dict: The parsed JSON response.
        """
        return await response.json()

    async def get_devices(self):
        """
        Get the list of devices.

        Returns:
            list: The list of devices.
        """
        child_devices = (await self.get_resource("api/devices")).get("devices", [])
        return child_devices

    def parse_measurement(self, measurement, default_unit=None):
        # New format: dict with 'value' and 'unit'
        if (
            isinstance(measurement, dict)
            and "value" in measurement
            and "unit" in measurement
        ):
            return Measurement(float(measurement["value"]), measurement["unit"])
        # Old format: string "value unit"
        elif isinstance(measurement, str):
            parts = measurement.split(" ")
            if len(parts) == 2:
                return Measurement(float(parts[0]), parts[1])
            elif len(parts) == 1 and default_unit:
                return Measurement(float(parts[0]), default_unit)

        # Already a float/int, use default unit if provided
        elif isinstance(measurement, (float, int)) and default_unit:
            return Measurement(float(measurement), default_unit)
        return None

    async def get_measurements(self):
        """
        Get the measurements.

        Returns:
            Measurements: The measurements object.

        Raises:
            ConnectionError: If an error occurs while connecting to the RestAPI.
        """
        json_data = None
        if self.device_index is not None and self.device_index >= 0:
            json_data = await self.get_resource(
                "api/measurement/" + str(self.device_index)
            )
            json_data = json_data.get("measurements", {})
            phases = []
            total = None
            frequency = None
            temperature = None

            for phase in json_data.get("Phases", []):
                voltage = None
                current = None
                active_power = None
                reactive_power = None
                apparent_power = None
                power_factor = None
                power_angle = None
                thd_voltage = None
                thd_current = None

                temp = phase.get("U", phase.get("voltage", None))
                if temp:
                    voltage = self.parse_measurement(temp)

                temp = phase.get("I", phase.get("current", None))
                if temp:
                    current = self.parse_measurement(temp)

                temp = phase.get("P", phase.get("active_power", None))
                if temp:
                    active_power = self.parse_measurement(temp)

                temp = phase.get("Q", phase.get("reactive_power", None))
                if temp:
                    reactive_power = self.parse_measurement(temp)

                temp = phase.get("S", phase.get("apparent_power", None))
                if temp:
                    apparent_power = self.parse_measurement(temp)

                temp = phase.get("PF", phase.get("power_factor", None))
                if temp:
                    power_factor = self.parse_measurement(temp)

                temp = phase.get("PA", phase.get("power_angle", None))
                if temp:
                    power_angle = self.parse_measurement(temp, "°")

                temp = phase.get("THDUp", phase.get("THD_voltage", None))
                if temp:
                    thd_voltage = self.parse_measurement(temp, "%")

                temp = phase.get("THDI", phase.get("THD_current", None))
                if temp:
                    thd_current = self.parse_measurement(temp, "%")

                phases.append(
                    Phase_Measurements(
                        voltage,
                        current,
                        active_power,
                        reactive_power,
                        apparent_power,
                        power_factor,
                        power_angle,
                        thd_voltage,
                        thd_current,
                    )
                )
            if json_data.get("Total"):
                total_measurements = json_data.get("Total", {})

                temp = total_measurements.get(
                    "P", total_measurements.get("active_power", None)
                )
                if temp:
                    active_power = self.parse_measurement(temp)

                temp = total_measurements.get(
                    "Q", total_measurements.get("reactive_power", None)
                )
                if temp:
                    reactive_power = self.parse_measurement(temp)

                temp = total_measurements.get(
                    "S", total_measurements.get("apparent_power", None)
                )
                if temp:
                    apparent_power = self.parse_measurement(temp)

                temp = total_measurements.get(
                    "PF", total_measurements.get("power_factor", None)
                )
                if temp:
                    power_factor = self.parse_measurement(temp)

                temp = total_measurements.get(
                    "PA", total_measurements.get("power_angle", None)
                )
                if temp:
                    power_angle = self.parse_measurement(temp, "°")

                total = Total_Measurements(
                    active_power,
                    reactive_power,
                    apparent_power,
                    power_factor,
                    power_angle,
                )

            temp = json_data.get("Frequency", json_data.get("frequency", None))
            if temp:
                frequency = self.parse_measurement(temp, "Hz")

            temp = json_data.get("Temperature", json_data.get("temperature", None))
            if temp:
                temperature = self.parse_measurement(temp, "°C")

            return Measurements(
                phases=phases,
                total=total,
                frequency=frequency,
                temperature=temperature,
            )

        return None

    async def get_counters(self):
        """
        Get the counters.

        Returns:
            tuple: A tuple containing the non-resettable, resettable counters.

        Raises:
            ConnectionError: If an error occurs while connecting to the RestAPI.
        """
        json_data = None

        json_data = await self.get_resource("api/counter/" + str(self.device_index))

        json_data = json_data.get("counters", {})
        non_resettable = []
        resettable = []
        if json_data.get("non_resettable"):
            for counter in json_data.get("non_resettable", []):
                try:
                    conunter_type = get_counter_type(
                        counter.get("direction"), counter.get("unit")
                    )
                    non_resettable.append(
                        Counter(
                            counter.get("value"),
                            counter.get("unit"),
                            counter.get("direction"),
                            conunter_type,
                        )
                    )
                except Exception as e:
                    log.error(
                        "Failed to parse non-resettable counter: %s: %s",
                        counter.get("name"),
                        e,
                    )

        if json_data.get("resettable"):
            for counter in json_data.get("resettable", []):
                try:
                    conunter_type = get_counter_type(
                        counter.get("direction"), counter.get("unit")
                    )
                    resettable.append(
                        Counter(
                            counter.get("value"),
                            counter.get("unit"),
                            counter.get("direction"),
                            conunter_type,
                        )
                    )
                except Exception as e:
                    log.error(
                        "Failed to parse resettable counter: %s: %s",
                        counter.get("name"),
                        e,
                    )
        return Counters(non_resettable, resettable)

    async def get_basic_info(self):
        """
        Retrieves basic information about the device.

        Returns:
            BasicInfo: An object containing the basic information of the device.
        """
        json_data = None
        if self.device_index is not None and self.device_index >= 0:
            try:
                child_devices = await self.get_devices()
            except Exception as e:
                raise DeviceConnectionError(
                    f"Failed to connect to the device: {e}"
                ) from e
            # filter out the right IR device
            child_devices = [
                device
                for device in child_devices
                if "Right IR" not in device["interface"]
            ]
            json_data = child_devices[self.device_index]
        else:

            json_data = (await self.get_resource("api")).get("device", {})
            # fix syntax to be consistent with other devices
            json_data["model"] = json_data["model_type"].strip()
            json_data["serial"] = json_data["serial_number"].strip()
            del json_data["model_type"]
            del json_data["serial_number"]

        return BasicInfo(
            serial=json_data.get("serial"),
            model=json_data.get("model"),
            description=json_data.get("description"),
            location=json_data.get("location"),
            sw_ver=json_data.get("sw_ver"),
        )
