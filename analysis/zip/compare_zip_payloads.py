"""Compare ZIP streams with hash-verified JFD file inventory; never execute payloads.

Input archives and JFDs are opened read-only. No archive members are extracted.
Output is comparison.json under analysis/zip. Compatibility script text is
recorded as evidence only, and never fed to a shell, BASIC, or ARM emulator.
"""
from pathlib import Path
import collections
import difflib
import gzip
import hashlib
import io
import json
import re
import struct
import zipfile

PROJECT = Path(__file__).resolve().parents[2]
MEDIA = PROJECT/'analysis'/'media'
OUT = PROJECT/'analysis'/'zip'/'comparison.json'
PREFIX = 'Apps/Games/!LOTUS/'
EXPECTED = {
    'Lotus-Turbo-Challenge-2_0-1.zip':'939663a6cb92ef5b315e6aa294dafbe9fba11960e54c1ffc14c1a8b668effb93',
    'Lotus-Turbo-Challenge-2_0-2.zip':'64e4ff2e69a8bc804629ffbfd0334e6c3ffe2633da3b9ad0377722758d5c31fe',
    'Lotus-Turbo-Challenge-2_0-3.zip':'cf164eed8610b4a7ea85fcf9cc5e3bfee05bc117beb549ca310a0b03daa7cca2',
}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def readjson(path):
    return json.loads(path.read_text(encoding='utf-8'))

def u32(data,offset):
    return struct.unpack_from('<I',data,offset)[0]

def textdata(data):
    return data.decode('latin-1')

def normalize(logical,disc):
    parts = logical.split('.')
    if disc == 1 and len(parts)>1 and parts[1].upper() == '!LOTUS':
        return '/'.join(parts[2:]).casefold()
    if disc == 2:
        return '/'.join(parts[1:]).casefold()
    return None

def diff_bytes(a,b):
    ranges = []
    start = None
    for i in range(max(len(a),len(b))):
        different = i>=len(a) or i>=len(b) or a[i]!=b[i]
        if different and start is None:
            start = i
        elif not different and start is not None:
            ranges.append({'offset':start,'bytes':i-start,'before_hex':a[start:i].hex(),'after_hex':b[start:i].hex()})
            start = None
    if start is not None:
        i = max(len(a),len(b))
        ranges.append({'offset':start,'bytes':i-start,'before_hex':a[start:i].hex(),'after_hex':b[start:i].hex()})
    return ranges

inventory = readjson(MEDIA/'inventory.json')
refs = {}
original_jfds = {}
for image in inventory:
    disc = image['disc_number']
    original = Path(image['original_path']).read_bytes()
    assert sha(original) == image['original_sha256'], 'Original JFD changed since inventory'
    original_jfds[disc] = original
    for row in readjson(MEDIA/('F10232%02d'%disc)/'files.json'):
        n = normalize(row['logical_path'],disc)
        if n is not None:
            assert n not in refs
            data = Path(row['output_path']).read_bytes()
            assert sha(data) == row['sha256'], 'Extracted evidence changed since inventory'
            refs[n] = {'disc':disc,**row}

