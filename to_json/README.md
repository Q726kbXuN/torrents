# to_json

Utility to convert a .torrent file to a JSON file.

Most of the work happens in `create_summary.py`.  It's meant to be called as a Python 
module, though it can be run from the command line directly:


```
$ ./create_summary.py example/a66a0db8eadffbc41eba803f5a3e1046e077a9ef.torrent
{
  "bt_version": 1,
  "content_length": 37610,
  "extensions": "iso",
  "files": [
    {
      "name": "xubuntu-14.04.3-desktop-i386.iso",
      "size": 981467136
    }
  ],
  "files_count": 1,
  "files_size": 981467136,
  "ih": "a66a0db8eadffbc41eba803f5a3e1046e077a9ef",
  "name": "xubuntu-14.04.3-desktop-i386.iso",
  "piece_length": 524288
}
```
