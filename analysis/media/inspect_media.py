"""Read-only JFD inventory and bounded ADFS E extraction.

Derived data go only beside this script; originals are never opened for writing.
JFD offsets follow the ADFFS 2.84 structure document (public transcription at
https://gist.github.com/Kaens/a139d96dc429b49788e47ea57e55017d).
Header/mask layout is also independently implemented by MAME at
https://github.com/mamedev/mame/blob/master/src/lib/formats/jfd_dsk.cpp.
This parser validates payload layout, not complete controller emulation;
MAME's reader does not consume every JFD field either.
ADFS layout follows the original FileCore PRM at
https://www.riscos.com/support/developers/prm/filecore.html.
No game or boot script is executed.
"""
from pathlib import Path
import argparse
import collections
import gzip
import hashlib
import json
import re
import struct

OUT = Path(__file__).resolve().parent
ORIGINALS = OUT.parents[1] / 'Lotus'

def u32(b, n):
    return struct.unpack_from('<I', b, n)[0]

def sha(b):
    return hashlib.sha256(b).hexdigest()

def name(b):
    return re.split(rb'[\x00-\x1f]', b, maxsplit=1)[0].decode('latin-1')

def safe_name(n):
    return re.sub(r'[<>:"/\\|?*]', '_', n)

def jsonwrite(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')

def zonecheck(b):
    a = c = d = e = 0
    for i in range(len(b)-4, 0, -4):
        a += b[i] + (e >> 8)
        e &= 255
        c += b[i+1] + (a >> 8)
        a &= 255
        d += b[i+2] + (c >> 8)
        c &= 255
        e += b[i+3] + (d >> 8)
        d &= 255
    a += e >> 8
    c += b[1] + (a >> 8)
    d += b[2] + (c >> 8)
    e += b[3] + (d >> 8)
    return (a ^ c ^ d ^ e) & 255

def directory_checkbyte(b):
    # Use the established new-directory checksum behavior: data before the
    # end marker and whole tail words at 2008..2043, excluding the final word.
    # Original PRM describes rotation; Linux ADFS clarifies tail byte alignment.
    end = 5
    while b[end] and end < 2007:
        end += 26
    total = 0
    def add(value):
        nonlocal total
        total = (value ^ ((total >> 13) | (total << 19))) & 0xffffffff
    p = 0
    while p+4 <= end:
        add(u32(b,p))
        p += 4
    while p < end:
        add(b[p])
        p += 1
    for p in range(2008,2044,4):
        add(u32(b,p))
    return (total ^ (total>>8) ^ (total>>16) ^ (total>>24)) & 255

def inspect(f):
    original = f.read_bytes()
    b = gzip.decompress(original)
    assert b[:4] == b'JFDI'
    assert len(b) == u32(b, 8)
    disc_number = u32(b,12) & 65535
    disc_count = u32(b,12) >> 16
    dest = OUT / ('F10232%02d' % disc_number)
    dest.mkdir(parents=True, exist_ok=True)
    tt, st, dt = (u32(b, x) for x in (24,28,32))
    obeylen = u32(b,312)
    datalen = len(b) - dt - obeylen
    flags = u32(b,304)
    metadata = {
        'original_path': str(f), 'original_bytes': len(original), 'original_sha256': sha(original),
        'gzip_header_hex': original[:10].hex(), 'gzip_crc32_and_size_validated': True,
        'jfd_uncompressed_bytes': len(b), 'jfd_uncompressed_sha256': sha(b),
        'minimum_adffs_version': u32(b,4)/100, 'disc_number': disc_number,
        'disc_count': disc_count, 'game_id': u32(b,16),
        'image_version_raw': u32(b,20), 'title': name(b[48:304]),
        'track_table_offset': tt, 'sector_table_offset': st, 'data_table_offset': dt,
        'delta_table_offsets': [u32(b,x) for x in (36,40,44)],
        'flags_hex': hex(flags), 'set_flag_bit_numbers': [x for x in range(32) if flags & (1<<x)],
        'nominal_game_fps_metadata': b[308]/2 if b[308] else None,
        'embedded_obey_bytes': obeylen,
        'platform': 'Acorn Archimedes / RISC OS / 26-bit ARM',
        'platform_confidence': 'high: JFDI + ADFS metadata + ARM executable + original boot commands',
    }
    if obeylen:
        (dest / 'embedded_adffs_boot.obey').write_bytes(b[-obeylen:])
    tracks = []
    sectors = []
    raw = bytearray(819200)
    known = bytearray(819200)
    observed = bytearray(819200)
    occupied = collections.defaultdict(list)
    for idx in range((st-tt)//4):
        off = u32(b,tt+4*idx)
        if off == 0xffffffff:
            tracks.append({'jfd_track':idx,'blank':True})
            continue
        p = st+off
        count = 0
        while u32(b,p) != 0xffffffff:
            hdr, dataoff = struct.unpack_from('<2I',b,p)
            length = 128 << (hdr & 15)
            sector_id = (hdr >> 8) & 255
            crc_flags = (hdr >> 4) & 15
            density = (hdr >> 16) & 15
            options = (hdr >> 20) & 15
            row = {'jfd_track':idx,'cylinder':idx//2,'head':idx%2,
                   'sector_id':sector_id,'size':length,'crc_flags':crc_flags,
                   'density':density,'options':options,'time_ms':hdr>>24,
                   'header_hex':hex(hdr),'data_offset':dataoff if dataoff!=0xffffffff else None}
            if dataoff != 0xffffffff:
                assert dataoff+length <= datalen
                data = b[dt+dataoff:dt+dataoff+length]
                row['sha256'] = sha(data)
                if idx < 160 and sector_id < 5 and length == 1024 and not (options & 1):
                    loc = (idx*5+sector_id)*1024
                    row['logical_offset'] = loc
                    occupied[loc].append(row)
                    if len(occupied[loc]) == 1:
                        raw[loc:loc+length] = data
                        observed[loc:loc+length] = b'\x01'*length
                        if not(crc_flags & 3):
                            known[loc:loc+length] = b'\x01'*length
                        else:
                            protection = dest / ('protection_c%02d_h%d_s%d.bin' % (idx//2,idx%2,sector_id))
                            protection.write_bytes(data)
                            row['isolated_payload_path'] = str(protection)
            sectors.append(row)
            count += 1
            p += 8
            assert p < dt
        tracks.append({'jfd_track':idx,'sector_count':count,'sector_table_relative_offset':off})
    metadata['sector_count'] = len(sectors)
    metadata['discop3_blocks'] = sum(bool(x['options']&1) for x in sectors)
    metadata['sector_options_counts'] = dict(collections.Counter(x['options'] for x in sectors))
    metadata['sector_time_counts'] = dict(collections.Counter(x['time_ms'] for x in sectors))
    metadata['represented_logical_payload_bytes_including_crc_errors'] = sum(observed)
    metadata['represented_ordinary_logical_bytes'] = sum(known)
    metadata['unknown_logical_bytes_zero_padded_for_analysis'] = len(raw)-sum(observed)
    metadata['missing_logical_sectors'] = [i for i in range(800) if not observed[i*1024]]
    metadata['special_sectors'] = [x for x in sectors if x.get('logical_offset') is None or x['crc_flags']&3]
    metadata['duplicate_logical_sectors'] = {hex(k):v for k,v in occupied.items() if len(v)>1}
    (dest / 'logical_zero_padded.adf').write_bytes(raw)
    jsonwrite(dest / 'sectors.json', sectors)
    jsonwrite(dest / 'tracks.json', tracks)
    metadata['logical_zero_padded_sha256'] = sha(raw)
    rec = raw[4:64]
    secsize = 1 << rec[0]
    bpmb = 1 << rec[5]
    idlen = rec[4]
    record = {'log2secsize':rec[0],'sector_bytes':secsize,'sectors_per_track':rec[1],
              'heads':rec[2],'density':rec[3],'idlen':idlen,'log2bpmb':rec[5],
              'bytes_per_map_bit':bpmb,'skew':rec[6],'bootoption':rec[7],
              'zones':rec[9],'zone_spare':int.from_bytes(rec[10:12],'little'),
              'root_internal_address_hex':hex(u32(rec,12)), 'disc_bytes':u32(rec,16),
              'disc_cycle_id':int.from_bytes(rec[20:22],'little'), 'disc_name':name(rec[22:32]),
              'format':'ADFS E / new map / new 2048-byte directories'}
    assert record['zones'] == 1 and record['disc_bytes'] == len(raw)
    record['first_map_zone_checksum_stored'] = raw[0]
    record['first_map_zone_checksum_calculated'] = zonecheck(raw[:secsize])
    record['map_copies_equal'] = raw[:secsize] == raw[secsize:2*secsize]
    metadata['disc_record'] = record
    # Single-zone E-format map: allocation bits begin after 4-byte header + 60-byte record.
    bitbase = 64*8
    limit = secsize*8 - record['zone_spare'] + 32
    assert (limit-bitbase)*bpmb == len(raw)
    def bits(pos, count):
        return sum(((raw[(pos+i)//8] >> ((pos+i)%8)) & 1) << i for i in range(count))
    freechain = set()
    nextfree = 8 + bits(8,idlen)
    while nextfree != 8 and nextfree < limit:
        assert nextfree not in freechain
        freechain.add(nextfree)
        link = bits(nextfree,idlen)
        if not link:
            break
        nextfree += link
    extents = []
    pos = bitbase
    while pos < limit:
        start = pos
        fragid = bits(pos,idlen)
        pos += idlen
        # Fragment 1 represents bad sectors and spare map bits beyond the disc;
        # the Lotus maps terminate this final fragment at the end of the sector.
        scanlimit = secsize*8 if fragid == 1 else limit
        while pos < scanlimit and not bits(pos,1):
            pos += 1
        assert pos < scanlimit, ('unterminated map fragment',pos)
        pos += 1
        extents.append({'fragment_id':fragid,'map_bit_start':start,
                        'physical_offset':(start-bitbase)*bpmb,'bytes':(pos-start)*bpmb,
                        'free':start in freechain,'beyond_disc_bytes':max(0,(pos-bitbase)*bpmb-len(raw))})
    jsonwrite(dest / 'extents.json',extents)
    fragdata = collections.defaultdict(list)
    for ext in extents:
        if not ext['free'] and ext['fragment_id'] != 1:
            fragdata[ext['fragment_id']].append(ext)
    files = []
    directory_checks = []
    def read_object(address, length):
        fid = (address>>8)&0x7fff
        off = max(0,(address&255)-1)*secsize
        data = bytearray()
        cover = bytearray()
        used = []
        for ext in fragdata[fid]:
            loc,end = ext['physical_offset'],ext['physical_offset']+ext['bytes']
            data += raw[loc:end]
            cover += known[loc:end]
            used.append({'physical_offset':loc,'bytes':end-loc})
        assert off+length <= len(data), (hex(address),length,len(data),off)
        return bytes(data[off:off+length]), all(cover[off:off+length]), used
    visited = set()
    def directory(address, logical, target):
        assert address not in visited, ('directory loop',logical)
        visited.add(address)
        data, covered, used = read_object(address,2048)
        assert covered, ('unknown directory bytes',logical)
        assert data[1:5] in (b'Nick',b'Hugo') and data[-5:-1] == data[1:5]
        assert data[0] == data[-6]
        checksum = directory_checkbyte(data)
        assert checksum == data[-1], ('directory checksum mismatch',logical,checksum,data[-1])
        target.mkdir(parents=True,exist_ok=True)
        checks = {'logical_path':logical,'internal_address_hex':hex(address),
                  'all_bytes_represented_in_jfd':covered,'matching_header_tail':True,
                  'matching_sequence_numbers':True,'checksum_stored':data[-1],
                  'checksum_calculated':checksum,'checksum_valid':True,
                  'sha256':sha(data),'fragment_extents':used}
        directory_checks.append(checks)
        for i in range(77):
            entry = data[5+26*i:5+26*(i+1)]
            if entry[0] == 0:
                break
            fn = name(entry[:10])
            load,exe,length = struct.unpack_from('<3I',entry,10)
            ind = int.from_bytes(entry[22:25],'little')
            attrs = entry[25]
            filepath = logical+'.'+fn
            if attrs&8:
                directory(ind,filepath,target/safe_name(fn))
            else:
                filedata,covered,used = read_object(ind,length)
                assert covered, ('unknown file bytes',filepath)
                output = target/safe_name(fn)
                output.write_bytes(filedata)
                files.append({'logical_path':filepath,'output_path':str(output),
                              'bytes':length,'sha256':sha(filedata),'load_address_hex':hex(load),
                              'exec_address_hex':hex(exe),'riscos_filetype_hex':hex((load>>8)&4095) if load>>20==4095 else None,
                              'internal_address_hex':hex(ind),'attributes_hex':hex(attrs),
                              'all_bytes_represented_in_jfd':covered,'fragment_extents':used,
                              'first_32_bytes_hex':filedata[:32].hex()})
    directory(u32(rec,12),'$',dest/'extracted')
    jsonwrite(dest/'files.json',files)
    jsonwrite(dest/'directories.json',directory_checks)
    metadata['extracted_file_count'] = len(files)
    metadata['extracted_bytes'] = sum(x['bytes'] for x in files)
    metadata['extraction_limitations'] = [
        'Logical ADF is an analysis reconstruction; unrepresented space is explicitly zero-filled.',
        'Represented CRC-error sector payloads are copied to the analysis ADF, but CRC/error behavior and JFD metadata are lost.',
        'Filesystem headers/tails, sequences, directory checksums, map checksums, mirror maps and complete file-byte coverage validated.',
        'Static evidence only; game, emulator, FPGA and audio/video behavior not exercised.',
    ]
    assert f.read_bytes() == original, 'original changed during analysis'
    metadata['original_verified_unchanged_after_analysis'] = True
    jsonwrite(dest/'metadata.json',metadata)
    return metadata

if __name__ == '__main__':
    args = argparse.ArgumentParser(description=__doc__).parse_args()
    results = [inspect(f) for f in sorted(ORIGINALS.glob('*.jfd'))]
    jsonwrite(OUT/'inventory.json',results)
    print(json.dumps([{'disc':x['disc_number'],'sha256':x['original_sha256'],
                       'files':x['extracted_file_count'],'special_sectors':x['special_sectors'],
                       'known_logical_bytes':x['represented_ordinary_logical_bytes']} for x in results], indent=2))
