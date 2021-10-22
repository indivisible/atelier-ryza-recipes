#!/usr/bin/env python3

from pathlib import Path
import subprocess
import re
import json


class TagFinder:
    strings: list[str]
    tags: dict[str, list[str]]

    def __init__(self, exe_path: Path):
        cmd = ['strings', str(exe_path)]
        res = subprocess.run(cmd,
                             capture_output=True,
                             encoding='ascii',
                             errors='replace',
                             check=True)
        self.strings = res.stdout.splitlines(False)
        ryza2_title = 'Atelier Ryza 2: Lost Legends & the Secret Fairy'
        self.game = 'ryza2' if ryza2_title in self.strings else 'ryza1'
        self.tags = {}
        self.find_all_tags(True)

    def save_tags(self, path: Path):
        with path.open('wt') as fp:
            json.dump(self.tags, fp)

    def find_all_tags(self, verbose: bool = False) -> None:
        item_types = [
            'MAT', 'MIX', 'EV_MIX', 'MIX', 'WEAPON', 'ARMOR', 'ACCESSORY',
            'EV_ACCESSORY', 'KEY', 'RUINS', 'QUEST', 'ESSENCE', 'BOOK',
        ]

        def find(pattern):
            pattern_str = f'^ITEM_({pattern})_[A-Z_0-9-]+'
            if verbose:
                print('pattern:', pattern_str)
            regex = re.compile(pattern_str)
            return self.find_tags(regex, verbose=verbose)

        self.tags['items'] = find('|'.join(item_types))
        if self.game == 'ryza1':
            # ryza1 has FURNITURE before BOOK, but strings for it
            # are after QUEST
            self.tags['items'] += find('FURNITURE')
            self.tags['items'] += find('BOOK')
            self.tags['items'] += find('DLC')
            self.tags['items_dlc_1'] = []
            self.tags['items_dlc_2'] = []
            # FIXME: I have no idea where furniture names are in ryza1
            self.tags['items_furniture'] = []
        else:
            dlc = find('DLC')
            self.tags['items_dlc_1'] = dlc[:40]
            self.tags['items_dlc_2'] = dlc[40:]
            self.tags['items_furniture'] = find('FURNITURE')
        self.tags['categories'] = find('CATEGORY')
        self.tags['effects'] = find('EFF')
        self.tags['ev_effects'] = find('EV_EFF')
        self.tags['potentials'] = find('POTENTIAL')

    def find_tags(self,
                  regex: re.Pattern,
                  min_num: int = 10,
                  verbose: bool = False) -> list[str]:
        res = None
        for s in self.strings:
            if regex.match(s):
                if res is None:
                    res = []
                res.append(s)
            elif res is not None:
                if len(res) < min_num:
                    res = None
                else:
                    if verbose:
                        print(f'next was: {s}')
                    return res
        if res is not None:
            return res
        return []


def print_list(lst: list[str], context: int, prefix: str = '') -> None:
    if (context * 2 + 1) >= len(lst):
        for i in lst:
            print(prefix + i)
    else:
        start = lst[:context]
        end = lst[-context:]
        middle = f'<snip {len(lst) - context*2} items>'
        for i in start + [middle] + end:
            print(prefix + i)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--context', default=3, type=int)
    parser.add_argument('exe', type=Path)
    parser.add_argument('patterns', nargs='*')

    args = parser.parse_args()

    finder = TagFinder(args.exe)
    print(f'game is {finder.game}')
    finder.save_tags(args.exe.with_suffix('.tags.json'))

    for key, tags in finder.tags.items():
        print(f'{key}: {len(tags)}')
    print()

    for pattern in args.patterns:
        print(f'{pattern}:')
        regex = re.compile(pattern)
        results = list(finder.find_tags(regex, verbose=True))
        print_list(results, args.context, '  ')
        print()


if __name__ == '__main__':
    main()
