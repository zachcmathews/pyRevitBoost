# pylint: disable=import-error
from Autodesk.Revit.DB import ElementTransformUtils, Line, XYZ
from Autodesk.Revit.DB.Structure import StructuralType

from gather import find_reference_plane


def map_block_to_family_instance(
    family_type, host, block, transform, doc, view, level
):
    transform = transform.Multiply(block.Transform)

    # Place family instance
    location = transform.OfPoint(XYZ.Zero)
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

    # Rotate family instance into alignment with block
    rotated = transform.OfVector(XYZ.BasisX)
    orientation = XYZ.BasisX.AngleTo(rotated)
    z_axis = Line.CreateBound(location, location + XYZ.BasisZ)

    ElementTransformUtils.RotateElement(
        doc,
        family_instance.Id,
        z_axis,
        orientation
    )

    return family_instance


def place_on_reference_plane(family_type, reference_plane, location, doc):
    direction = reference_plane.FreeEnd - reference_plane.BubbleEnd
    orientation = XYZ.BasisX.AngleTo(direction)
    z_axis = Line.CreateBound(location, location + XYZ.BasisZ)

    family_instance = doc.Create.NewFamilyInstance(
        reference_plane.GetReference(),
        location,
        direction,
        family_type
    )
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
