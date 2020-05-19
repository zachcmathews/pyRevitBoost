
# pylint: disable=import-error
from Autodesk.Revit.DB import (GeometryInstance, Options)

from rpw.db import Collector

from boostutils import get_name
from parse import parse_block_name


def find_family_type(category, family, family_type, family_types):
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


def get_family_types():
    return Collector(of_class='FamilySymbol').get_elements(wrapped=False)


def get_reference_planes():
    return Collector(of_class='ReferencePlane').get_elements(wrapped=False)


def group_blocks_by_name(blocks):
    blocks_grouped_by_name = {}
    for block in blocks:
        block_name = parse_block_name(get_name(block.Symbol))
        if block_name not in blocks_grouped_by_name:
            blocks_grouped_by_name[block_name] = [block]
        else:
            blocks_grouped_by_name[block_name].append(block)

    return blocks_grouped_by_name or None
