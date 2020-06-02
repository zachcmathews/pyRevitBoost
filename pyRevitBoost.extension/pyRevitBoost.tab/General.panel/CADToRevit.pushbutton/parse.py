# -*- coding: utf-8 -*-
# pylint: disable=import-error
import re
import math

from Autodesk.Revit.DB import Transform, UnitFormatUtils, UnitType, XYZ


regex = {
    'block': re.compile(r'^.*\.(?P<name>.+?)(_[0-9]+){0,1}$'),
    'host': re.compile(r'^(?P<type>Ceiling|Reference Plane|Level|Wall|Wall and Level) *(\((?P<param>.+)\)){0,1}$'),
    'origin-offset': re.compile(r'^\((?P<x>[0-9-\'"\/. ]+){0,1}, *(?P<y>[0-9-\'"\/. ]+){0,1}\)$'),
    'orientation-offset': re.compile(r'^(?P<angle>-{0,1}[0-9]*(\.[0-9]+){0,1}) *(?P<unit>deg|rad|°){0,1}$'),
    'parameter': re.compile(r'^(?P<name>.+?)\s*<(?P<type>True/False|Text|Length|Number)>\s*=\s*(?P<value>.*)$')
}


def parse_config(block_name, config, doc):
    try:
        [mapping] = [
            mapping for mapping in config
            if mapping.get('block') == block_name
        ]
    except ValueError:
        return None

    # Parse config
    from gather import find_family_type
    host = parse_host(mapping.get('host'), doc.GetUnits())
    family_type = find_family_type(
        category=mapping.get('category'),
        family=mapping.get('family'),
        family_type=mapping.get('type')
    )
    origin_offset = parse_center_offset(
        offset=mapping.get('origin-offset'),
        units=doc.GetUnits()
    )
    orientation_offset = parse_orientation_offset(
        offset=mapping.get('orientation-offset')
    )
    rotate_center_offset = parse_orientation_offset(
        offset=mapping.get('rotate-origin-offset')
    )
    parameters = parse_parameters(
        parameters=mapping.get('parameters')
    )

    map = {
        'family_type': family_type,
        'host': host,
        'origin_offset': origin_offset,
        'rotate_center_offset': rotate_center_offset,
        'orientation_offset': orientation_offset,
        'parameters': parameters
    }

    # If errors in parsing config return sentinel None
    if any(m is None for m in map.values()):
        return None

    # Apply rotate_center_offset
    rotation = Transform.CreateRotation(
        XYZ.BasisZ,
        rotate_center_offset
    )
    map['origin_offset'] = rotation.OfVector(origin_offset)

    family_type.Activate()  # Revit doesn't allow placing inactive families
    return map


def parse_block_name(block):
    results = regex['block'].search(block)
    return results.group('name') if results else None


def parse_host(host, units):
    results = regex['host'].search(host)
    type_ = results.group('type')
    param = results.group('param')

    if type_ == 'Wall' or type_ == 'Wall and Level':
        (succeeded, tolerance) = UnitFormatUtils.TryParse(
            units,
            UnitType.UT_Length,
            param
        )

        return {
            'type': type_,
            'tolerance': tolerance
        } if succeeded else None

    else:
        return {
            'type': type_,
            'id': param
        } if results else None


def parse_center_offset(offset, units):
    if offset:
        results = regex['origin-offset'].search(offset)
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

            # Succesfully parsed into internal units
            if x_succeeded and y_succeeded:
                return XYZ(x_offset, y_offset, 0)

            # Revit couldn't parse into internal units
            else:
                return None

        # We couldn't parse config 'origin-offset'
        else:
            return None

    # No offset specified
    else:
        return XYZ(0, 0, 0)


def parse_orientation_offset(offset):
    if offset:
        results = regex['orientation-offset'].search(offset)

        if results:
            angle = float(results.group('angle'))
            unit = results.group('unit')

            return (
              angle / 180 * math.pi if unit == 'deg' or unit == '°'
              else angle
            )

        # We couldn't parse config 'orientation-offset'
        else:
            return None

    # No offset specified
    else:
        return 0.0


def parse_parameters(parameters):
    if parameters:
        parsed = [parse_parameter(p) for p in parameters]
        return (
            None if any(p is None for p in parsed)
            else parsed
        )
    else:
        return []


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