archives = []
streams = []
for fn,expected in EXPECTED.items():
    path = PROJECT/'Lotus'/'zip'/fn
    archivebytes = path.read_bytes()
    assert sha(archivebytes)==expected, 'Archive differs from supplied hash'
    z = zipfile.ZipFile(io.BytesIO(archivebytes))
    members = {i.filename:z.read(i) for i in z.infolist() if not i.is_dir()}
    assert len(members) == len([i for i in z.infolist() if not i.is_dir()]), 'Duplicate ZIP member names'
    streams.append(members)
    matches = []
    changed = []
    additions = []
    seen = set()
    for member,data in members.items():
        if not member.startswith(PREFIX):
            continue
        rel = member[len(PREFIX):].casefold()
        if rel in refs:
            reference = refs[rel]
            referencebytes = Path(reference['output_path']).read_bytes()
            same = data == referencebytes
            seen.add(rel)
            row = {'archive_member':member,'bytes':len(data),'sha256':sha(data),
                   'jfd_disc':reference['disc'],'jfd_logical_path':reference['logical_path'],
                   'jfd_bytes':reference['bytes'],'jfd_sha256':reference['sha256'],'equal_bytes':same}
            if same:
                matches.append(row)
            else:
                row['differing_byte_count'] = sum(i>=len(referencebytes) or i>=len(data) or referencebytes[i]!=data[i]
                                                  for i in range(max(len(referencebytes),len(data))))
                if len(data)==len(referencebytes):
                    row['byte_changes'] = diff_bytes(referencebytes,data)
                if rel == '!run':
                    row['script_unified_diff'] = ''.join(difflib.unified_diff(
                        textdata(referencebytes).splitlines(keepends=True),textdata(data).splitlines(keepends=True),
                        fromfile='Original JFD !RUN',tofile=fn+' !Run'))
                changed.append(row)
        else:
            additions.append({'archive_member':member,'bytes':len(data),'sha256':sha(data)})
    f10232 = members[PREFIX+'F1023201']
    embed = gzip.decompress(f10232)
    assert embed[:4]==b'JFDI' and len(embed)==u32(embed,8)
    tt,st,dt = [u32(embed,x) for x in (24,28,32)]
    special = []
    sector_count = 0
    for t in range((st-tt)//4):
        off = u32(embed,tt+t*4)
        if off == 0xffffffff:
            continue
        p = st+off
        while u32(embed,p)!=0xffffffff:
            h,d = struct.unpack_from('<II',embed,p)
            sector_count += 1
            if (h>>4)&3:
                size = 128<<(h&15)
                special.append({'jfd_track':t,'cylinder':t//2,'head':t%2,'sector_id':(h>>8)&255,
                                'sector_size':size,'header_hex':hex(h),'crc_flags':(h>>4)&15,
                                'data_offset':d,'payload_sha256':sha(embed[dt+d:dt+d+size]) if d!=0xffffffff else None})
            p += 8
    obeylen = u32(embed,312)
    control = textdata(members['RiscPkg/Control'])
    record = {'archive_path':str(path),'archive_bytes':len(archivebytes),'archive_sha256':sha(archivebytes),
              'all_members_crc_validated_by_zipfile_read':True,
              'version':re.search(r'^Version: (.+)$',control,re.MULTILINE).group(1),
              'control_text':control,'copyright_sha256':sha(members['RiscPkg/Copyright']),
              'original_corresponding_game_files_count':len(refs),'exact_original_match_count':len(matches),
              'exact_original_matches':matches,'changed_against_original':changed,
              'new_application_members':additions,
              'absent_original_game_members':[{'relative_name':n,'disc':refs[n]['disc'],
                       'jfd_logical_path':refs[n]['logical_path'],'sha256':refs[n]['sha256']} for n in sorted(set(refs)-seen)],
              'embedded_F1023201':{'archive_member':PREFIX+'F1023201','bytes':len(f10232),
                       'sha256':sha(f10232),'equal_complete_supplied_original_jfd_bytes':f10232==original_jfds[1],
                       'kind':'Whole supplied gzip JFD container, not a metadata-only/protection-only stub.',
                       'physical_capture_limit':'Original JFD represents a recorded subset of physical sectors; it is not a full flux dump.',
                       'decompressed_bytes':len(embed),'sector_count':sector_count,
                       'game_id':u32(embed,16),'disc_number':u32(embed,12)&65535,'disc_count':u32(embed,12)>>16,
                       'flags_hex':hex(u32(embed,304)),'embedded_obey_bytes':obeylen,
                       'embedded_obey_sha256':sha(embed[-obeylen:]) if obeylen else None,'crc_error_sectors':special},
              'launch_script':{'archive_member':PREFIX+'!Run','bytes':len(members[PREFIX+'!Run']),
                       'sha256':sha(members[PREFIX+'!Run']),'text':textdata(members[PREFIX+'!Run'])},
              'script_and_dependency_limit':'Commands are static evidence, not executed or qualified; runtime behavior depends on ADFFS and classic ARM/RISC OS support.'}
    archives.append(record)

deltas = []
for i in (1,2):
    before,after = streams[i-1],streams[i]
    common = sorted(set(before)&set(after))
    changed = [n for n in common if before[n]!=after[n]]
    rows = []
    for n in changed:
        row = {'member':n,'before_bytes':len(before[n]),'after_bytes':len(after[n]),
               'before_sha256':sha(before[n]),'after_sha256':sha(after[n])}
        if n in ('RiscPkg/Control',PREFIX+'!Run'):
            row['unified_diff'] = ''.join(difflib.unified_diff(textdata(before[n]).splitlines(keepends=True),
                textdata(after[n]).splitlines(keepends=True),fromfile=archives[i-1]['version'],tofile=archives[i]['version']))
        rows.append(row)
    deltas.append({'before_version':archives[i-1]['version'],'after_version':archives[i]['version'],
                   'added_members':sorted(set(after)-set(before)),'removed_members':sorted(set(before)-set(after)),
                   'same_common_member_count':sum(before[n]==after[n] for n in common),'changed_members':rows})

summary = {
    'scope':'Static read-only ZIP member stream comparison against previously parsed JFD files; no binary/script execution.',
    'comparison_helper':str(Path(__file__).resolve()),
    'reference_inventory':str(MEDIA/'inventory.json'),
    'reference_original_hashes_reverified':True,
    'archives':archives,'archive_deltas':deltas,
    'candidate':{'latest_supplied_package':'Lotus-Turbo-Challenge-2_0-3.zip','package_version':'0-3',
       'runtime_asset_candidate':'Preferred latest supplied RiscPkg launch/asset reference for ADFFS-based investigation.',
       'technical_eligibility':'Contains native ARM game binaries and original matching assets plus exact original disk 1 JFD; depends on ADFFS.',
       'source_code_eligibility':'No game engine C/C++/assembly source or build system. Compatibility !Run scripts are editable source for launch/patch behavior only.',
       'license_declared':'Non free',
       'engine_change_limit':'No game binary or asset changes between these package versions; removed modules and launch delegation are package changes.',
       'reference_use':'Retain 0-1/0-2 script as additional static decryption/patch evidence and originals as canonical media.',
       'pocket_limit':'Package is not an openFPGA core or RISC-V executable; it does not remove the ARM/RISC OS emulation or reconstruction work.'},
    'private_payload_policy':'No game files were extracted by this helper; script content in JSON is forensic local evidence.',
    'unchanged_archives_after_analysis':all(sha(Path(x['archive_path']).read_bytes())==x['archive_sha256'] for x in archives),
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(OUT),'version_summary':[{'version':x['version'],
       'original_matches':x['exact_original_match_count'],'changed_against_original':[y['archive_member'] for y in x['changed_against_original']],
       'missing_original':[y['relative_name'] for y in x['absent_original_game_members']],
       'embedded_jfd_original_equal':x['embedded_F1023201']['equal_complete_supplied_original_jfd_bytes']}
       for x in archives],'unchanged_archives':summary['unchanged_archives_after_analysis']},indent=2))
