import logging
import time
import asyncio
import struct

from pyiskra.exceptions import InvalidResponseCode
from .BaseDevice import Device
from ..adapters import RestAPI, Modbus
from ..helper import (
    Measurements,
    Measurement,
    Phase_Measurements,
    Total_Measurements,
    Counter,
    Counters,
    counter_units,
    get_counter_direction,
    get_counter_type,
)

log = logging.getLogger(__name__)


class WM(Device):
    """
    Represents an Impact device.

    Attributes:
        supports_measurements (bool): Indicates whether the device supports measurements.
        supports_counters (bool): Indicates whether the device supports counters.
        fw_version (float): The firmware version of the device.
    """

    DEVICE_PARAMETERS = {
        "WM3M4": {"phases": 3, "resettable_counters": 0, "non_resettable_counters": 2},
        "WM3": {"phases": 3, "resettable_counters": 4, "non_resettable_counters": 4},
        "WM1": {"phases": 1, "resettable_counters": 4, "non_resettable_counters": 0},
        # Add more models as needed
    }

    supports_measurements = True
    supports_counters = True

    async def init(self):
        """
        Initializes the Impact device.

        This method retrieves basic information, updates the status, and logs a success message.
        """
        await self.get_basic_info()
        await self.update_status()
        log.debug(f"Successfully initialized {self.model} {self.serial}")

    async def get_measurements(self):
        """
        Retrieves measurements from the device.

        Returns:
            dict: A dictionary containing the measurements.
        """
        if isinstance(self.adapter, RestAPI):
            log.debug(
                f"Getting measurements from Rest API for {self.model} {self.serial}"
            )
            return await self.adapter.get_measurements()
        elif isinstance(self.adapter, Modbus):
            log.debug(f"Getting measurements from Modbus for {self.model} {self.serial}")
            response = await self.adapter.read_input_registers(2500, 106)

            phases = []
            for phase in range(self.phases):
                voltage = Measurement(
                    round(
                        struct.unpack(
                            ">f",
                            struct.pack(
                                ">HH",
                                response.registers[2 * phase],
                                response.registers[2 * phase + 1],
                            ),
                        )[0],
                        3,
                    ),
                    "V",
                )
                current = Measurement(
                    round(
                        struct.unpack(
                            ">f",
                            struct.pack(
                                ">HH",
                                response.registers[2 * phase + 16],
                                response.registers[2 * phase + 17],
                            ),
                        )[0],
                        3,
                    ),
                    "A",
                )
                active_power = Measurement(
                    round(
                        struct.unpack(
                            ">f",
                            struct.pack(
                                ">HH",
                                response.registers[2 * phase + 30],
                                response.registers[2 * phase + 31],
                            ),
                        )[0],
                        3,
                    ),
                    "W",
                )
                reactive_power = Measurement(
                    round(
                        struct.unpack(
                            ">f",
                            struct.pack(
                                ">HH",
                                response.registers[2 * phase + 38],
                                response.registers[2 * phase + 39],
                            ),
                        )[0],
                        3,
                    ),
                    "var",
                )
                apparent_power = Measurement(
                    round(
                        struct.unpack(
                            ">f",
                            struct.pack(
                                ">HH",
                                response.registers[2 * phase + 46],
                                response.registers[2 * phase + 47],
                            ),
                        )[0],
                        3,
                    ),
                    "VA",
                )
                power_factor = Measurement(
                    round(
                        struct.unpack(
                            ">f",
                            struct.pack(
                                ">HH",
                                response.registers[2 * phase + 54],
                                response.registers[2 * phase + 55],
                            ),
                        )[0],
                        3,
                    ),
                    "",
                )
                power_angle = Measurement(
                    round(
                        struct.unpack(
                            ">f",
                            struct.pack(
                                ">HH",
                                response.registers[2 * phase + 70],
                                response.registers[2 * phase + 71],
                            ),
                        )[0],
                        3,
                    ),
                    "°",
                )
                thd_current = Measurement(
                    round(
                        struct.unpack(
                            ">f",
                            struct.pack(
                                ">HH",
                                response.registers[2 * phase + 88],
                                response.registers[2 * phase + 81],
                            ),
                        )[0],
                        3,
                    ),
                    "%",
                )
                thd_voltage = Measurement(
                    round(
                        struct.unpack(
                            ">f",
                            struct.pack(
                                ">HH",
                                response.registers[2 * phase + 96],
                                response.registers[2 * phase + 97],
                            ),
                        )[0],
                        3,
                    ),
                    "%",
                )
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

            active_power_total = Measurement(
                round(
                    struct.unpack(
                        ">f",
                        struct.pack(
                            ">HH", response.registers[36], response.registers[37]
                        ),
                    )[0],
                    3,
                ),
                "W",
            )
            reactive_power_total = Measurement(
                round(
                    struct.unpack(
                        ">f",
                        struct.pack(
                            ">HH", response.registers[44], response.registers[45]
                        ),
                    )[0],
                    3,
                ),
                "VAR",
            )
            apparent_power_total = Measurement(
                round(
                    struct.unpack(
                        ">f",
                        struct.pack(
                            ">HH", response.registers[52], response.registers[53]
                        ),
                    )[0],
                    3,
                ),
                "VA",
            )
            power_factor_total = Measurement(
                round(
                    struct.unpack(
                        ">f",
                        struct.pack(
                            ">HH", response.registers[60], response.registers[61]
                        ),
                    )[0],
                    3,
                ),
                "",
            )
            power_angle_total = Measurement(
                round(
                    struct.unpack(
                        ">f",
                        struct.pack(
                            ">HH", response.registers[76], response.registers[77]
                        ),
                    )[0],
                    3,
                ),
                "°",
            )
            frequency = Measurement(
                round(
                    struct.unpack(
                        ">f",
                        struct.pack(
                            ">HH", response.registers[84], response.registers[85]
                        ),
                    )[0],
                    3,
                ),
                "Hz",
            )
            temperature = Measurement(
                round(
                    struct.unpack(
                        ">f",
                        struct.pack(
                            ">HH", response.registers[92], response.registers[93]
                        ),
                    )[0],
                    3,
                ),
                "°C",
            )
            total = Total_Measurements(
                active_power_total,
                reactive_power_total,
                apparent_power_total,
                power_factor_total,
                power_angle_total,
            )

            return Measurements(phases, total, frequency, temperature)

    async def get_counters(self):
        """
        Retrieves counters from the device.

        Returns:
            dict: A dictionary containing the counters.
        """
        if isinstance(self.adapter, RestAPI):
            log.debug(f"Getting counters from Rest API for {self.model} {self.serial}")
            return await self.adapter.get_counters()
        elif isinstance(self.adapter, Modbus):
            log.debug(f"Getting measurements from Modbus for {self.model} {self.serial}")

            # Open the connection
            handle_connection = not self.adapter.connected
            if handle_connection:
                await self.adapter.open_connection()

            response = await self.adapter.read_input_registers(2638, 16)
            direction_settings = await self.adapter.read_holding_registers(151, 1)
            resettable_settings = await self.adapter.read_holding_registers(421, 36)

            # Close the connection
            if handle_connection:
                await self.adapter.close_connection()

            non_resettable = []
            resettable = []
            reverse_connection = False
            if direction_settings.registers[0] & 2:
                reverse_connection = True

            for counter in range(self.resettable_counters):
                units = counter_units[resettable_settings.registers[10 * counter]]
                direction = get_counter_direction(
                    resettable_settings.registers[1 + 10 * counter], reverse_connection
                )
                counter_type = get_counter_type(direction, units)
                resettable.append(
                    Counter(
                        struct.unpack(
                            ">f",
                            struct.pack(
                                ">HH",
                                response.registers[2 * (counter)],
                                response.registers[1 + 2 * (counter)],
                            ),
                        )[0],
                        units,
                        direction,
                        counter_type,
                    )
                )

            return Counters(non_resettable, resettable)

    async def update_status(self):
        """
        Updates the status of the device.

        This method acquires a lock to ensure that only one update is running at a time.
        It retrieves measurements and counters, updates the corresponding attributes,
        and sets the update timestamp.
        """
        # If update is already running, wait for it to finish and then return
        if self.update_lock.locked():
            log.debug("Update already running for %s %s" % (self.model, self.serial))
            while self.update_lock.locked():
                await asyncio.sleep(0.1)
            return

        # If update is not running, acquire the lock and update
        async with self.update_lock:
            log.debug("Updating status for %s %s" % (self.model, self.serial))

            # if the adapter is Modbus, open the connection
            if isinstance(self.adapter, Modbus):
                await self.adapter.open_connection()

            self.measurements = await self.get_measurements()
            self.counters = await self.get_counters()

            # if the adapter is Modbus, close the connection
            if isinstance(self.adapter, Modbus):
                await self.adapter.close_connection()

            self.update_timestamp = time.time()
