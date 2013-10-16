from sys import argv
from os import system
from superdecompressor import Datapack
from utils import int2ints, str2byte

specials = {}
for line in open("specialcodes.txt"):
    code, replacement = tuple(line.strip().split(' ', 1))
    replacement = replacement.replace(r"\n", "\n")
    specials[replacement] = code

if __name__ == "__main__":
    if len(argv) < 4:
        print "\n".join([
            "python dumpscript.py <input file> <output file> <script>"])
        exit(0)
    else:
        infile, outfile, script = tuple(argv[1:4])

    system("cp %s %s" % (infile, outfile))
    infile = open(infile, 'rb')
    script = open(script)
    d, messagegroup, messagenum, message = None, None, None, None
    hold = ""
    for line in script:
        for replacement, code in specials.items():
            line = line.replace(replacement, code)

        line = hold + line
        if line[-1] != "\n":
            hold = line
            assert line[-3:] == "01>"
            continue

        line = line.decode('utf-8').strip()
        if not line and not hold:
            continue

        hold = ""
        if line[:2] == "#<" and line[-1] == ">":
            if (messagegroup is not None and messagenum is not None and
                    message is not None):
                d.messageslist[messagegroup][messagenum-1] = message
                messagegroup, messagenum = None, None

            if line[:3] == "#<@":
                if d is not None:
                    f = open(outfile, 'r+b')
                    try:
                        d.compile_and_write(f)
                    except AssertionError:
                        print "FAILURE %x" % d.baseaddr
                    f.close()
                address = int(line[3:-1], 16)
                d = Datapack(infile=infile, address=address)
            elif (len(line) == 8 and line[3] == "."):
                messagegroup, messagenum = tuple(map(int, line[2:-1].split('.')))
                message = []

        else:
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

    outfile = open(outfile, 'r+b')
