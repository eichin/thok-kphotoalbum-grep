# kpa-grep(1) -- search through KPhotoAlbum metadata for image paths

## SYNOPSIS

`kpa-grep` <flags>

## DESCRIPTION

`kpa-grep` is a simple CLI tool for pulling subsets of photos out of
KPhotoAlbum(1), by scanning the `index.xml` directly.

Actually finding the index is done by looking at KPhotoAlbum's own
configuration in `~/.kde/share/config/kphotoalbumrc`.  If that isn't
available (perhaps you're running `kpa-grep` on a different system
than the one where you use KPhotoAlbum itself) you can pass `--index`
<file> to explicitly point to the `index.xml` file.

There are a small set of options to filter results:

  * `--tag` <tagname>:
    Require <tagname> to include an image in the results.  While
    KPhotoAlbum groups tags into Categories, `kpa-grep` *currently* only
    looks at the names of the tags.
    
  * `--exclude` <tagname>:
    If <tagname> is present on an image, take it out of the result
    set.
    
  * `--since` <time>:
    In order to get specifically recent results, give a "human" time,
    like `--since "last week"` or `--since "Friday"`.  (See
    `parsedatetime.Calendar.parse` for specifics.)  Note that this
    isn't (currently) any faster, since the index is an XML document
    we still have to parse the entire thing and that's where most of
    the time is spent.

  * `--path` <filename>:
    In support of scripts that run `kpa-grep` and then pass those
    results back in to `kpa-grep` for further processing, treat the
    image filename as sort of "the ultimate tag" referring to exactly
    one file. For example, you could use `kpa-grep --tag --since` to
    get a subset, and then `kpa-grep --path --json` on each of those
    to extract the rest of the metadata.  The <filename> can either be
    a fully qualified path or a partial path relative to the index
    file.

The default output is just pathnames to the matching images, on the
assumption that you're selecting files to do something to them further
down a unix pipeline.  Options to modify that output include:

  * `--print0`:
    Same as find(1), instead of one file per line, each file has a NUL
    value after the name.  Paired with `xargs -0` (see xargs(1)) this
    avoids complications with image paths that contain whitespace.
    
  * `--relative`:
    Output paths are relative to the location of the KPhotoAlbum index
    file, instead of absolute filesystem paths.  (This is what
    KPhotoAlbum actually stores, but as this tool is generally an
    interface between KPhotoAlbum and unix tools, by default things
    that process the output of `kpa-grep` don't need to know that
    KPhotoAlbum even has an index file, so the absolute paths are
    usually more useful.)
    
While just getting paths out covers many use cases, over time I've
wanted to extract more of the data for further processing.  These
options generate output that includes all of the per-image metadata -
which ends up including the `file` attribute, which holds the relative
path:

  * `--json`:
    Output the entire record as a JSON object per-line (sometimes
    called "JSON Lines" format.) Keys are sorted by name for stability
    (but see github#14.)
    
  * `--xml`:
    Output the entire record as an XML "snippet" (no DTD, no higher
    level structure from the rest of the file - just the bit of XML
    that includes the metadata for the image. The top level tag is
    `image`; multiple records are just concatenated (see github#3.)
    
  * `--markdown`:
    This (experimental) option generates an adhoc Markdown snippet
    with a level 2 header with the image basename, an inline image
    expression, and then level 3 headers with any categories of tags
    or description that are present.  The idea was to have a tag
    filter produce the skeleton of a photoessay with all of the
    "tedious" image reference bits taken care of, and then let you
    write the actually document/story around it, deleting unused
    images as you go.  (The proof of concept worked well but the
    actual output may need streamlining or outright template support,
    at which point feeding `--json` output to some Jinja2 code instead
    might make more sense.)
    
Finally, there are a few options that don't fit in the groups above:

  * `--dump-tags`:
    Dump out all known tags, one per line.  The output includes the
    category name.  You can also extract a subset of the names by
    combining it with `--tag`, `--exclude`, and `--since` (in this
    mode it *doesn't* print a category - see github#15.)

  * `--index-path`:
    Print the pathname of the `index.xml` we're actually using.  (If
    we have a path but it doesn't exist, fail, but consider changing
    that if we find a use that would involve creating the expected one.)

## EXAMPLES

`kpa-grep --tag office --since "last month" | tar cf office-pics.tar --files-from=-`

## REFERENCES

find(1), xargs(1), https://jsonlines.org/
