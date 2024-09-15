# Make sure `kpa-grep` runs at all.

## setup

Find the built version (we haven't done the install step yet) and add
that to `PATH`.

    $ SCRIPTSBUILTDIR=$(realpath ${TESTDIR}/../build/scripts-*)
    $ export PATH=${SCRIPTSBUILTDIR}:$PATH

Run it with `--help` which should always work, even without an index.

    $ kpa-grep --help 1>/dev/null

Make sure it fails cleanly without an index.

    $ kpa-grep --dump-tags
    No kphotoalbum index given (with --index or in kphotoalbumrc)
    [1]
    $ kpa-grep --index-path
    No kphotoalbum index given (with --index or in kphotoalbumrc)
    [1]

Make sure it fails cleanly with an index arg that is missing.

    $ kpa-grep --index /tmp/missing-index.xml
    kphotoalbum index /tmp/missing-index.xml not found
    [1]
