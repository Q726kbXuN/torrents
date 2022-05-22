#!/usr/bin/env python3

import tor_cache_data
import json
import sys

def tor_to_summary(data):
    name, files, piece_length, extra = tor_cache_data.decode_torrent(data)
    file_count = len(files)
    file_size = 0
    extensions = set()
    for cur in files:
        try:
            temp = int(cur['size'])
            cur['size'] = temp
            file_size += temp
            extensions.add(cur['name'].split('.')[-1].lower())
        except:
            cur['size'] = 0
    body = {
        'ih': extra['v1_hash'], 
        'files': files, 
        'name': name,
        'files_count': file_count,
        'files_size': file_size,
        'piece_length': piece_length,
        'content_length': len(data),
        'extensions': ",".join(extensions),
        'bt_version': extra['torrent_version'],
    }
    if extra['torrent_version'] >= 2:
        body['ih_v2'] = extra['v2_hash']
        body['bt_hybrid'] = extra['hybrid']

    return body

def main():
    if len(sys.argv) != 2:
        print("Neeed .torrent file to parse")
    
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    
    summary = tor_to_summary(data)

    print(json.dumps(summary, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
