#!/usr/bin/env python3

from bencode import bdecode, bencode, Bensorted
import json
import hashlib

# Function to convert a torrent file to a useful summary of data
# Handles buggy clients, oddball encodings, and other real-world issues.
# This can either be called from the command line, or as a library.

# This function exists to try and turn a byte array into a python "string"
# (aka, Unicode string).  It first takes a stab at doing a decode, with
# the surrogatepass option (more on that in a moment).  If that fails, 
# it likely means that the byte array is encoded in some other code page.
# If it's some other code page, we have two options:
#
# #1: Bring in a fairly heavy-weight library to guess which code page.
# #2: Just copy the characters between 0x20 and 0x7e (inclusive, aka the 
#     "Safe ASCII" range) and call whatever we get out of that the string.
# 
# We go with route #2 since we need something quick, and it likely doesn't 
# matter what the string is in that case.
# 
# Three notes:
# - We're using surrogatepass here because that's how Python 2 behaves
#   when you call its .decode("utf8") function, and we need to make
#   sure any reruns on old infohashes will behave the same as they 
#   always did.
# 
# - Even for elements in the info dictionary like 'name.utf-8' where
#   one would assume the encoding is UTF-8, it sometimes isn't, so this
#   helper must be called, otherwise the results are unpredictable
# 
# - This assumes you're passing in a byte array.  That goes without saying,
#   but things that are spec'd as being byte arrays sometimes aren't, so 
#   you'll need to verify that before calling this function, and make 
#   decisions on what to do before calling this helper.
def safe_decode(value):
    try:
        return value.decode('utf-8', 'surrogatepass')
    except UnicodeDecodeError:
        return "".join([chr(x) if x >= 32 and x <= 126 else '.' for x in value])


