# pylint: disable=import-error
import re

from Autodesk.Revit.DB import CADLinkType, Element, FamilySymbol, FilteredElementCollector, \
ImportInstance, GraphicsStyle, ElementType, Reference, Options, GeometryInstance, ReferencePlane, \
XYZ, ElementTransformUtils, Line

import rpw
from pyrevit import forms, script
from boostutils import load_as_python

__doc__ = '''Map imported AutoCAD blocks to their equivalent Revit family type.
Requires configuration file config.yaml'''
__title__ = 'Convert\nDWG Blocks'
__author__ = 'Zachary Mathews'

doc = rpw.revit.doc
uidoc = rpw.revit.uidoc
view = uidoc.ActiveView

# Get configuration file
config = load_as_python(script.get_bundle_file('config.yaml'))

# Get DWG imports
cad_imports = FilteredElementCollector(doc) \
    .OfClass(ImportInstance) \
    .ToElements()

# Select DWG import if more than one
if len(cad_imports) > 1:
    dwg = forms.SelectFromList.show(
        title='Select CAD Import to Map to Revit',
        context=cad_imports,
        name_attr='Name'
    )
else:
    [dwg] = cad_imports

# Gather AutoCAD blocks
options = Options()
options.View = view
[importGeometry] = [
    g for g in dwg.get_Geometry(options)
    if type(g) == GeometryInstance
]
blocks = [
    g for g in importGeometry.GetSymbolGeometry()
    if type(g) == GeometryInstance
]

# Group blocks by name
blocks_grouped_by_name = {}
block_name_regex = re.compile(r'^.+\.(?<block_name>.+)_[0-9]+$')
for block in blocks:
    results = block_name_regex.search(rpw.db.Element(block.Symbol).name)
    if not results:
        continue

    block_name = results.group('block_name')
    if block_name in blocks_grouped_by_name.keys():
        blocks_grouped_by_name[block_name].append(block)
    else:
        blocks_grouped_by_name[block_name] = [block]

# Collect all family types
types = FilteredElementCollector(doc) \
    .OfClass(FamilySymbol) \
    .ToElements()

# Collect all reference planes
reference_planes = FilteredElementCollector(doc) \
    .OfClass(ReferencePlane) \
    .ToElements()

# Regex to discern host
host_regex = \
     re.compile(r'^(?<host_type>Reference Plane)\s+\((?<host_id>.+)\)$')

cnt = 0
total = len(blocks)
with forms.ProgressBar(title='{value} of {max_value}') as pb:
    with rpw.db.Transaction('Map DWG to Revit') as t:
        for block_name, blocks in blocks_grouped_by_name.items():
            # Find mapping for block_name, otherwise skip
            try:
                [mapping] = \
                    [m for m in config if m['block'] == block_name]
            except ValueError:
                continue

            # Find family symbol to place
            try:
                [typeToPlace] = [
                    t for t in types
                    if t.Category.Name == mapping['category']
                    and t.FamilyName == mapping['family']
                    and rpw.db.Element(t).name == mapping['type']
                ]
            except ValueError:
                continue

            # Find host element
            results = host_regex.search(mapping['host'])
            if not results:
                continue

            host_type = results.group('host_type')
            host_id = results.group('host_id')

            if host_type == 'Reference Plane':
                try:
                    [reference_plane] = \
                        [rp for rp in reference_planes if rp.Name == host_id]
                except ValueError:
                    continue

                for block in blocks:

                    block_location = \
                        importGeometry.Transform \
                        .Multiply(block.Transform) \
                        .OfPoint(XYZ(0, 0, 0))
                    rotated = \
                        importGeometry.Transform \
                        .Multiply(block.Transform) \
                        .OfVector(XYZ.BasisX)
                    rotation = \
                        XYZ.BasisX.AngleTo(XYZ(rotated.X, rotated.Y, 0))

                    family_instance = doc.Create.NewFamilyInstance(
                        reference_plane.GetReference(),
                        block_location,
                        XYZ(0, 0, 0),
                        typeToPlace
                    )
                    z_axis = \
                        Line.CreateBound(
                             block_location,
                             block_location + XYZ.BasisZ
                        )
                    ElementTransformUtils.RotateElement(
                        doc,
                        family_instance.Id,
                        z_axis,
                        rotation
                    )

            cnt += 1
            pb.update_progress(cnt, total)
