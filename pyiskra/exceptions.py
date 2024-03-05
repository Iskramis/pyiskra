# Description: Custom exceptions for pyiskra


class NotAuthorised(Exception):
    pass


class DeviceNotSupported(Exception):
    pass


class DeviceConnectionError(Exception):
    pass


class InvalidResponseCode(Exception):
    pass
