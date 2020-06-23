# -*- coding: utf-8 -*-
# pylint: disable=import-error
import re
import math

from Autodesk.Revit.DB import Transform, UnitFormatUtils, UnitType, XYZ


regex = {
    'block': re.compile(r'^.*\.(?P<name>.+?)(_[0-9]+){0,1}$'),
    'host': re.compile(r'^(?P<type>Ceiling|Reference Plane|Level|Wall|Wall and Level) *(\((?P<param>.+)\)){0,1}$'),
    'origin-offset': re.compile(r'^\((?P<x>[0-9-\'"\/. ]+){0,1}, *(?P<y>[0-9-\'"\/. ]+){0,1}\)$'),
    'orientation-offset': re.compile(r'^(?P<angle>-{0,1}[0-9]*(\.[0-9]+){0,1}) *(?P<unit>deg|rad|°){0,1}$')
}


def parse_config(block_name, config, doc):
    [mapping] = [
        mapping for mapping in config
        if mapping.get('block') == block_name
    ]

    # Ensure required fields
    if not (
        mapping.get('host')
        and mapping.get('category')
        and mapping.get('family')
        and mapping.get('host')
    ):
        raise ValueError

    # GSheets strips spaces (families with only one type)
    if not mapping.get('type'):
        mapping['type'] = ' '

    # Parse config
    from gather import find_family_type
    host = parse_host(mapping.get('host'), doc.GetUnits())
    if mapping.get('backup-host'):
        backup_host = parse_host(mapping.get('backup-host'), doc.GetUnits())
    else:
        backup_host = None
    family_type = find_family_type(
        category=mapping.get('category'),
        family=mapping.get('family'),
        family_type=mapping.get('type')
    )
    origin_offset = parse_origin_offset(
        offset=mapping.get('origin-offset'),
        units=doc.GetUnits()
    )
    orientation_offset = parse_orientation_offset(
        offset=mapping.get('orientation-offset')
    )
    rotate_origin_offset = parse_orientation_offset(
        offset=mapping.get('rotate-origin-offset')
    )
    parameters = mapping.get('parameters')

    map = {
        'family_type': family_type,
        'host': host,
        'backup_host': backup_host,
        'origin_offset': origin_offset,
        'rotate_origin_offset': rotate_origin_offset,
        'orientation_offset': orientation_offset,
        'parameters': parameters
    }

    # Apply rotate_origin_offset
    rotation = Transform.CreateRotation(
        XYZ.BasisZ,
        rotate_origin_offset
    )
    map['origin_offset'] = rotation.OfVector(origin_offset)

    family_type.Activate()  # Revit doesn't allow placing inactive families
    return map


def parse_block_name(block):
    results = regex['block'].search(block)
    if not results:
        raise ValueError

    return results.group('name')


def parse_host(host, units):
    results = regex['host'].search(host)
    type_ = results.group('type')
    param = results.group('param')

    if not results:
        raise ValueError

    if type_ == 'Wall' or type_ == 'Wall and Level':
        (succeeded, tolerance) = UnitFormatUtils.TryParse(
            units,
            UnitType.UT_Length,
            param
        )

        if not succeeded:
            raise ValueError

        return {
            'type': type_,
            'tolerance': tolerance
        }

    else:
        return {
            'type': type_,
            'id': param
        }


def parse_origin_offset(offset, units):
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
                raise ValueError

        # We couldn't parse config 'origin-offset'
        else:
            raise ValueError

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
            raise ValueError

    # No offset specified
    else:
        return 0.0
