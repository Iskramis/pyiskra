from datetime import datetime
import struct
import time
from enum import Enum


class IntervalMeasurementStats:
    last_interval_duration: int
    time_since_last_measurement: int


class BasicInfo:
    def __init__(
        self,
        serial,
        model,
        description,
        location,
        sw_ver,
    ):
        self.serial = serial
        self.model = model
        self.description = description
        self.location = location
        self.sw_ver = sw_ver

    def __str__(self):
        return f'{self.model} {self.serial} {self.sw_ver} {self.description} {self.location}'

class Measurement:
    value: float
    units: str

    def __init__(self, value=None, units=None):
        self.value = value
        self.units = units


class Phase_Measurements:
    voltage: Measurement
    current: Measurement
    active_power: Measurement
    reactive_power: Measurement
    apparent_power: Measurement
    power_factor: Measurement
    power_angle: Measurement
    thd_voltage: Measurement
    thd_current: Measurement

    def __init__(
        self,
        voltage=None,
        current=None,
        active_power=None,
        reactive_power=None,
        apparent_power=None,
        power_factor=None,
        power_angle=None,
        thd_voltage=None,
        thd_current=None,
    ):
        self.voltage = voltage
        self.current = current
        self.active_power = active_power
        self.reactive_power = reactive_power
        self.apparent_power = apparent_power
        self.power_factor = power_factor
        self.power_angle = power_angle
        self.thd_voltage = thd_voltage
        self.thd_current = thd_current


class Total_Measurements:
    active_power: Measurement
    reactive_power: Measurement
    apparent_power: Measurement
    power_factor: Measurement
    power_angle: Measurement

    def __init__(
        self,
        active_power=None,
        reactive_power=None,
        apparent_power=None,
        power_factor=None,
        power_angle=None,
    ):
        self.active_power = active_power
        self.reactive_power = reactive_power
        self.apparent_power = apparent_power
        self.power_factor = power_factor
        self.power_angle = power_angle


class Measurements:
    phases: list[Phase_Measurements]
    total: Total_Measurements
    frequency: Measurement
    temperature: Measurement
    interval_stats: IntervalMeasurementStats

    def __init__(
        self,
        phases=None,
        total=None,
        frequency=None,
        temperature=None,
        interval_stats=None,
    ):
        self.timestamp = time.time()

        self.phases = phases
        self.total = total
        self.frequency = frequency
        self.temperature = temperature
        self.interval_stats = interval_stats


class CounterType(Enum):
    ACTIVE_IMPORT = "active_import"
    ACTIVE_EXPORT = "active_export"
    REACTIVE_IMPORT = "reactive_import"
    REACTIVE_EXPORT = "reactive_export"
    APPARENT_IMPORT = "apparent_import"
    APPARENT_EXPORT = "apparent_export"
    SQUARED_IMPORT = "squared_import"
    SQUARED_EXPORT = "squared_export"
    UNKNOWN = "unknown"


class MeasurementType(Enum):
    ACTUAL_MEASUREMENTS = "actual_measurements"
    AVERAGE_MEASUREMENTS = "average_measurements"
    MIN_MEASUREMENTS = "min_measurements"
    MAX_MEASUREMENTS = "max_measurements"


class Counter:
    value: float
    units: str
    direction: str
    counter_type: CounterType

    def __init__(
        self,
        value=None,
        units=None,
        direction=None,
        counter_type=None,
    ):
        self.value = value
        self.units = units
        self.direction = direction
        self.counter_type = counter_type


class Counters:
    non_resettable: list[Counter]
    resettable: list[Counter]

    def __init__(self, non_resettable=None, resettable=None):
        self.timestamp = time.time()
        self.non_resettable = non_resettable if non_resettable is not None else []
        self.resettable = resettable if resettable is not None else []


counter_units = ("", "Wh", "varh", "VAh")

def get_counter_units(counter_parameter):
    # Check if counter is set to Ampere-squared hours
    if counter_parameter & 0x20:
        return "AAh"    
    # first 2 bits only
    return counter_units[counter_parameter & 0x3] 


def get_counter_direction(quadrants, reverse_connection):
    quadrants = quadrants & 0x0F
    direction = 0
    if quadrants == 9 or quadrants == 3:
        direction = "export"
    elif quadrants == 6 or quadrants == 12:
        direction = "import"
    elif quadrants == 15:
        direction = "bidirectional"

    if reverse_connection:
        if direction == "import":
            direction = "export"
        elif direction == "export":
            direction = "import"

    return direction


