# Tests with constructed index files.

## setup

Find the built version (we haven't done the install step yet) and add
that to `PATH`.

    $ SCRIPTSBUILTDIR=$(realpath ${TESTDIR}/../build/scripts-*)
    $ export PATH=${SCRIPTSBUILTDIR}:$PATH

Put the XML files in `/tmp` to make the tests more readable.

    $ cp ${TESTDIR}/kpa-*.xml /tmp/

## basic index

### Empty file, no tags.

Confirm that it parses.

    $ kpa-grep --index /tmp/kpa-empty-idx.xml

Confirm that dump-tags handles it.

    $ kpa-grep --index /tmp/kpa-empty-idx.xml --dump-tags

Confirm that a nonexistent tag doesn't break.

    $ kpa-grep --index /tmp/kpa-empty-idx.xml --tag fred

Test that `--index-path` works at all

    $ kpa-grep --index /tmp/kpa-empty-idx.xml --index-path
    /tmp/kpa-empty-idx.xml

### Two images, one keyword applied to one of them.

No filters should give all of the files.

    $ kpa-grep --index /tmp/kpa-idx.xml
    /tmp/test_img_1.jpg
    /tmp/test_img_2.jpg

Dump tags should work.

    $ kpa-grep --index /tmp/kpa-idx.xml --dump-tags
    test

Dump tags supports `--print0`.

    $ kpa-grep --index /tmp/kpa-idx.xml --dump-tags --print0 | cat --show-all
    test^@ (no-eol)

Dump tags supports `--since` and `--print0` together (turns out to be
separate code paths.)  See also
<https://github.com/eichin/thok-kphotoalbum-grep/issues/16>.

    $ kpa-grep --index /tmp/kpa-idx.xml --dump-tags --print0 --since 1970-01-01 | cat --show-all
    test^@ (no-eol)

The files are explicitly ancient (1980) so "since last week" should
not produce them.

    $ kpa-grep --index /tmp/kpa-idx.xml --dump-tags --since "last week"

But since the dawn of time *should*.

    $ kpa-grep --index /tmp/kpa-idx.xml --dump-tags --since 1970-01-01
    test

Known tag path gets printed.

    $ kpa-grep --index /tmp/kpa-idx.xml --tag test
    /tmp/test_img_1.jpg

Known tag generates expected json output.

    $ kpa-grep --index /tmp/kpa-idx.xml --tag test --json
    {"file": "test_img_1.jpg", "height": 0, "label": "", "md5sum": "", "startDate": "1980-01-01T00:00:10", "width": 0, "Keywords": ["test"]}

Get a second opinion on the validity of the json output.

    $ kpa-grep --index /tmp/kpa-idx.xml --tag test --json | jq -r .file
    test_img_1.jpg

xml whitespace should probably be better, not just for the test, see
<https://github.com/eichin/thok-kphotoalbum-grep/issues/3> about
making it more completely valid/useful.

(Note that for some reason, the original "call `etree.tostring` on the
actual `Element` from the index file strips a character's worth of
whitespace, so `<options>` is indented by 11 instead of 3*4.  The use
of `etree.indent` produces indentation that actually matches the
KPhotoAlbum-written `index.xml`, so I'm going to call that an
accidental fix of an unnoticed bug in the `--xml` output.)

    $ kpa-grep --index /tmp/kpa-idx.xml --tag test --xml
    <image file="test_img_1.jpg" label="" startDate="1980-01-01T00:00:10" md5sum="" width="0" height="0">
                <options>
                    <option name="Keywords">
                        <value value="test" />
                    </option>
                </options>
            </image> (no-eol)

Do a basic check of the XML output with an independent parser
(`xmllint` uses the GNOME `libxml2`, rather than the `expat` library
that python uses underneath `etree`.)

    $ kpa-grep --index /tmp/kpa-idx.xml --tag test --xml | xmllint --noout -

Try XML selection with `xq` and Xpath. (`xq` is in Go, so "even more
independent", but this might also be useful for "shape" testing when
we expand <https://github.com/eichin/thok-kphotoalbum-grep/issues/3>
further.)

    $ kpa-grep --index /tmp/kpa-idx.xml --tag test --xml | xq -x '//options/option/@name'
    Keywords
    $ kpa-grep --index /tmp/kpa-idx.xml --tag test --xml | xq -x '//options/option/value/@value'
    test

Test that `--exclude` gives us the other filename.

    $ kpa-grep --index /tmp/kpa-idx.xml --exclude test
    /tmp/test_img_2.jpg

Confirm that `--path` picks out an explicit file.

    $ kpa-grep --index /tmp/kpa-idx.xml --path test_img_1.jpg
    /tmp/test_img_1.jpg

Confirm that `--path` with a full path also works (the paths stored in
the XML file are relative to it - the above path worked with the exact
match, this is testing the "strip off the common prefix" feature.)

    $ kpa-grep --index /tmp/kpa-idx.xml --path /tmp/test_img_1.jpg
    /tmp/test_img_1.jpg

Get relative (to the XML file) paths instead of normalized ones.

    $ kpa-grep --index /tmp/kpa-idx.xml --relative
    test_img_1.jpg
    test_img_2.jpg

Test `--print0` explicitly.

    $ kpa-grep --index /tmp/kpa-idx.xml --relative --print0 |cat --show-all
    test_img_1.jpg^@test_img_2.jpg^@ (no-eol)

Test `--print0` against `xargs -0`.

    $ kpa-grep --index /tmp/kpa-idx.xml --relative --print0 |xargs -n1 -0 echo
    test_img_1.jpg
    test_img_2.jpg

Basic test of Markdown output.  (Strip blank lines to make editing the
test a little easier.)  This also tests that Keywords show up.

    $ kpa-grep --index /tmp/kpa-idx.xml --markdown|grep .
    ## test_img_1
    ![test_img_1](test_img_1.jpg){: title="test_img_1"}
    ### Keywords
    test
    ## test_img_2
    ![test_img_2](test_img_2.jpg){: title="test_img_2"}

## using kde config to find index

Test that the value is used even if the file is gone (if `kphotoalbum`
changes such that the value is stored elsewhere we want to know about
it.)

    $ mkdir -p ~/.kde/share/config

If the config is present but we can't parse out a configfile entry,
warn the user (this test makes sure sure [Be
friendlier](https://github.com/eichin/thok-kphotoalbum-grep/issues/11)
stays fixed.)

    $ touch ~/.kde/share/config/kphotoalbumrc
    $ kpa-grep
    Warning: kphotoalbumrc found, but no configfile entry found
    No kphotoalbum index given (with --index or in kphotoalbumrc)
    [1]

Make sure that we fail clearly when the file mentioned isn't actually
there.

    $ echo configfile=/tmp/missing-index.xml > ~/.kde/share/config/kphotoalbumrc
    $ kpa-grep
    kphotoalbum index /tmp/missing-index.xml not found
    [1]

Test that an actual config works.

    $ echo configfile=/tmp/kpa-idx.xml > ~/.kde/share/config/kphotoalbumrc
    $ kpa-grep
    /tmp/test_img_1.jpg
    /tmp/test_img_2.jpg

Test that `--index-path` shows the configured value.

    $ kpa-grep --index-path
    /tmp/kpa-idx.xml

Clean up to avoid messing with other tests.

    $ rm ~/.kde/share/config/kphotoalbumrc

## tag combinations

For these tests, `kpa-many-tags.xml` has tests with tags that match
the filenames; `test_img_a` has a tag of `Keyword a`, `test_img_abc`
has all three keywords, `a`, `b`, and `c`; and `test_img_none` has no
tags at all.

### dump-tags subset

Basic output

    $ kpa-grep --index /tmp/kpa-many-tags.xml --dump-tags
    a
    b
    c

Filtering on tags should filter to the *files* with those tags, not
the tags themselves, giving us a way to display "neighboring" tags;
for example, what Location tags also have the tag "ice cream".

    $ kpa-grep --index /tmp/kpa-many-tags.xml --dump-tags --tag a
    a
    b
    c
    $ kpa-grep --index /tmp/kpa-many-tags.xml --dump-tags --tag c
    a
    b
    c

Literal ice cream example (superset of `kpa-many-tags.xml` but
shouldn't show any of `a`, `b`, or `c` tags.)

    $ kpa-grep --index /tmp/kpa-ice-cream-tags.xml --dump-tags --tag "ice cream"
    ice cream
    Tosci's


Listing two tags should list the paths that have both present.

    $ kpa-grep --index /tmp/kpa-many-tags.xml --tag a --relative
    test_img_a.jpg
    test_img_ab.jpg
    test_img_abc.jpg
    $ kpa-grep --index /tmp/kpa-many-tags.xml --tag b --relative
    test_img_ab.jpg
    test_img_abc.jpg
    test_img_b.jpg
    $ kpa-grep --index /tmp/kpa-many-tags.xml --tag a --tag b --relative
    test_img_ab.jpg
    test_img_abc.jpg

Excluding two tags should show everything that doesn't have either of them.

    $ kpa-grep --index /tmp/kpa-many-tags.xml --exclude a --relative
    test_img_b.jpg
    test_img_c.jpg
    test_img_none.jpg
    $ kpa-grep --index /tmp/kpa-many-tags.xml --exclude b --relative
    test_img_a.jpg
    test_img_c.jpg
    test_img_none.jpg
    $ kpa-grep --index /tmp/kpa-many-tags.xml --exclude a --exclude b --relative
    test_img_c.jpg
    test_img_none.jpg

Excluding all the tags should still leave the untagged document.

    $ kpa-grep --index /tmp/kpa-many-tags.xml --exclude a --exclude b --exclude c --relative
    test_img_none.jpg

# tag labelling

The first half of
<https://github.com/eichin/thok-kphotoalbum-grep/issues/15> is simply
displaying the `Category.name` along with the tag value.  For now this
only applies to `--dump-tags`.  Syntax will just be `category:tag`
(it's ok that existing tags contain `:` characters - I've been using
them for exactly this kind of namespacing - since the first one will
*always* be the category, no defaults, so there's no need for
disambiguation.

The minimal test index has one tag:

    $ kpa-grep --index /tmp/kpa-idx.xml --dump-tags --show-category
    Keywords:test

The "why do we even need this" practical case from the ice cream tags
index:

    $ kpa-grep --index /tmp/kpa-ice-cream-tags.xml --dump-tags --tag "ice cream" --show-category
    Keywords:ice cream
    Location:Tosci's

# checking hashes

Some testing related to an archive upgrade turned up an image that
didn't match the md5sum in the `index.xml`.  There's probably a way to
check for that within `kphotoalbum` itself, but for scripting
convenience it seemed like something that would fit as a `kpa-grep`
option.

We'll test this with some sample files:

    $ dd if=/dev/zero of=/tmp/image1k bs=1k count=1 status=none
    $ dd if=/dev/zero of=/tmp/image100k bs=100k count=1 status=none
    $ dd if=/dev/zero of=/tmp/image2G bs=1M count=2074 status=none

(The last one is roughly the size of the largest file in my personal
archive, a 10 minute drone video.)  The different sizes are just to
test against potential memory problems.

First run it clean:

    $ kpa-grep --index /tmp/kpa-hashes.xml --check-hashes

Then corrupt one image (by truncation) and try again:

    $ truncate --size 999 /tmp/image1k
    $ kpa-grep --index /tmp/kpa-hashes.xml --check-hashes
    /tmp/image1k
    $ kpa-grep --index /tmp/kpa-hashes.xml --check-hashes --relative
    image1k
    $ kpa-grep --index /tmp/kpa-hashes.xml --check-hashes --print0 | cat --show-all
    /tmp/image1k^@ (no-eol)

It is currently intentional that `--check-hashes` just gives a list of
files but doesn't actually give an error status; revisit that.

Clean up:

    $ rm -f /tmp/image1k /tmp/image100k /tmp/image2G
