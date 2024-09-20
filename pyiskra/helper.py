import struct
import time
from enum import Enum


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

    def __init__(self, phases=None, total=None, frequency=None, temperature=None):
        self.timestamp = time.time()

        self.phases = phases
        self.total = total
        self.frequency = frequency
        self.temperature = temperature


class CounterType(Enum):
    ACTIVE_IMPORT = "active_import"
    ACTIVE_EXPORT = "active_export"
    REACTIVE_IMPORT = "reactive_import"
    REACTIVE_EXPORT = "reactive_export"
    APPARENT_IMPORT = "apparent_import"
    APPARENT_EXPORT = "apparent_export"
    UNKNOWN = "unknown"


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


counter_units = ["", "Wh", "varh", "VAh"]


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

    def get_float(self, desired_address, word_swap=True):
        value = self.get_value(desired_address)
        next_value = self.get_value(desired_address + 1)
        if value is None or next_value is None:
            return None
        # Combine the two 16-bit register values into a 32-bit integer
        combined = (next_value << 16) | value
        if word_swap:
            combined = (value << 16) | next_value
        # Convert the 32-bit integer to a float
        return round(struct.unpack("!f", struct.pack("!I", combined))[0], 3)

    def get_uint32(self, desired_address, word_swap=True):
        high_word = self.get_value(desired_address)
        low_word = self.get_value(desired_address + 1)
        if word_swap:
            return (low_word << 16) + high_word
        return (high_word << 16) + low_word

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
