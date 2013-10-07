from sys import argv
from os import system
from superdecompressor import Datapack
from utils import gen_formatted, str2byte, int2ints

def rewrite_message(messages, messagenum):
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
    return messages


if __name__ == "__main__":
    infile, outfile, address, messagenum = tuple(argv[1:5])
    system("cp %s %s" % (infile, outfile))
    infile = open(infile, "rb")
    outfile = open(outfile, "r+b")
    address = int(address, 16)
    messagenum = int(messagenum)
    d = Datapack(infile=infile, address=address)
    messages = d.extract_messages()
    d.messages = rewrite_message(messages, messagenum)
    d.compile_messages()
    d.recompress()
    d.write(outfile)
    #d.write(outfile, first=d.d_first, second=d.d_second)
