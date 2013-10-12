from os import system
from utils import int2ints, ints2int, gen_formatted, hexify


HEADER_SIZE = 12
COMPRESS_LOCATION = 12
ENDADDR_LOCATION = 4
BLOCK_HEADER_SIZE = 0x130
BLOCK_SIZE = 0x800
PERIOD = BLOCK_HEADER_SIZE + BLOCK_SIZE

outfile = open("smt_if.bin", 'r+b')


def roundup(value, step):
    current = 0
    while True:
        if value <= current:
            return current
        current += step


def contains_slice(bigger, smaller):
    for i in range(len(bigger)-1, -1, -1):
        if bigger[i:i+len(smaller)] == smaller:
            return i
    return None


class Datapack:
    def __init__(self, infile, address):
        self.infile = infile
        self.baseaddr = address

        header = self.get_header(0)
        self.seek_next_nonzero(ints2int(header[ENDADDR_LOCATION:ENDADDR_LOCATION + 2]))
        midderaddr = self.fakeaddress
        midder = self.get_header(midderaddr)
        endaddr = midderaddr + ints2int(midder[ENDADDR_LOCATION:ENDADDR_LOCATION + 2])
        assert self.peek(endaddr) == 0

        self.c_first, self.c_second = self.get_data(midderaddr, endaddr,
                                                    headerlen=len(header), midderlen=len(midder))
        if header[:2] == [1, 0]:
            self.d_first = list(self.c_first)
        else:
            self.d_first = self.decom_data(data=self.c_first)
        if midder[:2] == [1, 0]:
            self.d_second = list(self.c_second)
        else:
            self.d_second = self.decom_data(data=self.c_second)

    @property
    def fakeaddress(self):
        address = self.infile.tell()
        breaks = ((address - self.baseaddr) / BLOCK_SIZE) + 1
        return address - (BLOCK_HEADER_SIZE * breaks) - self.baseaddr

    def seek(self, address):
        assert address >= 0
        breaks = (address / BLOCK_SIZE) + 1
        realaddress = self.baseaddr + address + (BLOCK_HEADER_SIZE * breaks)
        self.infile.seek(realaddress)
        self.validate_position()

    def seek_rel(self, distance):
        self.seek(self.fakeaddress + distance)
        self.validate_position()

    def seek_next_nonzero(self, address=None):
        if address is not None:
            self.seek(address)
        data = 0
        while data == 0:
            data = self.read(1)[0]
        self.seek_rel(-1)

    def peek(self, address=None):
        old = self.fakeaddress
        if address:
            self.seek(address)
        value = self.read(1)
        self.seek(old)
        return value[0]

    def validate_position(self):
        assert (self.infile.tell() - self.baseaddr) % PERIOD >= BLOCK_HEADER_SIZE

    def read(self, numbytes):
        current = self.infile.tell()
        assert (current - self.baseaddr) % PERIOD >= BLOCK_HEADER_SIZE
        assert (current - self.baseaddr) % PERIOD + numbytes <= PERIOD
        assert not 0 < (current + numbytes - self.baseaddr) % PERIOD < BLOCK_HEADER_SIZE
        return map(ord, self.infile.read(numbytes))

    def get_header(self, address=None):
        if address is not None:
            self.seek(address)
        kind = self.read(2)
        self.infile.seek(self.infile.tell() - 2)
        if kind == [1, 2]:
            header = self.read(HEADER_SIZE)
        elif kind == [1, 0]:
            header = self.read(HEADER_SIZE - 4)
        else:
            assert False
        return header

    def get_data(self, midderaddr, endaddr,
                 headerlen=HEADER_SIZE, midderlen=HEADER_SIZE):
        endaddr = roundup(endaddr, BLOCK_SIZE) - 1
        breaks = (endaddr / BLOCK_SIZE) + 1
        data = []
        for i in range(breaks):
            self.seek(i * BLOCK_SIZE)
            d = self.read(BLOCK_SIZE)
            data.extend(d)

        assert not len(data) % BLOCK_SIZE
        first, second = (data[headerlen:midderaddr],
                         data[midderaddr + midderlen:])

        def remove_trailing(data):
            while data[-1] == 0:
                data = data[:-1]
            return data

        first, second = tuple(map(remove_trailing, (first, second)))

        return first, second

    def decom_data(self, data):
        uncompressed = []
        upcoming, data = data[0] + 1, data[1:]
        while data[-1] == 0:
            data = data[:-1]
        finished = False
        while True:
            if upcoming or finished:
                if not data:
                    if finished:
                        break
                    uncompressed.append(0)
                else:
                    uncompressed.append(data[0])
                    data = data[1:]
                if not finished:
                    upcoming += -1
            elif upcoming == 0:
                if not data:
                    break
                elif data[0] & 0x80 != 0x80:
                    finished = True
                    continue
                #assert data[0] & 0x80 == 0x80
                assert len(data) >= 2
                length = data[0] - 0x80 + 3
                lookback = -1 * (data[1] + 1)
                assert abs(lookback) <= len(uncompressed)
                window = uncompressed[lookback:]
                while len(window) < length:
                    window.extend(window)
                uncompressed.extend(window[:length])
                data = data[2:]
                if not data:
                    break

                if data[0] & 0x80 == 0x80:
                    upcoming = 0
                else:
                    upcoming = data[0] + 1
                    data = data[1:]
            elif upcoming < 0:
                raise Exception
        assert upcoming == 0

        while uncompressed[-1] == 0:
            uncompressed = uncompressed[:-1]
        return uncompressed

    def recom_data(self, data):
        buff = []
        output = []
        COMPRESSED_FLAG = False
        while data:
            for i in range(len(data)):
                buff = buff[-1*0xff:]
                if contains_slice(buff, data[:i]) is not None:
                    continue
                else:
                    break

            i = i - 1
            compress_index = contains_slice(buff, data[:i])
            if data[:i] == buff[compress_index:]:
                window, following = data[:i], data[i:]
                j = 0
                while True:
                    if following[:j+1] == window[:j+1]:
                        j += 1
                        if len(window) <= j:
                            window = window + window
                    else:
                        break
                i = i + j

            if i >= 3:
                #assumption: these values are not retrieved in decompression
                lengthbyte = "%x" % (0x80 + i - 3)
                location = len(buff) - compress_index - 1
                output.append(lengthbyte)
                output.append(location)
                assert 0x80 <= int(lengthbyte, 16) <= 0xff
                assert location < 0xff
                COMPRESSED_FLAG = True
                buff += data[:i]
                data = data[i:]
            else:
                if COMPRESSED_FLAG:
                    #assumption: this value is not retrieved in decompression
                    output.append(None)
                    COMPRESSED_FLAG = False
                buff.append(data[0])
                output.append(data[0])
                data = data[1:]

        return output

    def recompress(self):
        self.c_first = self.recom_data(self.d_first)
        self.c_second = self.recom_data(self.d_second)

    def generate_compress_locations(self, output, first=False):
        prev = None
        for i in range(len(output)-1, -1, -1):
            if type(output[i]) is str:
                prev = i
                output[i] = int(output[i], 16)
            if output[i] is None:
                if prev:
                    assert 0 <= prev - i - 2 < 0x80
                    output[i] = prev - i - 2
                    prev = False
                else:
                    if first:
                        #output[i] = len(output) - i - 1
                        output[i] = 0xff
                    else:
                        output[i] = 0

        return output

    def write(self, outfile, first=None, second=None):
        # TODO: Display a warning when new size exceeds limits
        first = first or self.c_first
        header = ([1, 2, 0, 0] + [0xff, 0xff] +
                  [0, 0] + int2ints(len(first) + HEADER_SIZE, 2) +
                  [0, 0] + [None])
        top = self.generate_compress_locations(header + first, first=True)
        offset = (-1 * len(top)) % 4  # align midder to multiple of 4
        top += [0] * offset
        top = top[:4] + int2ints(len(top), 2) + top[6:]

        second = second or self.c_second
        endaddr = roundup(len(top) + len(second) + HEADER_SIZE, 0x800) - len(top) - 1
        midder = ([1, 2, 0, 0] + int2ints(endaddr, 2) +
                  [0, 0] + int2ints(len(second) + HEADER_SIZE, 2) +
                  [0, 0] + [None])
        bottom = self.generate_compress_locations(midder + second)

        data = top + bottom
        outfile.seek(self.baseaddr + BLOCK_HEADER_SIZE)
        while data:
            chunk, data = data[:BLOCK_SIZE], data[BLOCK_SIZE:]
            chunk += [0] * (BLOCK_SIZE - len(chunk))
            assert len(chunk) == BLOCK_SIZE
            chunk = map(lambda x: x & 0xff, chunk)
            outfile.write("".join(map(chr, chunk)))
            outfile.seek(outfile.tell() + BLOCK_HEADER_SIZE)

    def extract_messages(self):
        pointers = []
        while True:
            location = len(pointers)*4
            if pointers and location >= min(pointers):
                break
            pointers.append(ints2int(self.d_second[location:location+4]))
        self.messages = []
        for pointer in pointers:
            message = []
            while True:
                chars = self.d_second[pointer:pointer+2]
                assert chars
                message += chars
                pointer += 2
                if chars == [0xff, 0xff]:
                    break
            self.messages.append(message)
        return self.messages

    def compile_messages(self):
        currentpointer = len(self.messages) * 4
        self.d_second = []
        for message in self.messages:
            self.d_second += int2ints(currentpointer, 4)
            currentpointer += len(message)
        for message in self.messages:
            self.d_second += message
        return self.d_second


if __name__ == "__main__":
    system("cp %s %s" % ("smt_if_clean.bin", "smt_if.bin"))
    infile = open("smt_if_clean.bin", 'rb')
    #address = 0x804c38
    #address = 0x804308
    address = 0x7f9478
    d = Datapack(infile, address)
    #d.d_second = self.repl_w_bullshit(self.d_second)
    #d.d_second = self.repl_w_kanji(self.d_second)
    #d.edit_top()
    d.extract_messages()
    d.compile_messages()
    #d.d_second = d.repl_w_kanji(d.d_second)
    d.recompress()

    #d.write(outfile, d.d_first, d.d_second)
    #d.write(outfile)

    infile.close()
    print gen_formatted(d.d_first)
    print
    print gen_formatted(d.d_second)
