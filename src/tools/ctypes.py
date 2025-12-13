from ctypes import c_int8, c_uint8, c_byte, c_ubyte, c_int16, c_uint16, \
    c_int32, c_uint32, c_int, c_uint, c_long, c_ulong, c_longlong, c_ulonglong, \
    c_int64, c_uint64, \
    sizeof


def limits(c_int_type):
    signed = c_int_type(-1).value < c_int_type(0).value
    bit_size = sizeof(c_int_type) * 8
    signed_limit = 2 ** (bit_size - 1)
    return (-signed_limit, signed_limit - 1) if signed else (0, 2 * signed_limit - 1)


MAX_INT8 = limits(c_int8)[1]
MAX_UINT8 = limits(c_uint8)[1]
MAX_BYTE = limits(c_byte)[1]
MAX_UBYTE = limits(c_ubyte)[1]
MAX_INT16 = limits(c_int16)[1]
MAX_UINT16 = limits(c_uint16)[1]
MAX_INT32 = limits(c_int32)[1]
MAX_UINT32 = limits(c_uint32)[1]
MAX_INT = limits(c_int)[1]
MAX_UINT = limits(c_uint)[1]
MAX_LONG = limits(c_long)[1]
MAX_ULONG = limits(c_ulong)[1]
MAX_LONGLONG = limits(c_longlong)[1]
MAX_ULONGLONG = limits(c_ulonglong)[1]
MAX_INT64 = limits(c_int64)[1]
MAX_UINT64 = limits(c_uint64)[1]
