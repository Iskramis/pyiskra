import logging
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.client import AsyncModbusSerialClient

from .BaseAdapter import Adapter
from ..helper import BasicInfo
from ..exceptions import InvalidResponseCode, DeviceConnectionError

log = logging.getLogger(__name__)


class Modbus(Adapter):
    """Adapter class for making REST API calls."""

    def __init__(
        self,
        protocol: str,
        ip_address=None,
        modbus_address=33,
        port=10001,
        stopbits=2,
        bytesize=8,
        parity="N",
        baudrate=115200,
    ):
        """
        Initialize the RestAPI adapter.

        Args:
            ip_address (str): The IP address of the REST API.
            device_index (int, optional): The index of the device. Defaults to None.
            authentication (dict, optional): The authentication credentials. Defaults to None.
        """
        self.modbus_address = modbus_address
        self.ip_address = ip_address
        if protocol == "tcp":
            self.protocol = "tcp"
            self.client = AsyncModbusTcpClient(host=ip_address, port=port, timeout=1)
        elif protocol == "rtu":
            self.protocol = "rtu"
            self.client = AsyncModbusSerialClient(
                method="rtu",
                port=port,
                stopbits=stopbits,
                bytesize=bytesize,
                parity=parity,
                baudrate=baudrate,
                timeout=1,
            )
        else:
            raise ValueError("Invalid protocol")

    @staticmethod
    def convert_registers_to_string(registers):
        """Converts a list of 16-bit registers to a string, separating each 8 bits of the register for each character."""
        string = ""
        for register in registers:
            high_byte = register >> 8
            low_byte = register & 0xFF
            string += chr(high_byte) + chr(low_byte)
        return string.split("\0")[0].strip()

    async def open_connection(self):
        """Connects to the device."""
        log.debug(f"Connecting to the device {self.ip_address}")
        await self.client.connect()
        if not self.connected:
            raise DeviceConnectionError(
                f"Failed to connect to the device {self.ip_address}"
            )

    def close_connection(self):
        """Closes the connection to the device."""
        log.debug(f"Closing the connection to the device {self.ip_address}")
        return self.client.close()

    @property
    def connected(self) -> bool:
        """Returns the connection status."""
        return self.client.connected

    async def get_basic_info(self):
        """
        Retrieves basic information about the device.

        Returns:
            BasicInfo: An object containing the basic information of the device.
        """
        basic_info = {}

        # Open the connection
        await self.open_connection()
        response = await self.read_input_registers(1, 14)

        basic_info["model"] = self.convert_registers_to_string(response.registers[0:8])
        basic_info["serial"] = self.convert_registers_to_string(
            response.registers[8:12]
        )
        basic_info["sw_ver"] = response.registers[13] / 100

        response = await self.read_holding_registers(101, 43)

        # Close the connection
        self.close_connection()
        basic_info["description"] = self.convert_registers_to_string(
            response.registers[0:20]
        )
        basic_info["location"] = self.convert_registers_to_string(
            response.registers[20:40]
        )

        return BasicInfo(**basic_info)

    async def read_holding_registers(self, start, count):
        """
        Reads the specified number of registers starting from the specified address.

        Args:
            start (int): The starting address of the registers.
            count (int): The number of registers to read.

        Returns:
            list: A list of the read registers.
        """
        handle_connection = not self.connected
        if handle_connection:
            await self.open_connection()
        try:
            response = await self.client.read_holding_registers(
                start, count, slave=self.modbus_address
            )
        except Exception as e:
            raise DeviceConnectionError(f"Failed to read holding registers: {e}") from e

        if handle_connection:
            self.close_connection()

        return response

    async def read_input_registers(self, start, count):
        """
        Reads the specified number of registers starting from the specified address.

        Args:
            start (int): The starting address of the registers.
            count (int): The number of registers to read.

        Returns:
            list: A list of the read registers.
        """
        handle_connection = not self.connected
        if handle_connection:
            await self.open_connection()
        try:
            response = await self.client.read_input_registers(
                start, count, slave=self.modbus_address
            )
        except Exception as e:
            raise DeviceConnectionError(f"Failed to read holding registers: {e}") from e

        if handle_connection:
            self.close_connection()

        return response
