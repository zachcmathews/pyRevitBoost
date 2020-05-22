# pylint: disable=import-error
from Autodesk.Revit.DB import ElementTransformUtils, Line, Transform, XYZ
from Autodesk.Revit.DB.Structure import StructuralType

from boostutils import get_parameter
from gather import find_nearest_wall_face, find_reference_plane


def map_block_to_family_instance(
    family_type, host, center_offset, orientation_offset,
    parameters, block, transform, doc, view, level
):
    transform = transform.Multiply(block.Transform)

    block_direction = transform.OfVector(XYZ.BasisX)
    block_orientation = XYZ.BasisX.AngleTo(block_direction)
    block_rotation = Transform.CreateRotation(
        XYZ.BasisZ,
        block_orientation
    )

    block_location = transform.OfPoint(XYZ.Zero)
    center_offset = block_rotation.OfVector(center_offset)
    location = block_location + center_offset

    # Place family instance
    if host['type'] == 'Reference Plane':
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
            tolerance=host['tolerance'],
            doc=doc
        )
        family_instance = place_on_wall(
            family_type,
            wall,
            doc
        )

    # Rotate family instance into alignment with block
    z_axis = Line.CreateBound(location, location + XYZ.BasisZ)
    ElementTransformUtils.RotateElement(
        doc,
        family_instance.Id,
        z_axis,
        block_orientation + orientation_offset
    )

    # Set family instance parameters
    set_parameters(
        el=family_instance,
        parameters=parameters,
        units=doc.GetUnits()
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


def place_on_level(family_type, level, location, doc):
    family_instance = doc.Create.NewFamilyInstance(
        location,
        family_type,
        level,
        StructuralType.NonStructural
    )

    return family_instance


def place_on_wall(family_type, wall, doc):
    family_instance = doc.Create.NewFamilyInstance(
        wall['face'].Reference,
        wall['point'],
        wall['normal'],
        family_type
    )

    return family_instance


def set_parameters(el, parameters, units):
    for p in parameters:
        set_parameter(el, p, units)


def set_parameter(el, parameter, units):
    ref = get_parameter(
        el=el,
        name=parameter['name'],
    )

    if parameter['type'] == 'True/False':
        ref.Set(False) if parameter['value'] == 'False' else ref.Set(True)

    elif parameter['type'] == 'Text':
        ref.Set(parameter['value'])

    elif parameter['type'] == 'Length':
        ref.SetValueString(parameter['value'])

    elif parameter['type'] == 'Number':
        ref.Set(float(parameter['value']))
