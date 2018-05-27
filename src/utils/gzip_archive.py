import struct


def get_uncompressed_size(filename):
    with open(filename, 'rb') as f:
        f.seek(-4, 2)
        return struct.unpack('I', f.read(4))[0]