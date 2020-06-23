# pylint: disable=import-error
from Autodesk.Revit.DB import (ElementTransformUtils, Line, Reference,
                               StorageType, Transform, XYZ)
from Autodesk.Revit.DB.Structure import StructuralType
from Autodesk.Revit.Exceptions import ArgumentException

from boostutils import get_parameter
from gather import (find_nearest_ceiling_face, find_nearest_wall_face,
                    find_reference_plane)


def map_block_to_family_instance(
    family_type, host, backup_host,
    origin_offset, orientation_offset,
    parameters, block, transform,
    doc, view, level
):
    block_transform = transform.Multiply(block.Transform)

    block_direction = block_transform.OfVector(XYZ.BasisX)
    block_orientation = XYZ.BasisX.AngleTo(block_direction)
    block_rotation = Transform.CreateRotation(
        XYZ.BasisZ,
        block_orientation
    )

    block_location = block_transform.OfPoint(XYZ.Zero)
    rotated_origin_offset = block_rotation.OfVector(origin_offset)
    location = block_location - rotated_origin_offset

    # Place family instance
    if host['type'] == 'Ceiling':
        ceiling = find_nearest_ceiling_face(location=location)
        if ceiling:
            family_instance = place_on_ceiling(
                family_type,
                ceiling,
                level,
                doc
            )
        elif backup_host:
            map_block_to_family_instance(
                family_type, backup_host, None,
                origin_offset, orientation_offset,
                parameters, block, transform,
                doc, view, level
            )
            return
        else:
            raise TypeError
    elif host['type'] == 'Reference Plane':
        reference_plane = find_reference_plane(name=host['id'])
        family_instance = place_on_reference_plane(
            family_type,
            reference_plane,
            location,
            doc
        )
    elif host['type'] == 'Level':
        family_instance = place_on_level(
            family_type,
            level,
            location,
            doc
        )
    elif host['type'] == 'Wall':
        wall = find_nearest_wall_face(
            location=location,
            tolerance=host['tolerance']
        )
        if wall:
            family_instance = place_on_wall(
                family_type,
                wall,
                level,
                doc
            )
        elif backup_host:
            map_block_to_family_instance(
                family_type, backup_host, None,
                origin_offset, orientation_offset,
                parameters, block, transform,
                doc, view, level
            )
            return
        else:
            raise TypeError
    elif host['type'] == 'Wall and Level':
        wall = find_nearest_wall_face(
            location=location,
            tolerance=host['tolerance']
        )
        if wall:
            family_instance = place_on_wall_and_level(
                family_type,
                wall,
                level,
                doc
            )
        elif backup_host:
            map_block_to_family_instance(
                family_type, backup_host, None,
                origin_offset, orientation_offset,
                parameters, block, transform,
                doc, view, level
            )
            return
        else:
            raise TypeError

    # Rotate family instance into alignment with block
    if (
        host['type'] == 'Ceiling'
        or host['type'] == 'Reference Plane'
        or host['type'] == 'Level'
    ):
        z_axis = Line.CreateBound(location, location + XYZ.BasisZ)
        ElementTransformUtils.RotateElement(
            doc,
            family_instance.Id,
            z_axis,
            block_orientation + orientation_offset
        )

    # Set schedule level to allow changing elevation
    schedule_level = get_parameter(
        el=family_instance,
        builtin='INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM'
    )
    schedule_level.Set(level.Id)

    # Set family instance parameters
    set_parameters(
        el=family_instance,
        parameters=parameters
    )

    return family_instance


def place_on_ceiling(family_type, ceiling, level, doc):
    direction = XYZ.BasisX.CrossProduct(ceiling['face'].FaceNormal)
    family_instance = doc.Create.NewFamilyInstance(
        ceiling['face_ref'],
        ceiling['point'],
        direction,
        family_type
    )

    # Negate direction of ceiling
    orientation = XYZ.BasisX.AngleTo(direction)
    z_axis = Line.CreateBound(ceiling['point'], ceiling['point'] + XYZ.BasisZ)
    ElementTransformUtils.RotateElement(
        doc,
        family_instance.Id,
        z_axis,
        -orientation
    )

    return family_instance


def place_on_level(family_type, level, location, doc):
    family_instance = doc.Create.NewFamilyInstance(
        location,
        family_type,
        level,
        StructuralType.NonStructural
    )

    return family_instance


def place_on_reference_plane(family_type, reference_plane, location, doc):
    plane = reference_plane.GetPlane()
    direction = reference_plane.FreeEnd - reference_plane.BubbleEnd
    offset = plane.Origin.DotProduct(plane.Normal) * plane.Normal
    family_instance = doc.Create.NewFamilyInstance(
        reference_plane.GetReference(),
        location + offset,
        direction,
        family_type
    )

    # Negate direction of reference plane
    orientation = XYZ.BasisX.AngleTo(direction)
    z_axis = Line.CreateBound(location, location + XYZ.BasisZ)
    ElementTransformUtils.RotateElement(
        doc,
        family_instance.Id,
        z_axis,
        -orientation
    )

    return family_instance


def place_on_wall(family_type, wall, level, doc):
    direction = XYZ.BasisZ.CrossProduct(wall['face'].FaceNormal)
    family_instance = doc.Create.NewFamilyInstance(
        wall['face_ref'],
        wall['point'],
        direction,
        family_type
    )

    return family_instance


def place_on_wall_and_level(family_type, wall, level, doc):
    direction = XYZ.BasisZ.CrossProduct(wall['face'].FaceNormal)
    family_instance = doc.Create.NewFamilyInstance(
        wall['point'],
        family_type,
        direction,
        wall['wall'],
        StructuralType.NonStructural
    )

    return family_instance


def set_parameters(el, parameters):
    for name, v in parameters.items():
        p = get_parameter(
            el=el,
            name=name,
        )

        if p.StorageType == StorageType.Integer:
            if v == 'Yes' or v == 'yes' or v == 'True' or v == 'true':
                v = 1
            elif v == 'No' or v == 'no' or v == 'False' or v == 'false':
                v = 0
            else:
                v = int(v)
            p.Set(v)
        elif p.StorageType == StorageType.Double:
            try:
                v = float(v)
            except:
                p.SetValueString(v)
            else:
                p.Set(v)
        elif p.StorageType == StorageType.String:
            p.Set(v)
        else:
            raise TypeError
