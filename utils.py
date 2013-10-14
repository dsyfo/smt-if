# -*- coding: utf-8 -*-
MIN_UNICODE_KANJI = u"\u4e00"
MAX_UNICODE_KANJI = u"\u9faf"

table = open("table.txt")

str2byte = {}
byte2str = {}

value = None
for line in table:
    oldvalue = value

    line = line.strip().split()
    if len(line) >= 2:
        value = int(line[-1], 16)
        char = line[0]
    elif len(line) == 1:
        value = value + 1
        char = line[0]

    assert value
    str2byte[char] = value
    byte2str[value] = char

str2byte["\n"] = 0xff03
str2byte[" "] = 0xfffe
byte2str[0xfffe] = " "
byte2str[0xff03] = "\n"


def ints2int(data, bigend=True):
    if bigend:
        data.reverse()
    value = 0
    for d in data:
        value = (value << 8) | d
    return value


def int2ints(value, size, bigend=True):
    data = []
    for i in range(size):
        data.append(value & 0xff)
        value = value >> 8
    if not bigend:
        data.reverse()
    return data


def hexify(data):
    h = lambda n: "%x" % n
    try:
        if type(data) in (list, tuple):
            return map(h, data)
        else:
            return h(data)
    except TypeError:
        return None


def is_unicode_kanji(char):
    if MIN_UNICODE_KANJI <= char <= MAX_UNICODE_KANJI:
        return True
    else:
        return False


def gen_formatted(message, lookup=None, spaces=False):
    if lookup is None:
        lookup = byte2str

    output = ""
    for i in range(0, len(message), 2):
        value = ints2int(message[i:i+2])
        if value in lookup:
            output += lookup[value]
        else:
            value = ints2int(message[i:i+2], bigend=True)
            if spaces:
                output = output.strip(' ')
                output = "{0} $<{1:0>4}> ".format(output, hexify(value))
            else:
                output = "{0}$<{1:0>4}>".format(output, hexify(value))

    output = "\n".join(line.strip() for line in output.split("\n"))
    return output.strip()


if __name__ == "__main__":
    pass
