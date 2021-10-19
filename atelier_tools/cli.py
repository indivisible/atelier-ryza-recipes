#!/usr/bin/env python3

from .ryza_parser import Database
from .ryza_chain_finder import ChainFinder


def main():
    import argparse

    main_parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    main_parser.add_argument('--game',
                             type=str,
                             default='ryza2',
                             help='game to use (ryza1 or ryza2)')
    main_parser.add_argument('--lang',
                             type=str,
                             default='en',
                             help='2 letter language code')
    main_parser.add_argument('-v', '--verbose', action='store_true')
    subparsers = main_parser.add_subparsers(dest='command')

    item_info_parser = subparsers.add_parser('items', help='item info')
    item_info_parser.add_argument('item_names', nargs='*', type=str.lower)

    item_chain_parser = subparsers.add_parser('chain', help='find craft chain')
    item_chain_parser.add_argument('--limit',
                                   type=int,
                                   default=10,
                                   help='number of chains to display')
    item_chain_parser.add_argument('source',
                                   type=str.lower,
                                   help='category or item to start chain from')
    item_chain_parser.add_argument('target',
                                   type=str.lower,
                                   help='category or item to chain to')

    recipe_find_parser = subparsers.add_parser('category',
                                               help='find recipe for category')
    recipe_find_parser.add_argument('category', type=str.lower)

    subparsers.add_parser('dump-effects', help='dump effect names')
    subparsers.add_parser('dump-categories', help='dump category names')

    dump_json = subparsers.add_parser('dump-json', help='dump effect names')
    dump_json.add_argument('dump_file', type=argparse.FileType('w'))

    args = main_parser.parse_args()

    db = Database(args.game, lang=args.lang)

    # TODO: re-add this option?
    # late game powerful items can mess up early game chain searches
    # disabled = [
    #     # 'red stone',
    #     # 'Philosopher\'s Stone',
    #     # 'Crystal Element',
    #     # 'Holy Nut',
    # ]

    if args.command == 'items':
        if not args.item_names:
            for item in db.items.values():
                item.print(args.verbose)
        else:
            seen = set()
            for q in args.item_names:
                for item in db.find_items(q):
                    if item.tag in seen:
                        continue
                    item.print(args.verbose)
                    seen.add(item.tag)
    elif args.command == 'chain':
        # find source
        source_item, source_cat = db.find_item_or_category(args.source)
        if not (source_item or source_cat):
            print(f'{args.source} not found!')
            return 1
        assert not (source_item and source_cat)

        # find target
        target_item, target_cat = db.find_item_or_category(args.target)
        if not (target_item or target_cat):
            print(f'{args.target} not found!')
            return 1
        assert not (target_item and target_cat)

        source = source_item or source_cat
        assert source
        target = target_item or target_cat
        assert target

        print(f'Finding craft chain from {source.name} to {target.name}...')
        finder = ChainFinder(db)
        finder.print_paths(source.tag, target.tag, args.limit)
    elif args.command == 'dump-effects':
        for eff in db.effects.values():
            # FIXME: dump some useful effect data?
            print(f'{eff.tag} -- {eff.name} : {eff.description}')
    elif args.command == 'dump-categories':
        for cat in db.categories.values():
            print(f'{cat.tag} -- {cat.name}')
    elif args.command == 'dump-json':
        db.dump(args.dump_file)
    else:
        raise ValueError(f'unkown command {args.command}')


if __name__ == '__main__':
    main()
