# Description: Custom exceptions for pyiskra


class NotAuthorised(Exception):
    pass


class DeviceNotSupported(Exception):
    pass


class ProtocolNotSupported(Exception):
    pass


class DeviceConnectionError(Exception):
    pass


class DeviceTimeoutError(Exception):
    pass


class InvalidResponseCode(Exception):
    pass
