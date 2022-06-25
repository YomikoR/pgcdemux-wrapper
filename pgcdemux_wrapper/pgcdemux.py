from __future__ import annotations
from typing import List, Tuple
import os
import shutil
import configparser
import subprocess


__all__ = [
    'PGCItem',
    'pgc_demux_call',
    'pgc_demux',
]


_pgc_demux_bin = os.path.join(os.path.dirname(__file__), 'PgcDemux.exe')


class PGCItem:
    def __init__(self, dir: str):
        self.dir = dir
        log = os.path.join(dir, 'LogFile.txt')
        config = configparser.ConfigParser()
        config.read(log)
        if 'General' not in config.keys():
            raise KeyError(f'The log file [{log}] cannot be parsed.')
        self.is_empty = False
        if int(config['General']['Total Number of Frames']) == 0:
            self.is_empty = True
        if int(config['Demux']['Number of Video Packs']) < 1:
            self.is_empty = True

        # General
        self.num_pgc_in_titles = int(config['General']['Total Number of PGCs   in Titles'])
        self.num_pgc_in_menus = int(config['General']['Total Number of PGCs   in  Menus'])
        # domain is 'Menus' or 'Titles'
        self.domain = config['General']['Demuxing Domain']
        # PGC index in domain, starting from 1
        self.pgc_index = int(config['General']['Selected PGC'])

        # Audio, tuple (index, delay)
        self.audio: List[Tuple[str, int]] = []
        for n in range(1, 9):
            audio_track = config['Audio Streams'][f'Audio_{n}']
            if audio_track != 'None':
                # e.g. 0xA0 -> AudioFile_A0.wav
                audio_delay = int(config['Audio Delays'][f'Audio_{n}'])
                self.audio.append((audio_track, audio_delay))

        # Subs, not guaranteed to be valid, e.g. accepted by mkvmerge
        self.subs: List[str] = []
        for n in range(1, 33):
            sub_track = config['Subs Streams'][f'Subs_{n:02}']
            if sub_track != 'None':
                # e.g. 0x21 -> Subpictures_21.sup
                self.subs.append(sub_track)


def pgc_demux_call(ifo: str, pgc_index: int, domain: str, dest_dir: str, pgc_demux_bin=_pgc_demux_bin):
    os.makedirs(dest_dir, exist_ok=True)
    subprocess.Popen([pgc_demux_bin,
        '-pgc', f'{pgc_index}',
        '-m2v',
        '-aud',
        '-sub',
        '-endt',
        '-log',
        f'-{domain}',
        ifo,
        dest_dir]).communicate()
    print(f'Demux output in {dest_dir}')


def pgc_demux(ifo_dir: str, dest_dir: str, pgc_demux_bin=_pgc_demux_bin, set_return=False):
    ''' Demux all PGC by brute force
    '''
    if not os.path.exists(os.path.join(ifo_dir, 'VIDEO_TS.IFO')):
        raise FileNotFoundError('Please set ifo_dir as the VIDEO_TS folder')
    os.makedirs(dest_dir, exist_ok=True)

    pgc_items: List[PGCItem] = []

    # VIDEO_TS.IFO, it seems there's only menu
    print('Reading VIDEO_TS.IFO...')
    demux_dir = os.path.join(dest_dir, f'VIDEO_TS_MENU_{1}')
    pgc_demux_call(
        ifo = os.path.join(ifo_dir, 'VIDEO_TS.IFO'),
        pgc_index = 1,
        domain = 'menu',
        dest_dir = demux_dir
    )
    item_vts_menu_1 = PGCItem(demux_dir)
    num_menus = item_vts_menu_1.num_pgc_in_menus
    if item_vts_menu_1.is_empty:
        shutil.rmtree(demux_dir)
    else:
        pgc_items.append(item_vts_menu_1)
    for n in range(2, num_menus + 1):
        demux_dir = os.path.join(dest_dir, f'VIDEO_TS_MENU_{n}')
        pgc_demux_call(
            ifo = os.path.join(ifo_dir, 'VIDEO_TS.IFO'),
            pgc_index = n,
            domain = 'menu',
            dest_dir = demux_dir
        )
        item = PGCItem(demux_dir)
        if item.is_empty:
            shutil.rmtree(demux_dir)
        else:
            pgc_items.append(item)

    # VTS_01_0.IFO, etc.
    files = os.listdir(ifo_dir)
    for file in files:
        if os.path.isfile(os.path.join(ifo_dir, file)) and file.startswith('VTS') and file.endswith('.IFO'):
            ifo_file = file
            print(f'Reading {ifo_file}...')
            # TITLE + MENU
            demux_dir = os.path.join(dest_dir, f'{ifo_file[:-4]}_TITLE_{1}')
            pgc_demux_call(
                ifo = os.path.join(ifo_dir, ifo_file),
                pgc_index = 1,
                domain = 'title',
                dest_dir = demux_dir
            )
            item_title_1 = PGCItem(demux_dir)
            num_titles = item_title_1.num_pgc_in_titles
            num_menus = item_title_1.num_pgc_in_menus
            if item_title_1.is_empty:
                shutil.rmtree(demux_dir)
            else:
                pgc_items.append(item_title_1)
            for n in range(2, num_titles + 1):
                demux_dir = os.path.join(dest_dir, f'{ifo_file[:-4]}_TITLE_{n}')
                pgc_demux_call(
                    ifo = os.path.join(ifo_dir, ifo_file),
                    pgc_index = n,
                    domain = 'title',
                    dest_dir = demux_dir
                )
                if item.is_empty:
                    shutil.rmtree(demux_dir)
                else:
                    pgc_items.append(item)
            for n in range(1, num_menus + 1):
                demux_dir = os.path.join(dest_dir, f'{ifo_file[:-4]}_MENU_{n}')
                pgc_demux_call(
                    ifo = os.path.join(ifo_dir, ifo_file),
                    pgc_index = n,
                    domain = 'menu',
                    dest_dir = demux_dir
                )
                if item.is_empty:
                    shutil.rmtree(demux_dir)
                else:
                    pgc_items.append(item)

    if set_return:
        return pgc_items

