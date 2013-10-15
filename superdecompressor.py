from os import system
from utils import int2ints, ints2int, gen_formatted, hexify


HEADER_SIZE = 12
COMPRESS_LOCATION = 12
ENDADDR_LOCATION = 4
BLOCK_HEADER_SIZE = 0x130
BLOCK_SIZE = 0x800
PERIOD = BLOCK_HEADER_SIZE + BLOCK_SIZE


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
        self.infile.seek(self.baseaddr)

        headers = []
        datas = []
        while True:
            header, data = self.get_header_and_data()
            if header and data:
                headers.append(header)
                datas.append(data)
            else:
                break

        self.datas = []
        for header, data in zip(headers, datas):
            if header[:2] == [1, 0]:
                self.datas.append(data)
            elif header[:2] == [1, 2]:
                self.datas.append(self.decom_data(data))
            else:
                assert False

        self.extract_all_messages()

    @property
    def fakeaddress(self):
        address = self.infile.tell()
        if address == self.baseaddr:
            return 0
        breaks = ((address - self.baseaddr) / PERIOD) + 1
        fakeaddress = address - (BLOCK_HEADER_SIZE * breaks) - self.baseaddr
        return fakeaddress

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
        data = []
        while len(data) < numbytes:
            current = self.infile.tell()
            distance = (self.baseaddr - current) % PERIOD
            if distance == 0:
                self.seek_rel(BLOCK_HEADER_SIZE)
                distance = BLOCK_SIZE
            assert distance <= BLOCK_SIZE
            distance = min(distance, numbytes - len(data))
            data.extend(map(ord, self.infile.read(distance)))
        return data

    def get_header(self, address=None):
        if address is not None:
            self.seek(address)
        self.seek_rel((0 - self.infile.tell()) % 4)
        kind = self.read(2)
        self.infile.seek(self.infile.tell() - 2)
        if kind == [1, 2]:
            header = self.read(HEADER_SIZE)
        elif kind == [1, 0]:
            header = self.read(HEADER_SIZE - 4)
        elif kind == [0, 0]:
            header = None
        else:
            assert False
        return header

    def get_header_and_data(self):
        header = self.get_header()
        if header is not None:
            length = ints2int(header[ENDADDR_LOCATION:ENDADDR_LOCATION + 2])
            length = length - len(header)
            return header, self.read(length)
        else:
            return None, None

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
                if len(data) == 1:
                    data.append(0)
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

                if data[0] != 0xff and data[0] & 0x80 == 0x80:
                    upcoming = 0
                elif len(data) <= data[0] + 2:
                    finished = True
                    data = data[1:]
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
            options = [(0, 0)]
            for i in range(len(data)):
                buff = buff[-1*0xff:]
                k = i
                compress_index = contains_slice(buff, data[:k])
                if compress_index is not None:
                    if data[:k] == buff[compress_index:]:
                        window, following = data[:k], data[k:]
                        j = 0
                        while True:
                            if following[:j+1] == window[:j+1]:
                                j += 1
                                if len(window) <= j:
                                    window = window + window
                            else:
                                break
                        k = k + j
                    options.append((k, compress_index))
                else:
                    break

            i, compress_index = max(options)
            if i >= 3:
                #assumption: these values are not retrieved in decompression
                lengthbyte = "%x" % (0x80 + i - 3)
                location = len(buff) - compress_index - 1
                output.append(lengthbyte)
                output.append(location)
                assert 0x80 <= int(lengthbyte, 16) <= 0xff
                assert location <= 0xff
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

    def generate_compress_locations(self, output):
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
                    output[i] = 0xff
                assert output[i] <= 0xff

        return output

    def prepare_for_write(self, data):
        # TODO: Display a warning when new size exceeds limits
        header = ([1, 2, 0, 0] + [0xff, 0xff] +
                  [0, 0] + int2ints(len(data) + HEADER_SIZE, 2) +
                  [0, 0] + [None])
        data = self.recom_data(data)
        data = self.generate_compress_locations(header + data)
        offset = (-1 * len(data)) % 4  # align midder to multiple of 4
        data += [0] * offset
        data = data[:4] + int2ints(len(data), 2) + data[6:]
        return data

    def write(self, outfile, data):
        outfile.seek(self.baseaddr + BLOCK_HEADER_SIZE)
        while data:
            chunk, data = data[:BLOCK_SIZE], data[BLOCK_SIZE:]
            chunk += [0] * (BLOCK_SIZE - len(chunk))
            assert len(chunk) == BLOCK_SIZE
            chunk = map(lambda x: x & 0xff, chunk)
            outfile.write("".join(map(chr, chunk)))
            outfile.seek(outfile.tell() + BLOCK_HEADER_SIZE)

    def extract_messages(self, data):
        pointers = []
        while True:
            location = len(pointers)*4
            if pointers and location >= min(pointers):
                break
            pointers.append(ints2int(data[location:location+4]))
        messages = []
        for pointer in pointers:
            message = []
            while True:
                chars = data[pointer:pointer+2]
                if not chars:
                    message = None
                    break
                message += chars
                pointer += 2
                if chars == [0xff, 0xff]:
                    break
            messages.append(message)
        if None in messages:
            return None
        else:
            return messages

    def extract_all_messages(self):
        self.messageslist = []
        for data in self.datas:
            messages = self.extract_messages(data)
            self.messageslist.append(messages)
        return self.messageslist

    def compile_messages(self, messages):
        currentpointer = len(messages) * 4
        data = []
        for message in messages:
            data += int2ints(currentpointer, 4)
            currentpointer += len(message)
        for message in messages:
            data += message
        return data

    def compile_and_write(self, outfile):
        outdata = []
        for (messages, data) in zip(self.messageslist, self.datas):
            if messages is None:
                out = data
            else:
                out = self.compile_messages(messages)
            outdata += self.prepare_for_write(out)
        self.write(outfile, outdata)


if __name__ == "__main__":
    system("cp %s %s" % ("smt_if_clean.bin", "smt_if.bin"))
    infile = open("smt_if_clean.bin", 'rb')
    outfile = open("smt_if.bin", 'r+b')

    #address = 0x804c38
    #address = 0x804308
    address = 0x7f9478
    d = Datapack(infile, address)
    d.compile_and_write(outfile)
    infile.close()
