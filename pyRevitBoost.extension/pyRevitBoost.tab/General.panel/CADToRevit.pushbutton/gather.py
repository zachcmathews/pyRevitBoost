
# pylint: disable=import-error
from itertools import chain

from Autodesk.Revit.DB import (GeometryInstance, HostObjectUtils, Options,
                               ShellLayerType, XYZ)

from rpw.db import Collector

from boostutils import get_name, memoize
from parse import parse_block_name


def find_family_type(category, family, family_type):
    family_types = get_family_types()
    try:
        [typeToPlace] = [
            t for t in family_types
            if t.Category.Name == category
            and t.FamilyName == family
            and get_name(t) == family_type
        ]
    except ValueError:
        return None
    else:
        return typeToPlace


def find_nearest_ceiling_face(location, tolerance=1e-9):
    ceiling_face_refs = get_ceiling_faces()

    nearest = {
        'ceiling': None,
        'face_ref': None,
        'face': None,
        'point': None,
        'uv': None,
        'distance': None
    }
    for ceiling, face_refs in ceiling_face_refs:
        for face_ref in face_refs:
            face = ceiling.GetGeometryObjectFromReference(face_ref)

            projection = face.Project(location)
            if projection:
                distance = projection.Distance
                uv = projection.UVPoint
                point = projection.XYZPoint

                if (
                    all(v is None for v in nearest.values())
                    or distance < nearest['distance']
                ):
                    nearest = {
                        'ceiling': ceiling,
                        'face_ref': face_ref,
                        'face': face,
                        'point': point,
                        'uv': uv,
                        'distance': distance
                    }

    if any(v is None for v in nearest.values()):
        return None
    else:
        direction = nearest['point'] - location
        isDirectlyAbove = direction.AngleTo(XYZ.BasisZ) < tolerance
        return nearest if isDirectlyAbove else None


def find_nearest_wall_face(location, tolerance):
    wall_face_refs = get_wall_faces()

    nearest = {
        'wall': None,
        'face_ref': None,
        'face': None,
        'point': None,
        'uv': None,
        'distance': None
    }
    for wall, face_refs in wall_face_refs:
        for face_ref in face_refs:
            face = wall.GetGeometryObjectFromReference(face_ref)

            projection = face.Project(location)
            if projection:
                distance = projection.Distance
                uv = projection.UVPoint
                point = projection.XYZPoint

                if (
                    (
                        all(v is None for v in nearest.values())
                        or distance < nearest['distance']
                    )
                    and distance <= tolerance
                ):
                    nearest = {
                        'wall': wall,
                        'face_ref': face_ref,
                        'face': face,
                        'point': point,
                        'uv': uv,
                        'distance': distance
                    }

    return nearest if not any(v is None for v in nearest.values()) else None


def find_reference_plane(name):
    reference_planes = get_reference_planes()
    try:
        [reference_plane] = \
            [rp for rp in reference_planes if rp.Name == name]
    except ValueError:
        return None
    else:
        return reference_plane


def get_blocks(cad_import):
    options = Options()
    try:
        [import_geometry] = [
            g for g in cad_import.get_Geometry(options)
            if type(g) == GeometryInstance
        ]
    except ValueError:
        return None
    else:
        return [
            g for g in import_geometry.GetSymbolGeometry()
            if type(g) == GeometryInstance
        ]


def get_cad_imports():
    return Collector(of_class='ImportInstance').get_elements(wrapped=False)


@memoize
def get_ceilings():
    return Collector(of_class='Ceiling').get_elements(wrapped=False)

@memoize
def get_ceiling_faces():
    ceilings = get_ceilings()

    face_refs = []
    for ceiling in ceilings:
        bottom_faces = HostObjectUtils.GetBottomFaces(ceiling)

        _face_refs = []
        _face_refs.extend([face_ref for face_ref in bottom_faces])

        face_refs.append(_face_refs)

    return zip(ceilings, face_refs)

@memoize
def get_family_types():
    return Collector(of_class='FamilySymbol').get_elements(wrapped=False)


@memoize
def get_reference_planes():
    return Collector(of_class='ReferencePlane').get_elements(wrapped=False)


@memoize
def get_walls():
    return Collector(of_class='Wall').get_elements(wrapped=False)


@memoize
def get_wall_faces():
    # .NET stuff
    slt_exterior = getattr(ShellLayerType, 'Exterior')
    slt_interior = getattr(ShellLayerType, 'Interior')

    walls = get_walls()
    face_refs = []
    for wall in walls:
        ext_side_faces = HostObjectUtils.GetSideFaces(wall, slt_exterior)
        int_side_faces = HostObjectUtils.GetSideFaces(wall, slt_interior)

        _face_refs = []
        _face_refs.extend([face_ref for face_ref in ext_side_faces])
        _face_refs.extend([face_ref for face_ref in int_side_faces])

        face_refs.append(_face_refs)

    return zip(walls, face_refs)


def group_blocks_by_name(blocks):
    blocks_grouped_by_name = {}
    for block in blocks:
        block_name = parse_block_name(get_name(block.Symbol))
        if block_name not in blocks_grouped_by_name:
            blocks_grouped_by_name[block_name] = [block]
        else:
            blocks_grouped_by_name[block_name].append(block)

    return blocks_grouped_by_name if blocks_grouped_by_name else None
