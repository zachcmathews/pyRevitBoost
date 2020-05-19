# pylint: disable=import-error
from itertools import chain

from Autodesk.Revit.DB import (XYZ, ElementTransformUtils, Line)
from Autodesk.Revit.DB.Structure import StructuralType
from Autodesk.Revit.Exceptions import ArgumentException

import rpw
from pyrevit import forms, script
from boostutils import load_as_python

from gather import (find_family_type, get_blocks, get_cad_imports,
                    get_family_types, get_reference_planes,
                    group_blocks_by_name)
from parse import parse_config, parse_host

__doc__ = 'Map imported AutoCAD blocks to their equivalent Revit family \
type. Requires configuration file config.yaml'
__title__ = 'Convert\nDWG Blocks'
__author__ = 'Zachary Mathews'

doc = rpw.revit.doc
uidoc = rpw.revit.uidoc
view = uidoc.ActiveView
level = view.GenLevel

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
import_transform = cad_import.GetTotalTransform()

blocks = get_blocks(cad_import)
blocks_grouped_by_name = group_blocks_by_name(blocks)

cnt = 0
total = len(blocks)
no_mapping = {}
failed = []
with forms.ProgressBar(title='{value} of {max_value}', step=10) as pb:
    with rpw.db.Transaction('Map DWG to Revit') as t:
        for block_name, blocks in blocks_grouped_by_name.items():
            try:
                (host, family_type) = parse_config(block_name, config)
            except TypeError:
                no_mapping[block_name] = blocks
                cnt += len(blocks)
                pb.update_progress(cnt, total)
                continue

            if host['type'] == 'Reference Plane':
                try:
                    [reference_plane] = \
                        [rp for rp in reference_planes if rp.Name == host['id']]
                except ValueError:
                    failed.extend(blocks)
                    cnt += len(blocks)
                    pb.update_progress(cnt, total)
                    continue

                reference_plane_direction = \
                    reference_plane.FreeEnd - reference_plane.BubbleEnd
                reference_plane_orientation = \
                    XYZ.BasisX.AngleTo(reference_plane_direction)

                for block in blocks:
                    block_location = \
                        import_transform \
                        .Multiply(block.Transform) \
                        .OfPoint(XYZ.Zero)
                    rotated = \
                        import_transform \
                        .Multiply(block.Transform) \
                        .OfVector(XYZ.BasisX)
                    block_orientation = XYZ.BasisX.AngleTo(rotated)
                    z_axis = \
                        Line.CreateBound(
                             block_location,
                             block_location + XYZ.BasisZ
                        )

                    try:
                      family_instance = doc.Create.NewFamilyInstance(
                          reference_plane.GetReference(),
                          block_location,
                          XYZ.Zero,
                          family_type
                      )
                      ElementTransformUtils.RotateElement(
                          doc,
                          family_instance.Id,
                          z_axis,
                          reference_plane_orientation - block_orientation
                      )
                    except ArgumentException:
                        failed.append(block)
                    finally:
                        cnt += 1
                        pb.update_progress(cnt, total)


            if host['type'] == 'Level':
                for block in blocks:
                    block_location = \
                        import_transform \
                        .Multiply(block.Transform) \
                        .OfPoint(XYZ.Zero)
                    rotated = \
                        import_transform \
                        .Multiply(block.Transform) \
                        .OfVector(XYZ.BasisX)
                    block_orientation = XYZ.BasisX.AngleTo(rotated)
                    z_axis = \
                        Line.CreateBound(
                             block_location,
                             block_location + XYZ.BasisZ
                        )

                    try:
                      family_instance = doc.Create.NewFamilyInstance(
                          block_location,
                          family_type,
                          level,
                          StructuralType.NonStructural
                      )
                      ElementTransformUtils.RotateElement(
                          doc,
                          family_instance.Id,
                          z_axis,
                          block_orientation
                      )
                    except ArgumentException:
                        failed.append(block)
                    finally:
                        cnt += 1
                        pb.update_progress(cnt, total)

            else:
                failed.extend(blocks)
                cnt += len(blocks)
                pb.update_progress(cnt, total)
                continue


no_mapping_count = sum(len(blocks) for blocks in no_mapping.values())
config_warning = (
    'No mapping found for {} blocks:\n'.format(no_mapping_count) +
    '\n'.join([
       '{} : {} blocks'.format(name, len(blocks))
       for (name, blocks) in no_mapping.items()
    ])
)
results = (
    ('Processed {} elements.\n' \
    'Successfully placed {} elements.\n' \
    'Failed to place {} elements.') \
    .format(total, total-no_mapping_count-len(failed), len(failed))
)
forms.alert(
    title='Results',
    msg='{}\n\n{}'.format(config_warning, results)
)
