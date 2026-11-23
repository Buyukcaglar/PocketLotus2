"""Summarize byte-verified local media evidence. No originals are changed."""
from pathlib import Path
import collections
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def readjson(path):
    return json.loads(path.read_text(encoding='utf-8'))

def source(path):
    data = path.read_bytes()
    return {'path':str(path),'bytes':len(data),'sha256':sha(data)}

sources = [
    {'id':'jfd_primary_reader','url':'https://github.com/mamedev/mame/blob/master/src/lib/formats/jfd_dsk.cpp',
     'kind':'primary source code','use':'Independent JFD header/sector table layout and CRC field masks.',
     'limit':'Reader implementation is not evidence that every JFD metadata/protection field is emulated.'},
    {'id':'jfd_structure','url':'https://gist.github.com/Kaens/a139d96dc429b49788e47ea57e55017d',
     'kind':'third-party transcription of original !ADFFS.!Structure v2.84',
     'use':'Format field descriptions; corroborated by primary MAME and local checks.',
     'limit':'Official archive download unavailable via direct urllib request (HTTP 403); transcription is not a primary publisher.'},
    {'id':'filecore_prm','url':'https://www.riscos.com/support/developers/prm/filecore.html',
     'kind':'original technical documentation','use':'ADFS E geometry, allocation map, indirect addresses and directories.'},
    {'id':'linux_map','url':'https://github.com/torvalds/linux/blob/master/fs/adfs/map.c',
     'kind':'primary source code','use':'Corroboration of free-link offsets and map layout.'},
    {'id':'linux_directory','url':'https://github.com/torvalds/linux/blob/master/fs/adfs/dir_f.c',
     'kind':'primary source code','use':'Corroboration of directory checksum tail alignment.'},
    {'id':'game_record','url':'https://forums.jaspp.org.uk/forum/viewtopic.php?f=25&t=226',
     'kind':'preservation maintainer primary report','use':'Game ID 10232, Archimedes conversion, 1 MiB RAM compatibility and loader guidance.'},
    {'id':'timing_report','url':'https://forums.jaspp.org.uk/forum/viewtopic.php?start=10&t=226',
     'kind':'preservation maintainer primary report','use':'50 Hz expectation and raster/music sensitivity; observation, not fresh runtime qualification.'},
    {'id':'adf_limit','url':'https://forums.jaspp.org.uk/forum/viewtopic.php?t=502',
     'kind':'preservation maintainer primary report','use':'Maintainer says Lotus uses disc protection and will not work as plain ADF.'},
    {'id':'mode_prm','url':'https://www.riscos.com/support/developers/prm/modes.html',
     'kind':'original technical documentation','use':'MODE 9 is 320x256, 16 colours, 40 KiB standard screen, 50 Hz.'},
    {'id':'filetype_prm','url':'https://riscos.com/support/developers/prm/filetypes.html',
     'kind':'original technical documentation','use':'Numeric file type interpretation.'},
]

