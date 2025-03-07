#!/usr/bin/python3

"""KPhotoAlbum Grep -- Simple CLI tool for pulling subsets of photos out of KPhotoAlbum, by
scanning the index.xml directly.  Base example:

    kpa-grep --tag office --since "last month" | tar cf office-pics.tar --files-from=-

finds the last month's files with the "office" keyword and puts them
in a tar file; it uses the default kphotoalbum index file, and outputs
full pathnames so tar can just find them.
"""

__version__ = "0.18"
__author__  = "Mark Eichin <eichin@thok.org>"
__license__ = "MIT"

import os
import sys
import argparse
import xml.etree.ElementTree as etree
import hashlib
import json
import sqlite3
import datetime
from pathlib import Path
import dateutil.parser
from parsedatetime import Calendar


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

    with open(kphotoalbumrc) as config:
        args = dict(line.rstrip("\n").split("=", 1)
                    for line in config
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
# TODO: Calendar.parse fails on "1980-01-02T00:00:35" but works
#   on "1980-01-02 00:00:35" so maybe feed a strict parser first?
def since(reltime):
    """return a lower timestamp for since-this-time"""
    value, success = Calendar().parse(reltime)
    if success == 0:
        raise ValueError(f"Didn't understand since \"{reltime}\"")
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


# https://specifications.freedesktop.org/basedir-spec/latest/index.html
def xdg_cache(project):
    """find (and create if necessary) an XDG-correct per-project cache dir"""
    base = os.environ.get("XDG_CACHE_HOME", os.environ["HOME"] + "/.cache")
    cachedir = Path(base)/project
    cachedir.mkdir(parents=True, exist_ok=True)
    return cachedir


# TODO: factor back into --json
def get_options(img):
    """extract tags from XML options elements into a simple dict"""
    image = {}
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
    return image


def catnames(image_options):
    """flatten category/tag hierarchy"""
    for cat in image_options:
        for tag in image_options[cat]:
            yield cat, tag


def pairup(name, rightgen):
    """flatten name/category/tag into rows for executemany"""
    for cat, tag in rightgen:
        yield dict(
            name=name,
            cat=cat,
            tag=tag,
            )


def cache_with_db(xmlpath, populate_fn):
    """if we've seen xmlpath before and we have a current cache, just
    open and return it.  If not, call populate and store that."""
    # TODO: just pass in the new db instead of the :memory: step?
    cachepath = xdg_cache("kpa-grep")/"caches.db"
    cachedb = sqlite3.connect(cachepath)
    cachecur = cachedb.cursor()
    cachecur.execute("create table if not exists dbs(upstreamname string unique primary key, upstreamdate timestamp, localname)")
    res = cachecur.execute("select upstreamdate, localname from dbs where upstreamname = :xmlpath",
                           dict(xmlpath=xmlpath))
    for upstreamdate, localname in res.fetchall():
        if Path(xmlpath).stat().st_mtime == float(upstreamdate):
            if Path(localname).exists():
                cachedb.close()
                return sqlite3.connect(localname)
    # not found and out of date are currently identical
    # consider using a hash here instead!
    localname = xdg_cache("kpa-grep")/(xmlpath.replace("/", "_") + ".db")
    realdb = populate_fn(xmlpath)
    backup = sqlite3.connect(localname)
    with backup:
        realdb.backup(backup)
    backup.close()

    cachecur.execute("insert or replace into dbs "
                     "values(:xmlpath, :xmldate, :localname)",
                     dict(xmlpath=str(xmlpath),
                          xmldate=Path(xmlpath).stat().st_mtime,
                          localname=str(localname)))
    cachecur.close()
    cachedb.commit()
    cachedb.close()
    # consider returning the cache for consistency
    return realdb


def cache_everything(name):
    """convert to sqlite, referencing original path for cache flushing"""
    kpa = etree.ElementTree(file=name)

    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.execute("create table tags(filename text, category, tag, "
                "foreign key(filename) references fields(file))")
    # <image file="" startDate="" angle="" md5sum="" width="" height="">
    cur.execute("create table fields(file text primary key, label, description, startDate, angle, md5sum, width, height)")
    for img in kpa.findall("images/image"):
        imgname = img.get("file")
        cur.executemany("INSERT INTO tags VALUES(:name, :cat, :tag)",
                          pairup(imgname, catnames(get_options(img))))

        image = {}
        for attr, val in sorted(img.items()):
            if attr in ["width", "angle", "height"]:
                # because md5sum is *sometimes* int
                image[attr] = int(val)
            elif attr in ["startDate"]:
                image[attr] = dateutil.parser.parse(val).timestamp()
            else:
                image[attr] = val
        if "angle" not in image:
            image["angle"] = None
        if "label" not in image:
            image["label"] = None
        if "description" not in image:
            image["description"] = None
        cur.execute("INSERT INTO fields VALUES(:file, :label, :description, :startDate, :angle, :md5sum, :width, :height)",
                    image)
    cur.execute("create index fields_filename on fields(file)")
    cur.execute("create index tags_filename on tags(filename)")
    cur.execute("create index tags_tag on tags(tag)")
    cur.close()
    con.commit()
    return con


def md5mismatch(indexpath, imgfile, md5sum):
    # internal names are always relative
    filepath = os.path.join(os.path.dirname(indexpath), imgfile)
    # TODO: raise from, to paint filepath into the exception chain?
    with open(filepath, "rb") as img:
        imgdigest = hashlib.file_digest(img, hashlib.md5)
    imgsum = imgdigest.hexdigest()
    return imgsum != md5sum


def img_from_name(kpadb, name):
    imgcur = kpadb.cursor()
    tags = dict()
    res = imgcur.execute("select category, tag from tags where filename is ?", (name,))
    for category, tag in sorted(res.fetchall()):
        tags[category] = tags.get(category, []) + [tag]

    attrs = {}
    res = imgcur.execute("select * from fields where file is ?", (name,))
    for file, label, description, startDate, angle, md5sum, width, height, in res:
        # preserve XML order in assignment order (yay python3)
        attrs["file"] = file
        if label is not None:
            attrs["label"] = label
        if description is not None:
            attrs["description"] = description
        attrs["startDate"] = datetime.datetime.fromtimestamp(startDate).isoformat()
        attrs["angle"] = angle
        attrs["md5sum"] = md5sum
        attrs["width"] = width
        attrs["height"] = height
    imgcur.close()
    return attrs, tags


def emit_path_plain(path, index, relative, print0):
    """given etree for <image>, just print the path"""
    if not relative:
        path = os.path.join(os.path.dirname(index), path)
    if print0:
        path = path + "\0"
    else:
        path = path + "\n"
    sys.stdout.write(path)
    sys.stdout.flush()


def emit_path_xml(path, kpadb):
    """write all the XML"""
    attrs, tags = img_from_name(kpadb, path)
    img = etree.fromstring("<image/>")
    for key, value in attrs.items():
        if value is not None:
            img.set(key, str(value))

    options = etree.SubElement(img, "options")
    for category in tags:
        option = etree.SubElement(options, "option",
                                  dict(name=category))
        for tag in tags[category]:
            value = etree.SubElement(option, "value",
                                     dict(value=tag))

    etree.indent(img, space=' '*4, level=2)
    sys.stdout.write(etree.tostring(img, encoding="unicode"))
    sys.stdout.flush()


def emit_path_json(path, kpadb):
    """similar to --xml, write out ad-hoc json"""
    attrs, tags = img_from_name(kpadb, path)
    image = {}
    for attr, val in sorted(attrs.items()):
        if attr in ["width", "angle", "height"]:
            # because md5sum is *sometimes* int
            if val is not None:
                image[attr] = int(val)
        else:
            image[attr] = val
    image.update(tags)
    print(json.dumps(image))
    sys.stdout.flush()


def emit_path_markdown(path, kpadb):
    """similar to --xml, write out ad-hoc markdown"""
    attrs, tags = img_from_name(kpadb, path)
    path = attrs["file"]
    basepath = path.split("/")[-1].split(".")[0]
    print(f"## {basepath}")
    print(f'![{basepath}]({path}){{: title="{basepath}"}}')
    print(f'{attrs.get("description") or ""}')
    for category in tags:
        print()
        print(f"### {category}")
        print(", ".join(sorted(tags[category])))
    print()


def build_where_clause(conditions):
    """Create a where clause from a list of conditions that may be empty"""
    if not conditions:
        return ""
    return "WHERE " + (" AND ".join(conditions))


def build_sql(tags, excludes, since, paths, ipath, tags_only=False,
              alt_results=None):
    subs = []
    group = f"group by file"
    if alt_results is None:
        alt_results = ["tag", "file"]
    selected_fields = ", ".join(alt_results)
    if tags:
        group = f"group by file having count(file) = {len(tags)}"

    select_join = f"select {selected_fields} from tags " \
        "full join fields on tags.filename = fields.file"

    where_and = []
    if tags:
        # The intersection of "files with tags" starts with the above
        #  join of tags and fields; we take the subset of rows that
        #  have a tag in the list.  The desired rows are the ones that
        #  have *exactly* the same number of rows as the number of tags.
        taglist = "(" + ",".join(["?" for t in tags]) + ")"
        subs.extend(tags)
        where_and.append(f"tag in {taglist}")

    if excludes:
        # To exclude "files with these tags" we collect the union of
        #  the set of files that have any of the excluded tags in them
        #  and then simply filter them out of the files presented.
        excludelist = "(" + ",".join(["?" for ex in excludes]) + ")"
        subs.extend(excludes)
        where_and.append("file not in (select file "\
                         "from tags join fields on tags.filename = fields.file "\
                         f"and tags.tag in {excludelist} )")

    if since:
        # To filter on a base time, we just filter everything down to
        #   those records which have a new enough startDate
        since_base_time = past_since(since).timestamp()
        where_and.append(f'fields.startDate > {since_base_time} ')

    if paths:
        # TODO: change this to an in()?
        indexdir = os.path.dirname(ipath)
        # each path as-is, then with the index prefix added
        expanded_paths = paths + \
            [p.replace(indexdir, "").lstrip("/") for p in paths]
        subs.extend(expanded_paths)
        allpaths = ['file == ?'] * len(expanded_paths)
        pathcond = " OR ".join(allpaths)
        where_and.append("( " + pathcond + ")")

    where = ("where " + " AND ".join(where_and)) if where_and else ""
    whole = f"{select_join} {where} {group}"
    if tags_only:
        # always return the category too - let the caller discard it
        select_join = "select distinct tag, category from tags "
        whole_just_tags = whole.replace("select tag, file", 
                                        "select file", 1)

        whole = f"{select_join} where filename in ( {whole_just_tags} )"
        # TODO: ORDER BY?

    return whole, subs


def main(argv):
    """pull subsets of photos out of KPhotoAlbum"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version',
                        version=f'%(prog)s {__version__}')

    parser.add_argument("--print0", action="store_true",
                        help="NUL instead of newline, for xargs -0")
    parser.add_argument("--relative", action="store_true",
                        help="paths relative to the index file (ie. don't normalize them)")
    parser.add_argument("--show-category", action="store_true",
                        help="Include the category when displaying tags")
    parser.add_argument("--index", metavar="PATH", default=kimdaba_default_album(),
                        help="explicitly specify the index file PATH")

    formatters = parser.add_mutually_exclusive_group()

    formatters.add_argument("--json", action="store_true",
                            help="output whole records as individual JSON objects")
    formatters.add_argument("--xml", action="store_true",
                            help="output whole records as KPhotoAlbum XML (no surrounding document)")
    formatters.add_argument("--markdown", action="store_true",
                            help="output whole records as ad-hoc Markdown")
    # we *could* add json/xml for these and put them in a separate group,
    #  but for now this eliminates some special cases.
    formatters.add_argument("--dump-tags", action="store_true",
                            help="dump all known tags")
    formatters.add_argument("--index-path", action="store_true",
                            help="Display the index path we're using if it exists")
    formatters.add_argument("--check-hashes", action="store_true",
                            help="Print path of all files that don't match the stored md5sum")

    parser.add_argument("--tag", action="append", dest="tags", default=[],
                        help="must match this tag")
    parser.add_argument("--exclude", action="append", dest="exclude_tags", default=[],
                        help="must *not* match this tag")
    parser.add_argument("--since",
                        help="only look this far back (freeform)")
    parser.add_argument("--path", action="append", dest="paths", default=[],
                        help='image "file" attribute must contain this string (index path is stripped if present)')


    parser.add_argument("--debug-sql", action="store_true", 
                        help=argparse.SUPPRESS)

    options = parser.parse_args(args=argv[1:])

    if not options.index:
        sys.exit("No kphotoalbum index given (with --index or in kphotoalbumrc)")

    if not os.path.exists(options.index):
        sys.exit(f"kphotoalbum index {options.index} not found")

    if options.index_path:
        # cut out early, we don't need to open the file, just print the name
        print(options.index)
        sys.exit()

    if not os.path.exists(options.index):
        raise IOError(f"Index {options.index} not found")

    # get a connection - either to the in-memory version or
    #  the one from the on-disk cache.
    kpadb = cache_with_db(options.index, cache_everything)

    emit_path = lambda name: emit_path_plain(name, options.index, options.relative, options.print0)

    if options.xml:
        emit_path = lambda name: emit_path_xml(name, kpadb)
    if options.json:
        emit_path = lambda name: emit_path_json(name, kpadb)
    if options.markdown:
        emit_path = lambda name: emit_path_markdown(name, kpadb)

    if options.check_hashes:
        # this could be a much simpler select, but this keeps the abstraction
        sql, subs = build_sql([], [], None, [], options.index,
                              alt_results=["file", "md5sum"])
        res = kpadb.execute(sql, subs)
        for imgfile, md5sum in res.fetchall():
            if md5mismatch(options.index, imgfile, md5sum):
                emit_path(imgfile)

        sys.stdout.flush()
        sys.exit()

    if options.dump_tags:
        sql, subs = build_sql(options.tags, options.exclude_tags,
                              options.since, options.paths, options.index,
                              tags_only=True)
        if options.debug_sql:
            print("sql:", sql)
            print("subs:", subs)
        res = kpadb.execute(sql, subs)
        #for tag, _imgfile, in res.fetchall():
        for tag, cat in res.fetchall():
            print(f"{cat}:{tag}" if options.show_category else tag, 
                  end='\0' if options.print0 else '\n')
        sys.stdout.flush()
        sys.exit()

    sql, subs = build_sql(options.tags, options.exclude_tags,
                          options.since, options.paths, options.index)
    if options.debug_sql:
        print("sql:", sql)
        print("subs:", subs)
    res = kpadb.execute(sql, subs)

    for _tag, imgfile, in res.fetchall():
        emit_path(imgfile)

    # database is readonly, don't need to commit anything


if __name__ == "__main__":
    sys.exit(main(sys.argv))
