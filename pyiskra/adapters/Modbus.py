import logging
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.client import AsyncModbusSerialClient

from .BaseAdapter import Adapter
from ..helper import BasicInfo, ModbusMapper
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
        self.port = port
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
        if not self.client:
            raise DeviceConnectionError("The connection is not configured")

        await self.client.connect()
        if not self.connected:
            if self.protocol == "tcp":
                raise DeviceConnectionError(
                    f"Failed to connect to the device {self.ip_address} on port {self.port}"
                )
            elif self.protocol == "rtu":
                raise DeviceConnectionError(
                    f"Failed to connect to the device on port {self.port}"
                )

    async def close_connection(self):
        """Closes the connection to the device."""
        log.debug(f"Closing the connection to the device {self.ip_address}")
        if not self.client:
            raise DeviceConnectionError("The connection is not configured")

        self.client.close()
        if self.connected:
            if self.protocol == "tcp":
                raise DeviceConnectionError(
                    f"Failed to close the connection to the device {self.ip_address} on port {self.port}"
                )
            elif self.protocol == "rtu":
                raise DeviceConnectionError(
                    f"Failed to close the connection to the device on port {self.port}"
                )

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
        try:
            data = await self.read_input_registers(1, 14)
            mapper = ModbusMapper(data, 1)

            basic_info["model"] = mapper.get_string_range(1, 8)
            basic_info["serial"] = mapper.get_string_range(9, 4)
            basic_info["sw_ver"] = mapper.get_uint16(13) / 100

            data = await self.read_holding_registers(101, 40)
            mapper = ModbusMapper(data, 101)
        except Exception as e:
            await self.close_connection()
            raise DeviceConnectionError(f"Failed to read basic info: {e}") from e

        # Close the connection
        await self.close_connection()
        basic_info["description"] = mapper.get_string_range(101, 20)
        basic_info["location"] = mapper.get_string_range(121, 20)
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
            await self.close_connection()

        return response.registers

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
            await self.close_connection()

        return response.registers
