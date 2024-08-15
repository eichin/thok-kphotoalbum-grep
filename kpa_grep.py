#!/usr/bin/python3

"""KPhotoAlbum Grep -- Simple CLI tool for pulling subsets of photos out of KPhotoAlbum, by
scanning the index.xml directly.  Base example:

    kpa-grep --tag office --since "last month" | tar cf office-pics.tar --files-from=-

finds the last month's files with the "office" keyword and puts them
in a tar file; it uses the default kphotoalbum index file, and outputs
full pathnames so tar can just find them.
"""

__version__ = "0.07"
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
    kphotoalbumrc = os.path.expanduser("~/.kde/share/config/kphotoalbumrc")

    if not os.path.exists(kphotoalbumrc):
        # We don't want to catch a broader exception, if it exists and we
        # can't read it, that is something we want to diagnose, not handle.
        # Since this just supplies the default argument, it'll be visible in
        # the --help as absent, as well (once we upgrade to argparse, anyway)
        return None

    args = dict(line.rstrip("\n").split("=", 1)
                for line in open(kphotoalbumrc)
                if "=" in line)
    return args["configfile"]

# This is the easiest "fluffy" date parse I've found; parsedatetime was
#  written for OSAF/Chandler.  Otherwise I'd have looked for something
#  based on TERQAS/TimeML, just for completeness.
def since(reltime):
    """return a lower timestamp for since-this-time"""
    from parsedatetime import Calendar
    value, success = Calendar().parse(reltime)
    if success == 0:
        raise Exception("Didn't understand since %s" % reltime)
    return datetime.datetime(*value[:6])

def past_since(reltime):
    """If parsedatetime gives back a future time, try harder"""
    when = since(reltime)
    if when > datetime.datetime.today():
        # "friday" can be in the future, so try "last friday"
        # we only try once, and don't have any better ideas, so just hand
        # back the result; even an exception is more useful than a future time
        return since("last " + reltime)
    return when

def main(argv):
    """pull subsets of photos out of KPhotoAlbum"""

    parser = optparse.OptionParser(usage=__doc__, version=__version__)
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
    parser.add_option("--path", action="append", dest="paths", default=[],
                      help='image "file" attribute must contain this string')

    # TODO: switch to argparse and add an exclusion-group
    parser.add_option("--dump-tags", action="store_true",
                      help="dump all known tags")

    since_base_time = None
    parser.add_option("--since",
                      help="only look this far back (freeform)")


    options, args = parser.parse_args(args=argv[1:])

    assert len(args) == 0

    if not options.index:
        sys.exit("No kphotoalbum index given (with --index or in kphotoalbumrc)")

    if not os.path.exists(options.index):
        sys.exit("kphotoalbum index {} not found".format(options.index))

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
        import json
        def emit_path(img):
            """similar to --xml, write out ad-hoc json"""
            # lxml.objectify didn't really help,
            image = {}
            for attr, val in sorted(img.items()):
                if attr in ["width", "angle", "height"]:
                    # because md5sum is *sometimes* int
                    image[attr] = int(val)
                else:
                    image[attr] = val
            for options in img:
                assert options.tag == "options", options.tag
                for option in options:
                    assert option.tag == "option", option.tag
                    # option
                    image[option.get("name")] = []
                    # values
                    for value in option:
                        for attr, val in value.items():
                            assert attr == "value", attr
                            image[option.get("name")].append(val)

            print(json.dumps(image))
            sys.stdout.flush()

        #raise NotImplementedError("--json")

    if not os.path.exists(options.index):
        raise IOError("Index %s not found" % options.index)

    if options.since:
        since_base_time = past_since(options.since)

    kpa = etree.ElementTree(file=options.index)

    if options.dump_tags:
        if options.xml:
            raise NotImplementedError("--dump-tags --xml")
        if options.json:
            raise NotImplementedError("--dump-tags --json")
        if options.tags:
            tags_required = set(options.tags)
        if since_base_time:
            # don't shortcut via categories, scrape tags from the images
            collectedtags = set()
            for img in kpa.findall("images/image"):
                imgtime = dateutil.parser.parse(img.get("startDate"))
                if imgtime < since_base_time:
                    # rejected due to being older than --since
                    continue
                imgtags = set([f.get("value") for f in img.findall("options/option/value")])
                if options.tags:
                    if tags_required - imgtags:
                        # rejected due to not satisfying the tags
                        continue
                collectedtags.update(imgtags)
            for tag in sorted(collectedtags):
                print(tag)
            sys.exit()

        # just use the cache - doesn't make it any faster, we still parse
        #  the whole file, but it simplifies the code a little
        for category in kpa.findall("Categories/Category"):
            catname = category.get("name")
            for catvalue in category.findall("value"):
                print(catname, catvalue.get("value"))
        sys.exit()

    for img in kpa.findall("images/image"):
        imgtags = set([f.get("value") for f in img.findall("options/option/value")])
        if options.tags:
            tags_required = set(options.tags)
            if tags_required - imgtags:
                # rejected due to not satisfying the tags
                continue
        if options.paths:
            for path in options.paths:
                if path in img.get("file"):
                    break
            else:
                # no matches, reject
                continue
        if since_base_time:
            imgtime = dateutil.parser.parse(img.get("startDate"))
            if imgtime < since_base_time:
                # rejected due to being older than --since
                continue
        emit_path(img)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
