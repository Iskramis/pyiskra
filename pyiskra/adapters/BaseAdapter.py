class Adapter:
    """Base class for all adapters."""

    async def get_basic_info(self):
        """Init status."""
        # Re-defined in all sub-classes
        raise NotImplementedError
