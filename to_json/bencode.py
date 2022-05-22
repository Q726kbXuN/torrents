#!/usr/bin/env python3

# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.1 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

# Written by Petru Paler
# Modified:
#
# Migrated to Python3, changing quite a bit to move away from strings to byte
# arrays.
#
# Added a 'Bencached' concept to allow placing a pre-encoded item in a more 
# complex object, so we can download the 'info' dictionary from elsewhere and 
# create a .torrent file out of it without a decode/encode cycle.
#
# Added a in_order flag to bdecode that decodes dictionaries to Bensorted, 
# which is a sorted dictionary thta should re-encode byte-for-byte to the same 
# bytes as the encoded version.  This is done because some clients produce 
# non-sorted dictionaries, and re-ordering the dictionaries will cause a hash 
# mismatch if an attempt is made later on to calculate an infohash.
#
# Handle encoding of sets as if they're lists.
#
# Various "treat all data as flawed and don't break if it is" bug fixes.

class BTFailure(Exception):
    pass


class Bencached(object):
    __slots__ = ['bencoded']

    # noinspection PyPropertyAccess
    def __init__(self, s):
        self.bencoded = s


class Bensorted(object):
    __slots__ = ['sorted']

    # noinspection PyPropertyAccess
    def __init__(self, s):
        self.sorted = s

    def __iter__(self):
        return self.sorted.__iter__()

    def __len__(self):
        return len(self.sorted)

    def __getitem__(self, key):
        for k, v in self.sorted:
            if k == key:
                return v
        raise KeyError()

    def __setitem__(self, key, value):
        for i in range(len(self.sorted)):
            if self.sorted[i][0] == key:
                self.sorted[i] = (key, value)
                return
        raise KeyError()

    def __contains__(self, key):
        for k, _v in self.sorted:
            if k == key:
                return True
        return False

    def get(self, key, default_value):
        for k, v in self.sorted:
            if k == key:
                return v
        return default_value


def decode_int(decode_func_type, x, f):
    f += 1
    newf = x.index(b'e', f)
    n = int(x[f:newf])
    if x[f] == b'-'[0]:
        if x[f + 1] == b'0':
            raise ValueError
    elif x[f] == b'0'[0] and newf != f + 1:
        raise ValueError
    return n, newf + 1


def decode_string(decode_func_type, x, f):
    colon = x.index(b':', f)
    n = int(x[f:colon])
    if x[f] == '0' and colon != f + 1:
        raise ValueError
    colon += 1
    return x[colon:colon + n], colon + n


def decode_list(decode_func_type, x, f):
    r, f = [], f + 1
    while x[f] != b'e'[0]:
        # noinspection PyCallingNonCallable
        v, f = decode_func_type[x[f]](decode_func_type, x, f)
        r.append(v)
    return r, f + 1


def decode_dict(decode_func_type, x, f):
    r, f = {}, f + 1
    while x[f] != b'e'[0]:
        k, f = decode_string(decode_func_type, x, f)
        # noinspection PyCallingNonCallable
        r[k], f = decode_func_type[x[f]](decode_func_type, x, f)
    return r, f + 1


def decode_dict_ordered(decode_func_type, x, f):
    r = Bensorted([])
    f = f + 1
    while x[f] != b'e'[0]:
        k, f = decode_string(decode_func_type, x, f)
        # noinspection PyCallingNonCallable
        v, f = decode_func_type[x[f]](decode_func_type, x, f)
        r.sorted.append((k, v))
    return r, f + 1


decode_func = {
    b'l'[0]: decode_list,
    b'd'[0]: decode_dict,
    b'i'[0]: decode_int,
    b'0'[0]: decode_string,
    b'1'[0]: decode_string,
    b'2'[0]: decode_string,
    b'3'[0]: decode_string,
    b'4'[0]: decode_string,
    b'5'[0]: decode_string,
    b'6'[0]: decode_string,
    b'7'[0]: decode_string,
    b'8'[0]: decode_string,
    b'9'[0]: decode_string,
}


decode_func_ordered = {
    b'l'[0]: decode_list,
    b'd'[0]: decode_dict_ordered,
    b'i'[0]: decode_int,
    b'0'[0]: decode_string,
    b'1'[0]: decode_string,
    b'2'[0]: decode_string,
    b'3'[0]: decode_string,
    b'4'[0]: decode_string,
    b'5'[0]: decode_string,
    b'6'[0]: decode_string,
    b'7'[0]: decode_string,
    b'8'[0]: decode_string,
    b'9'[0]: decode_string,
}


def bdecode(x, in_order=False):
    try:
        if in_order:
            # noinspection PyCallingNonCallable
            r, l = decode_func_ordered[x[0]](decode_func_ordered, x, 0)
        else:
            # noinspection PyCallingNonCallable
            r, l = decode_func[x[0]](decode_func, x, 0)
    except (IndexError, KeyError, ValueError):
        raise BTFailure("not a valid bencoded string")
    if l != len(x):
        raise BTFailure("invalid bencoded value (data after valid prefix)")
    return r


def encode_bencached(x, r):
    r.append(x.bencoded)


def encode_int(x, r):
    r.extend((b'i', str(x).encode("utf8"), b'e'))


def encode_string(x, r):
    r.extend((str(len(x)).encode("utf8"), b':', x))


def encode_list(x, r):
    r.append(b'l')
    for i in x:
        # noinspection PyCallingNonCallable
        encode_func[type(i)](i, r)
    r.append(b'e')


def encode_dict(x, r):
    r.append(b'd')
    ilist = list(x.items())
    ilist.sort()
    for k, v in ilist:
        r.extend((str(len(k)).encode("utf8"), b':', k))
        # noinspection PyCallingNonCallable
        encode_func[type(v)](v, r)
    r.append(b'e')


def encode_bensorted(x, r):
    r.append(b'd')
    for k, v in x.sorted:
        r.extend((str(len(k)).encode("utf8"), b':', k))
        # noinspection PyCallingNonCallable
        encode_func[type(v)](v, r)
    r.append(b'e')


encode_func = {
    Bencached: encode_bencached,
    Bensorted: encode_bensorted,
    type(0): encode_int,
    type(b""): encode_string,
    type([]): encode_list,
    type(set()): encode_list,
    type({}): encode_dict,
}


def bencode(x):
    r = []
    # noinspection PyCallingNonCallable
    encode_func[type(x)](x, r)
    return b''.join(r)


if __name__ == "__main__":
    print("This module can not be run directly")
