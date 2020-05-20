# -*- coding: utf-8 -*-
# pylint: disable=import-error
import re
import math

from Autodesk.Revit.DB import UnitFormatUtils, UnitType, XYZ


regex = {
    'block': re.compile(r'^.*\.(?P<name>.+?)(_[0-9]+){0,1}$'),
    'host': re.compile(r'^(?<type>Reference Plane|Level)\s*(\((?<id>.+)\)){0,1}$'),
    'center-offset': re.compile(r'^\((?P<x>[0-9-\'"\/. ]+){0,1}, *(?P<y>[0-9-\'"\/. ]+){0,1}\)$'),
    'orientation-offset': re.compile(r'^(?P<angle>[0-9.-]+) *(?P<unit>deg|rad|°){0,1}$'),
    'parameter': re.compile(r'^(?P<name>.+?)\s*<(?P<type>True/False|Text|Length|Number)>\s*=\s*(?P<value>.*)$')
}


def parse_config(block_name, config, doc):
    try:
        [mapping] = [
            mapping for mapping in config
            if mapping.get('block') == block_name
        ]
    except ValueError:
        return {}

    from gather import find_family_type, get_family_types
    host = parse_host(mapping.get('host'))
    family_type = find_family_type(
        category=mapping.get('category'),
        family=mapping.get('family'),
        family_type=mapping.get('type'),
        family_types=get_family_types()
    )
    center_offset = parse_center_offset(
        offset=mapping.get('center-offset'),
        units=doc.GetUnits()
    )
    orientation_offset = parse_orientation_offset(
        offset=mapping.get('orientation-offset')
    )
    parameters = (
        parse_parameters(mapping.get('parameters'))
        if mapping.get('parameters')
        else []
    )

    # Revit doesn't allow placing inactive families.
    # I don't know exactly what inactive entails,
    # but this works
    if family_type:
        family_type.Activate()

    return {
        'family_type': family_type,
        'host': host,
        'center_offset': center_offset,
        'orientation_offset': orientation_offset,
        'parameters': parameters
    }


def parse_block_name(block):
    results = regex['block'].search(block)
    return results.group('name') if results else None


def parse_host(host):
    results = regex['host'].search(host)
    return {
        'type': results.group('type'),
        'id': results.group('id')
    } if results else None


def parse_center_offset(offset, units):
    if offset:
        results = regex['center-offset'].search(offset)
        if results:
            x, y = results.group('x'), results.group('y')

            (x_succeeded, x_offset) = UnitFormatUtils.TryParse(
                units,
                UnitType.UT_Length,
                x
            )
            (y_succeeded, y_offset) = UnitFormatUtils.TryParse(
                units,
                UnitType.UT_Length,
                y
            )

            return XYZ(
                x_offset if x_succeeded else 0,
                y_offset if y_succeeded else 0,
                0
            )

    return XYZ(0, 0, 0)


def parse_orientation_offset(offset):
    if offset:
        results = regex['orientation-offset'].search(offset)

        if results:
          angle = float(results.group('angle'))
          unit = results.group('unit')

          return (
              angle / 180 * math.pi if unit == 'deg' or unit == '°'
              else 0
          )

    return 0


def parse_parameters(parameters):
    return [parse_parameter(p) for p in parameters]


def parse_parameter(parameter):
    results = regex['parameter'].search(parameter)
    name = results.group('name')
    type = results.group('type')
    value = results.group('value')

    return {
        'name': name,
        'type': type,
        'value': value
    } if all([name, type, value]) else None
