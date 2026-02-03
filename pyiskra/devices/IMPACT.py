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
    Time_Blocks_Measurements,
    Time_Block,
    Measurement,
    Phase_Measurements,
    Total_Measurements,
    Consumed_Energy,
    Excess_Power,
    Max_15min_Power,
    Active_Power_Measurements,
    Counter,
    Counters,
    get_counter_units,
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
        "IE38": {"phases": 3, "resettable_counters": 16, "non_resettable_counters": 4, "time_block_count": 5},
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
        # update "supports_iMC_functions" status flag
        if isinstance(self.adapter, Modbus):
            self.supports_iMC_functions = await self.check_iMC_functions_support()
            # Get nominal power
            self.nominal_power = await self.get_used_current_and_voltage()
            # check time blocks support
            self.supports_time_blocks = await self.check_time_blocks_support()  
        elif isinstance(self.adapter, RestAPI):
            self.supports_iMC_functions = await self.adapter.check_time_blocks_support()
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
                units = get_counter_units(non_resettable_settings_mapper.get_uint16(421 + 4 * counter))

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
                units = get_counter_units(resettable_settings_mapper.get_uint16(437 + 4 * counter))

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
            # Time blocks measurements
            self.time_blocks_measurements = await self.get_time_blocks_measurements()

            # if the adapter is Modbus, close the connection
            if isinstance(self.adapter, Modbus):
                await self.adapter.close_connection()

            self.update_timestamp = time.time()

    async def get_used_current_and_voltage(self):
        """
        Get meter configuration of used current and voltage.
        """
        log.debug(f"Getting config registers.")
        cnf_data = await self.adapter.read_holding_registers(148, 2)
        mapper = ModbusMapper(cnf_data, 148)

        cnf_data = await self.adapter.read_input_registers(15, 4)
        data_mapper = ModbusMapper(cnf_data, 15) # used voltage and current in cV & cA

        used_current = (mapper.get_uint16(148)/10000) * (data_mapper.get_uint16(17)/100)
        used_voltage = (mapper.get_uint16(149)/10000) * (data_mapper.get_uint16(15)/100)

        nominal_power = 3 * used_voltage * used_current

        return nominal_power

            
    async def get_config_register_value(self):
        """
        Get meter configuration status.
        """
        log.debug(f"Getting config register status.")
        cnf_data = await self.adapter.read_holding_registers(22514, 1)
        data_mapper = ModbusMapper(cnf_data, 22514)
        return data_mapper

    async def check_iMC_functions_support(self):
        """
        Get iMC functions status bit
        """
        mapper = await self.get_config_register_value()
        cnf_data = mapper.get_uint16(22514)
        iMC_bit = (cnf_data >> 4) & 1
        return bool(iMC_bit)
    
    async def check_time_blocks_support(self):
        """
        Check SW version for time blocks support
        """
        cnf_data = await self.adapter.read_input_registers(13, 1)
        mapper = ModbusMapper(cnf_data, 13)
        cnf_data = mapper.get_uint16(13)
        sw_version = cnf_data/100
        if sw_version < 1 or sw_version > 1.5:
            return True
        else:
            return False

    async def check_time_blocks_support(self):
        """
        Get version of meter software
        """
        log.debug(f"Get meter software version.")
        cnf_data = await self.adapter.read_input_registers(13, 1)
        mapper = ModbusMapper(cnf_data, 13)
        cnf_data = mapper.get_uint16(13)
        sw_version = cnf_data / 100
        if sw_version < 1 or sw_version > 1.5:
            return True
        else:
            return False

    async def get_time_blocks_measurements(self):
        """
        Retrieves time block measurements from the device.

        Returns:
            dict: A dictionary containing the time blocks measurements.
        """

        if isinstance(self.adapter, RestAPI):
            log.debug(f"Getting counters from Rest API for {self.model} {self.serial}")
            if self.supports_iMC_functions:
                return await self.adapter.get_tb_measurements()
            else:
                return None
        
        elif isinstance(self.adapter, Modbus):
            if (not self.supports_time_blocks):
                return None
            # Open the connection
            handle_connection = not self.adapter.connected
            if handle_connection:
                await self.adapter.open_connection()

            log.debug(f"Getting time blocks measurements for {self.model} {self.serial}")
            data = await self.adapter.read_input_registers(6761, 238)
            mapper = ModbusMapper(data, 6761)

            data = await self.adapter.read_holding_registers(990, 5)
            limits__mapper = ModbusMapper(data, 990)

            active_power_measurements = await self.adapter.read_input_registers(5244, 18)
            active_power_measurements_mapper = ModbusMapper(active_power_measurements, 5244)

            capture_timestamp = await self.adapter.read_input_registers(4901, 2)
            capture_timestamp_mapper = ModbusMapper(capture_timestamp, 4901)

            pred_15min_active_limit = await self.adapter.read_input_registers(5261, 2)
            pred_15min_active_limit_mapper = ModbusMapper(pred_15min_active_limit, 5261)

            if handle_connection:
                await self.adapter.close_connection()

            time_blocks = []
            consumed_energy = []
            excess_power = []
            max_15min_power = []

            exponent = mapper.get_int16(6762)

            for block in range (self.time_block_count):
                total =  Measurement(mapper.get_uint32(6786 + 42 * block)* (10**exponent),
                    "Wh",
                )
                timestamp_total =  Measurement(capture_timestamp_mapper.get_timestamp(4901),
                "",
                )
                last_month =  Measurement(mapper.get_uint32(6788 + 42 * block)* (10**exponent),
                    "Wh",
                )
                timestamp_last_month =  Measurement(mapper.get_timestamp(6766),
                "",
                )
                two_months_ago =  Measurement(mapper.get_uint32(6790 + 42 * block)* (10**exponent),
                    "Wh",
                )
                timestamp_two_months_ago =  Measurement(mapper.get_timestamp(6768),
                "",
                )
                last_year =  Measurement(mapper.get_uint32(6792 + 42 * block)* (10**exponent),
                    "Wh",
                )
                timestamp_last_year =  Measurement(mapper.get_timestamp(6770),
                "",
                )
                two_years_ago =  Measurement(mapper.get_uint32(6794 + 42 * block)* (10**exponent),
                    "Wh",
                )
                timestamp_two_years_ago =  Measurement(mapper.get_timestamp(6772),
                "",
                )
                this_month =  Measurement(mapper.get_uint32(6796 + 42 * block)* (10**exponent),
                    "Wh",
                )
                previous_month =  Measurement(mapper.get_uint32(6798 + 42 * block)* (10**exponent),
                    "Wh",
                )
                this_year =  Measurement(mapper.get_uint32(6800 + 42 * block)* (10**exponent),
                    "Wh",
                )
                previous_year =  Measurement(mapper.get_uint32(6802 + 42 * block)* (10**exponent),
                    "Wh",
                )
                consumed_energy.append(
                    Consumed_Energy(
                        total,
                        timestamp_total,
                        last_month,
                        timestamp_last_month,
                        two_months_ago,
                        timestamp_two_months_ago,
                        last_year,
                        timestamp_last_year,
                        two_years_ago,
                        timestamp_two_years_ago,
                        this_month,
                        previous_month,
                        this_year,
                        previous_year,
                    )
                )
                excess_power_limit =  Measurement(round((limits__mapper.get_uint16(990 + 1 * block) * (self.nominal_power/1000))/10), 
                    "W",
                )
                excess_power_this_month =  Measurement(mapper.get_t5(6804 + 42 * block),
                    "W",
                )
                excess_power_previous_month =  Measurement(mapper.get_t5(6806 + 42 * block),
                    "W",
                )
                excess_power.append(
                    Excess_Power(
                        excess_power_limit,
                        excess_power_this_month,
                        excess_power_previous_month,
                    )
                )
                max_15min_power_since_reset =  Measurement(mapper.get_t5(6808 + 42 * block),
                    "W",
                )
                timestamp_since_reset =  Measurement(mapper.get_timestamp(6810 + 42 * block),
                "",
                )
                max_15min_power_this_month =  Measurement(mapper.get_t5(6812 + 42 * block),
                    "W",
                )
                timestamp_this_month =  Measurement(mapper.get_timestamp(6814 + 42 * block),
                "",
                )
                max_15min_power_previous_month =  Measurement(mapper.get_t5(6816 + 42 * block),
                    "W",
                )
                timestamp_previous_month =  Measurement(mapper.get_timestamp(6818 + 42 * block),
                "",
                )
                max_15min_power_this_year =  Measurement(mapper.get_t5(6820 + 42 * block),
                    "W",
                )
                timestamp_this_year =  Measurement(mapper.get_timestamp(6822 + 42 * block),
                "",
                )
                max_15min_power_previous_year =  Measurement(mapper.get_t5(6824 + 42 * block),
                    "W",
                )
                timestamp_previous_year =  Measurement(mapper.get_timestamp(6826 + 42 * block),
                "",
                )
                reset_timestamp =  Measurement(mapper.get_timestamp(6764),
                "",
                )
                max_15min_power.append(
                    Max_15min_Power(
                        max_15min_power_since_reset,
                        timestamp_since_reset,
                        max_15min_power_this_month,
                        timestamp_this_month,
                        max_15min_power_previous_month,
                        timestamp_previous_month,
                        max_15min_power_this_year,
                        timestamp_this_year,
                        max_15min_power_previous_year,
                        timestamp_previous_year,
                        reset_timestamp,
                    )
                )

                time_blocks.append(
                    Time_Block(
                        consumed_energy,
                        excess_power,
                        max_15min_power,
                    )
                )

            actual_value =  Measurement(active_power_measurements_mapper.get_t5(5245),
                "W",
            )
            thermal_function =  Measurement(active_power_measurements_mapper.get_t5(5247),
                "W",
            )
            predicted_15min =  Measurement(active_power_measurements_mapper.get_t5(5249),
                "W",
            )
            predicted_15min_active_limit =  Measurement(pred_15min_active_limit_mapper.get_int16(5261)/100,
                "%",
            )
            last_15min =  Measurement(active_power_measurements_mapper.get_t5(5251),
                "W",
            )
            max_15min_since_reset =  Measurement(mapper.get_t5(6778),
                "W",
            )
            active_energy_total =  Measurement(mapper.get_uint32(6774)* (10**exponent),
                "W",
            )
            timestamp =  Measurement(mapper.get_timestamp(6780),
                "",
            )
            active_power_measurements_import = Active_Power_Measurements(
                actual_value, 
                thermal_function,
                predicted_15min,
                predicted_15min_active_limit,
                last_15min,
                max_15min_since_reset,
                active_energy_total,
                timestamp,
            )
            
            actual_value =  Measurement(active_power_measurements_mapper.get_t5(5253),
                "W",
            )
            thermal_function =  Measurement(active_power_measurements_mapper.get_t5(5255),
                "W",
            )
            predicted_15min =  Measurement(active_power_measurements_mapper.get_t5(5257),
                "W",
            )
            predicted_15min_active_limit =  Measurement(0,
                "",
            )
            last_15min =  Measurement(active_power_measurements_mapper.get_t5(5259),
                "W",
            )
            max_15min_since_reset =  Measurement(mapper.get_uint32(6782)* (10**exponent),
                "W",
            )
            active_energy_total =  Measurement(mapper.get_uint32(6776)* (10**exponent),
                "W",
            )
            timestamp =  Measurement(mapper.get_timestamp(6784),
                "",
            )
            active_power_measurements_export = Active_Power_Measurements(
                actual_value, 
                thermal_function,
                predicted_15min,
                predicted_15min_active_limit,
                last_15min,
                max_15min_since_reset,
                active_energy_total,
                timestamp,
            )
            
            active_block_index =  Measurement(mapper.get_uint16(6763),
                "",
            ) 
            time_to_end_interval =  Measurement(active_power_measurements_mapper.get_uint16(5244),
                "s",
            )

            return Time_Blocks_Measurements(time_blocks, active_power_measurements_import, active_power_measurements_export, active_block_index, time_to_end_interval)
