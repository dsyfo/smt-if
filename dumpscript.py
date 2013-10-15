from sys import argv
from superdecompressor import Datapack
from utils import gen_formatted

END_ADDRESS = 0xf489540

if __name__ == "__main__":
    if len(argv) < 3:
        print "\n".join([
            "python dumpscript.py <input file> <output file> <initial address>"])
        exit(0)

    if len(argv) >= 4:
        infile, outfile, address = tuple(argv[1:4])
    else:
        infile, outfile, address = argv[1], argv[2], "818"
        #infile, outfile, address = argv[1], argv[2], "115da8"

    infile = open(infile, "rb")
    outfile = open(outfile, "w+")
    address = int(address, 16)
    while True:
        if address >= END_ADDRESS:
            break

        print "%x" % address
        try:
            d = Datapack(infile=infile, address=address)
            for i, messages in enumerate(d.messageslist):
                if messages is None:
                    continue
                messages = map(gen_formatted, messages)
                outfile.write("#---------\n#{0:0>7}.{1}\n#---------\n\n".format("%x" % address, i))
                for num, message in enumerate(messages):
                    outfile.write("#<{0:0>2}.>\n{1}\n\n".format(num + 1, message))
        except (AssertionError, IndexError), e:
            # TODO: need to double check each assertion, probably too lenient
            # for example, still won't dump message at 1165fa
            print e

        address += 0x930
