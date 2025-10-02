import logging
import time
import asyncio
import struct
import re

from .BaseDevice import Device
from ..adapters import RestAPI, Modbus
from ..helper import (
    IntervalMeasurementStats,
    MeasurementType,
    ModbusMapper,
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
from ..exceptions import MeasurementTypeNotSupported

log = logging.getLogger(__name__)


class Impact(Device):
    """
    Represents an Impact device.

    Attributes:
        supports_measurements (bool): Indicates whether the device supports measurements.
        supports_counters (bool): Indicates whether the device supports counters.
        fw_version (float): The firmware version of the device.
    """

    DEVICE_PARAMETERS = {
        "IE38": {"phases": 3, "resettable_counters": 16, "non_resettable_counters": 4},
        "IE35": {"phases": 3, "resettable_counters": 16, "non_resettable_counters": 4},
        "IE14": {"phases": 1, "resettable_counters": 8, "non_resettable_counters": 4},
        # Add more models as needed
    }

    supports_measurements = True
    supports_counters = True
    supports_interval_measurements = True

    async def init(self):
        """
        Initializes the Impact device.

        This method retrieves basic information, updates the status, and logs a success message.
        """
        await self.get_basic_info()
        await self.update_status()
        log.debug(f"Successfully initialized {self.model} {self.serial}")

    async def get_measurements(
        self, measurement_type: MeasurementType = MeasurementType.ACTUAL_MEASUREMENTS
    ):
        """
        Retrieves measurements from the device.

        Returns:
            dict: A dictionary containing the measurements.
        """
        if (
            measurement_type != MeasurementType.ACTUAL_MEASUREMENTS
            and self.supports_interval_measurements == False
        ):
            raise MeasurementTypeNotSupported(
                f"{measurement_type} is not supported by {self.model}"
            )

        if isinstance(self.adapter, RestAPI):
            log.debug(
                f"Getting measurements from Rest API for {self.model} {self.serial}"
            )
            return await self.adapter.get_measurements()
        elif isinstance(self.adapter, Modbus):
            log.debug(
                f"Getting measurements from Modbus for {self.model} {self.serial}"
            )

            offset = 0
            last_interval_duration = None
            time_since_last_measurement = None
            avg_measurement_counter = None

            # Other measurement type registers are just shifted
            if measurement_type == MeasurementType.AVERAGE_MEASUREMENTS:
                offset = 5400
            elif measurement_type == MeasurementType.MAX_MEASUREMENTS:
                offset = 5500
            elif measurement_type == MeasurementType.MIN_MEASUREMENTS:
                offset = 5600

            interval_stats = None
            data = await self.adapter.read_input_registers(100 + offset, 91)
            mapper = ModbusMapper(data, 100)

            if measurement_type != MeasurementType.ACTUAL_MEASUREMENTS:
                interval_stats = IntervalMeasurementStats()
                interval_data = await self.adapter.read_input_registers(5500, 2)
                interval_stats_mapper = ModbusMapper(interval_data, 100)
                interval_stats.last_interval_duration = (
                    interval_stats_mapper.get_uint16(100) / 10
                )
                interval_stats.time_since_last_measurement = (
                    interval_stats_mapper.get_int16(101) / 10
                )

            phases = []
            for phase in range(self.phases):
                voltage = Measurement(
                    mapper.get_t5(107 + 2 * phase),
                    "V",
                )
                current = Measurement(
                    mapper.get_t5(126 + 2 * phase),
                    "A",
                )
                active_power = Measurement(
                    mapper.get_t6(142 + 2 * phase),
                    "W",
                )
                reactive_power = Measurement(
                    mapper.get_t6(150 + 2 * phase),
                    "var",
                )
                apparent_power = Measurement(
                    mapper.get_t5(158 + 2 * phase),
                    "VA",
                )
                power_factor = Measurement(
                    mapper.get_t7(166 + 2 * phase)["value"],
                    "",
                )
                power_angle = Measurement(
                    mapper.get_int16(173 + phase) / 100,
                    "°",
                )
                thd_voltage = Measurement(
                    mapper.get_uint16(182 + phase) / 100,
                    "%",
                )
                thd_current = Measurement(
                    mapper.get_uint16(188 + phase) / 100,
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
                mapper.get_t6(140),
                "W",
            )
            reactive_power_total = Measurement(
                mapper.get_t6(148),
                "var",
            )
            apparent_power_total = Measurement(
                mapper.get_t5(156),
                "VA",
            )
            power_factor_total = Measurement(
                mapper.get_t7(164)["value"],
                "",
            )
            power_angle_total = Measurement(
                mapper.get_int16(172) / 100,
                "°",
            )
            frequency = Measurement(
                mapper.get_t5(105),
                "Hz",
            )
            temperature = Measurement(
                mapper.get_int16(181) / 100,
                "°C",
            )
            total = Total_Measurements(
                active_power_total,
                reactive_power_total,
                apparent_power_total,
                power_factor_total,
                power_angle_total,
            )

            return Measurements(phases, total, frequency, temperature, interval_stats)

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
            # Open the connection
            handle_connection = not self.adapter.connected
            if handle_connection:
                await self.adapter.open_connection()

            log.debug(f"Getting counters from Modbus for {self.model} {self.serial}")
            data = await self.adapter.read_input_registers(2750, 96)
            data_mapper = ModbusMapper(data, 2750)

            direction_settings = await self.adapter.read_holding_registers(151, 1)

            non_resettable_counter_settings = await self.adapter.read_holding_registers(
                421, 16
            )
            non_resettable_settings_mapper = ModbusMapper(
                non_resettable_counter_settings, 421
            )

            resettable_counter_settings = await self.adapter.read_holding_registers(
                437, 64
            )
            resettable_settings_mapper = ModbusMapper(resettable_counter_settings, 437)

            if handle_connection:
                await self.adapter.close_connection()

            non_resettable = []
            resettable = []
            reverse_connection = False
            if direction_settings[0] & 2:
                reverse_connection = True

            for counter in range(self.non_resettable_counters):
                units = counter_units[
                    non_resettable_settings_mapper.get_uint16(421 + 4 * counter)
                ]
                direction = get_counter_direction(
                    non_resettable_settings_mapper.get_uint16(422 + 4 * counter),
                    reverse_connection,
                )
                counter_type = get_counter_type(direction, units)
                non_resettable.append(
                    Counter(
                        data_mapper.get_float(2752 + 2 * counter),
                        units,
                        direction,
                        counter_type,
                    )
                )

            for counter in range(self.resettable_counters):
                units = counter_units[
                    resettable_settings_mapper.get_uint16(437 + 4 * counter)
                ]
                direction = get_counter_direction(
                    resettable_settings_mapper.get_uint16(438 + 4 * counter),
                    reverse_connection,
                )
                counter_type = get_counter_type(direction, units)
                resettable.append(
                    Counter(
                        data_mapper.get_float(2760 + 2 * counter),
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
