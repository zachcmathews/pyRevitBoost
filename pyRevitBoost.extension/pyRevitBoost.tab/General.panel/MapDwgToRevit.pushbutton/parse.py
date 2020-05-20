# pylint: disable=import-error
import re

regex = {
    'block': re.compile(r'^.*\.(?P<name>.*?)(_[0-9]+){0,1}$'),
    'host': re.compile(r'^(?<type>Reference Plane|Level)\s+\((?<id>.+)\)$')
}


def parse_config(block_name, config):
    try:
        [mapping] = [
            mapping for mapping in config
            if mapping.get('block') == block_name
        ]
    except ValueError:
        return (None, None)

    from gather import find_family_type, get_family_types
    host = parse_host(mapping.get('host'))
    family_type = find_family_type(
        category=mapping.get('category'),
        family=mapping.get('family'),
        family_type=mapping.get('type'),
        family_types=get_family_types()
    )

    # Revit doesn't allow placing inactive families.
    # I don't know exactly what inactive entails,
    # but this works
    if family_type:
        family_type.Activate()

    return (family_type, host)


def parse_block_name(block):
    results = regex['block'].search(block)
    return results.group('name') if results else None


def parse_host(host):
    results = regex['host'].search(host)
    return {
        'type': results.group('type'),
        'id': results.group('id')
    } if results else None
