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

### Two images, one keyword applied to one of them.

No filters should give all of the files.

    $ kpa-grep --index /tmp/kpa-idx.xml
    /tmp/test_img_1.jpg
    /tmp/test_img_2.jpg

Dump tags should work.

    $ kpa-grep --index /tmp/kpa-idx.xml --dump-tags
    Keywords test

The files are explicitly ancient (1980) so "since last week" should
not produce them.

    $ kpa-grep --index /tmp/kpa-idx.xml --dump-tags --since "last week"

Known tag path gets printed.

    $ kpa-grep --index /tmp/kpa-idx.xml --tag test
    /tmp/test_img_1.jpg

Known tag generates expected json output.

    $ kpa-grep --index /tmp/kpa-idx.xml --tag test --json
    {"file": "test_img_1.jpg", "label": "", "startDate": "1980-01-01T00:00:10", "Keywords": ["test"]}

Get a second opinion on the validity of the json output.

    $ kpa-grep --index /tmp/kpa-idx.xml --tag test --json | jq -r .file
    test_img_1.jpg

xml whitespace should probably be better, not just for the test, see
<https://github.com/eichin/thok-kphotoalbum-grep/issues/3> about
making it more completely valid/useful.

    $ kpa-grep --index /tmp/kpa-idx.xml --tag test --xml
    <image file="test_img_1.jpg" label="" startDate="1980-01-01T00:00:10">
               <options>
                   <option name="Keywords">
                       <value value="test" />
                   </option>
               </options>
           </image>
            (no-eol)

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

## using kde config to find index

Test that the value is used even if the file is gone (if `kphotoalbum`
changes such that the value is stored elsewhere we want to fail hard,
not guess.)

    $ mkdir -p ~/.kde/share/config

If the config is present but we can't parse out a configfile entry, we
currently blow up with a `KeyError: 'configfile'` traceback.  [Be
friendlier](https://github.com/eichin/thok-kphotoalbum-grep/issues/11). 

    $ touch ~/.kde/share/config/kphotoalbumrc
    $ : SKIP kpa-grep

    $ echo configfile=/tmp/missing-index.xml > ~/.kde/share/config/kphotoalbumrc
    $ kpa-grep
    kphotoalbum index /tmp/missing-index.xml not found
    [1]

    $ echo configfile=/tmp/kpa-idx.xml > ~/.kde/share/config/kphotoalbumrc
    $ kpa-grep
    /tmp/test_img_1.jpg
    /tmp/test_img_2.jpg

Clean up to avoid messing with other tests.

    $ rm ~/.kde/share/config/kphotoalbumrc
