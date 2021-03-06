from sys import argv
from os import system
from superdecompressor import Datapack
from utils import gen_formatted, str2byte, int2ints

def rewrite_message(messages, messagenum):
    messages = [m[:-2] for m in messages]
    f = open("rewriter.tmp", "w+")
    f.write(gen_formatted(messages[messagenum-1]))
    f.write("\n")
    for i, message in enumerate(messages):
        f.write("\n")
        s = "# "
        if i + 1 == messagenum:
            s += "*{0:2}. ".format(i + 1)
        else:
            s += " {0:2}. ".format(i + 1)

        s += gen_formatted(message)
        s = s.replace("\n", "\n#      ")
        f.write(s)

    f.close()
    system("vim rewriter.tmp")
    f = open("rewriter.tmp")
    message = []
    for line in f:
        line = line.decode('utf-8').strip()
        if not line or line[0] == "#":
            continue
        if message:
            message.extend(int2ints(str2byte["\n"], 2))

        while line:
            if line[0] == '$' and line[1] == '<' and line[6] == '>':
                hexa = int2ints(int(line[2:6], 16), 2)
                line = line[7:]
            else:
                hexa = int2ints(str2byte[line[0].encode('utf-8')], 2)
                line = line[1:]
            message.extend(hexa)

    messages[messagenum - 1] = message
    f.close()
    system("rm rewriter.tmp")
    messages = [m + [0xff, 0xff] for m in messages]
    return messages


def get_kanji_filled_message(kanji_num=0x100):
    message = []
    for _ in range(5):
        for _ in range(8):
            message.extend(int2ints(kanji_num, 2))
            message.extend(int2ints(str2byte[" "], 2))
            kanji_num += 1
        message.extend(int2ints(str2byte["\n"], 2))
    message = message[:-2] + [0x01, 0xff, 0x02, 0xff, 0xff, 0xff]
    return message


if __name__ == "__main__":
    if len(argv) < 4:
        print "\n".join([
            "python rewriter.py <input file> <output file> <address> <message number> <message group>",
            "    address - Hex address of a data chunk inside rom. Ex: 804c38",
            "    message number - Which message to edit (omit for all)."])
        exit(0)

    infile, outfile, address = tuple(argv[1:4])
    if len(argv) >= 5:
        messagenum = int(argv[4])
        if len(argv) >= 6:
            messagegroup = int(argv[5])
        else:
            messagegroup = 1
    else:
        messagenum = None

    system("cp %s %s" % (infile, outfile))
    infile = open(infile, "rb")
    outfile = open(outfile, "r+b")
    address = int(address, 16)
    d = Datapack(infile=infile, address=address)
    messages = d.messageslist[messagegroup]
    if messagenum is None:
        for i in range(len(messages)):
            messages = rewrite_message(messages, i+1)
    else:
        messages = rewrite_message(messages, messagenum)
    d.messageslist[messagegroup] = messages
    d.compile_and_write(outfile)
