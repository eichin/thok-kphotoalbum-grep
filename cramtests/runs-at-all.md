# Make sure `kpa-grep` runs at all.

## setup

Find the built version (we haven't done the install step yet) and add
that to `PATH`.

    $ SCRIPTSBUILTDIR=$(realpath ${TESTDIR}/../build/scripts-*)
    $ export PATH=${SCRIPTSBUILTDIR}:$PATH

Run it with `--help` which should always work, even without an index.

    $ kpa-grep --help 1>/dev/null

Display version (extract from the module so we don't have to update
this test every version, or use a vague `(re)` or `(glob)` match.)

    $ MODULE_VERSION=$(python3 -c 'from kpa_grep import __version__; print(__version__)')
    $ kpa-grep --version | sed -e "s/${MODULE_VERSION}/MODVERSION/"
    kpa-grep MODVERSION

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