def get_counter_type(direction, units):
    if direction == "import":
        if units == "Wh":
            return CounterType.ACTIVE_IMPORT
        elif units == "varh":
            return CounterType.REACTIVE_IMPORT
        elif units == "VAh":
            return CounterType.APPARENT_IMPORT
    elif direction == "export":
        if units == "Wh":
            return CounterType.ACTIVE_EXPORT
        elif units == "varh":
            return CounterType.REACTIVE_EXPORT
        elif units == "VAh":
            return CounterType.APPARENT_EXPORT

    return CounterType.UNKNOWN


class ModbusMapper:
    def __init__(self, register_values, start_address):
        self.register_values = register_values
        self.start_address = start_address

    def get_value(self, desired_address):
        if (
            desired_address < self.start_address
            or desired_address >= self.start_address + len(self.register_values)
        ):
            raise Exception("desired address out of range")

        index = desired_address - self.start_address
        return self.register_values[index]

    def get_t5(self, desired_address, word_swap=False):
        high_word = self.get_value(desired_address)
        low_word = self.get_value(desired_address + 1)

        combined = (high_word << 16) | low_word
        if word_swap:
            combined = (low_word << 16) | high_word
        value = combined & 0xFFFFFF  # bits 0-23
        exponent = (combined >> 24) & 0xFF  # bits 24-31
        if exponent & 0x80:  # if the sign bit is set
            exponent -= 0x100  # convert to signed
        return round(value * (10**exponent), 3)

    def get_t6(self, desired_address, word_swap=False):
        high_word = self.get_value(desired_address)
        low_word = self.get_value(desired_address + 1)

        combined = (high_word << 16) | low_word
        if word_swap:
            combined = (low_word << 16) | high_word
        value = combined & 0xFFFFFF  # bits 0-23
        exponent = (combined >> 24) & 0xFF  # bits 24-31
        if exponent & 0x80:  # if the sign bit is set
            exponent -= 0x100  # convert to signed
        if value & 0x800000:  # if the sign bit is set
            value -= 0x1000000  # convert to signed
        return round(value * (10**exponent), 3)

    def get_t7(self, desired_address, word_swap=False):
        high_word = self.get_value(desired_address)
        low_word = self.get_value(desired_address + 1)

        combined = (high_word << 16) | low_word
        if word_swap:
            combined = (low_word << 16) | high_word

        value = combined & 0xFFFF  # bits 0-15
        inductive_capacitive = (combined >> 16) & 0xFF  # bits 16-23
        import_export = (combined >> 24) & 0xFF  # bits 24-31

        inductive_capacitive_str = (
            "inductive" if inductive_capacitive == 0x00 else "capacitive"
        )
        import_export_str = "import" if import_export == 0x00 else "export"

        return {
            "value": value / 10000,
            "inductive_capacitive": inductive_capacitive_str,
            "import_export": import_export_str,
        }

    def get_uint16(self, desired_address):
        value = self.get_value(desired_address)
        return value

    def get_int16(self, desired_address):
        value = self.get_value(desired_address)
        if value is None:
            return None
        if value > 32767:
            value -= 65536
        return value

    def get_timestamp(self, desired_address):
        value = self.get_uint32(desired_address)
        return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(value))

    def get_float(self, desired_address, word_swap=False):
        value = self.get_value(desired_address)
        next_value = self.get_value(desired_address + 1)
        if value is None or next_value is None:
            return None
        # Combine the two 16-bit register values into a 32-bit integer
        combined = (value << 16) | next_value

        if word_swap:
            combined = (next_value << 16) | value
        # Convert the 32-bit integer to a float
        return round(struct.unpack("!f", struct.pack("!I", combined))[0], 3)

    def get_uint32(self, desired_address, word_swap=False):
        high_word = self.get_value(desired_address)
        low_word = self.get_value(desired_address + 1)
        if word_swap:
            return (low_word << 16) + high_word
        return (high_word << 16) + low_word

    def get_int32(self, desired_address, word_swap=False):
        high_word = self.get_value(desired_address)
        low_word = self.get_value(desired_address + 1)
        value = (high_word << 16) + low_word
        if word_swap:
            value = (low_word << 16) + high_word

        if value & 0x80000000:  # if the sign bit is set
            value -= 0x100000000  # convert to signed
        return value

    def get_string(self, desired_address):
        value = self.get_value(desired_address)
        high_byte = (value >> 8) & 0xFF
        low_byte = value & 0xFF
        return "".join([chr(high_byte), chr(low_byte)])

    def get_string_range(self, desired_address, size):
        return "".join(
            [
                self.get_string(register)
                for register in range(desired_address, desired_address + size)
            ]
        )

    def dump(self):
        for i, value in enumerate(self.register_values):
            print(f"Address {self.start_address + i}: {value} 0x{value:04X}")
