from utils import ints2int
from os import system

blank = 0xf489428
filepos_addr = 0xd368
cleanfile = "smt_if_clean.bin"
filename = "smt_if.bin"

def get_file_address(index):
    return (index * 0x930) + 0x18

def get_index(address):
    return (address - 0x18) / 0x930

def get_all_file_addresses(infile):
    results = []
    while True:
        data = ints2int(map(ord, infile.read(4)))
        if data == 0:
            break
        else:
            data = get_file_address(data)
            results.append(data)
            print "%x %x" % (data, ints2int(map(ord, infile.read(4))))
    return results


if __name__ == "__main__":
    f = open(filename, 'rb')
    f.seek(filepos_addr)
    addresses = get_all_file_addresses(f)