# Decodes a torrent file, loading the list of files and some other metadata from the
# torrent.  Handles many different buggy client implementations, and attempts to make
# some sense of those bugs.
# quiet = Should this function output any information?
# max_files = Optional max number of files to include in the list
# decode_names = Attempt to decode names, otherwise, just return empty strings
def decode_torrent(torrent, quiet=True, max_files=None, decode_names=True):
    name, files, piece_length = '', [], 0

    # Hand off the heavy lifting of decoding the bdecode format, note that we keep
    # dictionaries in order so that we can re-encode them and have a byte-for-byte
    # matching encoding with how it came in
    torrent = bdecode(torrent, in_order=True)
    if b'info' in torrent:
        # Pull out the info dictionary, this is the 'core' of the torrent
        torrent = torrent[b'info']

    piece_length = torrent.get(b'piece length', 0)

    if b'file tree' in torrent and isinstance(torrent.get(b'file tree', None), Bensorted):
        # This torrent is a v2 torrent, pull out the v2 metadata
        if decode_names:
            name = torrent.get(b'name.utf-8', torrent.get(b'name', b''))
            if isinstance(name, list):
                try:
                    name = name[0]
                except:
                    name = b''
            if isinstance(name, int):
                name = str(name).encode("utf-8")
            name = safe_decode(name)

            # If we couldn't find one for whatever reason, give it an arbitrary name
            if len(name) == 0:
                name = "torrent"
        else:
            name = ""

        def decode_file_tree(part, cur_path):
            for cur, value in part:
                cur = safe_decode(cur)

                if isinstance(value, Bensorted):
                    if b"" in value and len(value) == 1:
                        files.append({'name': "/".join(cur_path + [cur]), 'size': value[b""].get(b"length", 0)})
                    else:
                        decode_file_tree(value, cur_path + [cur])

        decode_file_tree(torrent[b'file tree'], [])
    elif b'files' in torrent:
        # This torrent has multiple files, first off, try to get
        # The name of the torrent.  Most clients use this as
        # the folder to download into
        if decode_names:
            name = torrent.get(b'name.utf-8', torrent.get(b'name', b''))
            if isinstance(name, list):
                try:
                    name = name[0]
                except:
                    name = b''
            if isinstance(name, int):
                name = str(name).encode("utf-8")
            name = safe_decode(name)

            # If we couldn't find one for whatever reason, give it an arbitrary name
            if len(name) == 0:
                name = "torrent"
        else:
            name = ""

        # Now run through each file and decode it
        file_index = 0
        for current_file in torrent[b'files']:
            file_index += 1
            if max_files is not None:
                if max_files == 0:
                    break
                else:
                    max_files -= 1
            # Using a for loop here to deal with some odd character type possibilities
            if decode_names:
                temp = [name]

                parts = current_file.get(b'path.utf-8', None)
                if parts is None:
                    parts = current_file.get(b'path', [])
                if isinstance(parts, Bensorted):
                    parts = []
                if not isinstance(parts, list):
                    parts = [parts]

                for part in parts:
                    if isinstance(part, int):
                        temp.append(str(part))
                    else:
                        temp.append(safe_decode(part))
                if len(temp) == 1:
                    temp.append("<no filename for file #%d>" % (file_index,))
                temp = "/".join(temp)

                if len(name) == 0:
                    name = temp
            else:
                temp = ""

            # Also get the size, including dealing with oddities
            size = current_file.get(b'length', 0)
            if isinstance(size, list):
                try:
                    size = size[0]
                except:
                    size = 0
            if isinstance(size, bytes):
                try:
                    size = int(size.decode("utf-8"))
                except:
                    size = 0
            files.append({'name': temp, 'size': size})
    else:
        # This is a single file torrent, so its name is the filename
        if (b'name.utf-8' in torrent or b'name' in torrent) and b'length' in torrent:
            if decode_names:
                temp = torrent.get(b'name.utf-8', torrent.get(b'name', b''))
                if isinstance(temp, list):
                    try:
                        temp = name[0]
                    except:
                        temp = b''
                if isinstance(temp, int):
                    temp = str(temp).encode("utf-8")
                temp = safe_decode(temp)
                if len(name) == 0:
                    name = temp
            else:
                temp = ""
            
            # Single file torrents also have a length, deal with odd values here too
            size = torrent[b'length']
            if isinstance(size, list):
                try:
                    size = size[0]
                except:
                    size = 0
            if isinstance(size, bytes):
                try:
                    size = int(size.decode("utf-8"))
                except:
                    size = 0
            files.append({'name': temp, 'size': size})

    if not quiet:
        print("Describing torrent as '%s', '%s', '%d'" % (name, json.dumps(files), piece_length))

    # Store some useful metadata, might be useful to find trends
    extra = {}
    extra['piece_hash'] = hashlib.sha1(torrent.get(b"pieces", b'')).hexdigest()
    extra['first_chunk'] = torrent.get(b"pieces", b'')[0:20].hex()

    # Calculate a hash of the list of files to create a fingerprint
    files_hash = hashlib.sha1()
    for cur in sorted(files, key=lambda x:(x["name"], x["size"])):
        files_hash.update(cur["name"].encode("utf-8", "surrogatepass"))
        files_hash.update(str(cur["size"]).encode("utf-8", "surrogatepass"))
    extra['files_hash'] = files_hash.hexdigest()

    # Look for the version of the torrent, if it has 'file tree' or 'meta version' in
    # the info dictionary, it's a v2 torrent.
    extra['torrent_version'] = torrent.get(b"meta version", 1)
    extra['hybrid'] = extra['torrent_version'] >= 2 and b'pieces' in torrent

    # And calculate the infohash
    torrent_data = bencode(torrent)
    try:
        temp = hashlib.sha1(torrent_data).hexdigest()
        extra['v1_hash'] = temp
    except:
        extra['v1_hash'] = 'unknown'

    # Also calculate the v2 infohash, even for v1 torrents
    try:
        temp = hashlib.sha256(torrent_data).hexdigest()
        extra['v2_hash'] = temp
    except:
        extra['v2_hash'] = 'unknown'

    return name, files, piece_length, extra


