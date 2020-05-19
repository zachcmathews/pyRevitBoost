# pylint: disable=import-error
import re
from boostutils import get_name


regex = {
    'block': re.compile(r'^.+\.(?<name>.+)_[0-9]+$'),
    'host': re.compile(r'^(?<type>Reference Plane)\s+\((?<id>.+)\)$')
}


def parse_config(block_name, config):
    try:
        [mapping] = [
            mapping for mapping in config
            if mapping['block'] == block_name
        ]
    except ValueError:
        return None
    else:
        return mapping


def parse_block_name(block):
    results = regex['block'].search(block)
    return results.group('name') if results else None


def parse_host(host):
    results = regex['host'].search(host)
    return {
        'host_type': results.group('type'),
        'host_id': results.group('id')
    } if results else None
