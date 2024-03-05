import time


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
    aparrent_power: Measurement
    power_factor: Measurement
    power_angle: Measurement

    def __init__(
        self,
        active_power=None,
        reactive_power=None,
        apparrent_power=None,
        power_factor=None,
        power_angle=None,
    ):
        self.active_power = active_power
        self.reactive_power = reactive_power
        self.apparrent_power = apparrent_power
        self.power_factor = power_factor
        self.power_angle = power_angle


class Measurements:
    phases: list[Phase_Measurements]
    total: Total_Measurements
    frequency: Measurement
    temperature: Measurement

    def __init__(
        self, phases=None, total=None, frequency=None, temperature=None
    ):
        self.timestamp = time.time()

        self.phases = phases
        self.total = total
        self.frequency = frequency
        self.temperature = temperature


class Counter:
    value: float
    units: str
    direction: str

    def __init__(
        self,
        value=None,
        units=None,
        direction=None,
    ):
        self.value = value
        self.units = units
        self.direction = direction


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
