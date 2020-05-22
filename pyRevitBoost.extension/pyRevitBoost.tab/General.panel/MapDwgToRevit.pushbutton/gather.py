
# pylint: disable=import-error
from itertools import chain

from Autodesk.Revit.DB import (GeometryInstance, HostObjectUtils, Options,
                               ShellLayerType)

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


def find_reference_plane(name):
    reference_planes = get_reference_planes()
    try:
        [reference_plane] = \
            [rp for rp in reference_planes if rp.Name == name]
    except ValueError:
        return None
    else:
        return reference_plane


def find_nearest_wall_face(location, tolerance, doc):
    faces = get_wall_faces(doc)

    nearest = {'face': None, 'point': None, 'uv': None, 'distance': None}
    for face in faces:
        projection = face.Project(location)
        distance = projection
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
                'face': face,
                'point': point,
                'uv': uv,
                'distance': distance
            }

    return nearest.update(
        ('normal', nearest['face'].ComputeNormal(nearest['uv']))
    ) if any(v is None for v in nearest.values()) else None


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
def get_family_types():
    return Collector(of_class='FamilySymbol').get_elements(wrapped=False)


@memoize
def get_reference_planes():
    return Collector(of_class='ReferencePlane').get_elements(wrapped=False)


@memoize
def get_walls():
    return Collector(of_class='Wall').get_elements(wrapped=False)


@memoize
def get_wall_faces(doc):
    walls = get_walls()
    faces = chain(
        HostObjectUtils.GetSideFaces(
            wall,
            ShellLayerType.External
        ) for wall in walls
    )
    return [doc.GetElement(f) for f in faces]


def group_blocks_by_name(blocks):
    blocks_grouped_by_name = {}
    for block in blocks:
        block_name = parse_block_name(get_name(block.Symbol))
        if block_name not in blocks_grouped_by_name:
            blocks_grouped_by_name[block_name] = [block]
        else:
            blocks_grouped_by_name[block_name].append(block)

    return blocks_grouped_by_name if blocks_grouped_by_name else None
