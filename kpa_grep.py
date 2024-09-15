#!/usr/bin/python3

"""KPhotoAlbum Grep -- Simple CLI tool for pulling subsets of photos out of KPhotoAlbum, by
scanning the index.xml directly.  Base example:

    kpa-grep --tag office --since "last month" | tar cf office-pics.tar --files-from=-

finds the last month's files with the "office" keyword and puts them
in a tar file; it uses the default kphotoalbum index file, and outputs
full pathnames so tar can just find them.
"""

__version__ = "0.14"
__author__  = "Mark Eichin <eichin@thok.org>"
__license__ = "MIT"

import os
import sys
import argparse
import xml.etree.ElementTree as etree
import datetime
import dateutil.parser

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
    if "configfile" not in args:
        # kphotoalbumrc changes format more than index.xml does, but we
        #  should give some hints as to why we get
        print("Warning: kphotoalbumrc found, but no configfile entry found",
              file=sys.stderr)
        return None
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

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print0", action="store_true",
                        help="NUL instead of newline, for xargs -0")
    parser.add_argument("--relative", action="store_true",
                        help="paths relative to the index file (ie. don't normalize them)")
    parser.add_argument("--index", metavar="PATH", default=kimdaba_default_album(),
                        help="explicitly specify the index file PATH")
    parser.add_argument("--json", action="store_true",
                        help="output whole records as individual JSON objects")
    parser.add_argument("--xml", action="store_true",
                        help="output whole records as KPhotoAlbum XML (no surrounding document)")
    parser.add_argument("--markdown", action="store_true",
                        help="output whole records as ad-hoc Markdown")

    parser.add_argument("--tag", action="append", dest="tags", default=[],
                        help="must match this tag")
    parser.add_argument("--exclude", action="append", dest="exclude_tags", default=[],
                        help="must *not* match this tag")
    parser.add_argument("--path", action="append", dest="paths", default=[],
                        help='image "file" attribute must contain this string (index path is stripped if present)')

    # TODO: switch to argparse and add an exclusion-group
    parser.add_argument("--dump-tags", action="store_true",
                        help="dump all known tags")
    parser.add_argument("--index-path", action="store_true",
                        help="Display the index path we're using if it exists")

    since_base_time = None
    parser.add_argument("--since",
                        help="only look this far back (freeform)")


    options = parser.parse_args(args=argv[1:])

    if not options.index:
        sys.exit("No kphotoalbum index given (with --index or in kphotoalbumrc)")

    if not os.path.exists(options.index):
        sys.exit("kphotoalbum index {} not found".format(options.index))

    if options.index_path:
        print(options.index)
        sys.exit()

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
            sys.stdout.write(etree.tostring(img, encoding="unicode"))
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

    if options.markdown:
        def emit_path(img):
            """similar to --xml, write out ad-hoc json"""
            path = img.get("file")
            basepath = path.split("/")[-1].split(".")[0]
            print(f"## {basepath}")
            print(f'![{basepath}]({path}){{: title="{basepath}"}}')
            print(f'{img.get("description") or ""}')
            for options in img:
                assert options.tag == "options", options.tag
                for option in options:
                    assert option.tag == "option", option.tag
                    print()
                    print(f"### {option.get('name')}")
                    tags = []
                    for value in option:
                        for attr, val in value.items():
                            assert attr == "value", attr
                            tags.append(val)
                    print(", ".join(sorted(tags)))
            print()
        

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
        if options.exclude_tags:
            tags_forbidden = set(options.exclude_tags)
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
                if options.exclude_tags:
                    if tags_forbidden & imgtags:
                        # rejected due to having any excluded tags
                        continue
                collectedtags.update(imgtags)
            for tag in sorted(collectedtags):
                print(tag, end='\0' if options.print0 else '\n')
            sys.stdout.flush()
            sys.exit()

        # just use the cache - doesn't make it any faster, we still parse
        #  the whole file, but it simplifies the code a little
        for category in kpa.findall("Categories/Category"):
            catname = category.get("name")
            for catvalue in category.findall("value"):
                print(catname, catvalue.get("value"), 
                      end='\0' if options.print0 else '\n')
            sys.stdout.flush()
        sys.exit()

    for img in kpa.findall("images/image"):
        imgtags = set([f.get("value") for f in img.findall("options/option/value")])
        if options.tags:
            tags_required = set(options.tags)
            if tags_required - imgtags:
                # rejected due to not satisfying the tags
                continue
        if options.exclude_tags:
            tags_forbidden = set(options.exclude_tags)
            if tags_forbidden & imgtags:
                # rejected due to having any excluded tags
                continue
        if options.paths:
            indexdir = os.path.dirname(options.index)
            for path in options.paths:
                if path in img.get("file"):
                    break
                if path.startswith(indexdir):
                    if path.replace(indexdir, "").lstrip("/") in img.get("file"):
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
