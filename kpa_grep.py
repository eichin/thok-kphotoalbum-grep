#!/usr/bin/python

"""KPhotoAlbum Grep -- Simple CLI tool for pulling subsets of photos out of KPhotoAlbum, by
scanning the index.xml directly.  Base example:

    kpa-grep --tag office --since "last month" | tar cf office-pics.tar --files-from=-

finds the last month's files with the "office" keyword and puts them
in a tar file; it uses the default kphotoalbum index file, and outputs
full pathnames so tar can just find them.
"""

__version__ = "0.01"
__author__  = "Mark Eichin <eichin@thok.org>"
__license__ = "MIT"

import os
import sys
import optparse
import xml.etree.cElementTree as etree
import datetime
import dateutil.parser

# use cElementTree to get it off the ground - but a 40M index takes
#  7 seconds to parse, and I'd kind of like something faster (or at 
#  least faster-to-first-result)

# kimdaba_default_album lifted from thok kimdaba_album.py, by permission [from myself]
def kimdaba_default_album():
    """Find the path to the default album kimdaba will start with"""
    # could support cheap comments with an early .split("#",1)[0]
    # but the kde files don't use them
    args = dict(line.rstrip("\n").split("=", 1)
                for line in file(os.path.expanduser("~/.kde/share/config/kphotoalbumrc"))
                if "=" in line)
    return args["configfile"]

# This is the easiest "fluffy" date parse I've found; parsedatetime was
#  written for OSAF/Chandler.  Otherwise I'd have looked for something 
#  based on TERQAS/TimeML, just for completeness.
def since(reltime):
    """return a lower timestamp for since-this-time"""
    import parsedatetime.parsedatetime
    value, success = parsedatetime.parsedatetime.Calendar().parse(reltime)
    if success == 0:
        raise Exception("Didn't understand since %s" % reltime)
    return datetime.datetime(*value[:6])

def main(argv):
    """pull subsets of photos out of KPhotoAlbum"""

    parser = optparse.OptionParser(usage=__doc__)
    parser.add_option("--print0", action="store_true",
                      help="NUL instead of newline, for xargs -0")
    parser.add_option("--relative", action="store_true",
                      help="paths relative to the index file (ie. don't normalize them)")
    parser.add_option("--index", metavar="PATH", default=kimdaba_default_album(),
                      help="explicitly specify the index file PATH")
    parser.add_option("--json", action="store_true",
                      help="output whole records as individual JSON objects")
    parser.add_option("--xml", action="store_true",
                      help="output whole records as KPhotoAlbum XML (no surrounding document)")

    parser.add_option("--tag", action="append", dest="tags", default=[],
                      help="must match this tag")

    since_base_time = None
    parser.add_option("--since", 
                      help="only look this far back (freeform)")


    options, args = parser.parse_args(args=argv[1:])

    assert len(args) == 0

    def emit_path(img):
        """given etree for <image>, just print the path"""
        path = img.get("file")
        if not options.relative:
            path = os.path.join(os.path.dirname(options.index), path)
        if options.print0:
            path = path + "\0"
        else:
            path = path + "\n"
        sys.stdout.write(path)
        sys.stdout.flush()

    if options.xml:
        def emit_path(img):
            """write all the XML"""
            sys.stdout.write(etree.tostring(img))
            sys.stdout.flush()

    if options.json:
        # TODO: try lxml.objectify
        raise NotImplementedError("--json")

    if not os.path.exists(options.index):
        raise IOError("Index %s not found" % options.index)

    if options.since:
        since_base_time = since(options.since)

    kpa = etree.ElementTree(file=options.index)
    for img in kpa.findall("images/image"):
        imgtags = set([f.get("value") for f in img.findall("options/option/value")])
        if options.tags:
            tags_required = set(options.tags)
            if tags_required - imgtags:
                # rejected due to not satisfying the tags
                continue
        if since_base_time:
            imgtime = dateutil.parser.parse(img.get("startDate"))
            if imgtime < since_base_time:
                # rejected due to being older than --since
                continue
        emit_path(img)

        
