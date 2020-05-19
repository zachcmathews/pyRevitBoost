# pylint: disable=import-error
from Autodesk.Revit.DB import (XYZ, ElementTransformUtils, Line)

import rpw
from pyrevit import forms, script
from boostutils import load_as_python

from gather import (find_family_type, get_blocks, get_cad_imports,
                    get_family_types, get_reference_planes,
                    group_blocks_by_name)
from parse import parse_config, parse_host

__doc__ = '''Map imported AutoCAD blocks to their equivalent Revit family type.
Requires configuration file config.yaml'''
__title__ = 'Convert\nDWG Blocks'
__author__ = 'Zachary Mathews'

doc = rpw.revit.doc
uidoc = rpw.revit.uidoc
view = uidoc.ActiveView

config = load_as_python(script.get_bundle_file('config.yaml'))

family_types = get_family_types()
reference_planes = get_reference_planes()
cad_imports = get_cad_imports()

# Select DWG import if more than one
if len(cad_imports) > 1:
    cad_import = forms.SelectFromList.show(
        title='Select CAD Import to Map to Revit',
        context=cad_imports,
        name_attr='Name'
    )
else:
    [cad_import] = cad_imports

blocks = get_blocks(cad_import)
blocks_grouped_by_name = group_blocks_by_name(blocks)

cnt = 0
total = len(blocks)
with forms.ProgressBar(title='{value} of {max_value}') as pb:
    with rpw.db.Transaction('Map DWG to Revit') as t:
        for block_name, blocks in blocks_grouped_by_name.items():
            mapping = parse_config(block_name, config)
            family_type = find_family_type(
                category=mapping['category'],
                family=mapping['family'],
                family_type=mapping['type'],
                family_types=family_types
            )
            host = parse_host(mapping)

            if host['type'] == 'Reference Plane':
                try:
                    [reference_plane] = \
                        [rp for rp in reference_planes if rp.Name == host_id]
                except ValueError:
                    continue

                reference_plane_direction = \
                    reference_plane.FreeEnd - reference_plane.BubbleEnd
                reference_plane_orientation = \
                    XYZ.BasisX.AngleTo(reference_plane_direction)

                for block in blocks:
                    block_location = \
                        import_geometry.Transform \
                        .Multiply(block.Transform) \
                        .OfPoint(XYZ.Zero)
                    rotated = \
                        import_geometry.Transform \
                        .Multiply(block.Transform) \
                        .OfVector(XYZ.BasisX)
                    block_orientation = XYZ.BasisX.AngleTo(rotated)

                    family_instance = doc.Create.NewFamilyInstance(
                        reference_plane.GetReference(),
                        block_location,
                        XYZ.Zero,
                        family_type
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
                        reference_plane_orientation - block_orientation
                    )

            if host['type'] == 'Wall':
                break

            cnt += 1
            pb.update_progress(cnt, total)
