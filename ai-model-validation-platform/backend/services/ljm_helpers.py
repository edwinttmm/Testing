"""
LabJack LJM Helper Functions
Provides compatibility layer for LJM library functions that may not exist in all versions
"""

from labjack import ljm

def get_device_type_string(device_type_num: int) -> str:
    """Convert device type number to string representation"""
    device_type_map = {
        3: "U3",
        4: "T4", 
        7: "T7",
        8: "T8",
        9: "U6",
        200: "DIGIT",
        84: "TSERIES"
    }
    
    # Add missing constants to LJM if they don't exist
    try:
        if not hasattr(ljm.constants, 'dtU3'):
            ljm.constants.dtU3 = 3
        if not hasattr(ljm.constants, 'dtU6'):
            ljm.constants.dtU6 = 9
    except AttributeError:
        pass
    
    # Try using constants if available
    try:
        if device_type_num == ljm.constants.dtT4:
            return "T4"
        elif device_type_num == ljm.constants.dtT7:
            return "T7"
        elif device_type_num == ljm.constants.dtT8:
            return "T8"
        elif device_type_num == ljm.constants.dtTSERIES:
            return "TSERIES"
    except (AttributeError, KeyError):
        pass  # LJM constants not available or invalid device type
    
    return device_type_map.get(device_type_num, f"Unknown({device_type_num})")


def get_connection_type_string(connection_type_num: int) -> str:
    """Convert connection type number to string representation"""
    connection_type_map = {
        1: "USB",
        2: "ANY_TCP", 
        3: "ETHERNET",
        4: "WIFI",
        200: "ANY",
        201: "TCP"
    }
    
    # Try using constants if available
    try:
        if connection_type_num == ljm.constants.ctUSB:
            return "USB"
        elif connection_type_num == ljm.constants.ctETHERNET:
            return "ETHERNET"
        elif connection_type_num == ljm.constants.ctWIFI:
            return "WIFI"
    except (AttributeError, KeyError):
        pass  # LJM constants not available or invalid connection type
        
    return connection_type_map.get(connection_type_num, f"Unknown({connection_type_num})")


def number_to_ip(ip_number: int) -> str:
    """Convert IP number to IP address string"""
    # Convert integer IP to dotted notation
    octet1 = (ip_number >> 24) & 0xFF
    octet2 = (ip_number >> 16) & 0xFF
    octet3 = (ip_number >> 8) & 0xFF
    octet4 = ip_number & 0xFF
    return f"{octet1}.{octet2}.{octet3}.{octet4}"


# Compatibility layer - use these instead of ljm.numberToType etc
def numberToType(device_type_num: int) -> str:
    """Compatibility wrapper for ljm.numberToType"""
    if hasattr(ljm, 'numberToType'):
        return ljm.numberToType(device_type_num)
    return get_device_type_string(device_type_num)


def numberToDeviceType(device_type_num: int) -> str:
    """Compatibility wrapper for ljm.numberToDeviceType (alias for numberToType)"""
    if hasattr(ljm, 'numberToDeviceType'):
        return ljm.numberToDeviceType(device_type_num)
    return get_device_type_string(device_type_num)


def numberToConnectionType(connection_type_num: int) -> str:
    """Compatibility wrapper for ljm.numberToConnectionType"""
    if hasattr(ljm, 'numberToConnectionType'):
        return ljm.numberToConnectionType(connection_type_num)
    return get_connection_type_string(connection_type_num)


def numberToIP(ip_number: int) -> str:
    """Compatibility wrapper for ljm.numberToIP"""
    if hasattr(ljm, 'numberToIP'):
        return ljm.numberToIP(ip_number)
    return number_to_ip(ip_number)