inventory = readjson(HERE/'inventory.json')
filelists = [readjson(HERE/('F10232%02d'%x['disc_number'])/'files.json') for x in inventory]
allfiles = [x for rows in filelists for x in rows]
root = HERE/'F1023201'/'extracted'
orig_run = root/'!LOTUS'/'!RUN'
adffs_boot = HERE/'F1023201'/'embedded_adffs_boot.obey'
docs = {name:source(root/rel) for name,rel in {
    'original_application_run':'!LOTUS/!RUN',
    'original_control_readme':'!Read_Me/!Run',
    'original_hard_disc_readme':'!ReadMe_HD/Text',
}.items()}
loader = root/'!LOTUS'/'Loader'
loaderbytes = loader.read_bytes()
musmod = root/'!LOTUS'/'MusMod2'
musbytes = musmod.read_bytes()
words = [int.from_bytes(loaderbytes[x:x+4],'little') for x in range(0,32,4)]
evidence = {
    'scope':'Static read-only local media identification and bounded filesystem extraction; no runtime exercise.',
    'originals_directory':str(HERE.parents[1]/'Lotus'),
    'analysis_directory':str(HERE),
    'platform':{'name':'Acorn Archimedes / RISC OS','cpu':'ARM (classic 26-bit environment)',
                'confidence':'high','evidence':['JFDI signature, title and game ID','ADFS E volumes',
                   'Original readme explicitly identifies Archimedes conversion',
                   'Absolute Loader entry point is ARM instructions','RISC OS module and Obey loader formats']},
    'inventory':inventory,
    'filesystem':{'disc_file_counts':[len(x) for x in filelists],
                  'disc_file_bytes':[sum(x['bytes'] for x in rows) for rows in filelists],
                  'all_extracted_files_use_represented_valid_sector_bytes':all(x['all_bytes_represented_in_jfd'] for x in allfiles),
                  'unique_file_sha256_count':len({x['sha256'] for x in allfiles}),
                  'filetype_counts':dict(collections.Counter(x['riscos_filetype_hex'] for x in allfiles)),
                  'filetype_names':{'0xff8':'Absolute ARM application loaded at &8000','0xffa':'Relocatable module',
                     '0xfeb':'Obey script','0xff9':'Sprite/saved screen','0xffd':'Data','0xfff':'ASCII text',
                     '0xfe4':'DOS file label; FILE## contents are game data, not proven DOS executables',
                     '0x0':'User-defined type; SampleD actual sample encoding is not determined'}},
    'load_paths':{
        'original_riscos_application':{**source(orig_run),'commands':orig_run.read_text(encoding='latin-1').splitlines(),
            'requires':'Classic RISC OS environment and preserved floppy/controller protection behavior.',
            'note':'Original application loader route is distinct from later ADFFS compatibility wrapper.'},
        'embedded_adffs_compatibility_wrapper':{**source(adffs_boot),
            'commands':adffs_boot.read_text(encoding='latin-1').splitlines(),
            'requests':['MODE 9','80 KiB screen allocation','540 KiB WimpSlot',
                        'QTMTracker 1.43','MusicModule2 0.02','GOARM3JIT and IRQ/FIQ code changes on RISC OS 3.5+'],
            'note':'ADFFS is one compatibility route and is not mandatory for a sufficiently faithful hardware/OS emulation route.'}},
    'native_executable':{**source(loader),'entry_first_8_arm_words_hex':[hex(x) for x in words],
        'entry_observations':['E1A0C00D MOV ip,sp','E28FD044 ADD sp,pc,#0x44','E28DDC0C ADD sp,sp,#0xC00',
                              'E92D03FF STMFD sp!,{r0-r9}'],
        'protection_credit_ascii_offset':loaderbytes.index(b'X Lock Protection System'),
        'protection_credit':'X Lock Protection System, Daniel Simms, June 1992',
        'limit':'Main game and packed/encrypted code are not yet reconstructed or source-ported.'},
    'video':{'boot_mode':9,'prm_standard_pixels':[320,256],'prm_colours':16,'prm_standard_screen_bytes':40960,
             'boot_requested_screen_kib':80,'prm_standard_refresh_hz':50,
             'observations':['Original readme says ARM3 cache off reduces colour split flicker.',
                             'Maintainer reports raster palette swaps and music sensitive to timing.'],
             'inference':'80 KiB could accommodate two MODE 9 screens; actual double-buffer use is not yet traced.',
             'limit':'Native game render timings and sound/video acceptance not measured.'},
    'audio':{'module':source(musmod),'module_title':'MusicModule2','module_help_version':'MusicModule 1.02 (7 Apr 1990)',
             'module_help_string_offset':musbytes.index(b'*MusSamplerate N Sets'),
             'module_help_string':'*MusSamplerate N Sets the independent sound DMA 0=40Kc/s 1=28Kc/s 2=20K/cs 3=10Kc/s',
             'observations':['Game ships bootup/gameover/jingle files and SampleD data on both disks.',
                             'ADFFS compatibility wrapper requests QTMTracker and MusicModule2 modules.'],
             'limit':'Exact sample encoding, selected sample rate and interrupt behavior need tracing.'},
    'protection':{'disc1_sector':inventory[0]['special_sectors'],
                  'disc2_special_sector_count':len(inventory[1]['special_sectors']),
                  'discop3_block_counts':[x['discop3_blocks'] for x in inventory],
                  'duplicate_logical_sector_counts':[len(x['duplicate_logical_sectors']) for x in inventory],
                  'raw_adf_limit':'ADF preserves represented payload bytes but loses CRC error semantics, missing-sector semantics, JFD metadata and embedded compatibility script.',
                  'original_hard_disc_requirements_source':docs['original_hard_disc_readme'],
                  'runtime_blocker':'Do not assume plain ADF or extracted files will boot; preserve/emulate disk 1 protection or investigate an explicitly bounded adaptation.'},
    'publication':{'local_only':['Original JFDs','Zero-padded analysis ADFs','Extracted game files','Isolated protection payload'],
                   'safe_project_evidence':['Parser scripts','JSON file inventories and hashes','Factual analysis with source citations']},
    'external_sources':sources,
    'source_dates':'Browsed 2026-10-08; original reports retain their historical dates.',
    'outstanding':['ARM/OS/controller integration choice','Main executable unpacking/tracing',
                   'Exact keyboard/audio/video/timing behavior','Pocket resource fit and toolchain validation',
                   'Hardware runtime validation']
}
(HERE/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(HERE/'evidence.json'),'file_counts':evidence['filesystem']['disc_file_counts'],
                  'unique_hashes':evidence['filesystem']['unique_file_sha256_count'],
                  'byte_coverage_verified':evidence['filesystem']['all_extracted_files_use_represented_valid_sector_bytes']},indent=2))
