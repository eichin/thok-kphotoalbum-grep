# KPhotoAlbum Grep

Simple CLI tool for pulling subsets of photos out of KPhotoAlbum, by scanning the index.xml directly.  Base example:

    kpa-grep --tag office --since "last month" | tar cf office-pics.tar --files-from=-

finds the last month's files with the `office` keyword and puts them in a tar file; it uses the default kphotoalbum index file, and outputs full pathnames so tar can just find them.

Additional args:

  * `--print0`: `NUL` instead of newline, for `xargs -0`
  * `--relative`: paths relative to the index file (ie. don't normalize them)
  * `--index=`_PATH_: explicitly specify the index file
  * `--json`, `--xml`: output whole records (no surrounding document)

See [`kpa-grep(1)`](kpa-grep.1.ronn.md) for specifics.