def dump_dict(dump_data, value, header="", parent_key=""):
    if isinstance(value, int):
        dump_data(f"{header}{value}")
        header = " " * len(header)
    elif isinstance(value, str):
        dump_data(f"{header}{value}")
        header = " " * len(header)
    elif isinstance(value, bytes):
        dump_data(f"{header}{value.decode('utf-8')}")
        header = " " * len(header)
    elif isinstance(value, list):
        for i in range(len(value)):
            dump_dict(dump_data, value[i], f"{header}[{i}]", parent_key+"["+str(i)+"]")
            header = " " * len(header)
    elif isinstance(value, (dict, Bensorted)):
        for key in sorted(value.keys()):
            sub = value[key]
            try:
                key = key.decode("utf-8")
            except:
                key = key.hex()
            if key in {"path", "path.utf-8"}:
                is_list = False
                if isinstance(sub, list):
                    is_list = True
                    for i in range(len(sub)):
                        obj = sub[i]
                        if isinstance(obj, bytes):
                            obj = obj.decode("utf-8")
                            sub[i] = obj
                        if not isinstance(obj, str):
                            is_list = False
                            break
                if is_list:
                    sub = "/".join(sub)

            if isinstance(sub, int):
                dump_data(f"{header}{key}: {sub}")
                header = " " * len(header)
            elif isinstance(sub, str):
                dump_data(f"{header}{key}: {sub}")
                header = " " * len(header)
            elif isinstance(sub, (dict, list, Bensorted)):
                dump_data(f"{header}{key}:")
                header = " " * len(header)
                dump_dict(dump_data, sub, header + "  ", parent_key+key)
            elif isinstance(sub, bytes):
                try:
                    if len(sub) == 0:
                        raise Exception()
                    temp = sub.decode("utf-8")
                except:
                    temp = f"<binary data of {len(sub)} bytes>"
                dump_data(f"{header}{key}: {temp}")
                header = " " * len(header)
            else:
                raise Exception("Unknown sub type: " + str(type(sub)))
    else:
        raise Exception("Unknown value type: " + str(type(value)))


def cmd_decode(filename):
    def to_print(value):
        print(value)
    with open(filename, "rb") as f:
        body = f.read()
    data = bdecode(body)
    print(f"----- Contents of '{filename}' -----")
    dump_dict(to_print, data)


def cmd_filenames(filename):
    with open(filename, "rb") as f:
        body = f.read()
    data = bdecode(body)
    name = data[b'info'][b'name'].decode("utf-8")
    if b'files' in data[b'info']:
        for cur in data[b'info'][b'files']:
            temp = [name] + [x.decode("utf-8") for x in cur[b'path']]
            print("/".join(temp))
    else:
        print(name)


def cmd_pretty(filename):
    with open(filename, "rb") as f:
        body = f.read()
    name, files, piece_length, extra = decode_torrent(body)
    def header(value):
        print("-" * 5 + " " + value + " " + "-" * (70 - len(value)))
    header("Name")
    print(name)
    header("Piece Length")
    print(piece_length)
    header("Files")
    for cur in files:
        print(f"{cur['name']} ({cur['size']})")
    header("Extra")
    print(f"File count: {len(files)}")
    print(f"Data size: {sum(x['size'] for x in files)}")
    for key, value in extra.items():
        print(f"{key}: {value}")


def main():
    import sys

    show_help = True
    cmds = {
        "filenames": ["<filename> = Convert a .torrent file to a list of files", cmd_filenames, 1],
        "decode": ["<filename> = Convert a .torrent file to a human-readable version", cmd_decode, 1],
        "pretty": ["<filename> = Convert a .torrent file to a decoded version", cmd_pretty, 1],
    }

    temp = sys.argv[1:]
    while len(temp) > 0:
        if temp[0] in cmds:
            cmd = cmds[temp[0]]
            show_help = False
            cmd[1](*temp[1:1+cmd[2]])
            temp = temp[1+cmd[2]:]
        else:
            show_help = True
            break

    if show_help:
        print("Usage:")
        for key, cmd in cmds.items():
            print(f"  {key} {cmd[0]}")


if __name__ == "__main__":
    main()
